"""Client, browser-session helper, and text utilities for scraping scriptures from svarupa.org."""

from __future__ import annotations

import collections
import concurrent.futures
import html
import logging
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
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def to_madhyandina_svara(text: str) -> str:
  """Convert svarupa.org's U+0952 (``॒``) pitch-drop marks to Mādhyandina U+1CD8 (``᳘``)."""
  return text.strip().replace("\u0952", "\u1cd8")


def clean_overview_html(html_text: str | None) -> str:
  """Normalize simple HTML blocks (``<p>``, ``<br>``, entities, tags) from svarupa overview strings."""
  if not html_text:
    return ""
  s = re.sub(r"</p>\s*<p\b[^>]*>", "\n\n", html_text, flags=re.I)
  s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
  s = re.sub(r"</?p\b[^>]*>", "", s, flags=re.I)
  s = re.sub(r"<[^>]+>", "", s)
  s = html.unescape(s)
  return s.strip()


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
    if not isinstance(lang, dict):
      continue
    lang_name = lang.get("languageName")
    if not lang_name:
      continue
    entry: dict[str, Any] = {}
    for field in ("chanda", "devata", "rishi", "overview", "padapatha"):
      if lang.get(field):
        entry[field] = lang[field]
    comms = _extract_group_commentaries(lang.get("groups") or [])
    if comms:
      entry["commentary"] = comms
    if entry:
      out["languages"][lang_name] = entry
  return out


def _extract_group_commentaries(groups: list[Any]) -> list[dict[str, Any]]:
  comms: list[dict[str, Any]] = []
  for grp in groups:
    if not isinstance(grp, dict):
      continue
    for item in grp.get("groupContent") or []:
      if not isinstance(item, dict) or item.get("name") != "commentary":
        continue
      raw_values = item.get("value")
      if not isinstance(raw_values, list):
        continue
      for mahatma_entry in raw_values:
        if not isinstance(mahatma_entry, dict):
          continue
        vals = [
          {"key": d.get("key"), "source": d.get("source"), "value": d.get("value")}
          for d in (mahatma_entry.get("data") or [])
          if isinstance(d, dict) and d.get("value")
        ]
        if vals:
          comms.append(
            {
              "mahatmaId": mahatma_entry.get("mahatmaId"),
              "mahatmaName": mahatma_entry.get("mahatmaName"),
              "data": vals,
            }
          )
  return comms


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
  preferred_norm = preferred_mahatma.strip() if preferred_mahatma else None
  for comm in lang_entry.get("commentary") or []:
    if not isinstance(comm, dict):
      continue
    name = (comm.get("mahatmaName") or "").strip() or "Commentary"
    if preferred_norm and name != preferred_norm:
      continue
    parts = [
      clean_overview_html(str(d["value"]))
      for d in (comm.get("data") or [])
      if isinstance(d, dict) and d.get("value")
    ]
    joined = "\n\n".join(p for p in parts if p)
    if joined:
      blocks.append((name, joined))
  return blocks


_EXTRACT_TOKENS_JS = """
function unquote(x) {
  if (typeof x !== 'string') return x || '';
  try { const p = JSON.parse(x); return typeof p === 'string' ? p : x; } catch { return x; }
}
for (let i = 0; i < localStorage.length; i++) {
  const k = localStorage.key(i);
  const raw = localStorage.getItem(k);
  if (!raw) continue;
  if (k === 'authToken') {
    const tok = unquote(raw);
    if (tok) return {authToken: tok, refreshToken: unquote(localStorage.getItem('refreshToken') || '')};
  }
  try {
    const v = JSON.parse(raw);
    if (v && typeof v === 'object' && v.authToken) {
      return {authToken: unquote(v.authToken), refreshToken: unquote(v.refreshToken || '')};
    }
  } catch {}
}
return null;
"""


