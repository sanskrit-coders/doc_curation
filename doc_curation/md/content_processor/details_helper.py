import copy
import logging
import os
import textwrap

from bs4.element import PageElement
import doc_curation.md.content_processor.space_helper
import regex

from doc_curation.utils import patterns
from doc_curation.md.content_processor import get_quasi_section_int_map
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript
from doc_curation.md import content_processor
from bs4 import BeautifulSoup, NavigableString
from doc_curation.utils import sanskrit_helper


class Detail(object):
  def __init__(self, title, content):
    self.title = title
    self.content = content

  def to_md_html(self, attributes_str=None):
    if self.title is None:
      title = "Misc Detail"
      logging.warning(f"Unknown detail type for: {self.content}")
    else:
      title = self.title
    if attributes_str is None:
      if self.title in ["विश्वास-प्रस्तुतिः", "मूलम् (वचनम्)"]:
        attributes_str = "open"
      else:
        attributes_str = ""
    if attributes_str.strip() != "":
      attributes_str = " " + attributes_str
    return f"<details{attributes_str}><summary>{title}</summary>\n\n{self.content.strip()}\n</details>"

  def to_soup(self, attributes_str=None):
    return BeautifulSoup(self.to_md_html(attributes_str=attributes_str), 'html.parser')

  @classmethod
  def from_soup_tag(cls, detail_tag):
    title = detail_tag.select_one("summary").text.strip()
    detail_text = "".join([x.text for x in list(detail_tag.children)[1:]]).strip()
    return Detail(title=title, content=detail_text)


def interleave_from_file(md_file, source_file, dest_pattern="[^\d०-९೦-೯]([\d०-९೦-೯]+) *॥.*(?=\n|$)", source_pattern="(?<=\n|^)([\d०-९೦-೯]+).+\n", detail_title="English", dry_run=False):
  """
  
  :param md_file: 
  :param source_file: Can be a function returning a string or a string.
  :param dest_pattern: Common patterns: 
        [^\d०-९೦-೯]([\d०-९೦-೯]+) *॥.*(?=\n|$)
        <details.+?summary>मूलम् *- *(\S+)</summary>[\s\S]+?</details>\n
  :param source_pattern: Pattern to find in the source. Common patterns:
      (?<=\n|^)([\d०-९೦-೯]+).+\n
  :param detail_title: If None, no new detail is inserted.
  :param dry_run: Boolean
  :return: 
  """
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
  source_match_map = get_quasi_section_int_map(source_content, source_pattern)
  logging.info(f"Got {len(dest_matches)} dest matches and {len(source_match_map)} source matches ")
  for dest_match in dest_matches:
    index_str = sanscript.transliterate(dest_match.group(1), _to=sanscript.IAST)
    if not index_str.isnumeric():
      logging.warning("Could not get index for: %s", dest_match.group())
      continue
    index = int(index_str)
    if index not in source_match_map:
      logging.warning("Could not get index %d in source: %s", index, dest_match.group())
      continue
    if detail_title is not None:
      inserted_html = textwrap.dedent(
        """
        <details><summary>%s</summary>
  
        %s
        </details>
        """
      ) % (detail_title, source_match_map[index].group())
    else:
      inserted_html = source_match_map[index].group()
    dest_content = dest_content.replace(dest_match.group(), "%s\n\n%s" % (dest_match.group(), inserted_html))
    source_content = source_content.replace(source_match_map[index].group(), "")
  md_file.replace_content_metadata(new_content=dest_content, dry_run=dry_run)
  source_md.replace_content_metadata(new_content=source_content, dry_run=dry_run)


def transform_details_with_soup(content, metadata, transformer, title=None, *args, **kwargs):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content
  details = soup.select("body>details")
  for detail_tag in details:
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    if title is None or regex.fullmatch(title, detail.title):
      transformer(detail_tag, *args, **kwargs)
    detail_tag.insert_after("\n")
  return content_processor._make_content_from_soup(soup=soup)


