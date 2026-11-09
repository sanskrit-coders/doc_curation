#!/usr/bin/env python3
"""
push_map_to_sheet.py — Push pdf-lib/map.csv rows to the Google Sheet via Apps Script.

Modes:
  --mode edit    (default)  Sequential edit-suggestion POSTs chained after the
                            last sheet row. Works on the currently deployed
                            endpoint; new source_paths land with Pending="add"
                            and map_source=userId (map_source column value).
  --mode append              Clean appendRows POSTs (needs the newer
                            appScript.gs with append support; Pending="add").
                            Falls back is not automatic — if the response is
                            { ok:false, ... }, re-run with --mode edit.

Only rows whose source_path is missing from the sheet are sent (GET once,
up front). The local map.csv is the source of truth; this script never deletes
sheet rows.

Examples:
  ~/gitland/python_venv/bin/python push_map_to_sheet.py --dry-run
  ~/gitland/python_venv/bin/python push_map_to_sheet.py
  ~/gitland/python_venv/bin/python push_map_to_sheet.py --mode append
  ~/gitland/python_venv/bin/python push_map_to_sheet.py --filter 'ut-dharma:'
  ~/gitland/python_venv/bin/python push_map_to_sheet.py --filter 'gautama' --limit 3
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from appscript_client import (MAP_CSV, get_sheet, post_append_rows,  # noqa: E402
                              push_rows_chained)


def read_csv_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--csv", default=MAP_CSV, help="map.csv path")
    p.add_argument("--script-url", default=None,
                   help="Apps Script /exec URL (default: from browse.html)")
    p.add_argument("--mode", choices=["edit", "append"], default="edit")
    p.add_argument("--filter", default=None, dest="filter_",
                   help="regex/substring on source_path (e.g. ut-dharma:)")
    p.add_argument("--limit", type=int, default=None, help="push at most N rows")
    p.add_argument("--dry-run", action="store_true", help="print, do not POST")
    args = p.parse_args()

    rows = read_csv_rows(args.csv)
    if args.filter_:
        import re
        pat = re.compile(args.filter_)
        rows = [r for r in rows if pat.search(r.get("source_path", ""))]
    sheet = get_sheet(args.script_url)
    if not sheet.get("ok"):
        print(f"GET failed: {sheet.get('error')}")
        sys.exit(1)
    print(f"sheet: header={sheet.get('header')} rows={len(sheet.get('rows', []))} "
          f"csv: {len(rows)} rows (after filter)")
    existing = {r["source_path"] for r in sheet["rows"]}
    missing = [r for r in rows if r["source_path"] not in existing]
    if args.limit is not None:
        missing = missing[: args.limit]
    print(f"missing in sheet: {len(missing)}")
    for r in missing[:20]:
        print(f"  - {r['source_path']}  map_source={r.get('map_source', '')}")
    if len(missing) > 20:
        print(f"  ... and {len(missing) - 20} more")

    if args.dry_run:
        print("dry-run: no POSTs")
        return

    if args.mode == "append":
        payload = [{"source_path": r["source_path"],
                    "archive_urls": r.get("archive_urls", ""),
                    "site_path": r.get("site_path", ""),
                    "map_source": r.get("map_source", "")} for r in missing]
        resp = post_append_rows(args.script_url, payload)
        print("appendRows response:", resp)
        if not resp.get("ok"):
            print("append failed (old endpoint?). Re-run with --mode edit "
                  "for chained Pending=add appends.")
            sys.exit(1)
    else:
        resps = push_rows_chained(args.script_url, missing, dry_run=False)
        ok = sum(1 for r in resps if r.get("ok") and not r.get("skipped"))
        skipped = sum(1 for r in resps if r.get("skipped"))
        print(f"chained POSTs: ok={ok} skipped={skipped}")
        for r in resps[:5]:
            print(" ", r)


if __name__ == "__main__":
    main()
