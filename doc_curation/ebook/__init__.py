import logging
import os

import regex

from doc_curation.md import pandoc_helper
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library.combination import make_full_text_md
from doc_curation.md.pandoc_helper import pandoc_dump_md


def prep_content(content, detail_to_footnote=False, appendix=None):
  def _strip_figures(content):
    return regex.sub(r"(?<=\n|^)!\[.*\]\(.+\) *\n(\{.+\})?\n", "", content)
  content = regex.sub(r"\+\+\+(\(.+?\))\+\+\+", r'<span class="inline_comment">\1</span>', content)
  content = regex.sub(r" *\.\.\.\{Loading\}\.\.\.", fr"", content)
  if detail_to_footnote:
    content = details_helper.add_detail_footnotes(content=content, remove_detail=True)
  if appendix is not None:
    if os.path.exists(appendix):
      md_file = MdFile(file_path=appendix)
      metadata, appendix = md_file.read()
      appendix = _strip_figures(appendix)
      appendix = f"# Appendix - {metadata['title']}\n\n{appendix}"
    content = f"{content}\n\n{appendix}"
  return content


def via_full_md(source_dir, out_path, converter, dest_format, overwrite=True, cleanup=True):
  full_md_path = os.path.join(source_dir, "full.md")

  if not os.path.exists(full_md_path):
    full_md_path = make_full_text_md(source_dir=source_dir, overwrite=overwrite)
  # copy full_md_path to out_path
  os.makedirs(os.path.dirname(out_path), exist_ok=True)
  from shutil import copyfile
  md_path = get_book_path(source_dir, out_path) + ".md"
  copyfile(full_md_path, md_path)
  md_file = MdFile(file_path=md_path)
  md_file.set_title(title=title_from_path(dir_path=source_dir), dry_run=False)
  dest_path = get_book_path(source_dir, out_path) + f".{dest_format}"

  converter(md_file, dest_path)

  # Clean up full.md files under source_dir
  if cleanup:
    for dirpath, dirnames, filenames in os.walk(source_dir):
      if "full.md" in filenames:
        os.remove(os.path.join(dirpath, "full.md"))
    logging.info(f"Removed {os.path.join(dirpath, 'full.md')} etc..")


def get_book_path(source_dir, out_path):
  book_name = os.path.basename(source_dir)
  if book_name in ["sarva-prastutiH", "mUlam"]:
    source_dir = os.path.dirname(source_dir)
    book_name = os.path.basename(source_dir)
  book_path = os.path.join(out_path, f"{book_name}")
  return book_path


def from_dir(source_dir, out_path, pandoc_extra_args=[], dest_format="html", appendix=None, cleanup=True, overwrite=True):

  via_full_md(source_dir=source_dir, out_path=out_path, converter=lambda x,y: pandoc_helper.pandoc_from_md_file(x, y, dest_format=dest_format, pandoc_extra_args=pandoc_extra_args, content_maker=prep_content, appendix=appendix), dest_format=dest_format, cleanup=cleanup, overwrite=overwrite)


def title_from_path(dir_path):
  tome_match = regex.match("(.+)/(.+?)/sarva-prastutiH|mUlam/", dir_path)
  if tome_match is not None:
    ref_dir = os.path.join(tome_match.group(1), tome_match.group(2))
    title = MdFile(os.path.join(ref_dir, "_index.md")).get_title(omit_chapter_id=False)
    if not regex.match("sarva-prastutiH|mUlam", os.path.basename(dir_path)):
      title = MdFile(os.path.join(dir_path, "_index.md")).get_title(omit_chapter_id=False, ref_dir_for_ancestral_title=ref_dir)
  else:
    title = MdFile(os.path.join(dir_path, "_index.md")).get_title(omit_chapter_id=False)
  return title


def make_out_path(author, dir_path, out_path=f"/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/vv_ebook_pub/"):
  out_path = os.path.join(out_path, author)
  tome_match = regex.match("(.+)/(.+?)/sarva-prastutiH|mUlam/", dir_path)
  if tome_match is not None:
    tome = tome_match.group(2)
    out_path = os.path.join(out_path, tome)
  return out_path
