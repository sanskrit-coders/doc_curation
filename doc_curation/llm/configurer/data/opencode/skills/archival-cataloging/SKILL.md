---
name: archival-cataloging
description: Works with archive.org items (upload, lookup, item metadata via curation_utils/ia) and records source-to-site-page catalog mappings for scanned books in the vishvAsa Hugo site. Use when archiving scans, looking up an archive.org item, or updating the spreadsheet catalog of a PDF/book conversion.
---


## Source-to-site-page catalog

For updating the catalog mapping source PDFs/scans to their site pages, use `doc_curation.hugo_site`: figure out the destination page with `md_to_site_path()` and then post it with `appscript_client.post_append_rows()`.

```python
from doc_curation.hugo_site import md_to_site_path
from doc_curation.hugo_site.appscript_client import post_append_rows

site_path = md_to_site_path(md_path_relative_to_vishvAsa)
post_append_rows(sheet_url, [{"source_path": ..., "site_path": site_path, ...}])
```

## archive.org

Interact with archive.org through the `ia` command line (already configured) or `curation_utils.archive_utility` programmatically.

## Message archive updates
Archiving blogs (wordpress, medium, substack, mags etc.) - see `doc_curation/doc_curation_projects/blog/from_html.py` 

Archiving mail streams (googlegroups, mailman) - see `doc_curation_projects/mail_stream_dumper.py`