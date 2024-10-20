import copy, collections
import logging
import os
import textwrap

from bs4.element import PageElement
from tqdm import tqdm

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


def interleave_from_file(md_files, source_file, dest_pattern="[^\d०-९೦-೯]([\d०-९೦-೯]+) *॥.*(?=\n|$)", source_pattern="(?<=\n|^)([\d०-९೦-೯]+).+\n", detail_title="English", overwrite=False, dry_run=False):
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
  def _get_source_matches(source_file):
    if not os.path.exists(source_file):
      logging.warning("Source %s does not exist!", source_file)
      return
    logging.info("Sourcing content from %s", source_file)
    source_md = MdFile(file_path=source_file)
    (_, source_content) = source_md.read()
    source_match_map = get_quasi_section_int_map(source_content, source_pattern)
    logging.info(f"Got {len(source_match_map)} source matches ")
    return (source_md, source_content, source_match_map)

  missing_dest_indices = {}
  if not callable(source_file):
    source_md, source_content, source_match_map = _get_source_matches(source_file=source_file)
  for md_file in md_files:
    logging.info("Interleaving into %s", md_file.file_path)
    if callable(source_file):
      source_file = source_file(md_files.file_path)
      source_md, source_content, source_match_map = _get_source_matches(source_file=source_file)
    (_, dest_content) = md_file.read()
    dest_matches = list(regex.finditer(dest_pattern, dest_content))
    for dest_match in dest_matches:
      index_str = sanscript.transliterate(dest_match.group(1), _to=sanscript.IAST)
      if not index_str.isnumeric():
        logging.warning("Could not get index for: %s", dest_match.group())
        continue
      index = int(index_str)
      if index not in source_match_map:
        missing_dest_indices[index] = dest_match.group()
        continue
      if detail_title is not None:
        if detail_title == "विश्वास-प्रसुतिः":
          detail_params = " open"
        else:
          detail_params = ""
        inserted_html = textwrap.dedent(
          f"""
          <details{detail_params}><summary>{detail_title} - {dest_match.group(1)}</summary>
    
          {source_match_map[index].group()}
          </details>
          """
        )
        # textwrap.dedent seems to fail with in-place  formatted string
        inserted_html = regex.sub("(?<=\n|^) +", "", inserted_html)
      else:
        inserted_html = source_match_map[index].group().strip()
      if not overwrite:
        dest_content = dest_content.replace(dest_match.group(), "%s\n\n%s" % (dest_match.group(), inserted_html))
      else:
        dest_content = dest_content.replace(dest_match.group(), inserted_html)
      dest_content = _normalize_spaces(dest_content)
      source_content = source_content.replace(source_match_map[index].group(), "")
      source_content = _normalize_spaces(source_content)
    md_file.replace_content_metadata(new_content=dest_content, dry_run=dry_run)
    source_md.replace_content_metadata(new_content=source_content, dry_run=dry_run)

  if len(missing_dest_indices) > 0:
    logging.warning(f"Could not get indices in source: {missing_dest_indices}")
  

def transform_details_with_soup(content, metadata, transformer, title_pattern=None, *args, **kwargs):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content
  details = soup.select("body>details")
  for detail_tag in details:
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    transform_tag_strings(detail_tag=detail_tag, transformer=transformer, title_pattern=title_pattern, *args, **kwargs)
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

def insert_duplicate_adjascent(content, metadata, old_title_pattern="मूलम्.*", new_title="विश्वास-प्रस्तुतिः", inserter=PageElement.insert_before, content_transformer=lambda x:x):
  if new_title in content:
    logging.error(f"{new_title} already present. returning")
    return content
  def transformer(detail_tag):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    detail.title = new_title
    detail.content = content_transformer(detail.content)
    if new_title == "विश्वास-प्रस्तुतिः":
      attribute_str = "open"
    inserter(detail_tag, "\n\n")
    inserter(detail_tag, detail.to_soup(attributes_str=attribute_str))
    inserter(detail_tag, "\n\n")
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
  """
  
  :param content: 
  :param metadata: 
  :param title: 
  :return: (detail_tag, detail)
  """
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
  # Don't pick up details within details.
  details = soup.find_all(lambda x: x.name == 'details' and x.find_parent("details") is None)
  final_details = []
  title_to_detail = collections.defaultdict(list)
  for detail in details:
    title = _denumerify(detail.select_one("summary").text)
    if title in titles:
      title_to_detail[title].append(detail)
    else:
      title_to_detail["unarranged"].append(detail)
  for title in titles:
    if title in title_to_detail:
      for detail in title_to_detail[title]:
        final_details.append(detail)
  for detail in title_to_detail["unarranged"]:
    final_details.append(detail)
  current_detail = final_details[0]
  for index, detail in enumerate(final_details[1:]):
    spacer = NavigableString("\n\n")
    current_detail.insert_after(spacer)
    spacer.insert_after(detail)
    current_detail = detail
  # for index, detail in enumerate(final_details[1:]):
  #   detail.decompose()
  content_out = content_processor._make_content_from_soup(soup=soup)
  return content_out


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


