"""Client, browser-session helper, and text utilities for scraping scriptures from svarupa.org."""

from __future__ import annotations

import concurrent.futures
import os
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Callable

import requests

API_BASE_URL = "https://api.svarupa.org"
SITE_ORIGIN = "https://svarupa.org"


def to_madhyandina_svara(text: str) -> str:
  """Convert svarupa.org's U+0952 (``॒``) pitch-drop marks to Mādhyandina U+1CD8 (``᳘``)."""
  return text.strip().replace("\u0952", "\u1cd8")


def clean_overview_html(html_text: str | None) -> str:
  """Strip outer/inline HTML paragraph tags from a svarupa overview string."""
  if not html_text:
    return ""
  return re.sub(r"</?p\b[^>]*>", "", html_text).strip()


def extract_mantra_view_summary(view_json: dict[str, Any] | None) -> dict[str, Any] | None:
  """Extract compact scholarly metadata and commentary entries from a ``/scripture/tree/view/mantra/`` payload."""
  if not isinstance(view_json, dict):
    return None
  out: dict[str, Any] = {
    "mantraIndex": view_json.get("mantraIndex"),
    "displayIndex": view_json.get("displayIndex"),
    "languages": {},
  }
  for lang in view_json.get("language") or []:
    lang_name = lang.get("languageName")
    if not lang_name:
      continue
    entry: dict[str, Any] = {}
    for field in ("chanda", "devata", "rishi", "overview", "padapatha"):
      if lang.get(field):
        entry[field] = lang[field]
    comms = []
    for grp in lang.get("groups") or []:
      for item in grp.get("groupContent") or []:
        if item.get("name") != "commentary" or not item.get("value"):
          continue
        for mahatma_entry in item["value"]:
          vals = [
            {"key": d.get("key"), "source": d.get("source"), "value": d.get("value")}
            for d in (mahatma_entry.get("data") or [])
            if d.get("value")
          ]
          if vals:
            comms.append(
              {
                "mahatmaId": mahatma_entry.get("mahatmaId"),
                "mahatmaName": mahatma_entry.get("mahatmaName"),
                "data": vals,
              }
            )
    if comms:
      entry["commentary"] = comms
    if entry:
      out["languages"][lang_name] = entry
  return out


def extract_commentary_blocks(
  view_summary: dict[str, Any] | None,
  *,
  language: str = "English",
  preferred_mahatma: str | None = None,
) -> list[tuple[str, str]]:
  """Return ``[(mahatma_name, text), ...]`` commentary blocks from a compact view summary."""
  if not isinstance(view_summary, dict):
    return []
  lang_entry = (view_summary.get("languages") or {}).get(language) or {}
  blocks: list[tuple[str, str]] = []
  for comm in lang_entry.get("commentary") or []:
    name = (comm.get("mahatmaName") or "").strip() or "Commentary"
    if preferred_mahatma and name != preferred_mahatma:
      continue
    parts = [clean_overview_html(str(d["value"])) for d in (comm.get("data") or []) if d.get("value")]
    joined = "\n\n".join(p for p in parts if p)
    if joined:
      blocks.append((name, joined))
  return blocks


def extract_tokens_from_chrome_profile(
  *,
  chrome_user_data_dir: str | os.PathLike[str] | None = None,
  profile_name: str = "Default",
  scratch_profile_dir: str | os.PathLike[str],
  url: str = f"{SITE_ORIGIN}/scriptures?scriptureId=22",
  chrome_binary: str = "/opt/google/chrome/chrome",
  wait_seconds: float = 3.0,
) -> dict[str, str]:
  """Read ``authToken`` and ``refreshToken`` from a cloned Chrome profile via headless Chrome, then clean up."""
  from selenium import webdriver
  from selenium.webdriver.chrome.options import Options

  src_root = Path(chrome_user_data_dir) if chrome_user_data_dir else Path.home() / ".config/google-chrome"
  prof_root = Path(scratch_profile_dir)
  if prof_root.exists():
    shutil.rmtree(prof_root)
  (prof_root / profile_name).mkdir(parents=True, exist_ok=True)

  if (src_root / "Local State").exists():
    shutil.copy2(src_root / "Local State", prof_root / "Local State")
  for sub in ("Local Storage", "Session Storage", "Cookies", "Cookies-journal", "Preferences"):
    src = src_root / profile_name / sub
    dst = prof_root / profile_name / sub
    if src.is_dir():
      shutil.copytree(src, dst, ignore_dangling_symlinks=True)
    elif src.is_file():
      shutil.copy2(src, dst)

  opts = Options()
  opts.binary_location = chrome_binary
  opts.add_argument("--headless=new")
  opts.add_argument("--no-sandbox")
  opts.add_argument("--disable-gpu")
  opts.add_argument(f"--user-data-dir={prof_root}")
  opts.add_argument(f"--profile-directory={profile_name}")

  driver = webdriver.Chrome(options=opts)
  try:
    driver.get(url)
    time.sleep(wait_seconds)
    tokens = driver.execute_script(
      """
      function unquote(x) {
        if (typeof x !== 'string') return x || '';
        try { const p = JSON.parse(x); return typeof p === 'string' ? p : x; } catch { return x; }
      }
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        try {
          const v = JSON.parse(localStorage.getItem(k) || "{}");
          if (v && v.authToken) {
            return {authToken: unquote(v.authToken), refreshToken: unquote(v.refreshToken || "")};
          }
        } catch {}
      }
      return {authToken: "", refreshToken: ""};
      """
    )
  finally:
    driver.quit()
    shutil.rmtree(prof_root, ignore_errors=True)

  if not tokens or not tokens.get("authToken"):
    raise RuntimeError(f"No authToken found in Chrome profile {src_root / profile_name}")
  return tokens


