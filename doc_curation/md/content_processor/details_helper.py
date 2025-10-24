from collections import defaultdict
import copy, collections
import logging
import os
import textwrap

import doc_curation.translation
from bs4.element import PageElement
from tqdm import tqdm

import doc_curation.md.content_processor.space_helper
import regex

from doc_curation.md.content_processor.footnote_helper import Footnote
from doc_curation.utils import patterns
from doc_curation.md import library
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

  def __str__(self):
    return f"{self.title}: {self.content}"

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
    if detail_tag == None or detail_tag.name != "details":
      return None
    title = detail_tag.select_one("summary").text.strip()
    detail_text = "".join([x.text for x in list(detail_tag.children)[1:]]).strip()
    return Detail(title=title, content=detail_text)


def _remap_source_matches(source_map, dest_matches):
  if len(dest_matches) != len(source_map):
    logging.info(f"Skipping re-indexing. Lengths do not match. {len(dest_matches)} != {len(source_map)}")
    return source_map

  source_match_map_new = {}
  successful_mappings = 0

  # Pair the destination matches directly with the source map's VALUES
  # This still assumes order, but makes it much more explicit.
  source_values = source_map.values()
  for dest_match, source_value in zip(dest_matches, source_values):
    index_str = sanscript.transliterate(dest_match.group(1), _to=sanscript.IAST)

    if not index_str.isnumeric():
      logging.warning("Could not get numeric index for: %s. Skipping this entry.", dest_match.group())
      continue  # Skip this specific entry, but don't discard the whole operation

    index = int(index_str)

    # Check for potential duplicate keys in the destination text
    if index in source_match_map_new:
      logging.warning("Duplicate index %d found in destination matches. Overwriting previous value.", index)

    source_match_map_new[index] = source_value
    successful_mappings += 1

  # A more intelligent final check
  if successful_mappings != len(source_map):
    logging.error("Re-indexing failed. The original map will be used.")
    return source_map

  logging.info("Successfully re-indexed %d out of %d entries.", successful_mappings, len(source_map))
  return source_match_map_new


