---
name: pdf-to-md
description: Converts PDFs to Markdown — extracts the text layer, OCRs when extraction yields garbage (via the ocr skill), proofreads, then hyphenates Sanskrit, and updates the source-to-site-page catalog. Use when a PDF must become a Markdown page.
---

Convert the PDF you are given to Markdown. Work in this order and skip a step when it is unnecessary.

1. **Text layer first.** Check the file with `pdfinfo`, then extract with `pdftotext`. If it yields clean prose in the right script, skip OCR.

2. **OCR only when extraction is garbage, or is helpful to decipher it** — no text layer, mojibake, one word per line, wrong script, or page after page of `...[[??]]`. Hand the OCR to the `ocr` skill (drive OCR by default) rather than doing it here.

3. **Proofread, then hyphenate.** Hand the Markdown to the `proofreader-hyphenator` skill — it cleans up and corrects the text, then hyphenates the Sanskrit (including Sanskrit embedded in other-language text) once its fixes are settled.

4. **Update the spreadsheet catalog upon conversion.** When the output Markdown lands under `~/gitland/vishvAsa` (it backs a Hugo site) and the PDF is within `/media/vvasuki/vData/text/granthasangrahaH/` (currently mounted), hand the catalog update to the `archival-cataloging` skill (md_to_site_path/post_append_rows recipe there).


Report which steps ran, what was OCR'd, where the output landed, and the `source_path` → `site_path` row added/pushed (with sheet row number / `Pending=add` confirmation).
