---
name: archival-cataloging
description: Archives to and looks up archive.org items (ia CLI, curation_utils.archive_utility), records source-to-site-page catalog mappings for the vishvAsa Hugo site (md_to_site_path + appscript client), and archives blogs and mail streams. Use when archiving scans, blogs, or mail streams, looking up an archive.org item, or updating the spreadsheet catalog of a PDF/book conversion.
---

Archive.org work and the source-to-site-page catalog (venv: `~/gitland/python_venv`).

## Source-to-site-page catalog

Use `hugo_site`: compute the destination page with `md_to_site_path()` and post it with the appscript client.

```python
from doc_curation.hugo_site import md_to_site_path, get_catalog_source_path
from doc_curation.hugo_site.appscript_client import post_append_rows

site_path = md_to_site_path("vedAH/content/yajuH/taittirIyam/brAhmaNam/file.md")
rows = [{
    "source_path": get_catalog_source_path("/media/vvasuki/vData/text/granthasangrahaH/.../book.pdf"),
    "archive_urls": "https://archive.org/details/...",
    "site_path": site_path,
    "map_source": "LLM-crouton",
}]
post_append_rows(sheet_url, rows)
```

- `hugo_site` lives at `doc_curation/hugo_site/` — import it as `doc_curation.hugo_site`, not as a top-level `hugo_site`.
- `md_to_site_path` takes a path relative to `~/gitland/vishvAsa` (or any path containing `/content/`);
  `_index.md`/`index.md` map to the directory URL.
- Always build `source_path` with `get_catalog_source_path()`: granthasangrahaH PDFs → `vv-pdfs:<rel-path>`;
  UT dharmashAstra etexts → `ut-dharma:<slug>`; Muktabodha etexts → `muktabodha:<code>`.
  (The appscript client re-normalizes on POST, so older bare paths still land in the new form.)
- Row keys: `source_path`, `archive_urls`, `site_path`, `map_source` (posted as the sheet's `userId`).
  The server sets `Pending="add"` for a new `source_path` and `"replace"` for an existing one.
- Deletes and approvals bypass the endpoint (it has no delete/update): use `delete_rows_by_source_path()`
  and `clear_pending()` from the same client — they use the Sheets API directly with the proofing OAuth tokens.

## archive.org

Interact with archive.org through the `ia` command line (already configured) or
`curation_utils.archive_utility` programmatically.

## Blog and mail-stream archives

- Archiving blogs (wordpress, medium, substack, mags etc.) — see `doc_curation_projects/blog/from_html.py`.
- Archiving mail streams (googlegroups, mailman) — see `doc_curation_projects/mail_stream_dumper.py`.

## Etext collection updates
Check UT dharmashAstra library etexts https://sites.utexas.edu/sanskrit/resources/dharmasastra/ for new items, which are then generally dumped to  /home/vvasuki/gitland/vishvAsa/kalpAntaram/content/dharmaH/nibandhaH.  
Call doc_curation_projects/misc/sanskrit_docs.py 
Call /home/vvasuki/gitland/sanskrit-coders/doc_curation/doc_curation_projects/misc/muktabodha.py