def interleave_from_file(md_files, source_file, dest_pattern=r"[^\d०-९೦-೯]([\d०-९೦-೯]+) *॥.*(?=\n|$)", source_pattern=r"(?<=\n|^)([\d०-९೦-೯]+).+\n", detail_title="English", use_dest_number=False, overwrite=False, dry_run=False):
  r"""
  
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
  if isinstance(md_files, str):
    md_files = library.get_md_files_from_path(dir_path=md_files, file_pattern="**/*.md")
  elif isinstance(md_files, MdFile):
    md_files = [md_files]
  def _get_source_matches(source_file):
    if not os.path.exists(source_file):
      logging.warning("Source %s does not exist!", source_file)
      return (None, None, None)
    logging.info("Sourcing content from %s", source_file)
    source_md = MdFile(file_path=source_file)
    (_, source_content) = source_md.read()
    source_match_map = get_quasi_section_int_map(source_content, source_pattern, use_ordinal=use_dest_number)
    logging.info(f"Got {len(source_match_map)} source matches ")
    return (source_md, source_content, source_match_map)

  missing_dest_indices = {}
  if not callable(source_file):
    source_md, source_content, source_match_map = _get_source_matches(source_file=source_file)
  for md_file in md_files:
    logging.info("Interleaving into %s", md_file.file_path)
    if callable(source_file):
      source_file = source_file(md_file.file_path)
      source_md, source_content, source_match_map = _get_source_matches(source_file=source_file)
      if source_match_map is None:
        continue
    (_, dest_content) = md_file.read()
    dest_matches = list(regex.finditer(dest_pattern, dest_content))
    if use_dest_number: 
      source_match_map = _remap_source_matches(source_map=source_match_map, dest_matches=dest_matches)
  
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
    if source_content.strip() == "" and dest_content.strip() != "":
      logging.info(f"Removing {source_file}")
      if not dry_run:
        os.remove(source_file)
    else:
      source_md.replace_content_metadata(new_content=source_content, dry_run=dry_run)

  if len(missing_dest_indices) > 0:
    logging.warning(f"Could not get indices in source: {missing_dest_indices}")
  

def transform_details_with_soup(content, metadata, content_str_transformer=None, title_transformer=None, title_pattern=None, details_css="body>details", *args, **kwargs):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content
  # Note - fixes only top level details
  details = soup.select(details_css)
  for detail_tag in details:
    if title_pattern is not None and not regex.fullmatch(title_pattern, detail_tag.select_one("summary").text):
      continue
    if title_transformer is not None:
      detail_tag.select_one("summary").text = title_transformer(detail_tag.select_one("summary").text)
    if content_str_transformer is not None:
      for x in detail_tag.contents:
        if isinstance(x, NavigableString):
          x.replace_with(content_str_transformer(x, metadata=metadata, *args, **kwargs))
      detail_tag.insert_after("\n")
  return content_processor._make_content_from_soup(soup=soup)


def open_attribute_fixer(detail_tag, *args, **kwargs):
  if "open" in detail_tag.attrs:
    detail_tag["open"] = ""


def transform_detail_tags_with_soup(content, transformer, title_pattern=None, details_css="body>details", *args, **kwargs):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=kwargs.get('metadata', None))
  if soup is None:
    return content
  details = soup.select(details_css)
  for detail_tag in list(details):
    if detail_tag.parent is None:
      # detail_tag.decompose() may have been called.
      continue
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    if title_pattern is None or regex.fullmatch(title_pattern, detail.title):
      transformer(detail_tag, *args, **kwargs)
  return content_processor._make_content_from_soup(soup=soup)


def detail_remover(content, title, *args, **kwargs):
  return transform_detail_tags_with_soup(content=content, title_pattern=title, transformer=lambda x, *args, **kwargs: x.decompose())


def adjascent_inserter(detail_tag, metadata, neighbor_maker, inserter=PageElement.insert_after):
  detail = Detail.from_soup_tag(detail_tag=detail_tag)
  neighbor = neighbor_maker(detail)
  if neighbor is None:
    return 
  inserter(detail_tag, "\n\n")
  inserter(detail_tag, neighbor)
  inserter(detail_tag, "\n\n")


def add_detail_footnotes(content, remove_detail=False, *args, **kwargs):
  def transformer(detail_tag, *args, **kwargs):
    if detail_tag.get("open") is not None:
      return 
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    previous_details = detail_tag.find_all_previous(name=detail_tag.name)
    footnote = Footnote(id_str=f"fn_det_{detail.title[:3]}_{len(previous_details)}", content=detail.content)

    detail_tag.insert_after(f"\n\n({detail.title}{footnote.get_reference()})\n\n{footnote.to_definition()}\n\n")

  detail_css = "details:not([open])"
  content = transform_detail_tags_with_soup(content=content, metadata=None, transformer=transformer, details_css=detail_css)

  if remove_detail:
    # We don't want to affect len(previous_details) in footnote numbering - so we remove the details separately.
    def remover(detail_tag, *args, **kwargs):
      if detail_tag.get("open") is not None:
        return
      detail_tag.decompose()
    content = transform_detail_tags_with_soup(content=content, metadata=None, transformer=remover, details_css=detail_css)


  return content


def transliterate_details(content, source_script, dest_script=sanscript.DEVANAGARI, title=None):
  def transformer(detail_tag):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    new_text = content_processor.transliterate(text=detail.content, source_script=source_script, dest_script=dest_script)
    new_text = f"\n\n{new_text}\n"
    for child in list(detail_tag.children)[1:]:
      child.extract()
    list(detail_tag.children)[0].insert_after(new_text)

  return transform_detail_tags_with_soup(content=content, metadata=None, title=title, content_transformer=transformer)

def insert_duplicate_adjascent(content, old_title_pattern="मूलम्(.*)", new_title=r"विश्वास-प्रस्तुतिः\1", inserter=PageElement.insert_before, content_transformer=lambda x:x, *args, **kwargs):
  if new_title in content:
    logging.error(f"{new_title} already present. returning")
    return content
  def transformer(detail_tag, *args, **kwargs):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    detail.title = regex.sub(old_title_pattern, new_title, detail.title)
    detail.content = content_transformer(detail.content)
    attribute_str = None
    if new_title.startswith("विश्वास-प्रस्तुतिः"):
      attribute_str = "open"
    inserter(detail_tag, "\n\n")
    inserter(detail_tag, detail.to_soup(attributes_str=attribute_str))
    inserter(detail_tag, "\n\n")
    if "open" in detail_tag and "मूलम्" in old_title_pattern:
      del detail_tag["open"]

  content = transform_detail_tags_with_soup(content=content, transformer=transformer, title_pattern=old_title_pattern, *args, **kwargs)
  content.replace("open=\"\"", "open")
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


def get_detail_bunches(md_file, bunch_start_pattern="विश्वास-प्रस्तुतिः.*", comment_title_pattern="मूलम्.*|.*भाष्यम्.*|.*टीका.*|English.*|Español.*|विश्वास-टिप्पनी.*|विषयः|भावः|स्रोतः", ignored_titles = ""):
  details = extract_detail_tags_from_file(md_file=md_file)
  bunches = []
  bunch = None
  for index, detail_tag in enumerate(details):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    if detail_tag.parent.name == "div":
      # Likely to already be an include
      continue
    if regex.fullmatch(bunch_start_pattern, detail.title):
      if bunch is not None:
        bunches.append(bunch)
      bunch = [detail]
      gathering_commentaries = True
      comment_text = ""
    elif gathering_commentaries  and regex.match(comment_title_pattern, detail.title):
      bunch.append(detail)
    elif regex.fullmatch(ignored_titles, detail.title): 
      continue
    else:
      gathering_commentaries = False
      bunches.append(bunch)
      bunch = None
  if bunch is not None:
    bunches.append(bunch)
  return bunches


def insert_adjascent_element(content, metadata, title, new_element, inserter=PageElement.insert_after):
  # Stray usage of < can fool the soup parser. Hence the below.
  def _get_soup_element(new_element):
    if isinstance(new_element, str):
      new_element = BeautifulSoup(new_element, 'html.parser')
    if isinstance(new_element, Detail):
      new_element = new_element.to_soup()
    return new_element

  if title is None:
    new_element = _get_soup_element(new_element)
    soup = content_processor._soup_from_content(content=content, metadata=metadata)
    soup.body.append(new_element)
    return content_processor._make_content_from_soup(soup=soup)
  if "details" not in content or not regex.search(title, content):
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content
  new_element = _get_soup_element(new_element)
  details = soup.select("details")
  for detail in details:
    if regex.fullmatch(title, detail.select_one("summary").text.strip()):
      inserter(detail, "\n\n")
      inserter(detail, copy.copy(new_element))
      inserter(detail, "\n\n")
    # inserter(detail, "\n")
  return content_processor._make_content_from_soup(soup=soup)


def remove_adjascent_duplicates(content):
  content = regex.sub(r"(<details><summary>.+</summary>[^<]+</details>)\n+(?=\1)", "", content)
  return content


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
    if regex.match(title, detail.title):
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


def count_details(content, metadata, *args, **kwargs):
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    logging.info(f"No details found in {metadata['_file_path']}")
    return content
  # Don't pick up details within details.
  details = soup.find_all(lambda x: x.name == 'details' and x.find_parent("details") is None)
  details_dict = defaultdict(int)
  for detail_tag in details:
    title = Detail.from_soup_tag(detail_tag=detail_tag).title.split(" - ")[0]
    details_dict[title] += 1
  logging.info(f"{len(details_dict)} details found in {os.path.basename(metadata['_file_path'])} - {details_dict}")
  return content


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
  title_to_detail = collections.defaultdict(lambda:collections.defaultdict(list))
  for detail in details:
    title = detail.select_one("summary").text
    number = _get_number(title=title)
    title_denumerified = _denumerify(title)
    if title in titles:
      title_to_detail[title_denumerified][number].append(detail)
    else:
      title_to_detail["unarranged"][number].append(detail)
  def _get_details_with_id(id):
    details_list = []
    for title in titles + ["unarranged"]:
      details_list.extend(title_to_detail[title][id])
    details_list.extend(title_to_detail["unarranged"][id])
    return details_list
  for title in titles + ["unarranged"]:
    for id in title_to_detail[title].keys():
      if detail not in final_details:
        final_details.extend(_get_details_with_id(id=id))
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

def get_nieghbor_detail(detail_tag, seek_before=False):
  """Gets the neighboring detail tag based on seek direction.

  Args:
      detail_tag: The BeautifulSoup detail tag to start from
      seek_before: If True, look at previous siblings, else next siblings

  Returns:
      The neighboring Detail object or None if not found
  """
  if seek_before:
    sibling = detail_tag.find_previous_sibling("details")
  else:
    sibling = detail_tag.find_next_sibling("details")
  return sibling



def set_id_from_neighbor(content, target_title_pattern=".*", ref_title_pattern="मूलम्.+", seek_before=True, metadata=None):
  def copy_id(detail_tag, *args, **kwargs):
    ref_detail_tag = get_nieghbor_detail(detail_tag, seek_before=seek_before)
    ref_detail = Detail.from_soup_tag(detail_tag=ref_detail_tag)
    while ref_detail is not None and ref_detail.title is not None and not regex.fullmatch(ref_title_pattern, ref_detail.title):
      ref_detail_tag = get_nieghbor_detail(ref_detail_tag, seek_before=seek_before)
      ref_detail = Detail.from_soup_tag(detail_tag=ref_detail_tag)

    if ref_detail is None or not regex.fullmatch(ref_title_pattern, ref_detail.title):
      ref_detail = None
      return
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    base_title = detail.title.split(" - ")[0]
    ids = ref_detail.title.split(" - ")
    detail_tag.select_one("summary").string = " - ".join([base_title] + ids[1:])
  content = transform_detail_tags_with_soup(title_pattern=target_title_pattern, content=content, transformer=copy_id, metadata=metadata)
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


def _get_number(title):
  matches = regex.findall(f"{patterns.ALL_DIGITS}+", title)
  if len(matches) > 0:
    return matches[-1]
  else:
    return None

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


def pattern_to_details(content, title="टीका", pattern=patterns.TAMIL_BLOCK, content_group=1, title_suffix_group=None):
  def _detail_maker(match):
    local_title = title
    if title_suffix_group is not None:
      local_title = f"{title} - {match.group(title_suffix_group)}"
    detail = Detail(title=local_title, content=match.group(content_group).strip())
    return detail.to_md_html() + "\n\n"
  content = regex.sub(pattern, _detail_maker, content)
  return content

def sections_to_details(content, pattern=r"(?<=\n|^)\#+ +(\S.+)\s+(\S[^\#<]+?)(?=[\#<]|$)"):
  def _detail_maker(match):
    detail = Detail(title=match.group(1), content=match.group(2).strip())
    return detail.to_md_html() + "\n\n"
  content = regex.sub(pattern, _detail_maker, content)
  return content


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
    if "shloka_id" in pattern:
      shloka_id = match.group('shloka_id')
      shloka_id = regex.sub(r"[\.,]$", "", shloka_id)
      shloka_id = f" - {shloka_id}"
    elif pattern not in [patterns.PATTERN_2LINE_SHLOKA_NO_NUM, patterns.PATTERN_BOLDED_QUOTED_SHLOKA]:
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


def shlokas_to_muula_viprastuti_details(content, shloka_processor=lambda x:x, pattern=None, id_position=-1):
  if "विश्वास-प्रस्तुतिः" in content:
    logging.warning("विश्वास-प्रस्तुतिः found. Returning")
    content = regex.sub(r"(?<=/details>|^)\s*([^<]+?)\s*(?=<details|$)", lambda x: shlokas_to_muula_viprastuti_details(content=x.group(0), pattern=pattern, id_position=id_position), content)
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
    if "shloka_id" in pattern:
      shloka_id = match.group('shloka_id')
      shloka_id = regex.sub(r"[\.,]$", "", shloka_id)
      shloka_id = f" - {shloka_id}"
    elif pattern not in [patterns.PATTERN_2LINE_SHLOKA_NO_NUM, patterns.PATTERN_BOLDED_QUOTED_SHLOKA]:
      shloka_id = match.groups()[id_position].strip()
      if shloka_id != "":
        shloka_id = f" - {shloka_id}"
    else:
      shloka_id = ""
    shloka = shloka.replace("**", "")
    shloka = shloka_processor(shloka)
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
      translation = doc_curation.translation.translate(text=subcontent, source_language=source_language, dest_language=dest_language)
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
          translation = doc_curation.translation.translate(text=sentence, source_language=source_language, dest_language=dest_language)
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
          translation = doc_curation.translation.translate(text=detail.content, source_language=source_language, dest_language=dest_language)
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
    translation = doc_curation.translation.translate(text=detail.content, source_language=source_language, dest_language=dest_language)
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