import logging
import os, regex

import doc_curation.ebook.pandoc_helper
from doc_curation import ebook

from doc_curation.ebook import get_book_path, pandoc_helper
from doc_curation.ebook import calibre_helper
from doc_curation.md.file import MdFile
from doc_curation.ebook.pandoc_helper import pandoc_from_md_file
from doc_curation.pdf import booklet, latex


def epub_from_md_file(md_file, out_path, css_path=None, metadata={}, file_split_level=4, toc_depth=6, appendix=None, overwrite=True):
  def make_extra_args(file_split_level, toc_depth=6):
    pandoc_extra_args = ["--toc", f"--toc-depth={toc_depth}", f"--split-level={file_split_level}"]
    if css_path is not None:
      pandoc_extra_args.extend([f'--css={css_path}'])
    pandoc_extra_args.extend(["--resource-path", os.path.dirname(md_file.file_path)])
    return pandoc_extra_args

  pandoc_extra_args = make_extra_args(file_split_level=file_split_level, toc_depth=toc_depth)
  source_dir = os.path.dirname(md_file.file_path)

  if not out_path.endswith(".epub"):
    epub_path = get_book_path(source_dir, out_path) + ".epub"
  else:
    epub_path = out_path

  epub_path_min = epub_path.replace(".epub", "_min.epub")
  epub_path_min_notoc = epub_path.replace(".epub", "_min_notoc.epub")
  if True == overwrite or "epub" in overwrite:
    pandoc_from_md_file(md_file=md_file, dest_path=epub_path, metadata=metadata, pandoc_extra_args=pandoc_extra_args, detail_to_footnote=True)
    _fix_details_in_epub(epub_path=epub_path)

    md_file_min = MdFile(file_path=epub_path.replace(".epub", "_min.md"))
    metadata, content = md_file_min.read()
  
    pandoc_extra_args = make_extra_args(file_split_level=1)
    pandoc_from_md_file(md_file=md_file_min, dest_path=epub_path_min, metadata=metadata, pandoc_extra_args=pandoc_extra_args, appendix=appendix, detail_to_footnote=False)
    _fix_details_in_epub(epub_path=epub_path_min)
    overwrite = True

  if True == overwrite or "calibre" in overwrite:
    calibre_helper.to_pdf(epub_path=epub_path_min, paper_size="a4")
  
    pandoc_extra_args.remove("--toc")
    pandoc_from_md_file(md_file=md_file_min, dest_path=epub_path_min_notoc, metadata=metadata, pandoc_extra_args=pandoc_extra_args, appendix=appendix, detail_to_footnote=False)
    _fix_details_in_epub(epub_path=epub_path_min_notoc)

    calibre_helper.to_pdf(epub_path=epub_path_min_notoc, paper_size="a4", move_toc=True)
    a5_path = calibre_helper.to_pdf(epub_path=epub_path_min_notoc, paper_size="a5", move_toc=True)
    # booklet.duplicated_booklet(input_pdf_path=a5_path, output_pdf_path=a5_path.replace(".pdf", "_dup_booklet.pdf"))

  # if True == overwrite or "latex" in overwrite:
  #   a5_latex_path = regex.sub("(_min.*)?.epub", f"_A5.latex", epub_path_min_notoc)
  #   latex_body = latex.from_md(content=content)
  #   latex.to_pdf(latex_body=latex_body, dest_path=a5_path.replace(".pdf", "_latex_local.pdf"), metadata=metadata)


  if True == overwrite or "kobo" in overwrite:
    epub_for_kobo(epub_path=epub_path)
    calibre_helper.to_azw3(epub_path=epub_path, metadata=metadata)

  return epub_path


def make_epubs_recursively(source_dir, out_path, recursion_depth=None, dry_run=False, cleanup=True, *args, **kwargs):
  if out_path is None:
    out_path = source_dir
  if recursion_depth is not None:
    for subdir in os.listdir(source_dir):
      subdir_path = os.path.join(source_dir, subdir)
      if os.path.isdir(subdir_path):
        if recursion_depth > 0:
          make_epubs_recursively(source_dir=subdir_path, out_path=os.path.join(out_path, subdir), recursion_depth=recursion_depth - 1, dry_run=dry_run, cleanup=False, *args, **kwargs)


  epub_from_full_md(source_dir=source_dir, out_path=out_path, cleanup=cleanup, *args, **kwargs)


