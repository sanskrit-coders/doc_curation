# hugo_site tooling

This directory holds the maintenance tooling for the Hugo sites'
PDF-library mappings stored in Google Sheets.

- **Data / Client (in the Hugo site):**
  `~/gitland/vishvAsa/vishvAsa.github.io/content/interests/private/pdf-lib/`
  — `appScript.gs` (Apps Script server code), `browse.html`/`browse.js`.
- **Tooling (here):** `vv_pdf_library.py` scans local PDFs/sites and identifies/syncs
  mappings to the Sheet; `appscript_client.py` and `check_sheet.py` interact with the Sheet.

See `~/gitland/vishvAsa/vishvAsa.github.io/content/interests/private/pdf-lib/README.md`
for details on the library and conventions.

## `source_path` keys

Every `source_path` is normalized with `get_catalog_source_path()`:

- granthasangrahaH PDFs: `vv-pdfs:<path-relative-to-granthasangrahaH/>`
- UT-Austin dharmashAstra etexts: `ut-dharma:<slug>`
- Muktabodha etexts: `muktabodha:<catalog-code-or-slug>`

`find_new_pdf_mappings()` emits these keys, and `appscript_client`
(`post_edit`, `post_append_rows`, `push_rows_chained`) normalizes
`source_path` again on POST, so bare/absolute paths from older callers
still land in the new form. `delete_rows_by_source_path()` and
`clear_pending()` in the same client use the Sheets API directly (the
Apps Script endpoint has no delete/update action).

## LLM provenance

`map_source` records how each row was found:

- Algorithmic: `size:<file>`, `md:<match>`, `ocr:<score>`, `correspondence:<score>`
- LLM: `LLM - MODEL_NAME` (default for new runs via `--llm-label`), `LLM-claude` (historical), etc.
- Manual: `manual`

Sheet `Pending`: `add` for brand-new `source_path` rows, `replace` for
corrections to an existing `source_path`, blank once approved. Set by
`appScript.gs` (both edit-mode and `appendRows`); redeploy it in Google
Apps Script after changing it.
