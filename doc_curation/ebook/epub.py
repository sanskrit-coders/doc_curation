import logging
import os

import regex

from doc_curation import ebook

from doc_curation.ebook import prep_content, get_book_path, title_from_path
from doc_curation.ebook.convert import to_azw3
from doc_curation.md.pandoc_helper import pandoc_from_md_file


def epub_from_md_file(md_file, out_path, css_path=None, metadata={}, file_split_level=4, toc_depth=6, appendix=None):
  pandoc_extra_args = ["--toc", f"--toc-depth={toc_depth}", f"--epub-chapter-level={file_split_level}"]
  if css_path is not None:
    pandoc_extra_args.extend([f'--css={css_path}'])

  if not out_path.endswith(".epub"):
    source_dir = os.path.dirname(md_file.file_path)
    epub_path = get_book_path(source_dir, out_path) + ".epub"
    metadata["title"] = title_from_path(dir_path=source_dir)

  pandoc_from_md_file(md_file=md_file, dest_path=epub_path, metadata=metadata, pandoc_extra_args=pandoc_extra_args, content_maker=prep_content, appendix=appendix)
  epub_for_kobo(epub_path=epub_path)
  to_azw3(epub_path=epub_path)

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


def epub_from_full_md(source_dir, out_path, css_path=None, metadata={}, file_split_level=4, toc_depth=6, 
                      overwrite=True, appendix=None): 
  full_md_path = os.path.join(source_dir, "full.md")

  epub_path = get_book_path(source_dir, out_path) + ".epub"
  if os.path.exists(epub_path) and not overwrite:
    logging.info(f"Skipping {epub_path} as it already exists.")
    return

  converter = lambda md_file, out_path: epub_from_md_file(md_file=md_file, out_path=out_path, metadata=metadata, file_split_level=file_split_level, toc_depth=toc_depth, css_path=css_path, appendix=appendix)
  ebook.via_full_md(source_dir=source_dir, out_path=epub_path, converter=converter, overwrite=overwrite, cleanup=True)
  


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


def get_epub_metadata_path(author, dir_path, out_path=f"/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/vv_ebook_pub/"):
  out_path = os.path.join(out_path, author)
  tome_match = regex.match("(.+)/(.+?)/sarva-prastutiH|mUlam/", dir_path)
  metadata = {}
  if author is not None:
    metadata["author"] = author
  if tome_match is not None:
    tome = tome_match.group(2)
    out_path = os.path.join(out_path, tome)
  return metadata, out_path