def epub_from_full_md(source_dir, out_path, omit_pattern=None, css_path=None, metadata={}, file_split_level=4, toc_depth=6, 
                      overwrite=True, appendix=None, detail_pattern_to_remove=r"मूलम्.*"): 
  full_md_path = os.path.join(source_dir, "full.md")

  epub_path = get_book_path(source_dir, out_path) + ".epub"
  if os.path.exists(epub_path) and not overwrite:
    logging.info(f"Skipping {epub_path} as it already exists.")
    return

  converter = lambda md_file, out_path: epub_from_md_file(md_file=md_file, out_path=out_path, metadata=metadata, file_split_level=file_split_level, toc_depth=toc_depth, css_path=css_path, overwrite=overwrite)
  ebook.via_full_md(source_dir=source_dir, out_path=os.path.dirname(epub_path), converter=converter, omit_pattern=omit_pattern, overwrite=overwrite, dest_format="epub", cleanup=True, detail_pattern_to_remove=detail_pattern_to_remove, appendix=appendix, metadata=metadata)
  


def epub_for_kobo(epub_path: str):

  logging.info("\nStep 2: Converting EPUB to KEPUB with kepubify...")
  kepubify_command = ['/home/vvasuki/go/bin/kepubify', epub_path, "-o", os.path.dirname(epub_path)]

  import subprocess
  result = subprocess.run(kepubify_command, capture_output=True, text=True)

  kepub_path = epub_path.replace(".epub", ".kepub.epub")
  if result.returncode == 0:
    logging.info(f"Successfully created '{kepub_path}'!")
  else:
    logging.error("Error during kepubify conversion:")
    logging.error(result.stderr)


def _fix_details_in_epub(epub_path: str):
  """
  Post-process an EPUB to convert <details ... open> into <details ... open="open">.
  Ensures 'mimetype' stays first and uncompressed as per EPUB spec.
  """
  import re
  import zipfile
  import tempfile
  import shutil

  if not os.path.isfile(epub_path):
    logging.warning(f"EPUB not found for post-process: {epub_path}")
    return

  # Read original EPUB
  with zipfile.ZipFile(epub_path, "r") as zin:
    # Extract 'mimetype' to preserve as-is (must be first and uncompressed)
    mimetype_data = None
    try:
      mimetype_data = zin.read("mimetype")
    except KeyError:
      pass  # Not strictly required to exist, but typical; we'll just proceed.

    # Create temp output EPUB
    fd, temp_epub = tempfile.mkstemp(suffix=".epub")
    os.close(fd)
    try:
      with zipfile.ZipFile(temp_epub, "w") as zout:
        # Write mimetype first, uncompressed if present
        if mimetype_data is not None:
          zinfo = zipfile.ZipInfo("mimetype")
          zinfo.compress_type = zipfile.ZIP_STORED
          zout.writestr(zinfo, mimetype_data)

        # Process all other files
        for item in zin.infolist():
          if item.filename == "mimetype":
            continue
          data = zin.read(item.filename)

          # Modify only XHTML/HTML files
          if item.filename.lower().endswith((".xhtml", ".html", ".htm")):
            try:
              text = data.decode("utf-8")
            except UnicodeDecodeError:
              # Try common fallback; if it fails, leave as-is
              try:
                text = data.decode("utf-16")
              except UnicodeDecodeError:
                zout.writestr(item, data)
                continue

            # Replace bare boolean open with explicit value, without touching open=
            pattern = re.compile(r'(<details\b[^>]*?)\sopen(?!\s*=)(?=(\s|/?>))', flags=re.IGNORECASE)
            fixed = pattern.sub(r'\1 open="open"', text)

            # Also handle stray cases like "<details open>" exactly
            fixed = re.sub(r'<details\s+open\s*>', '<details open="open">', fixed, flags=re.IGNORECASE)

            data = fixed.encode("utf-8")

          # Preserve compression for the rest (deflated)
          zout.writestr(item, data)

      # Replace original EPUB
      shutil.move(temp_epub, epub_path)
      logging.info(f"Normalized <details open> in EPUB: {epub_path}")
    finally:
      try:
        if os.path.exists(temp_epub):
          os.remove(temp_epub)
      except Exception:
        pass