def transliterate_details(content, source_script, dest_script=sanscript.DEVANAGARI, title=None):
  def transformer(detail_tag):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    new_text = content_processor.transliterate(text=detail.content, source_script=source_script, dest_script=dest_script)
    new_text = f"\n\n{new_text}\n"
    for child in list(detail_tag.children)[1:]:
      child.extract()
    list(detail_tag.children)[0].insert_after(new_text)

  return transform_details_with_soup(content=content, metadata=None, title=title, transformer=transformer)

def insert_duplicate_before(content, metadata, old_title_pattern="मूलम्.*", new_title="विश्वास-प्रस्तुतिः"):
  if new_title in content:
    logging.error(f"{new_title} already present. returning")
    return content
  def transformer(detail_tag):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    detail.title = new_title
    if new_title == "विश्वास-प्रस्तुतिः":
      attribute_str = "open"
    detail_tag.insert_before("\n\n")
    detail_tag.insert_before(detail.to_soup(attributes_str=attribute_str))
    detail_tag.insert_before("\n\n")
    if "open" in detail_tag and "मूलम्" in old_title_pattern:
      del detail_tag["open"]
  content = transform_details_with_soup(content=content, metadata=metadata, transformer=transformer, title=old_title_pattern)
  content.replace("open = \"\"", "open")
  if "मूलम्" in old_title_pattern:
    content.replace("<details open><summary>मूलम्", "<details><summary>मूलम्")
  return content


def extract_detail_tags_from_file(md_file):
  [metadata, content] = md_file.read()
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return []
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  details = soup.select("body>details", recursive=False)
  return details


def insert_adjascent_detail(content, metadata, title, new_element, inserter=PageElement.insert_after):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content or title not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content
  if isinstance(new_element, str):
    new_element = BeautifulSoup(new_element, 'html.parser')
  if isinstance(new_element, Detail):
    new_element = new_element.to_soup()
  details = soup.select("details")
  for detail in details:
    if detail.select_one("summary").text.strip() == title:
      inserter(detail, "\n")
      inserter(detail, new_element)
      inserter(detail, "\n")
    # inserter(detail, "\n")
  return content_processor._make_content_from_soup(soup=soup)


def get_details(content, title, metadata=None):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return []
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return []
  details = soup.select("details")
  result = []
  for detail_tag in details:
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    if detail.title == title:
      result.append((detail_tag, detail))
  return result


def get_detail(content, metadata, title):
  details = get_details(content=content, metadata=metadata, title=title)
  if len(details) == 0:
    return (None, None)
  else:
    return details[0]

def get_detail_content(content, titles, metadata=None):
  result = ""
  for title in titles:
    details = get_details(content=content, metadata=metadata, title=title)
    for detail_tuple in details:
      (tag, detail) = detail_tuple
      result = f"{result}  \n{detail.content}"
  return result


def dump_detail_content(source_md, dest_path, titles, dry_run=False):
  (metadata, content) = source_md.read()
  metadata["_file_path"] = source_md.file_path
  detail_content = get_detail_content(content=content, metadata=metadata, titles=titles)
  dest_md = MdFile(file_path=dest_path)
  dest_md.dump_to_file(metadata={"title": " ".join(titles)}, content=detail_content, dry_run=dry_run)


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


def merge_successive(content, title_filter=".*"):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content)
  if soup is None:
    return content
  details = soup.select("details")
  final_details = []
  prev_detail = None
  prev_detail_tag = None
  for index, detail_tag in enumerate(details):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    title = _denumerify(detail.title)
    if prev_detail is not None:
      prev_title = _denumerify(prev_detail.title)
    if prev_detail is not None and title == prev_title and regex.fullmatch(title_filter, prev_title):
      prev_detail_tag.append(f"\n{detail.content}\n")
      detail_tag.decompose()
    prev_detail = detail
    prev_detail_tag = detail_tag
  content = content_processor._make_content_from_soup(soup=soup)
  content = _normalize_spaces(content)
  return content


