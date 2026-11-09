# vishvaasa_sites tooling

This directory holds the maintenance tooling for the Hugo sites'
PDF-library map and its Google Sheet mirror.

- **Data (unchanged, in the Hugo site):**
  `~/gitland/vishvAsa/vishvAsa.github.io/content/interests/private/pdf-lib/`
  — `map.csv`, `appScript.gs` (Apps Script server code), `browse.html`/`browse.js`.
- **Tooling (here):** `update_map.py` regenerates `map.csv`; `appscript_client.py`,
  `push_map_to_sheet.py`, `check_sheet.py` push/check it in the Sheet.

See `~/gitland/vishvAsa/vishvAsa.github.io/content/interests/private/pdf-lib/README.md`
for the `map.csv` format and regeneration commands.

## LLM provenance

`map_source` records how each row was found:

- Algorithmic: `size:<file>`, `md:<match>`, `ocr:<score>`, `correspondence:<score>`
- LLM: `LLM-crouton` (default for new runs via `--llm-label`), `LLM-claude` (historical), etc.
- UT-Austin: `ut-dharma:<slug>` (preserved across `update_map.py` regens)
- Manual: `manual` (preserved across regens)

Sheet `Pending`: `add` for brand-new `source_path` rows, `replace` for
corrections to an existing `source_path`, blank once approved. Set by
`appScript.gs` (both edit-mode and `appendRows`); redeploy it in Google
Apps Script after changing it.
