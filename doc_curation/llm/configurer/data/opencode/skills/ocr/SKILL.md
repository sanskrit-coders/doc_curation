---
name: ocr
description: OCRs PDFs and scans to text. Default is Google Drive OCR (doc_curation pdf/drive_ocr); custom Tesseract or other bulk batch jobs run on Kaggle or Colab, never on the local machine, and only when explicitly directed. Use when a PDF or scan must be OCR'd, whether standalone or as part of pdf-to-md.
---

OCR the PDF or scan you are given.

In case you have a 2-page scan, or multi-column pages, consider splitting before OCR (use and modify as needed `pdf/splitter` for splitting two-up scanned PDFs into single pages).

**Default: Google Drive OCR via `doc_curation`'s `pdf/drive_ocr`.** OCR yourself only if explicitly directed otherwise — never run custom OCR jobs on the local machine.

Split large PDFs into small chunks before OCR — Drive's OCR quality degrades on long files:

```python
from doc_curation.pdf import drive_ocr

drive_ocr.split_and_ocr_all(dir_path=..., small_pdf_pages=10, file_pattern=r"(?!.*-double\.pdf$)[^_].*\.pdf")
```

- `split_and_ocr_all(dir_path=...)` handles a whole directory; `split_and_ocr_on_drive(pdf_path=...)` a single file.
- `small_pdf_pages=10` is a good default for Drive OCR quality; `detext=False` keeps the text layer when one exists.
- Segment files, tmp intermediates and `clear_tmp_files(base_dir=...)` cleanup live beside the source PDFs.

## Special tools — custom / bulk OCR

Run only when explicitly directed. Custom (e.g. Tesseract) OCR and other bulk batch jobs run on Kaggle or Colab, never on the local machine.

- Keep run scripts, dataset staging and a short README with kernel/dataset IDs and commands **in the project**, not only in `/tmp` — `/tmp` is wiped on session restart.
- Install dependencies inside every run: `poppler-utils` for `pdf2image`, and language data via `tessdata_best/<lang>.traineddata` when apt lacks it (e.g. `tesseract-ocr-san`); confirm with something like `tesseract --list-langs`.
- Run the OCR **sequentially**. On a 4-vCPU Kaggle box, 4 workers turn a 7 s page into a >120 s timeout — parallelism is a pessimisation for OCR.
- Wrap each page in `subprocess.run(..., timeout=…)` and write its output immediately, so one pathological scan cannot hang the session and partial results survive.
- Kaggle publishes no logs or outputs until a kernel finishes, so `RUNNING` says nothing about progress. Prefer several short, targeted runs over one long one, and print per-chunk progress lines.
- If a bulk job stalls twice, stop retrying. Count exactly which pages are actually needed and OCR only those.

## Report

Report the tool used (drive OCR or custom), the input paths, where the OCR output landed, and anything skipped or left ambiguous.
