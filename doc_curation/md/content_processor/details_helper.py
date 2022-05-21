import logging
import os
import textwrap

import regex
from bs4 import NavigableString

from doc_curation.md.file import MdFile
from indic_transliteration import sanscript
from doc_curation.md import content_processor


class Detail(object):
  def __init__(self, type, content):
    self.type = type
    self.content = content

  def to_html(self, attributes_str=None):
    if self.type is None:
      title = "Misc Detail"
      logging.warning(f"Unknown detail type for: {self.content}")
    else:
      title = self.type
    if attributes_str is None:
      if self.type in ["विश्वास-प्रस्तुतिः", "मूलम् (वचनम्)"]:
        attributes_str = "open"
      else:
        attributes_str = ""
    if attributes_str.strip() != "":
      attributes_str = " " + attributes_str
    return f"<details{attributes_str}><summary>{title}</summary>\n\n{self.content.strip()}\n</details>"


def interleave_from_file(md_file, source_file, dest_pattern="[^\d०-९೦-೯]([\d०-९೦-೯]+) *॥.*(?=\n|$)", source_pattern="(?<=\n|^)([\d०-९೦-೯]+).+\n", detail_title="English", dry_run=False):
  (_, dest_content) = md_file.read()
  if callable(source_file):
    source_file = source_file(md_file.file_path)
  if not os.path.exists(source_file):
    logging.warning("Source %s does not exist!", source_file)
    return 
  logging.info("Interleaving content from %s into %s", source_file, md_file.file_path)
  source_md = MdFile(file_path=source_file)
  (_, source_content) = source_md.read()
  dest_matches = list(regex.finditer(dest_pattern, dest_content))
  source_matches = list(regex.finditer(source_pattern, source_content))
  source_match_map = {}
  for source_match in source_matches:
    index_str = sanscript.transliterate(source_match.group(1), _to=sanscript.IAST)
    if index_str.isnumeric():
      source_match_map[int(index_str)] = source_match
    else:
      logging.warning("Could not get index for: %s", source_match.group())
  for dest_match in dest_matches:
    index_str = sanscript.transliterate(dest_match.group(1), _to=sanscript.IAST)
    if not index_str.isnumeric():
      logging.warning("Could not get index for: %s", dest_match.group())
      continue
    index = int(index_str)
    if index not in source_match_map:
      logging.warning("Could not get index %d in source: %s", index, dest_match.group())
      continue
    detail_html = textwrap.dedent(
      """
      
      <details><summary>%s</summary>

      %s
      </details>
      """
    ) % (detail_title, source_match_map[index].group())
    dest_content = dest_content.replace(dest_match.group(), "%s\n%s" % (dest_match.group(), detail_html))
    source_content = source_content.replace(source_match_map[index].group(), "")
  md_file.replace_content_metadata(new_content=dest_content, dry_run=dry_run)
  source_md.replace_content_metadata(new_content=source_content, dry_run=dry_run)


def transform_details_with_soup(content, metadata, transformer, *args, **kwargs):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content
  details = soup.select("details")
  for detail in details:
    transformer(detail, *args, **kwargs)
    detail.insert_after("\n")
  return content_processor._make_content_from_soup(soup=soup)


def vishvAsa_sanskrit_transformer(detail_tag):
  if detail_tag.select_one("summary").text != "विश्वास-प्रस्तुतिः":
    return
  for x in detail_tag.contents:
    if isinstance(x, NavigableString):
      x.replace_with(content_processor.rehyphenate_sanskrit_line_endings(x))