def autonumber_details(content, title_filter=".*", number_pattern=None, script = sanscript.DEVANAGARI):
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
    if number_pattern is not None:
      matches = list(regex.finditer(number_pattern, detail.content))
      if len(matches) == 0:
        title_index = None
      else:
        title_index = sanscript.get_number(matches[-1].group(1))
    if title_index is not None:
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
  content = regex.sub(r"(?<=\n)(<\w+)", r"\n\n\1", content)
  content = regex.sub(r"\n *\n *\s+", "\n\n", content)
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


def transform_tag_strings(detail_tag, transformer, title_pattern=None):
  if title_pattern is not None and not regex.fullmatch(title_pattern, detail_tag.select_one("summary").text):
    return
  for x in detail_tag.contents:
    if isinstance(x, NavigableString):
      x.replace_with(transformer(x))


def shlokas_to_details(content, pattern=None, title_base="टीका"):
  from doc_curation.utils import patterns, sanskrit_helper
  if f">{title_base}" in content:
    return content
  content = sanskrit_helper.seperate_uvaacha(text=content)
  if pattern is None:
    pattern = patterns.PATTERN_2LINE_SHLOKA
  def detail_maker(match):
    shloka = match.group()
    if pattern == patterns.PATTERN_BOLDED_QUOTED_SHLOKA:
      shloka = shloka.replace("**", "")
      shloka = regex.sub("\n> *", "\n", shloka)
    if pattern not in [patterns.PATTERN_2LINE_SHLOKA_NO_NUM, patterns.PATTERN_BOLDED_QUOTED_SHLOKA]:
      shloka_id = f" - {match.groups()[-1].strip()}"
    else:
      shloka_id = ""
    detail = Detail(title=f"{title_base}{shloka_id}", content=shloka)
    return f"\n{detail.to_md_html()}\n"
  try:
    content = regex.sub(pattern, detail_maker, content)
  except TimeoutError as x:
    print(x)
    logging.fatal(f"pattern: {pattern}")
  content = _normalize_spaces(content)
  return content


def shlokas_to_muula_viprastuti_details(content, pattern=None, id_position=-1):
  if "विश्वास-प्रस्तुतिः" in content:
    return content
  from doc_curation.utils import patterns, sanskrit_helper
  content = sanskrit_helper.seperate_uvaacha(text=content)
  if pattern is None:
    pattern = patterns.PATTERN_2LINE_SHLOKA
  def detail_maker(match):
    shloka = match.group()
    if pattern == patterns.PATTERN_BOLDED_QUOTED_SHLOKA:
      shloka = shloka.replace("**", "")
      shloka = regex.sub("\n> *", "\n", shloka)
    if pattern not in [patterns.PATTERN_2LINE_SHLOKA_NO_NUM, patterns.PATTERN_BOLDED_QUOTED_SHLOKA]:
      shloka_id = f" - {match.groups()[id_position].strip()}"
    else:
      shloka_id = ""
    shloka = shloka.replace("**", "")
    detail_vishvaasa = Detail(title=f"विश्वास-प्रस्तुतिः{shloka_id}", content=shloka)
    detail_muula = Detail(title=f"मूलम्{shloka_id}", content=shloka)
    return f"\n{detail_vishvaasa.to_md_html()}\n\n{detail_muula.to_md_html()}" 
  try:
    content = regex.sub(pattern, detail_maker, content)
  except TimeoutError as x:
    print(x)
    logging.fatal(f"pattern: {pattern}")
  return content


