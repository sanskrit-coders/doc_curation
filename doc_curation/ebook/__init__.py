import logging
import os

import regex
from doc_curation.ebook.epub import epub_from_md_file


from doc_curation.ebook import pandoc_helper, md_book
from doc_curation.md.file import MdFile
from doc_curation.ebook.pandoc_helper import pandoc_dump_md
from doc_curation.pdf import pdf_maker


def get_book_path(source_dir, out_path):
  book_name = os.path.basename(source_dir)
  if book_name in ["sarva-prastutiH", "mUlam"]:
    source_dir = os.path.dirname(source_dir)
    book_name = os.path.basename(source_dir)
  book_path = out_path
  if book_name not in book_path:
    book_path = os.path.join(out_path, book_name)
  book_path = os.path.join(book_path, os.path.basename(book_path))
  return book_path


def from_dir(source_dir, out_path, omit_pattern=None, pandoc_extra_args=None, dest_format="html", appendix=None, cleanup=True, overwrite=".*"):

  make_all(source_dir=source_dir, out_path=out_path, omit_pattern=omit_pattern, converter=lambda x,y: pandoc_helper.pandoc_from_md_file(x, y, dest_format=dest_format, pandoc_extra_args=pandoc_extra_args, content_maker=prep_content, appendix=appendix), dest_format=dest_format, cleanup=cleanup, overwrite=overwrite)


def make_out_path(author, dir_path, out_path=f"/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/vv_ebook_pub/"):
  if author is not None:
    out_path = os.path.join(out_path, author)
  tome_match = regex.match("(.+)/(.+?)/sarva-prastutiH|mUlam/", dir_path)
  if tome_match is not None:
    tome = tome_match.group(2)
    out_path = os.path.join(out_path, tome)
  return out_path


def make_all(source_dir, out_path, omit_pattern=None, css_path=None, metadata={}, file_split_level=4, toc_depth=6,
             overwrite=".*", appendix=None, detail_pattern_to_remove=r"मूलम्.*", cleanup=True):



  src_full_md_path = os.path.join(source_dir, "full.md")
  epub_path = get_book_path(source_dir, out_path) + ".epub"
  md_path = get_book_path(source_dir, out_path) + ".md"

  if not os.path.exists(md_path) or regex.match(overwrite, "md"):
    md_file = md_book.prep_full_md(omit_pattern=omit_pattern, md_path=md_path, overwrite=overwrite, source_dir=source_dir, metadata=metadata, base_url="https://vishvAsa.github.io", appendix=appendix)


    md_book.make_min_full_md(md_path=md_path, source_dir=source_dir, detail_pattern_to_remove=detail_pattern_to_remove)

  if cleanup:
    md_book.remove_full_mds(source_dir)


  if os.path.exists(epub_path) and not regex.match(overwrite, "epub"):
    logging.info(f"Skipping {epub_path} as it already exists.")
  else:
    epub_from_md_file(md_file=md_file, epub_path=epub_path, metadata=metadata, file_split_level=file_split_level, toc_depth=toc_depth, css_path=css_path, overwrite=overwrite)

  if regex.match(overwrite, "pdf"):
    pdf_maker.from_epub(epub_path=epub_path)

  make_deprecated = False

  if make_deprecated:
    if regex.match(overwrite, "latex"):
      a5_latex_path = regex.sub("(_min.*)?.epub", f"_A5.latex", epub_path_min_notoc)
      latex_body = latex.from_md(content=content)
      latex.to_pdf(latex_body=latex_body, dest_path=a5_path.replace(".pdf", "_latex_local.pdf"), metadata=metadata)
