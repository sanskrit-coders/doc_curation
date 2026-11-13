---
name: archival-cataloging
description: Works with archive.org items (upload, lookup, item metadata via curation_utils/ia) and records source-to-site-page catalog mappings for scanned books in the vishvAsa Hugo site. Use when archiving scans, looking up an archive.org item, or updating the spreadsheet catalog of a PDF/book conversion.
---

Archive.org work and the source-to-site-page catalog (venv: `~/gitland/python_venv`).

## Source-to-site-page catalog

Use `hugo_site`: compute the destination page with `md_to_site_path()` and post it with the
appscript client.

```python
from doc_curation.hugo_site import md_to_site_path
from doc_curation.hugo_site.appscript_client import post_append_rows

site_path = md_to_site_path("vedAH/content/yajuH/taittirIyam/brAhmaNam/file.md")
rows = [{
    "source_path": "/media/vvasuki/vData/text/granthasangrahaH/.../book.pdf",
    "archive_urls": "https://archive.org/details/...",
    "site_path": site_path,
    "map_source": "LLM-crouton",
}]
post_append_rows(sheet_url, rows)
```

- `md_to_site_path` takes a path relative to `~/gitland/vishvAsa` (or any path containing `/content/`);
  `_index.md`/`index.md` map to the directory URL.
- Row keys: `source_path`, `archive_urls`, `site_path`, `map_source` (posted as the sheet's `userId`).
  The server sets `Pending="add"` for a new `source_path` and `"replace"` for an existing one.
- **Older deployed `appScript.gs` has no `appendRows`**: `post_append_rows` then returns
  `{ok:false, error:"original row not found: undefined"}`. Fall back to
  `push_rows_chained(url, rows, dry_run=...)`, which appends in order anchored on the sheet's last row
  and skips `source_path`s already present. Pass `dry_run=True` first to see where rows would land.

## archive.org

Interact with archive.org through the `ia` command line (already configured) or
`curation_utils.archive_utility` programmatically.

## Blog and mail-stream archives

- Archiving blogs (wordpress, medium, substack, mags etc.) — see `doc_curation_projects/blog/from_html.py`.
- Archiving mail streams (googlegroups, mailman) — see `doc_curation_projects/mail_stream_dumper.py`.
