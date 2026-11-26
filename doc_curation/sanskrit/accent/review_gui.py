"""FastAPI web GUI for reviewing Vedic accent fix suggestions, marking accepted files for commit, and inserting ``+++(FEEDBACK!!)+++`` comments.

Run from the command line::

  ~/gitland/python_venv/bin/python -m doc_curation.sanskrit.accent.review_gui \\
    --dir /home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/maitrAyaNIyam/saMhitA/sarva-prastutiH
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import threading
import time
import webbrowser
from typing import Any, Sequence

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from doc_curation.sanskrit.accent import review

_PRESET_CANDIDATES = [
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/maitrAyaNIyam/saMhitA/sarva-prastutiH",
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/kaTha-kapiShTalAH/saMhitA/sarva-prastutiH",
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/AraNyakam/sarva-prastutiH",
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/sarva-prastutiH",
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam",
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH",
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/kANvam/shatapatha-brAhmaNam/sarva-prastutiH",
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam",
]


class _ScanRequest(BaseModel):
  dir_path: str


class _DecisionRequest(BaseModel):
  item_id: str
  decision: str
  sync_prefills: bool = True


class _FileAcceptRequest(BaseModel):
  file_path: str
  decision: str = "accept"
  sync_prefills: bool = True


class _FileMarkRequest(BaseModel):
  file_path: str
  marked: bool | None = None


class _FeedbackRequest(BaseModel):
  item_id: str
  feedback_text: str
  target_mode: str = "auto"
  sync_prefills: bool = True


class _SubmitRequest(BaseModel):
  item_id: str
  decision: str = "pending"
  feedback_text: str = ""
  target_mode: str = "auto"
  sync_prefills: bool = True


class _CommitRequest(BaseModel):
  file_paths: list[str]
  commit_message: str = "Review accepted accent fix suggestions"


class _OpenIdeaRequest(BaseModel):
  file_path: str
  line: int | None = None
  needle: str | None = None


class _OpenGoldenDictRequest(BaseModel):
  word: str


class _SessionStore:
  def __init__(self, initial_dir: str | None = None, default_n: int = 3, cache_dir: str = review.DEFAULT_REVIEW_CACHE_DIR) -> None:
    self.lock = threading.RLock()
    self.cache_dir = cache_dir
    self.default_n = max(0, default_n)
    self.scan_data: dict[str, Any] | None = None
    self.item_by_id: dict[str, review.ReviewItem] = {}
    self.state: dict[str, Any] = {"decisions": {}, "file_overrides": {}}
    if initial_dir and os.path.isdir(initial_dir):
      self.load_dir(initial_dir)

  def load_dir(self, dir_path: str) -> dict[str, Any]:
    abs_d = os.path.abspath(os.path.expanduser(dir_path))
    data = review.scan_directory(abs_d)
    st = review.load_review_state(abs_d, cache_dir=self.cache_dir)
    with self.lock:
      self.scan_data = data
      self.item_by_id = {it.item_id: it for it in data["items"]}
      self.state = st
    return data

  def refresh_git_statuses(self) -> None:
    if self.scan_data is None:
      return
    file_statuses: dict[str, str] = {}
    repo_staged: dict[str, list[str]] = {}
    for rr in self.scan_data["repo_roots"]:
      smap, staged = review.get_git_status_map(rr)
      file_statuses.update(smap)
      repo_staged[rr] = staged
    self.scan_data["file_statuses"] = file_statuses
    self.scan_data["repo_staged"] = repo_staged

  def summary_payload(self) -> dict[str, Any]:
    if self.scan_data is None:
      return {
        "dir_path": None,
        "total_items": 0,
        "counts": {"pending": 0, "accept": 0, "reject": 0, "with_feedback": 0},
        "files": [],
        "marked_files": [],
        "repo_staged": {},
      }
    decisions = self.state["decisions"]
    cnt = {"pending": 0, "accept": 0, "reject": 0, "with_feedback": 0}
    for it in self.scan_data["items"]:
      d = decisions.get(it.item_id, "pending")
      if it.existing_feedback:
        cnt["with_feedback"] += 1
        if d in ("accept", "reject"):
          cnt[d] += 1
      else:
        cnt[d if d in cnt else "pending"] += 1
    files = review.compute_file_summaries(self.scan_data, self.state)
    marked = [f["file_path"] for f in files if f["marked"]]
    return {
      "dir_path": self.scan_data["dir_path"],
      "total_items": len(self.scan_data["items"]),
      "counts": cnt,
      "files": files,
      "marked_files": marked,
      "repo_staged": self.scan_data["repo_staged"],
    }


def _pick_directory_dialog(initial_dir: str | None = None) -> str | None:
  start = initial_dir if initial_dir and os.path.isdir(initial_dir) else "/home/vvasuki/gitland/vishvAsa"
  if shutil.which("zenity"):
    try:
      out = subprocess.check_output(
        ["zenity", "--file-selection", "--directory", f"--filename={start.rstrip('/')}/"],
        stderr=subprocess.DEVNULL,
        text=True,
      ).strip()
      return out or None
    except subprocess.CalledProcessError:
      return None
  return None


def _resolve_idea_binary() -> str | None:
  """Locate an executable IntelliJ IDEA CLI launcher on the local machine."""
  candidates: list[Path] = []
  which_idea = shutil.which("idea")
  if which_idea:
    candidates.append(Path(which_idea))
  candidates.append(Path.home() / ".local/share/JetBrains/Toolbox/apps/intellij-idea/bin/idea")
  scripts_dir = Path.home() / ".local/share/JetBrains/Toolbox/scripts"
  if scripts_dir.is_dir():
    candidates.extend(sorted(p for p in scripts_dir.glob("idea*") if p.is_file()))
  for fallback in ("idea.sh", "jetbrains-idea"):
    w = shutil.which(fallback)
    if w:
      candidates.append(Path(w))
  for cand in candidates:
    try:
      resolved = cand.resolve(strict=True)
    except OSError:
      continue
    if resolved.is_file() and os.access(resolved, os.X_OK):
      return str(cand if os.access(cand, os.X_OK) else resolved)
  return None


def _infer_line_for_file(file_path: Path, *, line: int | None = None, needle: str | None = None) -> int | None:
  """Return 1-based line number from ``line`` or by locating ``needle`` inside ``file_path``."""
  if line is not None and line >= 1:
    return line
  if not needle or not needle.strip():
    return None
  try:
    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
  except OSError:
    return None
  clean_needle = needle.strip()
  for idx, ln in enumerate(lines, 1):
    if clean_needle in ln:
      return idx
  first_ln = next((p.strip() for p in clean_needle.splitlines() if p.strip()), "")
  if first_ln:
    for idx, ln in enumerate(lines, 1):
      if first_ln in ln:
        return idx
  return None


def open_in_intellij(file_path: str, *, line: int | None = None, needle: str | None = None) -> dict[str, Any]:
  """Launch/focus ``file_path`` inside the local IntelliJ IDEA IDE (optionally at ``line``)."""
  abs_path = Path(file_path).expanduser().resolve()
  if not abs_path.is_file():
    raise FileNotFoundError(f"File not found: {file_path}")
  idea_bin = _resolve_idea_binary()
  if not idea_bin:
    raise RuntimeError("IntelliJ IDEA CLI binary ('idea') not found")
  target_line = _infer_line_for_file(abs_path, line=line, needle=needle)
  cmd = [idea_bin]
  if target_line is not None:
    cmd.extend(["--line", str(target_line)])
  cmd.append(str(abs_path))
  subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  return {"ok": True, "file_path": str(abs_path), "line": target_line, "command": cmd}


def _resolve_goldendict_binary() -> str | None:
  """Locate an executable GoldenDict CLI binary on the local machine."""
  for name in ("goldendict", "goldendict-ng"):
    path = shutil.which(name)
    if path:
      return path
  return None


def open_in_goldendict(word: str) -> dict[str, Any]:
  """Look up unaccented ``word`` in the running GoldenDict application."""
  query = re.sub(r"[\u0951-\u0954\u1cd0-\u1cff\u0300-\u036f]", "", (word or "")).strip()
  if not query:
    raise ValueError("Empty lookup word")
  gd_bin = _resolve_goldendict_binary()
  if not gd_bin:
    raise RuntimeError("GoldenDict CLI binary ('goldendict') not found")
  cmd = [gd_bin, query]
  subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  return {"ok": True, "word": query, "command": cmd}


def create_app(
  initial_dir: str | None = None,
  *,
  default_n: int = 3,
  cache_dir: str = review.DEFAULT_REVIEW_CACHE_DIR,
) -> FastAPI:
  """Create the FastAPI application for interactive accent suggestion review."""
  app = FastAPI(title="Vedic Accent Fix Suggestion Reviewer")
  store = _SessionStore(initial_dir=initial_dir, default_n=default_n, cache_dir=cache_dir)

  @app.get("/", response_class=HTMLResponse)
  def index() -> HTMLResponse:
    return HTMLResponse(_RENDERED_HTML)

  @app.get("/api/presets")
  def api_presets() -> dict[str, Any]:
    presets = [p for p in _PRESET_CANDIDATES if os.path.isdir(p)]
    with store.lock:
      cur_dir = store.scan_data["dir_path"] if store.scan_data else (initial_dir or "")
    return {"presets": presets, "default_n": store.default_n, "current_dir": cur_dir}

  @app.post("/api/browse")
  def api_browse() -> dict[str, Any]:
    with store.lock:
      cur = store.scan_data["dir_path"] if store.scan_data else initial_dir
    picked = _pick_directory_dialog(cur)
    return {"dir_path": picked}

  @app.post("/api/scan")
  def api_scan(req: _ScanRequest) -> dict[str, Any]:
    try:
      store.load_dir(req.dir_path)
    except FileNotFoundError as exc:
      raise HTTPException(status_code=404, detail=str(exc)) from exc
    with store.lock:
      return store.summary_payload()

  @app.get("/api/items")
  def api_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    n_context: int = Query(3, ge=0, le=30),
    file_filter: str = Query(""),
    git_filter: str = Query("all"),  # "all" | "dirty" | "clean"
    status_filter: str = Query("all"),  # "all" | "pending" | "accept" | "hold" | "has_feedback"
    kind_filter: str = Query("all"),  # "all" | "both" | "pp_only" | "vp_only"
    search: str = Query(""),
  ) -> dict[str, Any]:
    with store.lock:
      summary = store.summary_payload()
      if store.scan_data is None:
        return {"summary": summary, "filtered_total": 0, "page": 1, "total_pages": 1, "items": []}

      decisions = store.state["decisions"]
      fstat = store.scan_data["file_statuses"]
      q = search.strip().lower()
      matched: list[review.ReviewItem] = []

      for it in store.scan_data["items"]:
        if file_filter and file_filter != it.display_file and file_filter not in it.relevant_files and file_filter not in it.host_files:
          continue
        if kind_filter != "all" and it.kind != kind_filter:
          continue
        dec = decisions.get(it.item_id, "pending")
        if status_filter == "has_feedback":
          if not it.existing_feedback:
            continue
        elif status_filter == "pending":
          if dec != "pending" or it.existing_feedback:
            continue
        elif status_filter != "all" and dec != status_filter:
          continue
        if git_filter != "all":
          any_dirty = any(fstat.get(rf, "clean") != "clean" for rf in it.relevant_files)
          if git_filter == "dirty" and not any_dirty:
            continue
          if git_filter == "clean" and any_dirty:
            continue
        if q:
          hay = "\n".join([
            it.rel_path,
            it.vp_file or "",
            it.pp_file or "",
            *it.host_files,
            it.vp_raw_body,
            it.pp_line_core,
            it.vp_sug_old,
            it.vp_sug_new,
            it.existing_feedback,
          ]).lower()
          if q not in hay:
            continue
        matched.append(it)

      total = len(matched)
      total_pages = max(1, (total + page_size - 1) // page_size)
      clamped_page = min(page, total_pages)
      s_idx = (clamped_page - 1) * page_size
      e_idx = min(total, s_idx + page_size)
      hugo_base = store.scan_data.get("hugo_base_dir")
      page_items = [
        it.to_dict(
          n_context=n_context,
          decision=decisions.get(it.item_id, "pending"),
          file_statuses=fstat,
          hugo_base_dir=hugo_base,
        )
        for it in matched[s_idx:e_idx]
      ]
      return {
        "summary": summary,
        "filtered_total": total,
        "page": clamped_page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": page_items,
      }

  @app.post("/api/submit")
  def api_submit(req: _SubmitRequest) -> dict[str, Any]:
    if req.decision not in ("pending", "accept", "reject"):
      raise HTTPException(status_code=400, detail=f"Invalid decision: {req.decision}")
    with store.lock:
      if store.scan_data is None or req.item_id not in store.item_by_id:
        raise HTTPException(status_code=404, detail="Review item not found")
      it = store.item_by_id[req.item_id]
      try:
        res = review.submit_review_item(
          it,
          decision=req.decision,
          feedback_text=req.feedback_text,
          sibling_items=store.scan_data["items"],
          target_mode=req.target_mode,
          sync_prefills=req.sync_prefills,
          hugo_base_dir=store.scan_data["hugo_base_dir"],
          scan_dir=store.scan_data["dir_path"],
        )
      except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

      store.state["decisions"][it.item_id] = req.decision
      for rf in it.relevant_files:
        store.state["file_overrides"].pop(rf, None)
      store.refresh_git_statuses()
      review.save_review_state(store.scan_data["dir_path"], store.state, cache_dir=store.cache_dir)
      it_dict = it.to_dict(
        decision=req.decision,
        file_statuses=store.scan_data["file_statuses"],
        hugo_base_dir=store.scan_data["hugo_base_dir"],
      )
      return {
        **res,
        "item": it_dict,
        "summary": store.summary_payload(),
      }

  @app.post("/api/decision")
  def api_decision(req: _DecisionRequest) -> dict[str, Any]:
    if req.decision not in ("pending", "accept", "reject"):
      raise HTTPException(status_code=400, detail=f"Invalid decision: {req.decision}")
    with store.lock:
      if store.scan_data is None or req.item_id not in store.item_by_id:
        raise HTTPException(status_code=404, detail="Review item not found")
      it = store.item_by_id[req.item_id]
      try:
        res = review.apply_vp_decision_for_item(
          it,
          req.decision,
          sibling_items=store.scan_data["items"],
          sync_prefills=req.sync_prefills,
          hugo_base_dir=store.scan_data["hugo_base_dir"],
          scan_dir=store.scan_data["dir_path"],
        )
      except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
      store.state["decisions"][req.item_id] = req.decision
      for rf in it.relevant_files:
        store.state["file_overrides"].pop(rf, None)
      store.refresh_git_statuses()
      review.save_review_state(store.scan_data["dir_path"], store.state, cache_dir=store.cache_dir)
      return {
        **res,
        "summary": store.summary_payload(),
        "item_id": req.item_id,
        "decision": req.decision,
      }

  @app.post("/api/file_accept_all")
  def api_file_accept_all(req: _FileAcceptRequest) -> dict[str, Any]:
    if req.decision not in ("pending", "accept", "reject"):
      raise HTTPException(status_code=400, detail=f"Invalid decision: {req.decision}")
    norm_f = os.path.normpath(req.file_path)
    with store.lock:
      if store.scan_data is None:
        raise HTTPException(status_code=400, detail="No directory loaded")
      touched = 0
      previous_states: list[dict[str, str]] = []
      for it in store.scan_data["items"]:
        if norm_f == it.display_file or norm_f in it.relevant_files:
          prev_dec = store.state["decisions"].get(it.item_id, "pending")
          previous_states.append({"item_id": it.item_id, "decision": prev_dec})
          review.apply_vp_decision_for_item(
            it,
            req.decision,
            sibling_items=store.scan_data["items"],
            sync_prefills=req.sync_prefills,
            hugo_base_dir=store.scan_data["hugo_base_dir"],
            scan_dir=store.scan_data["dir_path"],
          )
          store.state["decisions"][it.item_id] = req.decision
          for rf in it.relevant_files:
            store.state["file_overrides"].pop(rf, None)
          touched += 1
      store.refresh_git_statuses()
      review.save_review_state(store.scan_data["dir_path"], store.state, cache_dir=store.cache_dir)
      return {"touched": touched, "previous_states": previous_states, "summary": store.summary_payload()}

  @app.post("/api/file_mark")
  def api_file_mark(req: _FileMarkRequest) -> dict[str, Any]:
    norm_f = os.path.normpath(req.file_path)
    with store.lock:
      if store.scan_data is None:
        raise HTTPException(status_code=400, detail="No directory loaded")
      if req.marked is None:
        store.state["file_overrides"].pop(norm_f, None)
      else:
        store.state["file_overrides"][norm_f] = bool(req.marked)
      review.save_review_state(store.scan_data["dir_path"], store.state, cache_dir=store.cache_dir)
      return {"summary": store.summary_payload()}

  @app.post("/api/feedback")
  def api_feedback(req: _FeedbackRequest) -> dict[str, Any]:
    with store.lock:
      if store.scan_data is None or req.item_id not in store.item_by_id:
        raise HTTPException(status_code=404, detail="Review item not found")
      it = store.item_by_id[req.item_id]
      try:
        res = review.insert_feedback_for_item(
          it,
          req.feedback_text,
          target_mode=req.target_mode,
          sibling_items=store.scan_data["items"],
          sync_prefills=req.sync_prefills,
          hugo_base_dir=store.scan_data["hugo_base_dir"],
          scan_dir=store.scan_data["dir_path"],
        )
      except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

      if res["comment"] and store.state["decisions"].get(it.item_id, "pending") == "pending":
        pass  # keep Accept/Reject independent of Feedback; feedback pill shows has_feedback
      for rf in it.relevant_files:
        store.state["file_overrides"].pop(rf, None)
      store.refresh_git_statuses()
      review.save_review_state(store.scan_data["dir_path"], store.state, cache_dir=store.cache_dir)
      return {
        **res,
        "decision": store.state["decisions"].get(it.item_id, "pending"),
        "summary": store.summary_payload(),
      }

  @app.get("/api/diff")
  def api_diff(file_path: str = Query(...)) -> dict[str, Any]:
    if not os.path.isfile(file_path):
      raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return {"file_path": file_path, "diff": review.get_file_diff(file_path)}

  @app.post("/api/open_in_idea")
  def api_open_in_idea(req: _OpenIdeaRequest) -> dict[str, Any]:
    try:
      return open_in_intellij(req.file_path, line=req.line, needle=req.needle)
    except FileNotFoundError as exc:
      raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
      raise HTTPException(status_code=500, detail=str(exc)) from exc

  @app.post("/api/open_in_goldendict")
  def api_open_in_goldendict(req: _OpenGoldenDictRequest) -> dict[str, Any]:
    try:
      return open_in_goldendict(req.word)
    except ValueError as exc:
      raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
      raise HTTPException(status_code=500, detail=str(exc)) from exc

  @app.post("/api/commit")
  def api_commit(req: _CommitRequest) -> dict[str, Any]:
    if not req.file_paths:
      raise HTTPException(status_code=400, detail="No files selected for committing")
    with store.lock:
      if store.scan_data is None:
        raise HTTPException(status_code=400, detail="No directory loaded")
      try:
        results = review.commit_marked_files(req.file_paths, req.commit_message)
      except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
      store.refresh_git_statuses()
      for fp in req.file_paths:
        store.state["file_overrides"].pop(os.path.normpath(fp), None)
      review.save_review_state(store.scan_data["dir_path"], store.state, cache_dir=store.cache_dir)
      return {"results": results, "summary": store.summary_payload()}

  return app


def _find_free_port(preferred: int = 8765) -> int:
  for port in [preferred, *range(8766, 8790), 0]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
      try:
        s.bind(("127.0.0.1", port))
        return s.getsockname()[1]
      except OSError:
        continue
  return 8765


def _launch_browser(url: str) -> None:
  time.sleep(0.6)
  chrome = shutil.which("google-chrome") or shutil.which("chromium")
  if chrome and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
    try:
      subprocess.Popen(
        [chrome, f"--app={url}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
      )
      return
    except Exception:
      pass
  webbrowser.open(url)


def main(argv: Sequence[str] | None = None) -> int:
  p = argparse.ArgumentParser(
    description="Launch the Vedic accent fix suggestion reviewer GUI."
  )
  p.add_argument("--dir", default=None, help="Initial directory to scan for accent fix suggestions.")
  p.add_argument("-n", "--context-lines", type=int, default=3, help="Number of preceding/succeeding padapāṭha lines to show (default: 3).")
  p.add_argument("--port", type=int, default=8765, help="Port to bind on 127.0.0.1 (default: 8765 or next free port).")
  p.add_argument("--no-browser", action="store_true", help="Do not auto-open browser window.")
  args = p.parse_args(argv)

  app = create_app(initial_dir=args.dir, default_n=args.context_lines)
  port = _find_free_port(args.port)
  url = f"http://127.0.0.1:{port}/"
  print(f"Vedic Accent Fix Reviewer running at {url}", flush=True)
  if not args.no_browser:
    threading.Thread(target=_launch_browser, args=(url,), daemon=True).start()
  uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
  return 0


_RENDERED_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Vedic Accent Fix Reviewer</title>
<style>
  :root {
    --bg: #f6f4ef;
    --surface: #ffffff;
    --surface-2: #fbfaf7;
    --border: #ddd6c7;
    --text: #1f1c18;
    --muted: #6a6257;
    --accent: #8b4513;
    --accent-soft: #fdf3e7;
    --green: #186a3b;
    --green-soft: #eafaf1;
    --amber: #9c5700;
    --amber-soft: #fff8e1;
    --red: #943126;
    --red-soft: #fdedec;
    --blue: #1b4f72;
    --blue-soft: #ebf5fb;
    --dev: "Adishila SanVedic", "Tiro Devanagari Sanskrit", "Noto Sans Devanagari", "Annapurna SIL", serif;
    --dev-font-size: 26px;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
    line-height: 1.45;
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }
  header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 10px 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex-shrink: 0;
  }
  .row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  input[type="text"], input[type="number"], select {
    padding: 6px 9px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: #fff;
    color: var(--text);
    font-size: 13px;
  }
  #dirInput { flex: 1; min-width: 280px; font-family: monospace; }
  #presetSelect { max-width: 300px; }
  button {
    padding: 6px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface-2);
    color: var(--text);
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
  }
  button:hover { background: #efeae0; }
  button.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
  button.primary:hover { background: #70360d; }
  button.green { background: var(--green); color: #fff; border-color: var(--green); }
  button.green:hover { background: #11502c; }
  button.small { padding: 3px 8px; font-size: 12px; }

  .stat-pill {
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid var(--border);
    background: var(--surface-2);
  }
  button.filter-pill {
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: box-shadow 0.12s, filter 0.12s;
  }
  button.filter-pill:hover { filter: brightness(0.96); }
  button.filter-pill.active { box-shadow: 0 0 0 2px var(--accent); }
  .pill-accept { background: var(--green-soft); color: var(--green); border-color: #a9dfbf; }
  .pill-hold { background: var(--amber-soft); color: var(--amber); border-color: #f9e79f; }
  .pill-pending { background: var(--surface-2); color: var(--muted); }
  .pill-dirty { background: #fef5e7; color: #b9770e; border-color: #f5cba7; }
  .pill-clean { background: #f4f6f7; color: #7f8c8d; border-color: #d5dbdb; }

  .workspace {
    display: grid;
    grid-template-columns: 290px minmax(0, 1fr) 300px;
    flex: 1;
    min-height: 0;
  }
  aside.sidebar, aside.commit-pane {
    background: var(--surface);
    border-right: 1px solid var(--border);
    overflow-y: auto;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  aside.commit-pane {
    border-right: none;
    border-left: 1px solid var(--border);
  }
  main {
    min-width: 0;
    overflow-y: auto;
    padding: 14px 18px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .pane-title {
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .file-item {
    padding: 6px 8px;
    border-radius: 6px;
    border: 1px solid transparent;
    cursor: pointer;
    font-size: 11px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .file-item:hover { background: var(--surface-2); border-color: var(--border); }
  .file-item.active { background: var(--accent-soft); border-color: #d5b28f; }
  .file-name { font-family: monospace; word-break: break-all; font-weight: 600; font-size: 11px; }
  .file-meta { color: var(--muted); font-size: 11px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow-wrap: anywhere;
    transition: background 0.12s ease, box-shadow 0.12s ease, border-color 0.12s ease;
  }
  .card.dec-accept { border-left: 5px solid var(--green); }
  .card.dec-reject { border-left: 5px solid var(--red); }
  .card.dec-pending { border-left: 5px solid #d5cfc2; }
  .card.focused {
    background: var(--accent-soft);
    border-top-color: var(--accent);
    border-right-color: var(--accent);
    border-bottom-color: var(--accent);
    outline: 3px solid var(--accent);
    box-shadow: 0 0 0 5px rgba(139, 69, 19, 0.16), 0 6px 18px rgba(139, 69, 19, 0.14);
  }
  .card.focused.dec-pending { border-left-color: var(--accent); }
  .card.focused .card-head { border-bottom-color: #e4c8ab; }
  .card.focused .vp-box,
  .card.focused .pp-box { border-color: #d5b28f; }
  .active-badge {
    display: none;
    align-items: center;
    padding: 1px 7px;
    border-radius: 999px;
    background: var(--accent);
    color: #fff;
    font-family: system-ui, sans-serif;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-right: 6px;
    vertical-align: middle;
  }
  .card.focused .active-badge { display: inline-flex; }
  .card.collapsed { padding: 8px 14px; gap: 0; opacity: 0.88; cursor: pointer; }
  .card.collapsed:hover,
  .card.focused.collapsed { opacity: 1; }
  .card.collapsed .card-head { border-bottom: none; padding-bottom: 0; align-items: center; }
  .card.collapsed .path-row,
  .card.collapsed .mula-details,
  .card.collapsed > :not(.card-head) { display: none; }
  .collapse-summary {
    display: none;
    align-items: center;
    gap: 8px;
    margin-left: 8px;
    font-size: 12px;
  }
  .card.collapsed .collapse-summary { display: inline-flex; flex-wrap: wrap; }
  .collapse-correction {
    font-family: var(--dev);
    font-size: var(--dev-font-size);
    line-height: 1.35;
    display: inline-flex;
    align-items: baseline;
    gap: 5px;
    flex-wrap: wrap;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1px 8px;
  }
  .collapse-correction .old-txt { color: var(--red); text-decoration: line-through; opacity: 0.85; }
  .collapse-correction .arrow { color: var(--muted); font-size: calc(var(--dev-font-size) - 4px); }
  .collapse-correction .new-txt { font-weight: 700; color: var(--green); }
  .collapse-btn {
    border: 1px solid var(--border);
    background: var(--surface-2);
    color: var(--muted);
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 11px;
    cursor: pointer;
    flex-shrink: 0;
  }
  .collapse-btn:hover { background: #ebe4d5; color: var(--fg); }

  .card-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 10px;
    border-bottom: 1px solid #efeae0;
    padding-bottom: 8px;
  }
  .card-title { font-family: monospace; font-size: 12px; color: var(--blue); font-weight: 600; word-break: break-all; }
  .file-link {
    color: inherit;
    text-decoration: underline dotted rgba(31, 95, 168, 0.55);
    text-underline-offset: 2px;
    cursor: pointer;
  }
  .file-link:hover {
    color: var(--blue);
    text-decoration: underline solid var(--blue);
  }
  .card-section { font-family: var(--dev); font-size: calc(var(--dev-font-size) - 4px); color: var(--muted); margin-left: 8px; }
  .path-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-top: 4px; font-family: monospace; font-size: 11px; }

  .vp-box {
    background: var(--surface-2);
    border: 1px solid #e6dfd1;
    border-radius: 8px;
    padding: 12px 16px;
    font-family: var(--dev);
    font-size: var(--dev-font-size);
    line-height: 1.65;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .vp-label {
    font-family: system-ui, sans-serif;
    font-size: 11px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 4px;
    display: flex;
    justify-content: space-between;
  }
  .sug-focus {
    background: #fff0b3;
    border: 1.5px solid #d48806;
    border-radius: 5px;
    padding: 1px 6px;
  }
  .sug-focus .old-txt {
    text-decoration: line-through;
    color: var(--red);
    opacity: 0.85;
    margin-right: 4px;
  }
  .sug-focus .arrow { color: var(--muted); margin: 0 3px; font-size: calc(var(--dev-font-size) - 4px); }
  .sug-focus .new-txt { font-weight: 700; color: var(--green); }
  .sug-other {
    background: var(--blue-soft);
    border: 1px solid #aed6f1;
    border-radius: 4px;
    padding: 0 4px;
  }
  .sug-other .old-txt { text-decoration: line-through; color: #7f8c8d; margin-right: 3px; }
  .sug-other .new-txt { font-weight: 600; color: var(--blue); }
  .plain-focus {
    background: #fff0b3;
    border-bottom: 2px solid #d48806;
    border-radius: 3px;
    padding: 0 3px;
  }
  .accepted-focus {
    background: var(--green-soft);
    border: 1.5px solid #2e8b57;
    color: var(--green);
    font-weight: 700;
    border-radius: 5px;
    padding: 1px 6px;
  }
  .rejected-focus {
    background: var(--red-soft);
    border: 1.5px solid #c0392b;
    color: var(--red);
    font-weight: 700;
    border-radius: 5px;
    padding: 1px 6px;
  }
  .inline-note {
    font-size: 80%;
    color: rgb(114, 47, 55);
    font-style: italic;
    vertical-align: sub;
  }
  .inline-feedback-tag {
    display: inline-block;
    background: var(--amber-soft);
    color: var(--amber);
    border: 1px solid #f5b041;
    border-radius: 4px;
    padding: 1px 7px;
    font-size: calc(var(--dev-font-size) - 8px);
    font-family: system-ui, sans-serif;
    margin-left: 6px;
  }

  .mula-box {
    background: #faf6ee;
    border: 1px dashed #d5c8b4;
    border-radius: 6px;
    padding: 8px 12px;
    font-family: var(--dev);
    font-size: calc(var(--dev-font-size) - 3px);
    line-height: 1.55;
    white-space: pre-wrap;
    margin-top: 4px;
  }

  .pp-box {
    border: 1px solid #e2ddd2;
    border-radius: 8px;
    overflow: hidden;
  }
  .pp-header {
    background: #f0ece3;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
    color: #4f483f;
    display: flex;
    justify-content: space-between;
  }
  .pp-line {
    padding: 7px 14px;
    font-family: var(--dev);
    font-size: calc(var(--dev-font-size) - 2px);
    line-height: 1.55;
    border-top: 1px solid #f2eee6;
    overflow-wrap: anywhere;
  }
  .pp-line.ctx { color: #5f584e; background: #fdfcf9; }
  .pp-line.target {
    background: #fff9e6;
    border-left: 4px solid #d48806;
    font-size: var(--dev-font-size);
    line-height: 1.6;
    color: #111;
    padding: 10px 14px;
  }
  .pp-tag { color: #6c3483; font-style: italic; font-size: calc(var(--dev-font-size) - 4px); }
  .pp-arrow-word { color: var(--green); font-weight: 700; }
  .gd-inline {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 5px;
    margin-left: 10px;
    padding: 1px 7px;
    background: rgba(31, 95, 168, 0.08);
    border: 1px solid rgba(31, 95, 168, 0.22);
    border-radius: 5px;
    font-family: system-ui, sans-serif;
    font-size: 12px;
    color: var(--blue);
    vertical-align: middle;
  }
  .gd-link { font-family: var(--dev); font-size: calc(var(--dev-font-size) - 6px); color: var(--blue); }

  .controls-bar {
    display: flex;
    flex-direction: column;
    gap: 0;
    align-items: stretch;
    padding-top: 2px;
  }
  .decision-row {
    display: flex;
    gap: 10px;
    align-items: center;
    margin: 0;
    padding: 0;
  }
  .radio-group {
    display: inline-flex;
    border: 1px solid var(--border);
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    overflow: hidden;
    background: var(--surface-2);
  }
  .radio-group label {
    padding: 4px 11px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    border-right: 1px solid var(--border);
    user-select: none;
  }
  .radio-group label:last-child { border-right: none; }
  .radio-group label.sel-accept { background: var(--green-soft); color: var(--green); font-weight: 700; }
  .radio-group label.sel-reject { background: var(--red-soft); color: var(--red); font-weight: 700; }
  .radio-group label.sel-pending { background: #ede9df; color: var(--text); }
  .kbd-hint {
    font-size: 10px;
    font-family: monospace;
    color: var(--muted);
    background: rgba(0,0,0,0.05);
    padding: 1px 4px;
    border-radius: 3px;
  }

  .fb-row {
    display: flex;
    gap: 8px;
    align-items: center;
    margin: 0;
    padding: 0;
  }
  .fb-input {
    flex: 1;
    padding: 6px 10px;
    border: 1px solid var(--border);
    border-radius: 0 6px 6px 6px;
    font-size: 13px;
    font-family: system-ui, sans-serif;
  }
  .submit-row {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-top: 6px;
  }
  .fb-status { font-size: 11px; color: var(--green); font-weight: 600; }

  .commit-file-row {
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 7px 8px;
    font-size: 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    background: var(--surface-2);
  }
  .commit-file-row.marked { background: var(--green-soft); border-color: #a9dfbf; }
  .commit-box {
    margin-top: auto;
    border-top: 1px solid var(--border);
    padding-top: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  textarea#commitMsg {
    width: 100%;
    min-height: 54px;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 8px;
    font-size: 12px;
    resize: vertical;
  }
  .pager {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
  }
  dialog {
    border: 1px solid var(--border);
    border-radius: 10px;
    max-width: 900px;
    width: 90vw;
    max-height: 85vh;
    padding: 16px;
    box-shadow: 0 12px 32px rgba(0,0,0,0.22);
  }
  pre.diff-pre {
    background: #1e1e1e;
    color: #e8e8e8;
    padding: 12px;
    border-radius: 6px;
    overflow: auto;
    max-height: 62vh;
    font-size: 12px;
    line-height: 1.45;
  }
</style>
</head>
<body>
<header>
  <div class="row">
    <strong style="font-size:15px;">Vedic Accent Fix Reviewer</strong>
    <select id="presetSelect" title="Quick preset directories"></select>
    <input id="dirInput" type="text" placeholder="/path/to/vedAH_yajuH/content/..." />
    <button onclick="browseDir()">Browse...</button>
    <button class="primary" onclick="scanDirectory()">Scan Directory</button>
    <span id="scanSpinner" style="color:var(--muted); font-size:12px;"></span>
  </div>
  <div class="row">
    <label>Context lines (n): <input id="nInput" type="number" min="0" max="30" value="3" style="width:62px" onchange="loadItems(1)" /></label>
    <button id="refreshBtn" class="small" title="Reload UI (Ctrl+R rescans directory)" onclick="reloadUi()">↻ Reload</button>
    <label title="Matches VS Code (25) / IntelliJ IDEA (28)">Editor font (px): <input id="fontPxInput" type="number" min="14" max="42" value="26" style="width:62px" onchange="applyEditorFont(this.value)" /></label>
    <label>Git:
      <select id="gitFilter" onchange="loadItems(1)">
        <option value="all">All files</option>
        <option value="dirty">Uncommitted only (M / ??)</option>
        <option value="clean">Committed only</option>
      </select>
    </label>
    <label>Review state:
      <select id="statusFilter" onchange="loadItems(1)">
        <option value="all">All</option>
        <option value="pending" selected>Pending</option>
        <option value="accept">Accepted</option>
        <option value="reject">Rejected</option>
        <option value="has_feedback">With !! comment</option>
      </select>
    </label>
    <label>Pairing:
      <select id="kindFilter" onchange="loadItems(1)">
        <option value="all">All VP suggestions</option>
        <option value="both">Paired (VP + पद-पाठः)</option>
        <option value="vp_only">Unpaired VP (no पद-पाठः)</option>
      </select>
    </label>
    <input id="searchInput" type="text" placeholder="Filter Devanagari / path / sūtra..." style="width:210px;" oninput="debouncedSearch()" />
    <button id="undoBtn" class="small" title="Undo last review action (Ctrl+Z)" onclick="undoLastAction()" disabled>↶ Undo <span class="kbd-hint">Ctrl+Z</span></button>
    <button type="button" class="stat-pill filter-pill" id="statTotal" data-status-filter="all" title="Show all matching suggestions (Alt+L / Alt+0)" onclick="setStatusFilter('all')">0 suggestions <span class="kbd-hint">Alt+L</span></button>
    <button type="button" class="stat-pill filter-pill pill-pending active" id="statPending" data-status-filter="pending" title="Show only pending suggestions without !! (Alt+P)" onclick="setStatusFilter('pending')">Pending: 0 <span class="kbd-hint">Alt+P</span></button>
    <button type="button" class="stat-pill filter-pill pill-accept" id="statAccept" data-status-filter="accept" title="Show only accepted suggestions (Alt+A)" onclick="setStatusFilter('accept')">Accepted: 0 <span class="kbd-hint">Alt+A</span></button>
    <button type="button" class="stat-pill filter-pill" id="statReject" data-status-filter="reject" title="Show only rejected suggestions (Alt+R)" style="background:var(--red-soft); color:var(--red); border-color:#f5b7b1;" onclick="setStatusFilter('reject')">Rejected: 0 <span class="kbd-hint">Alt+R</span></button>
    <button type="button" class="stat-pill filter-pill pill-hold" id="statHold" data-status-filter="has_feedback" title="Show only suggestions with !! comments (Alt+W)" onclick="setStatusFilter('has_feedback')">With !!: 0 <span class="kbd-hint">Alt+W</span></button>
  </div>
</header>

<div class="workspace">
  <aside class="sidebar">
    <div class="pane-title">
      <span>Files (<span id="fileCount">0</span>)</span>
      <button class="small" onclick="selectFileFilter('')">Show All</button>
    </div>
    <div id="fileList"></div>
  </aside>

  <main id="mainPane">
    <div class="pager">
      <div id="pageInfo" style="color:var(--muted); font-size:12px;">Enter a directory above and click Scan Directory.</div>
      <div class="row">
        <button class="small" onclick="changePage(-1)">← Prev</button>
        <span id="pageLabel" style="font-size:12px;">1 / 1</span>
        <button class="small" onclick="changePage(1)">Next →</button>
      </div>
    </div>
    <div id="cardsContainer"></div>
    <div class="pager">
      <div style="color:var(--muted); font-size:11px;">Shortcuts: Alt+P Pending • Alt+A Accepted • Alt+R Rejected • Alt+W With !! • Alt+L/0 All • Alt+1 Accept • Alt+2 Reject • Alt+3 Feedback • Enter Submit • Ctrl+Enter Accept+Submit • Ctrl+R Rescan • Ctrl+Z Undo • j/k/↑/↓ navigate • ←/→ Collapse/Expand</div>
      <div class="row">
        <button class="small" onclick="changePage(-1)">← Prev</button>
        <span id="pageLabelBottom" style="font-size:12px;">1 / 1</span>
        <button class="small" onclick="changePage(1)">Next →</button>
      </div>
    </div>
  </main>

  <aside class="commit-pane">
    <div class="pane-title">
      <span>Relevant Files for Commit</span>
      <span class="stat-pill pill-accept" id="markedCountPill">0 marked</span>
    </div>
    <div style="font-size:11px; color:var(--muted);">
      Accepting suggestions marks uncommitted files below (only checked dirty files are committed via scoped <code>git commit --only</code>).
    </div>
    <div id="markedFilesList" style="display:flex; flex-direction:column; gap:6px; flex:1; overflow-y:auto;"></div>
    <div class="commit-box">
      <label style="font-size:12px; font-weight:600;">Commit message:
        <textarea id="commitMsg">Review accepted accent fix suggestions</textarea>
      </label>
      <label style="font-size:12px; display:flex; align-items:center; gap:6px;">
        <input type="checkbox" id="syncPrefillsChk" checked /> Refresh prefilled js_includes on edit
      </label>
      <button class="green" onclick="commitMarked()">Commit Marked Files</button>
      <div id="commitResult" style="font-size:12px; white-space:pre-wrap;"></div>
    </div>
  </aside>
</div>

<dialog id="diffDialog">
  <div class="row" style="justify-content:space-between; margin-bottom:8px;">
    <strong id="diffTitle" style="font-family:monospace; font-size:13px;"></strong>
    <button class="small" onclick="document.getElementById('diffDialog').close()">Close</button>
  </div>
  <pre class="diff-pre" id="diffBody"></pre>
</dialog>

<script>
let currentDir = "";
let selectedFile = "";
let currentPage = 1;
let totalPages = 1;
let lastFilteredTotal = 0;
let lastPageSize = 25;
let currentItems = [];
let draftDecisions = {};
let collapsedCards = {};
let latestSummary = null;
let focusedIdx = -1;
let searchTimer = null;
let undoStack = [];

function updateUndoButton() {
  const btn = document.getElementById("undoBtn");
  if (!btn) return;
  btn.disabled = !undoStack.length;
  const top = undoStack[undoStack.length - 1];
  btn.title = top ? `Undo ${top.label || "last action"} (Ctrl+Z)` : "Undo last review action (Ctrl+Z)";
}

function flashStatus(msg) {
  const sp = document.getElementById("scanSpinner");
  if (!sp || !msg) return;
  sp.textContent = msg;
  setTimeout(() => { if (sp.textContent === msg) sp.textContent = ""; }, 2500);
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function debouncedSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadItems(1), 220);
}

function applyEditorFont(pxVal) {
  const px = Math.max(14, Math.min(42, Number(pxVal) || 26));
  document.documentElement.style.setProperty("--dev-font-size", `${px}px`);
  const inp = document.getElementById("fontPxInput");
  if (inp) inp.value = px;
  try { localStorage.setItem("accent_review_font_px", String(px)); } catch (_) {}
}

async function init() {
  try {
    const savedPx = localStorage.getItem("accent_review_font_px");
    if (savedPx) applyEditorFont(savedPx);
  } catch (_) {}
  const resp = await fetch("/api/presets");
  const data = await resp.json();
  document.getElementById("nInput").value = data.default_n ?? 3;
  const sel = document.getElementById("presetSelect");
  sel.innerHTML = `<option value="">-- Preset directories --</option>` +
    data.presets.map(p => `<option value="${esc(p)}">${esc(p.split("/").slice(-3).join("/"))}</option>`).join("");
  sel.onchange = () => {
    if (sel.value) {
      document.getElementById("dirInput").value = sel.value;
      scanDirectory();
    }
  };
  if (data.current_dir) {
    document.getElementById("dirInput").value = data.current_dir;
    await loadItems(1);
  }
}

async function browseDir() {
  const resp = await fetch("/api/browse", { method: "POST" });
  const data = await resp.json();
  if (data.dir_path) {
    document.getElementById("dirInput").value = data.dir_path;
    await scanDirectory();
  }
}

async function _runScan(dirPath, { preserveView = false } = {}) {
  const sp = document.getElementById("scanSpinner");
  if (sp) sp.textContent = "Scanning...";
  try {
    const resp = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dir_path: dirPath }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      alert(data.detail || "Scan failed");
      return;
    }
    if (!preserveView) {
      selectedFile = "";
      collapsedCards = {};
      undoStack = [];
      updateUndoButton();
    }
    currentDir = data.dir_path;
    await loadItems(preserveView ? currentPage : 1);
    if (preserveView) flashStatus("Refreshed");
  } finally {
    if (sp && sp.textContent === "Scanning...") sp.textContent = "";
  }
}

async function scanDirectory() {
  const dirPath = document.getElementById("dirInput").value.trim();
  if (!dirPath) return;
  await _runScan(dirPath, { preserveView: false });
}

async function refreshDirectory() {
  const dirPath = (document.getElementById("dirInput").value || currentDir || "").trim();
  if (!dirPath) return;
  await _runScan(dirPath, { preserveView: true });
}

function reloadUi() {
  window.location.reload();
}

function updateStatusFilterPills(statusVal) {
  const active = statusVal || document.getElementById("statusFilter").value || "all";
  const pillMap = [
    ["statTotal", "all"],
    ["statPending", "pending"],
    ["statAccept", "accept"],
    ["statReject", "reject"],
    ["statHold", "has_feedback"],
  ];
  for (const [id, val] of pillMap) {
    const el = document.getElementById(id);
    if (el && el.classList) {
      el.classList.toggle("active", active === val);
    }
  }
}

function setStatusFilter(statusVal) {
  const target = statusVal || "all";
  const sel = document.getElementById("statusFilter");
  sel.value = target;
  updateStatusFilterPills(target);
  return loadItems(1);
}

async function loadItems(page) {
  currentPage = page || 1;
  const nCtx = document.getElementById("nInput").value || 3;
  const statusVal = document.getElementById("statusFilter").value;
  updateStatusFilterPills(statusVal);
  const params = new URLSearchParams({
    page: currentPage,
    page_size: 25,
    n_context: nCtx,
    file_filter: selectedFile,
    git_filter: document.getElementById("gitFilter").value,
    status_filter: statusVal,
    kind_filter: document.getElementById("kindFilter").value,
    search: document.getElementById("searchInput").value,
  });
  const resp = await fetch(`/api/items?${params.toString()}`);
  const data = await resp.json();
  latestSummary = data.summary;
  currentItems = data.items || [];
  draftDecisions = {};
  for (const it of currentItems) {
    draftDecisions[it.item_id] = it.decision || "pending";
  }
  currentPage = data.page || 1;
  totalPages = data.total_pages || 1;
  lastFilteredTotal = data.filtered_total || 0;
  lastPageSize = data.page_size || 25;
  focusedIdx = currentItems.length ? 0 : -1;
  renderSummary(data.summary);
  renderCards(data);
}

function renderSummary(sum) {
  if (!sum) return;
  document.getElementById("statTotal").innerHTML = `${sum.total_items} suggestions <span class="kbd-hint">Alt+L</span>`;
  document.getElementById("statPending").innerHTML = `Pending: ${sum.counts.pending} <span class="kbd-hint">Alt+P</span>`;
  document.getElementById("statAccept").innerHTML = `Accepted: ${sum.counts.accept} <span class="kbd-hint">Alt+A</span>`;
  document.getElementById("statReject").innerHTML = `Rejected: ${sum.counts.reject || 0} <span class="kbd-hint">Alt+R</span>`;
  document.getElementById("statHold").innerHTML = `With !!: ${sum.counts.with_feedback || 0} <span class="kbd-hint">Alt+W</span>`;
  updateStatusFilterPills();
  document.getElementById("markedCountPill").textContent = `${sum.marked_files.length} marked`;

  const files = sum.files || [];
  document.getElementById("fileCount").textContent = files.length;
  document.getElementById("fileList").innerHTML = files.map((f, fi) => {
    const active = selectedFile === f.file_path ? "active" : "";
    const gitCls = f.dirty ? "pill-dirty" : "pill-clean";
    const mk = f.marked ? `<span class="stat-pill pill-accept" style="padding:1px 6px;">✓ commit</span>` : "";
    return `<div class="file-item ${active}" onclick="selectFileFilterIdx(${fi})">
      <div class="file-name"><a href="#" class="file-link" title="Open ${esc(f.file_path)} in IntelliJ IDEA (click card margin to filter)" onclick="event.stopPropagation(); event.preventDefault(); openSummaryFileInIdea(${fi});">${esc(f.rel_display)}</a></div>
      <div class="file-meta">
        <span class="stat-pill ${gitCls}" style="padding:1px 6px;">${esc(f.git_label)}</span>
        <span>${f.counts.accepted} acc / ${f.counts.rejected || 0} rej / ${f.counts.total}</span>
        ${f.counts.with_feedback ? `<span style="color:var(--amber)">${f.counts.with_feedback} !!</span>` : ""}
        ${mk}
      </div>
    </div>`;
  }).join("");

  const indexed = files.map((f, fi) => ({ f, fi }));
  const dirtyFiles = indexed.filter(({ f }) => f.dirty || f.counts.accepted > 0 || (f.counts.rejected || 0) > 0 || (f.counts.with_feedback || 0) > 0);
  dirtyFiles.sort((a, b) => (b.f.marked - a.f.marked) || (b.f.dirty - a.f.dirty) || a.f.rel_display.localeCompare(b.f.rel_display));
  document.getElementById("markedFilesList").innerHTML = dirtyFiles.map(({ f, fi }) => {
    const chk = f.marked ? "checked" : "";
    const disabled = f.dirty ? "" : "disabled";
    const rowCls = f.marked ? "marked" : "";
    const gitBadge = f.dirty ? `<span class="stat-pill pill-dirty" style="padding:0 5px;">${esc(f.git_xy)}</span>` : `<span class="stat-pill pill-clean" style="padding:0 5px;">clean</span>`;
    return `<div class="commit-file-row ${rowCls}">
      <div style="display:flex; gap:6px; align-items:flex-start;">
        <input type="checkbox" ${chk} ${disabled} style="cursor:pointer; margin-top:2px;" onchange="toggleFileMarkIdx(${fi}, this.checked)" />
        <a href="#" class="file-link" style="font-family:monospace; font-size:11px; word-break:break-all;" title="Open ${esc(f.file_path)} in IntelliJ IDEA" onclick="event.preventDefault(); openSummaryFileInIdea(${fi});">${esc(f.rel_display)}</a>
      </div>
      <div class="file-meta">
        ${gitBadge}
        <span>${f.counts.accepted} acc / ${f.counts.rejected || 0} rej / ${f.counts.total}</span>
        ${f.counts.with_feedback ? `<span style="color:var(--amber)">${f.counts.with_feedback} !!</span>` : ""}
        ${f.dirty ? `<button class="small" onclick="viewDiffIdx(${fi})">Diff</button>` : ""}
        ${f.counts.pending > 0 ? `<button class="small" onclick="acceptAllInFileIdx(${fi})">Accept all (${f.counts.total})</button>` : ""}
      </div>
    </div>`;
  }).join("") || `<div style="color:var(--muted); font-size:12px;">No modified or reviewed files yet.</div>`;
}

function selectFileFilter(fp) {
  selectedFile = selectedFile === fp ? "" : fp;
  loadItems(1);
}

function selectFileFilterIdx(fi) {
  const f = latestSummary?.files?.[fi];
  if (f) selectFileFilter(f.file_path);
}

function toggleFileMarkIdx(fi, checked) {
  const f = latestSummary?.files?.[fi];
  if (f) toggleFileMark(f.file_path, checked);
}

function viewDiffIdx(fi) {
  const f = latestSummary?.files?.[fi];
  if (f) viewDiff(f.file_path);
}

function openSummaryFileInIdea(fi) {
  const f = latestSummary?.files?.[fi];
  if (f) openInIdea(f.file_path, null);
}

function _ideaNeedleForItemFile(it, filePath) {
  if (!it) return null;
  if (it.pp_file && filePath === it.pp_file) {
    return it.pp_line_core || it.pp_target_line || null;
  }
  if ((it.decision || "pending") === "pending" && it.vp_sug_old && it.vp_sug_new) {
    return `[[${it.vp_sug_old}|${it.vp_sug_new}]]`;
  }
  return it.vp_raw_body || it.pp_line_core || null;
}

function openItemFileInIdea(idx) {
  const it = currentItems?.[idx];
  if (!it) return;
  const fp = it.vp_file || it.display_file;
  if (fp) openInIdea(fp, _ideaNeedleForItemFile(it, fp), it.item_id);
}

function _gdTargetsForItem(it) {
  const gd = it?.pp_goldendict;
  if (!gd || !gd.primary) return [];
  return [gd.primary, ...(gd.alternatives || [])];
}

function openItemGoldenDict(idx, candIdx) {
  const it = currentItems?.[idx];
  const targets = _gdTargetsForItem(it);
  const w = targets[candIdx];
  if (w) openInGoldenDict(w, it.item_id);
}

function openRelevantFileInIdea(idx, rfi) {
  const it = currentItems?.[idx];
  const rf = it?.relevant_files?.[rfi];
  if (rf?.path) openInIdea(rf.path, _ideaNeedleForItemFile(it, rf.path), it.item_id);
}

function acceptAllInFileIdx(fi) {
  const f = latestSummary?.files?.[fi];
  if (f) acceptAllInFile(f.file_path);
}

function formatTextSegment(text) {
  // Render `[[OLD|NEW]]`, `+++(...)+++`, and `**bold**` inside an unfocused VP segment
  let out = "";
  const tokRe = /(\[\[[^|\]]+\|[^\]]+\]\]|\+\+\+[\s\S]*?\+\+\+)/g;
  let last = 0;
  let m;
  while ((m = tokRe.exec(text)) !== null) {
    out += esc(text.slice(last, m.index)).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    const tok = m[0];
    if (tok.startsWith("[[")) {
      const bar = tok.indexOf("|");
      const oldW = tok.slice(2, bar);
      const newW = tok.slice(bar + 1, -2);
      out += `<span class="sug-other"><span class="old-txt">${esc(oldW)}</span>→ <span class="new-txt">${esc(newW)}</span></span>`;
    } else {
      const inner = tok.slice(3, -3);
      if (inner.includes("!!")) {
        out += `<span class="inline-feedback-tag">${esc(tok)}</span>`;
      } else {
        out += `<span class="inline-note">${esc(inner)}</span>`;
      }
    }
    last = m.index + tok.length;
  }
  out += esc(text.slice(last)).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  return out;
}

function renderFocusedSpan(tok, decision) {
  if (tok.startsWith("[[") && tok.includes("|") && tok.endsWith("]]")) {
    const bar = tok.indexOf("|");
    const oldW = tok.slice(2, bar);
    const newW = tok.slice(bar + 1, -2);
    return `<span class="sug-focus"><span class="old-txt">${esc(oldW)}</span><span class="arrow">→</span><span class="new-txt">${esc(newW)}</span></span>`;
  }
  if (decision === "accept") return `<span class="accepted-focus" title="Accepted">✓ ${esc(tok)}</span>`;
  if (decision === "reject") return `<span class="rejected-focus" title="Rejected (kept original)">✗ ${esc(tok)}</span>`;
  return `<span class="plain-focus">${esc(tok)}</span>`;
}

function renderFullVP(vpText, ranges, decision) {
  if (!vpText) return `<em style="color:var(--muted)">(No विश्वास-प्रस्तुतिः paired)</em>`;
  const sorted = [...(ranges || [])].sort((a, b) => a[0] - b[0]);
  let out = "";
  let pos = 0;
  for (const [s, e] of sorted) {
    if (s < pos || s >= vpText.length) continue;
    out += formatTextSegment(vpText.slice(pos, s));
    out += renderFocusedSpan(vpText.slice(s, e), decision);
    pos = e;
  }
  out += formatTextSegment(vpText.slice(pos));
  return out;
}

function formatPadapathaLineHtml(line) {
  let html = esc(line);
  html = html.replace(/\*\*([^*]+)\*\*/g, '<span class="pp-arrow-word">$1</span>');
  html = html.replace(/\*([A-Za-z0-9-]+|ŚB)\*/g, '<span class="pp-tag">*$1*</span>');
  html = html.replace(/(\+\+\+[\s\S]*?\+\+\+)/g, tok =>
    tok.includes("!!")
      ? `<span class="inline-feedback-tag">${tok}</span>`
      : `<span class="inline-note">${tok.slice(3, -3)}</span>`
  );
  return html;
}

function renderOneCardHtml(it, idx, pageOffset) {
  const savedDec = it.decision || "pending";
  const draftDec = draftDecisions[it.item_id] ?? savedDec;
  const focCls = idx === focusedIdx ? "focused" : "";
  const isCollapsed = !!collapsedCards[it.item_id];
  const colCls = isCollapsed ? "collapsed" : "";
  const fileBadges = it.relevant_files.map((rf, rfi) =>
    `<span class="stat-pill ${rf.git_status === 'clean' ? 'pill-clean' : 'pill-dirty'}" style="padding:2px 7px;" title="${esc(rf.path)}"><strong>${esc(rf.role || '')}:</strong> <a href="#" class="file-link" title="Open ${esc(rf.path)} in IntelliJ IDEA" onclick="event.stopPropagation(); event.preventDefault(); openRelevantFileInIdea(${idx}, ${rfi});">${esc(rf.vishvasa_rel || rf.short)}</a> (${esc(rf.git_status.trim() || 'clean')})</span>`
  ).join(" ");

  const gdTargets = _gdTargetsForItem(it);
  const gdInline = gdTargets.length
    ? `<span class="gd-inline" title="Look up in GoldenDict"><span>📖</span>${gdTargets.map((w, ci) =>
        `<a href="#" class="file-link gd-link" style="${ci === 0 ? 'font-weight:700;' : 'opacity:0.85;'}" title="Look up ${esc(w)} in GoldenDict" onclick="event.stopPropagation(); event.preventDefault(); openItemGoldenDict(${idx}, ${ci});">${esc(w)}</a>`
      ).join('<span style="color:var(--border);">·</span>')}</span>`
    : "";

  const ctxBefore = (it.pp_context_before || []).map(l => `<div class="pp-line ctx">${formatPadapathaLineHtml(l)}</div>`).join("");
  const ctxTarget = it.pp_target_line
    ? `<div class="pp-line target" id="ppTarget_${esc(it.item_id)}">${formatPadapathaLineHtml(it.pp_target_line)}${gdInline}</div>`
    : `<div class="pp-line ctx"><em>(No aligned पद-पाठः line)</em>${gdInline}</div>`;
  const ctxAfter = (it.pp_context_after || []).map(l => `<div class="pp-line ctx">${formatPadapathaLineHtml(l)}</div>`).join("");
  const fbTargetOpts = it.pp_file
    ? `<option value="auto" selected>End of पद-पाठः line</option><option value="vp">विश्वास-प्रस्तुतिः text</option><option value="both">Both</option>`
    : `<option value="vp" selected>विश्वास-प्रस्तुतिः text</option>`;
  const unsaved = draftDec !== savedDec ? `<span style="color:var(--amber);">Unsaved (Enter submits)</span>` : "";
  const colDecPill = savedDec === "accept"
    ? `<span class="stat-pill pill-accept">Accepted ✓</span>`
    : (savedDec === "reject"
      ? `<span class="stat-pill pill-reject">Rejected ✗</span>`
      : `<span class="stat-pill pill-pending">Pending</span>`);
  const colFbPill = it.existing_feedback
    ? `<span class="stat-pill" style="background:var(--amber-soft); color:var(--amber);">!! ${esc(it.existing_feedback)}</span>`
    : "";
  let colOld = it.vp_sug_old || "";
  let colNew = it.vp_sug_new || "";
  if ((!colOld || !colNew) && it.pp_line_core) {
    const pm = it.pp_line_core.match(/^-\s+(.+?)\s*→\s*\*\*(.+?)\*\*/);
    if (pm) {
      colOld = pm[1].trim();
      colNew = pm[2].trim();
    }
  }
  const colTokPreview = (colOld && colNew)
    ? `<span class="collapse-correction"><span class="old-txt">${esc(colOld)}</span><span class="arrow">→</span><span class="new-txt">${esc(colNew)}</span></span>`
    : (it.pp_line_core ? `<span class="collapse-correction">${esc(it.pp_line_core.replace(/^-\s+/, ""))}</span>` : "");

  return `<div class="card dec-${savedDec} ${focCls} ${colCls}" id="card_${idx}" onclick="handleCardClick(${idx})" onfocusin="setFocused(${idx})">
    <div class="card-head">
      <div style="min-width:0; flex:1;">
        <span class="active-badge">Active</span><span class="card-title">#${pageOffset + idx + 1} · <a href="#" class="file-link" title="Open ${esc(it.vp_file || it.display_file || '')} in IntelliJ IDEA" onclick="event.stopPropagation(); event.preventDefault(); openItemFileInIdea(${idx});">${esc(it.rel_path)}</a></span>
        <span class="card-section">${esc(it.section_heading)}</span>
        <span class="collapse-summary">${colDecPill}${colFbPill}${colTokPreview}</span>
        <div class="path-row">
          ${fileBadges}
          <span class="stat-pill" style="padding:1px 6px;">${esc(it.kind)}</span>
        </div>
      </div>
      <div class="row" style="align-items:flex-start; flex-shrink:0;">
        ${it.mula_preview ? `<details class="mula-details" style="font-size:12px; max-width:36vw;"><summary style="cursor:pointer; color:var(--muted);">मूलम्</summary><div class="mula-box">${esc(it.mula_preview)}</div></details>` : ""}
        <button type="button" class="collapse-btn" onclick="event.stopPropagation(); toggleCardCollapse(${idx})">${isCollapsed ? "▸ Expand" : "▾ Collapse"}</button>
      </div>
    </div>

    <div>
      <div class="vp-label"><span>${esc(it.vp_summary || "विश्वास-प्रस्तुतिः")}</span></div>
      <div class="vp-box">${renderFullVP(it.vp_raw_body, it.vp_highlight_ranges, savedDec)}</div>
    </div>

    <div class="pp-box">
      <div class="pp-header">
        <span>${esc(it.pp_summary || "पद-पाठः (यान्त्रिकः)")}</span>
        <span>line ${it.pp_target_idx !== null ? it.pp_target_idx + 1 : "-"}/${it.pp_total_lines} (±${document.getElementById("nInput").value} context)</span>
      </div>
      ${ctxBefore}
      ${ctxTarget}
      ${ctxAfter}
    </div>

    <div class="controls-bar">
      <div class="decision-row">
        <div class="radio-group" id="radioGroup_${idx}">
          <label class="${draftDec === 'accept' ? 'sel-accept' : ''}">
            <input type="radio" name="dec_${esc(it.item_id)}" value="accept" ${draftDec === 'accept' ? 'checked' : ''} onchange="selectRadio(${idx}, 'accept')" /> Accept <span class="kbd-hint">Alt+1</span>
          </label>
          <label class="${draftDec === 'reject' ? 'sel-reject' : ''}">
            <input type="radio" name="dec_${esc(it.item_id)}" value="reject" ${draftDec === 'reject' ? 'checked' : ''} onchange="selectRadio(${idx}, 'reject')" /> Reject <span class="kbd-hint">Alt+2</span>
          </label>
        </div>
        <span class="fb-status" id="fbStatus_${esc(it.item_id)}">${unsaved}</span>
      </div>

      <div class="fb-row">
        <input class="fb-input" id="fbInput_${esc(it.item_id)}" type="text"
          value="${esc(it.existing_feedback)}"
          placeholder="Feedback (Alt+3) -> +++(FEEDBACK!!)+++ · Enter submits" />
        <select id="fbTarget_${esc(it.item_id)}">${fbTargetOpts}</select>
      </div>

      <div class="submit-row">
        <button class="primary" onclick="event.stopPropagation(); submitCard(${idx})">Submit <span class="kbd-hint" style="background:rgba(255,255,255,0.2); color:#fff;">Enter</span></button>
        <span style="font-size:11px; color:var(--muted);">Ctrl+Enter = Accept + Submit</span>
        ${(savedDec !== 'pending' || it.existing_feedback) ? `<button class="small" title="Revert to [[OLD|NEW]] and clear feedback" onclick="event.stopPropagation(); resetCard(${idx})">Reset</button>` : ""}
      </div>
    </div>
  </div>`;
}

function renderCards(data) {
  document.getElementById("pageInfo").textContent =
    `Showing ${data.filtered_total ? ((currentPage - 1) * data.page_size + 1) : 0}–${Math.min(data.filtered_total, currentPage * data.page_size)} of ${data.filtered_total} matching suggestions`;
  document.getElementById("pageLabel").textContent = `${currentPage} / ${totalPages}`;
  document.getElementById("pageLabelBottom").textContent = `${currentPage} / ${totalPages}`;

  const container = document.getElementById("cardsContainer");
  if (!currentItems.length) {
    container.innerHTML = `<div class="card">No suggestions match current filters.</div>`;
    return;
  }
  const pageOffset = (currentPage - 1) * lastPageSize;
  container.innerHTML = currentItems.map((it, idx) => renderOneCardHtml(it, idx, pageOffset)).join("");
}

function setFocused(idx) {
  if (idx < 0 || idx >= currentItems.length) return;
  focusedIdx = idx;
  document.querySelectorAll("#cardsContainer > .card").forEach((el, i) => el.classList.toggle("focused", i === idx));
}

function toggleCardCollapse(idx, forceState) {
  if (idx < 0 || idx >= currentItems.length) return;
  const it = currentItems[idx];
  const next = typeof forceState === "boolean" ? forceState : !collapsedCards[it.item_id];
  if (next) collapsedCards[it.item_id] = true;
  else delete collapsedCards[it.item_id];
  const cardEl = document.getElementById(`card_${idx}`);
  if (cardEl) {
    const pageOffset = (currentPage - 1) * lastPageSize;
    cardEl.outerHTML = renderOneCardHtml(it, idx, pageOffset);
  }
  setFocused(idx);
}

function handleCardClick(idx) {
  if (idx < 0 || idx >= currentItems.length) return;
  const it = currentItems[idx];
  if (collapsedCards[it.item_id]) {
    toggleCardCollapse(idx, false);
  } else {
    setFocused(idx);
  }
}

function selectRadio(idx, choice, toggle = false) {
  if (idx < 0 || idx >= currentItems.length) return;
  const it = currentItems[idx];
  if (collapsedCards[it.item_id]) toggleCardCollapse(idx, false);
  setFocused(idx);
  const cur = draftDecisions[it.item_id] ?? it.decision ?? "pending";
  const nextChoice = (toggle && cur === choice) ? "pending" : choice;
  draftDecisions[it.item_id] = nextChoice;
  const rg = document.getElementById(`radioGroup_${idx}`);
  if (rg) {
    rg.querySelectorAll("label").forEach(lbl => {
      const inp = lbl.querySelector("input");
      lbl.classList.remove("sel-accept", "sel-reject");
      if (inp) {
        inp.checked = (inp.value === nextChoice);
        if (inp.checked) lbl.classList.add(`sel-${nextChoice}`);
      }
    });
  }
  const st = document.getElementById(`fbStatus_${it.item_id}`);
  if (st) {
    st.innerHTML = draftDecisions[it.item_id] !== (it.decision || "pending")
      ? `<span style="color:var(--amber);">Unsaved (Enter submits)</span>`
      : "";
  }
}

function focusFeedback(idx) {
  if (idx < 0 || idx >= currentItems.length) return;
  const it = currentItems[idx];
  if (collapsedCards[it.item_id]) toggleCardCollapse(idx, false);
  setFocused(idx);
  const inp = document.getElementById(`fbInput_${it.item_id}`);
  if (inp) {
    inp.scrollIntoView({ block: "nearest" });
    inp.focus();
  }
}

async function submitCard(idx, collapseOnDone = true, recordUndo = true) {
  if (idx < 0 || idx >= currentItems.length) return;
  const it = currentItems[idx];
  const itemId = it.item_id;
  const decision = draftDecisions[itemId] ?? it.decision ?? "pending";
  const txt = document.getElementById(`fbInput_${itemId}`)?.value ?? "";
  const targetMode = document.getElementById(`fbTarget_${itemId}`)?.value ?? "auto";
  const syncPrefills = document.getElementById("syncPrefillsChk").checked;
  const undoSnap = {
    type: "submit",
    itemId,
    prevDecision: it.decision || "pending",
    prevFeedback: it.existing_feedback || "",
    prevTargetMode: it.pp_file ? "auto" : "vp",
    prevCollapsed: !!collapsedCards[itemId],
    label: it.vp_sug_old || it.pp_line_core || it.rel_path || itemId,
  };

  const resp = await fetch("/api/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      item_id: itemId,
      decision,
      feedback_text: txt,
      target_mode: targetMode,
      sync_prefills: syncPrefills,
    }),
  });
  const data = await resp.json();
  if (!resp.ok) return alert(data.detail || "Submit failed");

  if (recordUndo && (decision !== undoSnap.prevDecision || txt.trim() !== undoSnap.prevFeedback.trim())) {
    undoStack.push(undoSnap);
    updateUndoButton();
  }

  const activeEl = document.activeElement;
  if (activeEl && activeEl.id === `fbInput_${itemId}`) activeEl.blur();

  if (data.item) {
    currentItems[idx] = data.item;
    draftDecisions[itemId] = data.item.decision || "pending";
  } else {
    currentItems[idx] = { ...it, decision, existing_feedback: data.existing_feedback ?? txt };
  }
  if (collapseOnDone) collapsedCards[itemId] = true;
  else delete collapsedCards[itemId];
  renderSummary(data.summary);

  if (document.getElementById("statusFilter").value !== "all") {
    await loadItems(currentPage);
    return;
  }

  // Refresh the whole page cards when VP text changed in case sibling cards share the same VP block offsets
  const pageOffset = (currentPage - 1) * lastPageSize;
  const cardEl = document.getElementById(`card_${idx}`);
  if (cardEl) {
    const itemObj = data.item || currentItems[idx];
    cardEl.outerHTML = renderOneCardHtml(itemObj, idx, pageOffset);
    const st = document.getElementById(`fbStatus_${itemId}`);
    if (st) {
      const parts = [];
      if (decision !== "pending") parts.push(decision === "accept" ? "Saved Accept ✓" : "Saved Reject ✗");
      if (data.comment) parts.push(`Saved ${data.comment}`);
      st.textContent = parts.join(" · ") || "Saved";
    }
  }
  // If sibling card on this page shares the same VP block, refresh its raw snapshot too
  if (data.item) {
    await refreshSamePageSiblings(idx, data.item);
  }
  if (idx + 1 < currentItems.length) {
    setFocused(idx + 1);
    document.getElementById(`card_${idx + 1}`)?.scrollIntoView({ block: "nearest" });
  }
}

async function refreshSamePageSiblings(submittedIdx, updatedItem) {
  const hasSibling = currentItems.some((other, j) => j !== submittedIdx && other.vp_file && other.vp_file === updatedItem.vp_file);
  if (!hasSibling) return;
  const nCtx = document.getElementById("nInput").value || 3;
  const params = new URLSearchParams({
    page: currentPage,
    page_size: lastPageSize,
    n_context: nCtx,
    file_filter: selectedFile,
    git_filter: document.getElementById("gitFilter").value,
    status_filter: document.getElementById("statusFilter").value,
    kind_filter: document.getElementById("kindFilter").value,
    search: document.getElementById("searchInput").value,
  });
  const resp = await fetch(`/api/items?${params.toString()}`);
  const fresh = await resp.json();
  currentItems = fresh.items || [];
  for (const it of currentItems) {
    if (!(it.item_id in draftDecisions)) draftDecisions[it.item_id] = it.decision || "pending";
  }
  const pageOffset = (currentPage - 1) * lastPageSize;
  document.getElementById("cardsContainer").innerHTML = currentItems.map((it, i) => renderOneCardHtml(it, i, pageOffset)).join("");
}

async function resetCard(idx) {
  if (idx < 0 || idx >= currentItems.length) return;
  const it = currentItems[idx];
  draftDecisions[it.item_id] = "pending";
  delete collapsedCards[it.item_id];
  const inp = document.getElementById(`fbInput_${it.item_id}`);
  if (inp) inp.value = "";
  await submitCard(idx, false);
}

async function acceptAllInFile(fp) {
  const syncPrefills = document.getElementById("syncPrefillsChk").checked;
  const resp = await fetch("/api/file_accept_all", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: fp, decision: "accept", sync_prefills: syncPrefills }),
  });
  const data = await resp.json();
  if (!resp.ok) return alert(data.detail || "Failed");
  const changed = (data.previous_states || []).filter(s => s.decision !== "accept");
  if (changed.length) {
    undoStack.push({
      type: "batch_decisions",
      prevStates: changed,
      syncPrefills,
      label: `Accept all (${changed.length})`,
    });
    updateUndoButton();
  }
  await loadItems(currentPage);
}

async function undoLastAction() {
  if (!undoStack.length) return;
  const snap = undoStack.pop();
  updateUndoButton();
  const syncPrefills = document.getElementById("syncPrefillsChk").checked;
  if (snap.type === "submit") {
    const resp = await fetch("/api/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        item_id: snap.itemId,
        decision: snap.prevDecision,
        feedback_text: snap.prevFeedback,
        target_mode: snap.prevTargetMode,
        sync_prefills: syncPrefills,
      }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      undoStack.push(snap);
      updateUndoButton();
      return alert(data.detail || "Undo failed");
    }
    if (snap.prevCollapsed) collapsedCards[snap.itemId] = true;
    else delete collapsedCards[snap.itemId];
    await loadItems(currentPage);
    const restoredIdx = currentItems.findIndex(x => x.item_id === snap.itemId);
    if (restoredIdx >= 0) {
      setFocused(restoredIdx);
      document.getElementById(`card_${restoredIdx}`)?.scrollIntoView({ block: "nearest" });
    }
    flashStatus(`Undone: ${snap.label}`);
  } else if (snap.type === "batch_decisions") {
    for (const prev of (snap.prevStates || [])) {
      const resp = await fetch("/api/decision", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          item_id: prev.item_id,
          decision: prev.decision,
          sync_prefills: snap.syncPrefills ?? syncPrefills,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        return alert(data.detail || "Batch undo failed");
      }
    }
    await loadItems(currentPage);
    flashStatus(`Undone: ${snap.label}`);
  }
}

async function toggleFileMark(fp, marked) {
  const resp = await fetch("/api/file_mark", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: fp, marked }),
  });
  const data = await resp.json();
  renderSummary(data.summary);
}

async function viewDiff(fp) {
  const resp = await fetch(`/api/diff?file_path=${encodeURIComponent(fp)}`);
  const data = await resp.json();
  document.getElementById("diffTitle").textContent = fp;
  document.getElementById("diffBody").textContent = data.diff || "";
  document.getElementById("diffDialog").showModal();
}

async function openInGoldenDict(word, itemId) {
  const resp = await fetch("/api/open_in_goldendict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ word }),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    return alert(data.detail || `Failed to open GoldenDict for: ${word}`);
  }
  const msg = `Looked up ${data.word || word} in GoldenDict`;
  const cardSt = itemId ? document.getElementById(`saveStatus_${itemId}`) : null;
  if (cardSt) cardSt.textContent = msg;
  const sp = document.getElementById("scanSpinner");
  if (sp) {
    sp.textContent = msg;
    setTimeout(() => { if (sp.textContent === msg) sp.textContent = ""; }, 2500);
  }
}

async function openInIdea(filePath, needleOrLine, itemId) {
  const payload = { file_path: filePath };
  if (typeof needleOrLine === "number" && needleOrLine >= 1) {
    payload.line = needleOrLine;
  } else if (typeof needleOrLine === "string" && needleOrLine.trim()) {
    payload.needle = needleOrLine;
  }
  const resp = await fetch("/api/open_in_idea", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    return alert(data.detail || `Failed to open in IntelliJ IDEA: ${filePath}`);
  }
  const baseName = filePath.split("/").pop() || filePath;
  const loc = data.line ? `${baseName}:${data.line}` : baseName;
  const msg = `Opened ${loc} in IntelliJ IDEA`;
  const cardSt = itemId ? document.getElementById(`saveStatus_${itemId}`) : null;
  if (cardSt) {
    cardSt.textContent = msg;
  }
  const sp = document.getElementById("scanSpinner");
  if (sp) {
    sp.textContent = msg;
    setTimeout(() => { if (sp.textContent === msg) sp.textContent = ""; }, 2500);
  }
}

async function commitMarked() {
  if (!latestSummary) return;
  const toCommit = (latestSummary.files || []).filter(f => f.marked && f.dirty).map(f => f.file_path);
  if (!toCommit.length) {
    alert("No dirty marked files to commit.");
    return;
  }
  const msg = document.getElementById("commitMsg").value.trim() || "Review accepted accent fix suggestions";
  const resp = await fetch("/api/commit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_paths: toCommit, commit_message: msg }),
  });
  const data = await resp.json();
  if (!resp.ok) return alert(data.detail || "Commit failed");
  document.getElementById("commitResult").textContent = (data.results || [])
    .map(r => `${r.repo_root}: ${r.sha || "no-op"} (${r.committed.length} files)`).join("\n");
  await loadItems(currentPage);
}

function changePage(delta) {
  const nxt = Math.max(1, Math.min(totalPages, currentPage + delta));
  if (nxt !== currentPage) loadItems(nxt);
}

document.addEventListener("keydown", (ev) => {
  const target = ev.target;
  const id = (target && target.id) || "";
  const tag = (target && target.tagName || "").toUpperCase();

  // Ctrl+R rescans directory even when list is empty
  if ((ev.key === "r" || ev.key === "R") && ev.ctrlKey && !ev.altKey && !ev.metaKey && !ev.shiftKey) {
    ev.preventDefault();
    refreshDirectory();
    return;
  }

  // Ctrl+Z undoes last submitted review action (outside text fields so inline typing keeps native undo)
  if ((ev.key === "z" || ev.key === "Z") && ev.ctrlKey && !ev.altKey && !ev.metaKey && !ev.shiftKey) {
    const isTextInput = tag === "TEXTAREA" || (tag === "INPUT" && target.type !== "radio" && target.type !== "checkbox");
    if (!isTextInput) {
      ev.preventDefault();
      undoLastAction();
      return;
    }
  }

  // Alt+P Pending, Alt+A Accepted, Alt+R Rejected, Alt+W With !!, Alt+L/0 All (work even when list is empty)
  if (ev.altKey && !ev.ctrlKey && !ev.metaKey) {
    const ak = (ev.key || "").toLowerCase();
    const ac = ev.code || "";
    const statusShortcuts = {
      p: "pending",
      a: "accept",
      r: "reject",
      w: "has_feedback",
      l: "all",
      "0": "all",
    };
    const codeShortcuts = {
      KeyP: "pending",
      KeyA: "accept",
      KeyR: "reject",
      KeyW: "has_feedback",
      KeyL: "all",
      Digit0: "all",
    };
    const nextFilter = statusShortcuts[ak] || codeShortcuts[ac];
    if (nextFilter) {
      ev.preventDefault();
      setStatusFilter(nextFilter);
      return;
    }
  }

  if (!currentItems.length) return;

  // Alt+1 Accept, Alt+2 Reject, Alt+3 Focus feedback (work even inside feedback textbox or radio)
  if (ev.altKey && !ev.ctrlKey && !ev.metaKey) {
    if (ev.key === "1" || ev.code === "Digit1") {
      ev.preventDefault();
      if (focusedIdx >= 0) selectRadio(focusedIdx, "accept", true);
      return;
    }
    if (ev.key === "2" || ev.code === "Digit2") {
      ev.preventDefault();
      if (focusedIdx >= 0) selectRadio(focusedIdx, "reject", true);
      return;
    }
    if (ev.key === "3" || ev.code === "Digit3") {
      ev.preventDefault();
      if (focusedIdx >= 0) focusFeedback(focusedIdx);
      return;
    }
  }

  // Ctrl+Enter = Accept + Submit in one step (works anywhere on card, including inside feedback input)
  if (ev.key === "Enter" && ev.ctrlKey && !ev.altKey && !ev.metaKey) {
    if (focusedIdx >= 0 && id !== "dirInput" && id !== "commitMsg") {
      ev.preventDefault();
      selectRadio(focusedIdx, "accept");
      submitCard(focusedIdx);
      return;
    }
  }

  // Enter submits the focused card (when inside a card's feedback input, radio, or outside header controls)
  if (ev.key === "Enter" && !ev.shiftKey && !ev.altKey && !ev.ctrlKey && !ev.metaKey) {
    if (id === "dirInput") {
      ev.preventDefault();
      scanDirectory();
      return;
    }
    const isFbInput = id.startsWith("fbInput_");
    const isCardRadio = target && target.type === "radio" && target.name && target.name.startsWith("dec_");
    const isBlockedControl = tag === "TEXTAREA" || tag === "SELECT" || tag === "BUTTON" || tag === "A" || (tag === "INPUT" && !isFbInput && !isCardRadio);
    if (!isBlockedControl && focusedIdx >= 0) {
      ev.preventDefault();
      submitCard(focusedIdx);
      return;
    }
  }

  if (tag === "TEXTAREA" || tag === "SELECT" || (tag === "INPUT" && target.type !== "radio")) return;
  if (ev.key === "j" || ev.key === "ArrowDown") {
    ev.preventDefault();
    setFocused(Math.min(currentItems.length - 1, focusedIdx + 1));
    document.getElementById(`card_${focusedIdx}`)?.scrollIntoView({ block: "nearest" });
  } else if (ev.key === "k" || ev.key === "ArrowUp") {
    ev.preventDefault();
    setFocused(Math.max(0, focusedIdx - 1));
    document.getElementById(`card_${focusedIdx}`)?.scrollIntoView({ block: "nearest" });
  } else if (ev.key === "ArrowLeft" && !ev.ctrlKey && !ev.altKey && !ev.metaKey && !ev.shiftKey && focusedIdx >= 0) {
    ev.preventDefault();
    toggleCardCollapse(focusedIdx, true);
  } else if (ev.key === "ArrowRight" && !ev.ctrlKey && !ev.altKey && !ev.metaKey && !ev.shiftKey && focusedIdx >= 0) {
    ev.preventDefault();
    toggleCardCollapse(focusedIdx, false);
  } else if (ev.key === "u" && focusedIdx >= 0) {
    resetCard(focusedIdx);
  }
});

init();
</script>
</body>
</html>
"""


if __name__ == "__main__":
  raise SystemExit(main())