def autonumber_details(content, title_filter=".*", script = sanscript.DEVANAGARI):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content)
  if soup is None:
    return content
  details = soup.select("details")
  import collections
  detail_counts = {}
  prev_detail = None
  prev_detail_tag = None
  for index, detail_tag in enumerate(details):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    title  = detail.title
    title = _denumerify(title)
    title_index = detail_counts.get(title, 0) + 1
    detail_counts[title] = title_index
    index_str = "%02d" % title_index
    index_str = sanscript.transliterate(index_str, _to=script)
    list(detail_tag.children)[0].string = f"{title} - {index_str}"
  content = content_processor._make_content_from_soup(soup=soup)
  content = _normalize_spaces(content)
  return content


def _denumerify(title):
  title = regex.sub(patterns.ALL_DIGITS, "", title)
  title = regex.sub("[ -]*$", "", title)
  return title


def _normalize_spaces(content):
  content = regex.sub("(?<=\n)(<\w+)", r"\n\n\1", content)
  content = regex.sub("\n\n\n+", "\n\n", content)
  return content


def detail_content_replacer_soup(detail_tag, replacement):
  summary = detail_tag.select_one("summary")
  detail = Detail.from_soup_tag(detail_tag=detail_tag)
  for x in summary.find_next_siblings():
    x.extract()
  for x in detail_tag.contents:
    if isinstance(x, NavigableString):
      x.extract()
  if callable(replacement):
    replacement = replacement(detail.content)
  summary.insert_after(f"\n\n{replacement}\n")


def transform_tag_strings(detail_tag, transformer, type_pattern=None):
  if type_pattern is not None and not regex.fullmatch(type_pattern, detail_tag.select_one("summary").text):
    return
  for x in detail_tag.contents:
    if isinstance(x, NavigableString):
      x.replace_with(transformer(x))


def sanskrit_tag_transformer(detail_tag, type_pattern):
  def transformer(x):
    # x = doc_curation.md.content_processor.space_helper.dehyphenate_sanskrit_line_endings(x)
    x = sanskrit_helper.fix_lazy_anusvaara(x)
    return x
  transform_tag_strings(detail_tag=detail_tag, transformer=transformer, type_pattern=type_pattern)


def shlokas_to_muula_viprastuti_details(content, pattern=None):
  if "विश्वास-प्रस्तुतिः" in content:
    return content
  from doc_curation.utils import patterns, sanskrit_helper
  content = sanskrit_helper.seperate_uvaacha(text=content)
  if pattern is None:
    pattern = patterns.PATTERN_2LINE_SHLOKA
  def detail_maker(match):
    shloka = match.group()
    detail_vishvaasa = Detail(title="विश्वास-प्रस्तुतिः", content=shloka)
    detail_muula = Detail(title="मूलम्", content=shloka)
    return f"\n{detail_vishvaasa.to_md_html()}\n\n{detail_muula.to_md_html()}" 
  try:
    content = regex.sub(pattern, detail_maker, content, timeout=2)
  except TimeoutError as x:
    print(x)
    logging.fatal(f"pattern: {pattern}")
  if pattern == patterns.PATTERN_BOLDED_QUOTED_SHLOKA:
    content = content.replace("**", "")
    content = regex.sub("\n> *", "\n", content)
  return content


def wrap_into_detail(content, title, attributes_str=None):
  content_out = content.strip()
  if content_out == "":
    return content
  return Detail(title=title, content=content.strip()).to_md_html(attributes_str=attributes_str)


def non_detail_parts_to_detail(content, title):
  content = regex.sub(r"(?<=/details>|^)\s*([^<]+?)\s*(?=<details|$)", rf"\n\n<details><summary>{title}</summary>\n\n\1\n</details>\n\n", content)
  return content