def sentences_to_translated_details(content, source_language="en", dest_language="es"):
  from nltk.tokenize import sent_tokenize
  from doc_curation.utils import text_utils
  if f"<details><summary>{dest_language}</summary>" in content:
    logging.debug("Skipping translation because <summary>%s</summary>", dest_language)
    return content
  subcontents = regex.split(r"((?<=\n|^)[#\-<!]+[^\n]+(?=\n|$))", content)
  content_out = ""
  for subcontent in tqdm(subcontents, desc='Sec', ):
    if regex.match(r"[#\-<! ]+", subcontent):
      translation = text_utils.translate(text=subcontent, source_language=source_language, dest_language=dest_language)
      content_out += f"{subcontent}  \n  {{{translation}}}\n"
      continue
    soup = content_processor._soup_from_content(content=subcontent)
    if soup is None:
      return subcontent
    for element in soup.select_one("body").children:
      if isinstance(element, NavigableString):
        tokenizer_language = {"en": "english", "es": "spanish"}
        sentences = sent_tokenize(element.text, language=tokenizer_language[source_language])
        detail_pairs = []
        for sentence in tqdm(sentences, desc='Sent', ):
          detail_muula = Detail(title = source_language, content=sentence)
          translation = text_utils.translate(text=sentence, source_language=source_language, dest_language=dest_language)
          detail_trans = Detail(title = dest_language, content=translation)
          detail_pairs.append([detail_muula, detail_trans])
        detail_pairs.reverse()
        for [detail_muula, detail_trans] in detail_pairs:
          element.insert_after(NavigableString("\n\n"))
          element.insert_after(detail_trans.to_soup())
          element.insert_after(NavigableString("\n\n"))
          element.insert_after(detail_muula.to_soup(attributes_str="open"))
        element.extract()
        if element.name == "details":
          detail = Detail.from_soup_tag(detail_tag=element)
          translation = text_utils.translate(text=detail.content, source_language=source_language, dest_language=dest_language)
          detail_trans = Detail(title = f"{detail.title} {dest_language}", content=translation)
          element.insert_after(NavigableString("\n\n"))
          element.insert_after(detail_trans.to_soup())
          element.insert_after(NavigableString("\n\n"))
    subcontent = content_processor._make_content_from_soup(soup=soup)
    content_out = content_out + subcontent + "\n\n"
  content_out = _normalize_spaces(content_out)
  return content_out


def add_translation(content, src_detail_pattern="English", source_language="en", dest_language="es"):
  from doc_curation.utils import text_utils
  def _title_from_detail(detail):
    title = f"{detail.title} {dest_language}"
    if detail.title == "English":
      title = "Español"
    return title
  soup = content_processor._soup_from_content(content=content)
  if soup is None:
    return content
  content_modified = False
  elements = [element for element in soup.select_one("body").children if element.name == "details" and regex.match(src_detail_pattern, Detail.from_soup_tag(detail_tag=element).title)]
  dest_elements = [element for element in soup.select_one("body").children if element.name == "details" and _title_from_detail(Detail.from_soup_tag(detail_tag=elements[0])) == Detail.from_soup_tag(detail_tag=element).title]
  if len(dest_elements) > 0:
    logging.debug("Skipping translation")
    return content
  for element in tqdm(elements):
    detail = Detail.from_soup_tag(detail_tag=element)
    title = _title_from_detail(detail)
    translation = text_utils.translate(text=detail.content, source_language=source_language, dest_language=dest_language)
    translation = regex.sub(r"\[^", fr"\[^{dest_language}", translation)
    translation = regex.sub(r"(?<=\n|^) (\[^.+?\]:|>)", fr"\1", translation)
    detail_trans = Detail(title=title, content=translation)
    element.insert_after(detail_trans.to_soup())
    content_modified = True
  if content_modified:
    content = content_processor._make_content_from_soup(soup=soup)
    content = _normalize_spaces(content)
  return content


def wrap_into_detail(content, title, attributes_str=None):
  content_out = content.strip()
  if content_out == "":
    return content
  return Detail(title=title, content=content.strip()).to_md_html(attributes_str=attributes_str)


def non_detail_parts_to_detail(content, title):

  if title in ["विश्वास-प्रस्तुतिः", "मूलम् (वचनम्)"]:
    attributes_str = " open"
  else:
    attributes_str = ""
  content = regex.sub(r"(?<=/details>|^)\s*([^<]+?)\s*(?=<details|$)", rf"\n\n<details{attributes_str}><summary>{title}</summary>\n\n\1\n</details>\n\n", content)
  content = regex.sub(rf"<details><summary>{title}</summary>\n\n*</details>", "", content)
  content = _normalize_spaces(content)
  
  return content