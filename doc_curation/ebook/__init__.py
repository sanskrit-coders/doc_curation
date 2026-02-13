import logging
import os
from shutil import copyfile

import regex

from doc_curation.utils import patterns
from doc_curation.md import content_processor
from doc_curation.ebook import pandoc_helper
from doc_curation.md.content_processor import details_helper, footnote_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library.combination import make_full_text_md
from doc_curation.ebook.pandoc_helper import pandoc_dump_md


def prep_content(content, detail_to_footnote=False, appendix=None, target="epub"):
  def _strip_figures(content):
    return regex.sub(r"(?<=\n|^)!\[.*\]\(.+\) *\n(\{.+\})?\n", "", content)
  if target == "latex":
    content = regex.sub(r"\+\+\+(\(.+?\))\+\+\+", r'\\inlinecomment{\1}', content)
  else:
    content = regex.sub(r"\+\+\+(\(.+?\))\+\+\+", r'<span class="inline_comment">\1</span>', content)
  content = regex.sub(r" *\.\.\.\{Loading\}\.\.\.", fr"", content)

  # The below messes empty lines within details.
  # content = regex.sub(f"({patterns.DEVANAGARI_BLOCK})"], r'<span class="deva">\1</span>', content)

  if detail_to_footnote:
    content = details_helper.add_detail_footnotes(content=content, remove_detail=True)
  if appendix is not None:
    if os.path.exists(appendix):
      md_file = MdFile(file_path=appendix)
      metadata, appendix = md_file.read()
      appendix = _strip_figures(appendix)
      appendix = f"# Appendix - {metadata['title']}\n\n{appendix}"
      # appendix = include_helper.fix_headers(content=appendix, h1_level=2)
    content = f"{content}\n\n{appendix}"
  return content


def via_full_md(source_dir, out_path, converter, dest_format, omit_pattern=None, overwrite=True, cleanup=True, detail_pattern_to_remove=r"मूलम्.*", metadata={},
                baseUrl="https://vishvAsa.github.io"):
  md_file = prep_full_md(omit_pattern, out_path, overwrite==True, source_dir, metadata=metadata, base_url=baseUrl)

  make_min_full_md(md_file.file_path, out_path, source_dir, detail_pattern_to_remove=detail_pattern_to_remove)

  dest_path = get_book_path(source_dir, out_path) + f".{dest_format}"

  converter(md_file, dest_path)

  # Clean up full.md files under source_dir
  if cleanup:
    for dirpath, dirnames, filenames in os.walk(source_dir):
      if "full.md" in filenames:
        os.remove(os.path.join(dirpath, "full.md"))
    logging.info(f"Removed {os.path.join(dirpath, 'full.md')} etc..")


def prep_full_md(omit_pattern, out_path, overwrite: bool, source_dir, metadata, base_url):
  full_md_path = os.path.join(source_dir, "full.md")

  if not os.path.exists(full_md_path):
    full_md_path = make_full_text_md(source_dir=source_dir, omit_pattern=omit_pattern, overwrite=overwrite)
  # copy full_md_path to out_path
  os.makedirs(os.path.dirname(out_path), exist_ok=True)
  from shutil import copyfile
  md_path = get_book_path(source_dir, out_path) + ".md"
  os.makedirs(os.path.dirname(md_path), exist_ok=True)
  copyfile(full_md_path, md_path)
  # copy directory images to out_path, if it exists.
  if os.path.exists(os.path.join(source_dir, "images")):
    import shutil
    images_dest = os.path.join(out_path, "images")
    shutil.copytree(os.path.join(source_dir, "images"), images_dest, dirs_exist_ok=True)
    logging.info(f"Copied images to {images_dest}")

  md_file = MdFile(file_path=md_path)
  md_file.set_title(title=title_from_path(dir_path=source_dir), dry_run=False)

  def _fix_metadata(c, m):
    m.update(metadata)
    return m

  logging.info(f"Fixing links and metadata for {md_path}")
  md_file.transform(
    content_transformer=lambda c, *args, **kwargs: regex.sub(r'(!?\[.*?\]\()../([^\)\s]+)(\))', r'\1\2)', c),
    metadata_transformer=_fix_metadata, dry_run=False)
  md_file.transform(content_transformer=lambda c, *args, **kwargs: regex.sub(r'(!?\[.*?\]\()/([^\)\s]+)(\))',
                                                                                       fr'\1{base_url}/\2)', c),
                    metadata_transformer=_fix_metadata, dry_run=False)

  logging.info("Fixing footnotes")
  md_file.transform(
    content_transformer=lambda c, *args, **kwargs: footnote_helper.to_plain_footnotes(content=c),
    dry_run=False)


  logging.info(f"Fixing open details tags for {md_path}")
  md_file.transform(
    content_transformer=lambda c, *args, **kwargs: details_helper.transform_detail_tags_with_soup(c,
                                                                                                            transformer=details_helper.open_attribute_fixer,
                                                                                                            details_css="details"),
    dry_run=False)

  md_file.transform(
    content_transformer=lambda c, *args, **kwargs: details_helper.transform_details_with_soup(c,
                                                                                                  title_transformer=lambda x: regex.sub("^विश्वास-", "मूल-", x), title_pattern="विश्वास-प्रस्तुतिः.*"),
    dry_run=False)

  return md_file


def make_min_full_md(md_path: str, out_path, source_dir, detail_pattern_to_remove):
  md_path_min = get_book_path(source_dir, out_path) + "_min.md"
  copyfile(md_path, md_path_min)
  md_file_min = MdFile(file_path=md_path_min)

  # Remove some detail tags.
  md_file_min.transform(
    content_transformer=lambda c, *args, **kwargs: details_helper.transform_detail_tags_with_soup(c, transformer=lambda  x, *args, **kwargs: x.decompose(),title_pattern=detail_pattern_to_remove,details_css="details"),
    dry_run=False)
  logging.info(f"Removed <details> tags from {md_path_min}")

  # Open all details.
  content_processor.replace_texts(md_file=md_file_min, patterns=[r"<details>"], replacement=r"<details open="">",
                                  flags=regex.MULTILINE)
  md_file_min.transform(content_transformer=footnote_helper.add_for_links, dry_run=False)
  logging.info(f"Added link-footnotes for {md_path_min}")


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


def from_dir(source_dir, out_path, omit_pattern=None, pandoc_extra_args=None, dest_format="html", appendix=None, cleanup=True, overwrite=True):

  via_full_md(source_dir=source_dir, out_path=out_path, omit_pattern=omit_pattern, converter=lambda x,y: pandoc_helper.pandoc_from_md_file(x, y, dest_format=dest_format, pandoc_extra_args=pandoc_extra_args, content_maker=prep_content, appendix=appendix), dest_format=dest_format, cleanup=cleanup, overwrite=overwrite)


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
  if author is not None:
    out_path = os.path.join(out_path, author)
  tome_match = regex.match("(.+)/(.+?)/sarva-prastutiH|mUlam/", dir_path)
  if tome_match is not None:
    tome = tome_match.group(2)
    out_path = os.path.join(out_path, tome)
  return out_path
