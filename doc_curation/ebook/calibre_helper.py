import logging
import os
import subprocess

from pypdf import PdfReader, PdfWriter
import regex

from doc_curation import pdf

CALIBRE = 'ebook-convert'


def metadata_to_calibre_args(metadata):
  args = []
  for key, value in metadata.items():
    if key.startswith("_"):
      continue
    args.append('--%s' % key)
    args.append(value)
  return args


def to_azw3(epub_path: str, metadata={}):
  logging.info("\nStep 3: Converting EPUB to AZW3...")
  # Construct the command for ebook-convert
  # The command is: ebook-convert "input_path.epub" "output_path.azw3"
  azw3_path = epub_path.replace(".epub", ".azw3")
  command = [CALIBRE, epub_path, azw3_path]
  # options = metadata_to_calibre_args(metadata=metadata)
  # command.extend(options)

  logging.info(f"Converting {os.path.basename(epub_path)} to AZW3...")

  # Execute the command
  result = subprocess.run(command, check=True, capture_output=True, text=True)

  logging.info("Conversion successful!")
  return azw3_path


# TODO: footnotes not appearing the bottom of the page.
def to_pdf(epub_path: str, paper_size="a5", margins=None, move_toc=False):
  # Actual results -  
  # left 36 - 14.5mm, left 39.7 - 15.87mm, right 36 - 16.6mm, top 24 - 9.31mm, bottom 24 - 1.75 mm to the page number, bottom 60.94 - 8.36 to page number.
  # theoretical - 1pt = 0.3528mm, 36 pt = 12.7 mm. 24 pt = 8.5 mm
  if margins is None:
    # For 39.7 is 14 mm theoretical; 60.95 is 21.5mm
    margins = {"left": "40.7", "right": "40", "top": "39.7", "bottom": "70.94"}
  dest_path = regex.sub("(_min.*)?.epub", f"_{paper_size}.pdf", epub_path)
  command = [
    CALIBRE,
    epub_path,
    dest_path,
    # generic_eink below ruins devanAgarI.
    '--output-profile', 'default',
    '--paper-size', f'{paper_size}',
    '--pdf-serif-family', 'Noto Serif Devanagari',
    '--pdf-sans-family', 'Noto Sans Devanagari',
    '--pdf-mono-family', 'Nimbus Mono PS [urw]',
    '--pdf-standard-font', 'sans',
    '--pdf-default-font-size', '14',
    '--pdf-mono-font-size', '14',
    '--pdf-page-margin-left', margins["left"],
    '--pdf-page-margin-right', margins["right"],
    '--pdf-page-margin-top', margins["top"],
    '--pdf-page-margin-bottom', margins["bottom"],
    '--chapter-mark', 'rule',
    '--pdf-add-toc',
    '--pdf-page-numbers',
    # The below fail.
    # '--pdf-header-template', '[title] — [chapter] — [section]',
    # '--pdf-footer-template', '[page]/[topage]'
  ]

  def _get_non_toc_page_length(command, dest_path):
    command = command.copy()
    command.remove("--pdf-add-toc")
    dest_path = dest_path.replace(".pdf", "_tmp.pdf")
    command[2] = dest_path
    logging.debug(" ".join(command))
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    if result.returncode != 0:
      logging.debug(result)
      raise Exception(result.stderr)
    reader = PdfReader(dest_path)
    total_pages = len(reader.pages)
    os.remove(dest_path)
    logging.info(f"Total pages without TOC: {total_pages}")
    return total_pages


  # Below Doesn't work with unicode metadata.
  # options = metadata_to_calibre_args(metadata=metadata)
  # command.extend(options)
  # Execute the command
  result = subprocess.run(command, check=True, capture_output=True, text=True)

  if move_toc:
    non_toc_page_length = _get_non_toc_page_length(command=command, dest_path=dest_path)
    writer = PdfWriter()
    with PdfReader(dest_path) as reader:
      # Add cover page
      writer.add_page(reader.pages[0])
      # Add TOC pages (which are at the end of the original PDF)
      for page in reader.pages[non_toc_page_length:]:
        writer.add_page(page)
      # Add content pages (from page 1 up to the start of TOC)
      for page in reader.pages[1:non_toc_page_length]:
        writer.add_page(page)

    # Safely overwrite the original file now that the reader is closed
    with open(dest_path, "wb") as f:
      writer.write(f)
    logging.info(f"Successfully created final PDF with TOC at front: {dest_path}")


  logging.info("Conversion successful!")
  # The below only complesses slightly (8%), and removes all devanAgarI fonts!
  # pdf.compress_with_gs(input_file_path=dest_path, output_file_path=dest_path)

  pdf.sample_pdf_margins(dest_path, page_size="a5", page_type="all")
  pdf.sample_pdf_margins(dest_path, page_size="a5", page_type="odd")
  pdf.sample_pdf_margins(dest_path, page_size="a5", page_type="even")

  return dest_path