class SvarupaClient:
  """Authenticated client for ``api.svarupa.org`` scripture tree and mantra endpoints."""

  def __init__(
    self,
    auth_token: str,
    refresh_token: str = "",
    *,
    base_url: str = API_BASE_URL,
    session: requests.Session | None = None,
    timeout: float = 30.0,
    max_retries: int = 4,
  ) -> None:
    self.auth_token = auth_token
    self.refresh_token = refresh_token
    self.base_url = base_url.rstrip("/")
    self.timeout = timeout
    self.max_retries = max_retries
    self._lock = threading.Lock()
    if session is not None:
      self.session = session
    else:
      self.session = requests.Session()
      adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16)
      self.session.mount("https://", adapter)
      self.session.headers.update({"Origin": SITE_ORIGIN, "Referer": f"{SITE_ORIGIN}/"})

  def _refresh(self, failed_token: str) -> bool:
    with self._lock:
      if self.auth_token != failed_token:
        return True
      if not self.refresh_token:
        return False
      resp = self.session.post(
        f"{self.base_url}/api/auth/refreshToken",
        json={"refreshToken": self.refresh_token},
        timeout=self.timeout,
      )
      if resp.ok:
        new_token = resp.json().get("token")
        if new_token:
          self.auth_token = new_token
          return True
      return False

  def get_json(self, path: str) -> Any:
    url = f"{self.base_url}/{path.lstrip('/')}"
    last_exc: Exception | None = None
    for attempt in range(self.max_retries):
      tok = self.auth_token
      try:
        resp = self.session.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=self.timeout)
        if resp.status_code == 401:
          if self._refresh(tok):
            continue
          raise RuntimeError(f"Authentication rejected (401) for {path}")
        if resp.status_code == 200:
          return resp.json()
      except requests.RequestException as exc:
        last_exc = exc
      if attempt + 1 < self.max_retries:
        time.sleep(0.4 * (attempt + 1))
    if last_exc:
      raise RuntimeError(f"Failed GET {path}") from last_exc
    raise RuntimeError(f"Failed GET {path} after {self.max_retries} attempts")

  def fetch_level_info(self, hierarchy_index: str | int) -> list[dict[str, Any]]:
    data = self.get_json(f"/scripture/tree/levelInfo/{hierarchy_index}")
    levels: list[dict[str, Any]] = []
    for group in data.get("levelInfo") or []:
      levels.extend(group.get("levels") or [])
    return levels

  def fetch_overview(self, hierarchy_index: str | int) -> dict[str, Any]:
    return self.get_json(f"/scripture/tree/overview/{hierarchy_index}")

  def fetch_leaf_mantras(self, hierarchy_index: str) -> list[dict[str, Any]]:
    data = self.get_json(f"/scripture/tree/all/mantras/{hierarchy_index}")
    return data.get("mantraList") or []

  def fetch_mantra_view(self, mantra_index: str) -> dict[str, Any]:
    return self.get_json(f"/scripture/tree/view/mantra/{mantra_index}")

  def fetch_tree_and_mantras(
    self,
    scripture_id: int | str,
    *,
    max_workers: int = 8,
  ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Walk ``scripture_id`` recursively and return ``(tree, overviews, mantras_by_leaf)``."""
    overviews: dict[str, dict[str, Any]] = {str(scripture_id): self.fetch_overview(scripture_id)}
    top_levels = self.fetch_level_info(scripture_id)
    leaves: list[str] = []

    def is_leaf(node: dict[str, Any]) -> bool:
      if node.get("last") is True or str(node.get("last")).lower() == "true":
        return True
      return bool(re.search(r"mantr", str(node.get("childType") or ""), re.I))

    def walk(nodes: list[dict[str, Any]]) -> None:
      def process_node(node: dict[str, Any]) -> None:
        hi = str(node["hierarchyIndex"])
        ov = self.fetch_overview(hi)
        with self._lock:
          overviews[hi] = ov
        if is_leaf(node):
          with self._lock:
            leaves.append(hi)
          return
        children = self.fetch_level_info(hi)
        node["_children"] = children
        if children:
          walk(children)
        else:
          with self._lock:
            leaves.append(hi)

      with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(process_node, nodes))

    walk(top_levels)
    mantras_by_leaf: dict[str, list[dict[str, Any]]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
      futs = {pool.submit(self.fetch_leaf_mantras, hi): hi for hi in leaves}
      for fut in concurrent.futures.as_completed(futs):
        hi = futs[fut]
        mantras_by_leaf[hi] = fut.result()

    return top_levels, overviews, mantras_by_leaf

  def fetch_many_mantra_views(
    self,
    mantra_indices: list[str],
    *,
    max_workers: int = 10,
    compact: bool = True,
    on_progress: Callable[[int, int], None] | None = None,
  ) -> dict[str, dict[str, Any] | None]:
    """Fetch ``/scripture/tree/view/mantra/{id}`` for ``mantra_indices`` in parallel."""
    results: dict[str, dict[str, Any] | None] = {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
      futs = {pool.submit(self.fetch_mantra_view, mid): mid for mid in mantra_indices}
      for fut in concurrent.futures.as_completed(futs):
        mid = futs[fut]
        try:
          raw = fut.result()
          results[mid] = extract_mantra_view_summary(raw) if compact else raw
        except Exception:
          results[mid] = None
        done += 1
        if on_progress:
          on_progress(done, len(mantra_indices))
    return {mid: results.get(mid) for mid in mantra_indices}
