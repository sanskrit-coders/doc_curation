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
                          overwrite_backup=True):
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
        layout = detector.detect_double_page_layout(image)
        if not layout.is_double_page:
          output.insert_pdf(source, from_page=page.number, to_page=page.number)
          continue

        for left_half in (True, False):
          output.insert_pdf(source, from_page=page.number, to_page=page.number)
          new_page = output[-1]
          new_page.set_rotation((page.rotation + layout.rotation) % 360)
          rect = new_page.rect
          split_x = rect.x0 + rect.width * layout.gutter
          if left_half:
            crop = pymupdf.Rect(rect.x0, rect.y0, split_x, rect.y1)
          else:
            crop = pymupdf.Rect(split_x, rect.y0, rect.x1, rect.y1)
          new_page.set_cropbox(crop * new_page.derotation_matrix)

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


def split_all_double_page_pdfs(dir_path, backup_suffix=BACKUP_SUFFIX,
                               recursive=True, min_double_fraction=0.5,
                               dpi=detector.RENDER_DPI,
                               overwrite_backup=False):
  """
  Detect and split all double-page PDFs under `dir_path`.

  Files already named with `backup_suffix` are skipped so that originals are not
  re-split. Returns the paths of PDFs that were split.
  """
  dir_path = os.path.abspath(os.path.expanduser(dir_path))
  split_paths = []
  for root, dir_names, file_names in os.walk(dir_path):
    if not recursive:
      dir_names[:] = []
    else:
      dir_names.sort()

    for file_name in sorted(file_names):
      stem, extension = os.path.splitext(file_name)
      if extension.lower() != ".pdf":
        continue
      if (backup_suffix and stem.endswith(backup_suffix)) or \
          file_name.endswith(".single.tmp.pdf"):
        continue

      pdf_path = os.path.join(root, file_name)
      try:
        output_path = split_double_page_pdf(
          pdf_path,
          backup_suffix=backup_suffix,
          min_double_fraction=min_double_fraction,
          dpi=dpi,
          overwrite_backup=overwrite_backup,
        )
      except FileExistsError as error:
        logger.warning("%s; skipping", error)
        continue
      except Exception:
        logger.exception("Failed to split %s", pdf_path)
        continue
      if output_path:
        split_paths.append(output_path)

  logger.info("Split %d double-page PDFs under %s", len(split_paths), dir_path)
  return split_paths
