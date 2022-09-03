import copy
import logging
import os
import textwrap

import doc_curation.md.content_processor.line_helper
import regex
from bs4 import NavigableString, BeautifulSoup

from doc_curation.md.file import MdFile
from doc_curation.scraping.html_scraper import souper
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
  details = soup.select("body>details")
  for detail in details:
    transformer(detail, *args, **kwargs)
    detail.insert_after("\n")
  return content_processor._make_content_from_soup(soup=soup)


def extract_details_from_file(md_file):
  [metadata, content] = md_file.read()
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return []
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  details = soup.select("body>details", recursive=False)
  return details


def insert_after_detail(content, metadata, title, new_element):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content
  details = soup.select("details")
  for detail in details:
    if detail.select_one("summary").text.strip() == title:
      detail.insert_after("\n")
      detail.insert_after(new_element)
      detail.insert_after("\n")
    detail.insert_after("\n")
  return content_processor._make_content_from_soup(soup=soup)


def get_detail(content, metadata, title):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return None
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return None
  details = soup.select("details")
  for detail in details:
    if detail.select_one("summary").text.strip() == title:
      return "".join([x.text for x in list(detail.children)[1:]])
  return None

def rearrange_details(content, metadata, titles, *args, **kwargs):
  # UNTESTED
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content
  details = soup.select("details")
  final_details = []
  title_to_detail = {detail.select_one("summary").text: detail for detail in details}
  for title in titles:
    if title in title_to_detail:
      final_details.append(copy.copy(title_to_detail[title]))
  for index, detail in details.enumerate():
    detail.insert_after("\n")
    detail.insert_after(final_details[index])
    detail.decompose()
  return content_processor._make_content_from_soup(soup=soup)


def detail_content_replacer_soup(detail_tag, title, new_text):
  summary = detail_tag.select_one("summary")
  if summary.text != title:
    return
  for x in summary.find_next_siblings():
    x.extract()
  for x in detail_tag.contents:
    if isinstance(x, NavigableString):
      x.extract()
  summary.insert_after(f"\n\n{new_text}\n")


def vishvAsa_sanskrit_transformer(detail_tag):
  if detail_tag.select_one("summary").text != "विश्वास-प्रस्तुतिः":
    return
  for x in detail_tag.contents:
    if isinstance(x, NavigableString):
      x.replace_with(doc_curation.md.content_processor.line_helper.rehyphenate_sanskrit_line_endings(x))


def shlokas_to_muula_viprastuti_details(content, pattern=None):
  if "विश्वास-प्रस्तुतिः" in content:
    return content
  if pattern is None:
    from doc_curation.md.content_processor import patterns
    pattern = patterns.PATTERN_2LINE_SHLOKA
  def detail_maker(match):
    shloka = match.group()
    detail_vishvaasa = Detail(type="विश्वास-प्रस्तुतिः", content=shloka)
    detail_muula = Detail(type="मूलम्", content=shloka)
    return f"{detail_vishvaasa.to_html()}\n\n{detail_muula.to_html()}" 
  content = regex.sub(pattern, detail_maker, content)
  return content