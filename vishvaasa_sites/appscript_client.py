#!/usr/bin/env python3
"""
appscript_client.py — Low-level helpers to call the pdf-lib Apps Script endpoint.

The Apps Script server code lives in the Hugo site (pdf-lib/appScript.gs).
This module is the Python client used by push_map_to_sheet.py / check_sheet.py.

Endpoint contract (see pdf-lib/appScript.gs):
  GET  -> JSON { ok, header, rows:[{source_path, archive_urls, site_path,
           map_source, Pending, __row}, ...] }   (JSONP via ?callback= also works)
  Pending: "add" for brand-new source_path rows, "replace" for corrections
  to an existing source_path, blank once approved.
  POST (edit suggestion):
        { source_path, archive_urls, site_path, userId, originalSourcePath }
        Inserts the edited row below the original row, sets Pending to
        "add"/"replace" per above, map_source=userId. Original row untouched.
  POST (clean append, requires newer appScript.gs):
        { action:"append"|"appendRows", rows:[{source_path, archive_urls,
          site_path, map_source}, ...] }  (Pending="add").
        Existing source_path values are skipped.

Default script URL is the one embedded in pdf-lib/browse.html. Override with
PDF_LIB_SCRIPT_URL env var or an explicit `url` argument.
"""

import json
import os
import urllib.request

PDF_LIB_DIR = os.path.expanduser(
    "~/gitland/vishvAsa/vishvAsa.github.io/content/interests/private/pdf-lib")
MAP_CSV = os.path.join(PDF_LIB_DIR, "map.csv")
BROWSE_HTML = os.path.join(PDF_LIB_DIR, "browse.html")

# Fallback to the URL currently deployed for the pdf-lib sheet.
# Prefer reading it from browse.html so rotations do not break callers.
FALLBACK_SCRIPT_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbxN0DMuFrQRspr1fLMkAiN9-dgllGUQBRaRIaWvAgJcBb6iEVJQt1kRvOo10OBAbWdK/exec")


def default_script_url():
    """Resolve the Apps Script URL: env var > browse.html > fallback."""
    env = os.environ.get("PDF_LIB_SCRIPT_URL", "").strip()
    if env:
        return env
    try:
        text = open(BROWSE_HTML, encoding="utf-8").read()
        import re
        m = re.search(r"https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec", text)
        if m:
            return m.group(0)
    except FileNotFoundError:
        pass
    return FALLBACK_SCRIPT_URL


def _parse_appscript_text(txt):
    """Strip XSSI guard + unwrap JSONP, mirroring browse.js parseAppsScriptText."""
    import re
    txt = re.sub(r"^/\*O_o\*/\n?", "", txt.strip())
    m = re.match(r"^[a-zA-Z_$][\w$]*\s*\(([\s\S]*)\)\s*;?$", txt)
    if m:
        txt = m.group(1)
    return json.loads(txt)


def get_sheet(url=None, timeout=30):
    """GET the sheet and return the parsed payload dict."""
    url = url or default_script_url()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 pdf-lib-client"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        txt = resp.read().decode("utf-8")
    return _parse_appscript_text(txt)


def _post(url, payload, timeout=30):
    url = url or default_script_url()
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "text/plain;charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        txt = resp.read().decode("utf-8")
    return _parse_appscript_text(txt)


def post_edit(url, *, source_path, archive_urls, site_path, user_id,
              original_source_path, timeout=30):
    """POST one edit-suggestion row (Pending="add" if source_path is new, else "replace")."""
    return _post(url, {
        "source_path": source_path,
        "archive_urls": archive_urls,
        "site_path": site_path,
        "userId": user_id,
        "originalSourcePath": original_source_path,
    }, timeout=timeout)


def post_append_rows(url, rows, timeout=30):
    """POST clean appends via action appendRows. Returns response dict.

    `rows` is a list of dicts with source_path/archive_urls/site_path/map_source.
    On the older deployed appScript.gs (without append support) this returns
    { ok:false, error:"original row not found: undefined" } — use push_map_to_sheet
    --mode edit (chained) instead.
    """
    return _post(url, {"action": "appendRows", "rows": list(rows)}, timeout=timeout)


def push_rows_chained(url, rows, *, timeout=30, sleep_s=0.5, dry_run=False):
    """Append rows at the end of the sheet via edit-mode chaining.

    Works on the older endpoint (no appendRows): each row is POSTed anchored
    after the previous one (originalSourcePath = anchor), so bulk appends land
    in order at the end. New source_paths are marked Pending="add" by the
    server (edits to existing source_paths are "replace"). Use
    post_append_rows when the deployed appScript.gs supports it (also "add").

    `rows` must be in the desired sheet order. Returns list of responses.
    """
    import time
    sheet = get_sheet(url, timeout=timeout)
    if not sheet.get("rows"):
        raise RuntimeError("sheet has no rows; cannot anchor appends")
    anchor = sheet["rows"][-1]["source_path"]
    existing = {r["source_path"] for r in sheet["rows"]}
    responses = []
    for r in rows:
        if r["source_path"] in existing:
            responses.append({"ok": True, "skipped": True,
                              "source_path": r["source_path"]})
            continue
        if dry_run:
            responses.append({"ok": True, "dry_run": True,
                              "source_path": r["source_path"],
                              "anchor": anchor})
            anchor = r["source_path"]
            continue
        resp = post_edit(
            url,
            source_path=r["source_path"],
            archive_urls=r.get("archive_urls", ""),
            site_path=r.get("site_path", ""),
            user_id=r.get("map_source") or r.get("userId") or "LLM-crouton",
            original_source_path=anchor,
            timeout=timeout,
        )
        responses.append(resp)
        if not resp.get("ok"):
            raise RuntimeError(f"POST failed for {r['source_path']}: {resp}")
        existing.add(r["source_path"])
        anchor = r["source_path"]
        if sleep_s:
            time.sleep(sleep_s)
    return responses
