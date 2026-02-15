import logging
import os
from shutil import copyfile

import regex
from doc_curation.md import content_processor
from doc_curation.md.content_processor import footnote_helper, details_helper, embed_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library.combination import make_full_text_md



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


def prep_full_md(omit_pattern, md_path, overwrite: bool, source_dir, metadata, base_url, appendix=None, detail_to_footnote=False):
  full_md_path = os.path.join(source_dir, "full.md")

  if not os.path.exists(full_md_path) or regex.match(overwrite, "md"):
    full_md_path = make_full_text_md(source_dir=source_dir, omit_pattern=omit_pattern, overwrite=regex.match(overwrite, "md"))
  # copy full_md_path to out_path
  os.makedirs(os.path.dirname(md_path), exist_ok=True)
  from shutil import copyfile
  os.makedirs(os.path.dirname(md_path), exist_ok=True)
  copyfile(full_md_path, md_path)
  # copy directory images to out_path, if it exists.
  if os.path.exists(os.path.join(source_dir, "images")):
    import shutil
    images_dest = os.path.join(md_path, "images")
    shutil.copytree(os.path.join(source_dir, "images"), images_dest, dirs_exist_ok=True)
    logging.info(f"Copied images to {images_dest}")

  md_file = MdFile(file_path=md_path)
  md_file.set_title(title=title_from_path(dir_path=source_dir), dry_run=False)

  def _fix_metadata(c, m):
    m.update(metadata)
    return m

  def _fix_content(content, *args, **kwargs):

    if appendix is not None and os.path.exists(appendix):
      md_file_appendix = MdFile(file_path=appendix)
      metadata, content_appendix = md_file_appendix.read()
      content_appendix = f"# Appendix - {metadata['title']}\n\n{content_appendix}"
      logging.info("Strip appendix figures")
      content_appendix = regex.sub(r"(?<=\n|^)!\[.*?\]\(.+?\) *\n(\{.+?\})?\n", "", content_appendix)
      # appendix = include_helper.fix_headers(content=appendix, h1_level=2)
      content = f"{content}\n\n{content_appendix}"
      return content
 
    logging.info(f"Fixing links and metadata")
    content = regex.sub(r'(!?\[.*?\]\()../([^\)\s]+)(\))', r'\1\2)', content)
    content = regex.sub(r'(!?\[.*?\]\()/([^\)\s]+)(\))',
                        fr'\1{base_url}/\2)', content)


    logging.info("Fixing footnotes")
    content = footnote_helper.to_plain_footnotes(content=content)

    logging.info(f"Fixing open details tags for {md_path}")
    content = details_helper.transform_detail_tags_with_soup(content, transformer=details_helper.open_attribute_fixer, details_css="details")
    content = details_helper.transform_details_with_soup(content, title_transformer=lambda x: regex.sub("^विश्वास-", "मूल-", x), title_pattern="विश्वास-प्रस्तुतिः.*")

    content = embed_helper.remove_embeds(content=content)
    content = regex.sub(r" *\.\.\.\{Loading\}\.\.\.", fr"", content)
    
    # The below messes empty lines within details.
    # content = regex.sub(f"({patterns.DEVANAGARI_BLOCK})"], r'<span class="deva">\1</span>', content)
  
    if detail_to_footnote:
      content = details_helper.add_detail_footnotes(content=content, remove_detail=True)

  md_file.transform(
    content_transformer=_fix_content, metadata_transformer=_fix_metadata,
    dry_run=False)

  return md_file


def make_min_full_md(md_path: str, source_dir, detail_pattern_to_remove):
  md_path_min = md_path.replace(".md", "_min.md")
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


def remove_full_mds(source_dir):
  for dirpath, dirnames, filenames in os.walk(source_dir):
    if "full.md" in filenames:
      os.remove(os.path.join(dirpath, "full.md"))
  logging.info(f"Removed {os.path.join(dirpath, 'full.md')} etc..")
