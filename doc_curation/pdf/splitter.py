"""
Split PDFs whose pages contain two photographed book pages into single-page PDFs.
"""
import logging
import os
import shutil

import pymupdf

from doc_curation.pdf import detector

logger = logging.getLogger(__name__)

BACKUP_SUFFIX = "-double"


def split_double_page_pdf(pdf_path, backup_suffix=BACKUP_SUFFIX,
                          min_double_fraction=0.5, dpi=detector.RENDER_DPI,
                          overwrite_backup=False):
  """
  Move `pdf_path` to `<name><backup_suffix>.pdf` and write a single-page-per-image
  PDF back to `pdf_path`.

  Pages that are already single-page images (e.g. the cover) are copied unchanged.
  Returns the output path, or None if the PDF does not look like a double-page scan.
  """
  pdf_path = os.path.abspath(os.path.expanduser(pdf_path))
  if not detector.is_double_page_pdf(pdf_path,
                                     min_double_fraction=min_double_fraction,
                                     dpi=dpi):
    logger.info("Not a double-page scan, leaving unchanged: %s", pdf_path)
    return None

  backup_path = f"{os.path.splitext(pdf_path)[0]}{backup_suffix}.pdf"
  if os.path.exists(backup_path) and not overwrite_backup:
    raise FileExistsError(f"Backup already exists: {backup_path}")

  temp_path = f"{pdf_path}.single.tmp.pdf"
  if os.path.exists(temp_path):
    os.remove(temp_path)

  try:
    with pymupdf.open(pdf_path) as source, pymupdf.open() as output:
      for page in source:
        image = detector.render_page_gray(page, dpi=dpi)
        if detector.is_double_page_image(image):
          gutter = detector.find_page_gutter(image)
          rect = page.rect
          split_x = rect.x0 + rect.width * gutter
          halves = ((rect.x0, split_x), (split_x, rect.x1))
          for left, right in halves:
            new_page = output.new_page(width=right - left, height=rect.height)
            new_page.show_pdf_page(
              new_page.rect, source, page.number,
              clip=pymupdf.Rect(left, rect.y0, right, rect.y1),
            )
        else:
          output.insert_pdf(source, from_page=page.number, to_page=page.number)
      output.set_metadata(source.metadata)
      output.save(temp_path, garbage=4, deflate=True)

    shutil.move(pdf_path, backup_path)
    os.replace(temp_path, pdf_path)
  finally:
    if os.path.exists(temp_path):
      os.remove(temp_path)

  logger.info("Split %s into single pages; original saved as %s",
               pdf_path, backup_path)
  return pdf_path
