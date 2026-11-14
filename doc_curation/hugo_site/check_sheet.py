#!/usr/bin/env python3
"""
check_sheet.py — Inspect the Google Sheet backing the pdf-lib map via Apps Script.

Usage:
  ~/gitland/python_venv/bin/python check_sheet.py [--script-url URL] [--q PAT] [--tail N]

Shows header, total rows, Pending counts, and the last N rows (or rows whose
source_path/archive_urls/site_path/map_source match the --q regex).
"""

import argparse
import re
import sys

from doc_curation.hugo_site.appscript_client import get_sheet


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--script-url", default=None,
                   help="Apps Script /exec URL (default: from browse.html)")
    p.add_argument("--q", default=None, help="regex filter over row text")
    p.add_argument("--tail", type=int, default=5, help="show last N rows")
    args = p.parse_args()

    sheet = get_sheet(args.script_url)
    if not sheet.get("ok"):
        print(f"GET failed: {sheet.get('error')}")
        sys.exit(1)
    rows = sheet.get("rows", [])
    print(f"header: {sheet.get('header')}")
    print(f"rows: {len(rows)}")
    pend = {}
    for r in rows:
        pend[r.get("Pending", "")] = pend.get(r.get("Pending", ""), 0) + 1
    print(f"Pending counts: {pend}")
    if args.q:
        pat = re.compile(args.q)
        matched = [r for r in rows
                   if pat.search(" ".join(str(r.get(c, ""))
                                          for c in ("source_path", "archive_urls",
                                                    "site_path", "map_source")))]
        print(f"q={args.q!r}: {len(matched)} matches")
        for r in matched[:20]:
            print(f"  row {r.get('__row')}: {r.get('source_path')} "
                  f"map_source={r.get('map_source')} Pending={r.get('Pending')}")
        return
    for r in rows[-args.tail:] if args.tail else rows:
        print(f"  row {r.get('__row')}: {r.get('source_path')} "
              f"map_source={r.get('map_source')} Pending={r.get('Pending')}")


if __name__ == "__main__":
    main()