def extract_tokens_from_chrome_profile(
  *,
  chrome_user_data_dir: str | os.PathLike[str] | None = None,
  profile_name: str = "Default",
  scratch_profile_dir: str | os.PathLike[str],
  url: str = f"{SITE_ORIGIN}/scriptures?scriptureId=22",
  chrome_binary: str = "/opt/google/chrome/chrome",
  wait_seconds: float = 10.0,
) -> dict[str, str]:
  """Read ``authToken`` and ``refreshToken`` from a cloned Chrome profile via headless Chrome, then clean up."""
  from selenium import webdriver
  from selenium.common.exceptions import TimeoutException
  from selenium.webdriver.chrome.options import Options
  from selenium.webdriver.support.ui import WebDriverWait

  src_root = Path(chrome_user_data_dir) if chrome_user_data_dir else Path.home() / ".config/google-chrome"
  prof_root = Path(scratch_profile_dir)
  driver = None
  try:
    if prof_root.exists():
      shutil.rmtree(prof_root)
    (prof_root / profile_name).mkdir(parents=True, exist_ok=True)

    if (src_root / "Local State").exists():
      shutil.copy2(src_root / "Local State", prof_root / "Local State")
    for sub in ("Local Storage", "Session Storage", "Cookies", "Cookies-journal", "Cookies-wal", "Cookies-shm", "Preferences"):
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
    driver.get(url)
    try:
      tokens = WebDriverWait(driver, wait_seconds).until(lambda d: d.execute_script(_EXTRACT_TOKENS_JS))
    except TimeoutException:
      tokens = None
  finally:
    if driver is not None:
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
    self._refresh_lock = threading.Lock()
    if session is not None:
      self.session = session
    else:
      self.session = requests.Session()
      adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16)
      self.session.mount("https://", adapter)
      self.session.headers.update({"Origin": SITE_ORIGIN, "Referer": f"{SITE_ORIGIN}/"})

  def _refresh(self, failed_token: str) -> bool:
    with self._refresh_lock:
      if self.auth_token != failed_token:
        return True
      if not self.refresh_token:
        return False
      try:
        resp = self.session.post(
          f"{self.base_url}/api/auth/refreshToken",
          json={"refreshToken": self.refresh_token},
          timeout=self.timeout,
        )
        if not resp.ok:
          return False
        payload = resp.json()
      except (requests.RequestException, ValueError):
        return False
      new_token = payload.get("token") if isinstance(payload, dict) else None
      if not new_token:
        return False
      self.auth_token = str(new_token)
      new_refresh = payload.get("refreshToken") or payload.get("refresh_token")
      if new_refresh:
        self.refresh_token = str(new_refresh)
      return True

  def get_json(self, path: str) -> Any:
    url = f"{self.base_url}/{path.lstrip('/')}"
    last_exc: Exception | None = None
    last_status: int | None = None
    last_body = ""
    refreshed = False
    attempts = 0
    while attempts < self.max_retries:
      tok = self.auth_token
      try:
        resp = self.session.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=self.timeout)
        if resp.status_code == 401:
          if not refreshed and self._refresh(tok):
            refreshed = True
            continue
          raise RuntimeError(f"Authentication rejected (401) for {path}")
        if resp.status_code == 200:
          return resp.json()
        last_status = resp.status_code
        last_body = (getattr(resp, "text", "") or "")[:200]
        if resp.status_code not in _RETRYABLE_STATUS:
          raise RuntimeError(f"HTTP {resp.status_code} for {path}: {last_body}")
      except (requests.RequestException, ValueError) as exc:
        last_exc = exc
      attempts += 1
      if attempts < self.max_retries:
        time.sleep(0.4 * attempts)
    if last_exc:
      raise RuntimeError(f"Failed GET {path}: {last_exc}") from last_exc
    raise RuntimeError(f"Failed GET {path} (last status={last_status}): {last_body}")

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
    """Walk ``scripture_id`` with a single bounded thread pool and return ``(tree, overviews, mantras_by_leaf)``."""
    overviews: dict[str, dict[str, Any]] = {str(scripture_id): self.fetch_overview(scripture_id)}
    top_levels = self.fetch_level_info(scripture_id)
    leaves: list[str] = []

    def is_leaf(node: dict[str, Any]) -> bool:
      if node.get("last") is True or str(node.get("last")).lower() == "true":
        return True
      return bool(re.search(r"mantr", str(node.get("childType") or ""), re.I))

    def process_node(node: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]] | None]:
      hi = str(node["hierarchyIndex"])
      ov = self.fetch_overview(hi)
      if is_leaf(node):
        return node, ov, None
      children = self.fetch_level_info(hi)
      node["_children"] = children
      return node, ov, children

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
      pending: collections.deque[concurrent.futures.Future] = collections.deque(
        pool.submit(process_node, node) for node in top_levels
      )
      while pending:
        fut = pending.popleft()
        node, ov, children = fut.result()
        hi = str(node["hierarchyIndex"])
        overviews[hi] = ov
        if not children:
          leaves.append(hi)
        else:
          for child in children:
            pending.append(pool.submit(process_node, child))

      mantras_by_leaf: dict[str, list[dict[str, Any]]] = {}
      leaf_futs = {pool.submit(self.fetch_leaf_mantras, hi): hi for hi in leaves}
      for fut in concurrent.futures.as_completed(leaf_futs):
        hi = leaf_futs[fut]
        mantras_by_leaf[hi] = fut.result()

    return top_levels, overviews, mantras_by_leaf

  def fetch_many_mantra_views(
    self,
    mantra_indices: list[str],
    *,
    max_workers: int = 10,
    compact: bool = True,
    raise_on_error: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
  ) -> dict[str, dict[str, Any] | None]:
    """Fetch ``/scripture/tree/view/mantra/{id}`` for ``mantra_indices`` in parallel."""
    results: dict[str, dict[str, Any] | None] = {}
    errors: list[tuple[str, Exception]] = []
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
      futs = {pool.submit(self.fetch_mantra_view, mid): mid for mid in mantra_indices}
      for fut in concurrent.futures.as_completed(futs):
        mid = futs[fut]
        try:
          raw = fut.result()
          results[mid] = extract_mantra_view_summary(raw) if compact else raw
        except Exception as exc:
          logging.error("Failed fetching mantra view %s: %s", mid, exc)
          errors.append((mid, exc))
          results[mid] = None
        done += 1
        if on_progress:
          on_progress(done, len(mantra_indices))
    if raise_on_error and errors:
      raise RuntimeError(f"Failed fetching {len(errors)}/{len(mantra_indices)} mantra views (first: {errors[0][0]})")
    return {mid: results.get(mid) for mid in mantra_indices}
