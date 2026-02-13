import textwrap

import regex
import logging
from collections import defaultdict

REF_PATTERN = r"\[\^([^\]\n]+?) *\]"
DEF_ENDING = r"(?=$|\n\[\^|\n<|\n#|\n\n)"
DEFINITION_PATTERN_SINGLE_LINE = rf"(?<=\n)({REF_PATTERN}):\s*(\S[\s\S]+?){DEF_ENDING}"
DEFINITION_PATTERN_MULTI_LINE = rf"(?<=\n)({REF_PATTERN}): *\n((   .*|\n)+?){DEF_ENDING}"


for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


class Footnote(object):
  def __init__(self, id_str, content):
    self.id_str = id_str
    self.content = content.strip()

  def to_single_line_definition(self):
    return f"\n{self.get_reference()}: {self.content}\n"

  def to_multi_line_definition(self):
    content = textwrap.indent(self.content.strip(), prefix="    ")
    return f"\n{self.get_reference()}:\n\n{content}\n\n"

  def to_definition(self):
    if "\n" in self.content:
      return self.to_multi_line_definition()
    else:
      return self.to_single_line_definition()

  def get_reference(self):
    return f"[^{self.id_str}]"


def transform_footnote_marks(content, transformer):
  content = regex.sub(r"\[\^(.+?)\]", transformer, content)
  return content


def define_footnotes_near_use(content, *args, **kwargs):
  # For correct regex matching.
  content = "\n%s\n\n" % content.strip()
  content, definitions = extract_definitions(content)
  content = insert_definitions_near_use(content, definitions)
  content = make_ids_unique_per_def(content)
  # Undo initial additions
  content = regex.sub(r"^\n", "", content)
  content = regex.sub(r"\n\n+$", "", content)
  return content

def insert_definitions_near_use(content, definitions):
  definitions.reverse()
  for definition in definitions:
    old_content = content
    ref_para_pattern = rf"({regex.escape(definition.group(1))}[\s\S]*?\n)(\n|</details|#)"
    try:
      content = regex.sub(ref_para_pattern,
                          rf"\g<1>\n{definition.group(0)}\n\g<2>", content, count=1, timeout=1)
    except TimeoutError:
      logging.warning(f"Regex sub timed out trying to find {definition.group(1)}")
      pass
    if old_content == content:
      logging.warning(f"Could not find {definition.group(1)} with {ref_para_pattern}")
      content += "\n\n" + definition.group(0)
  content = regex.sub("\n\n\n+", "\n\n", content)
  return content


def extract_definitions(content):
  seen_matches = set()
  definitions = []
  # Extracts definitions matching pattern; removes matches from content
  def _process_pattern(pattern, content):
    definitions.extend([
      match
      for match in regex.finditer(pattern, content)
      if match.group(0) not in seen_matches and not seen_matches.add(match.group(0))
    ])
    content = regex.sub(pattern, "", content)
    return content
  content = _process_pattern(DEFINITION_PATTERN_SINGLE_LINE, content=content)
  content = _process_pattern(DEFINITION_PATTERN_MULTI_LINE, content=content)
  return content, definitions


def transform_definitions(content, transformer, *args, **kwargs):
  content = regex.sub(DEFINITION_PATTERN_SINGLE_LINE, transformer, content)
  return content


def to_latex_footnotes(content):
  content, definitions = extract_definitions(content=content)
  for definition in definitions:
    content = content.replace(definition.group(1), f"\\footnote{{{definition.group(2)}}}")
  return content


def fix_intra_word_footnotes(content, *args, **kwargs):
  content = regex.sub(r"(\[\^[\d-]+?\])([^:\[\s]+)", "\\2\\1", content)
  return content

PLAIN_FN_REF_GUTEN = r"\[\\\[(\d+)\\\]\]\(#Foot.+?\)"
PLAIN_FN_DEF_GUTEN = r"\[\\\[(\d+)\\\]\]\(#FN.+?\)"
PLAIN_FN_REF_2SQ = r"\[\\?\[(\d+)\\?\]\]\(#.+?\)"
PLAIN_FN_DEF_2SQ = r"(?<=\n)\[\\?\[(\d+)\\?\]\]\(#.+?\)"

def fix_plain_footnotes(content, def_pattern="(?<=\n)(\d+)\.?(?= )", def_replacement_pattern=r"[^\1]:", ref_pattern=r"(?<=[^\s\d\^\-,\(\);:])(\d+)(?=\D)"):
  """
  Common def_patterns: (?<=\n)(\d+)\.?(?= ) to r"[^\1]:"
  r"\((\d+)[\. ]*([^\d\)][^\)]+)\) *" to r"\n[^\1]: \2\n"
  Also see variables above.
  
  ref_patterns: r"(?<=[^\s\d\^\-,\(\);:])(\d+)(?=\D)" to r"[^\1]"
  r"\((\d+)\)"  
  
  
  :param content: 
  :param def_pattern: 
  :return: 
  """
  if def_pattern is not None:
    logging.info(f"Replacing definitions of pattern {def_pattern}")
    content = regex.sub(def_pattern, def_replacement_pattern, content)
  if ref_pattern is not None:
    logging.info(f"Replacing references of pattern {ref_pattern}")
    content = regex.sub(ref_pattern, r"[^\1]", content)
  return content


def to_plain_footnotes(content):
  content = regex.sub(r"\[\^", "[#", content)
  return content


def get_max_index(content):
  indexes_old = [0]  # Initialize the list within the function
  indexes_old.extend(int(x.group(1)) for x in regex.finditer(REF_PATTERN, content) if x.group(1).isdigit())
  logging.debug(f"{len(indexes_old) - 1} footnotes found.")
  return max(indexes_old)


def inline_comments_to_footnotes(content, pattern=r"\[([^\^][^\]]+)?\]"):
  definitions = list(regex.finditer(pattern, content))
  if len(definitions) == 0:
    logging.info("No footnote found.")
    return content
  footnotes = {}
  max_index = get_max_index(content)
  for index, definition in enumerate(definitions):
    footnote = Footnote(id_str=f"{max_index + index + 1}", content=definition.group(1))
    footnotes[index] = footnote

  # Rather than content.replace(f"{definition.group(0)}", footnote.get_reference()),  
  # we do the below to avoid unwarranted replacements due to not caring for lookahead or lookbefore patterns. 
  result = ""
  last_match_end = 0
  for index, definition in enumerate(definitions):
    footnote = footnotes[index]
    result += content[last_match_end:definition.start()]
    result += footnote.get_reference()
    last_match_end = definition.end()
  result += content[last_match_end:]
  content = result

  for index, footnote in footnotes.items():
    content += footnote.to_definition()
  logging.info(f"{len(definitions)} footnotes found.")
  return content


def comments_to_footnotes(content):
  content = inline_comments_to_footnotes(content=content, pattern=r"\+\+\+\(([\s\S]+?)\)\+\+\+")
  return content


def split_clean_definition_group(content, def_group_pattern=r"(?<=\n|^)\s*\[\^", def_pattern=r"(\[^.+?\])[\.\s:]*", def_replacement_pattern=r"\n\n\1: "):
  # Handle lines like  
  # [^1]. इह च अ । [^2] कैङ्कर्य - आ । [^3] कैङ्कर्य - आ । [^4] नितराम् - अ ।
  # TODO: complete
  
  content = regex.sub(def_group_pattern, lambda x: fix_plain_footnotes(content=x.group(0), def_pattern=def_pattern, def_replacement_pattern=def_replacement_pattern, ref_pattern=None), content)

  return content


def fix_ambuda_footnote_definition_groups(content):
  content = split_clean_definition_group(content, def_group_pattern=r"(?<=\n|^)\s*\[\^.+?(?=\n|$)", def_pattern=r"(\[\^.+?\])[\.\s:]*", def_replacement_pattern=r"\n\n\1: ")
  return content


def insert_page_breaks(content):
  DEFINITION_GROUP_PATTERN = r"\n(\[\^(.+?)\]:.+)\n*(\[\^(.+?)\]:.+|\n|  .+)*(?=\n*[^\[ ])"
  definition_groups = list(regex.finditer(DEFINITION_GROUP_PATTERN, content))
  for index, def_group in enumerate(definition_groups):
    content = regex.sub(regex.escape(def_group.group(0)), f"{def_group.group(0)}\n\n<dg {index+1}/>\n\n", content)
  content = regex.sub("\n\n+", "\n\n", content)
  return content


def add_page_id_to_ref_ids(content, page_pattern=r"[\s\S]+?<dg (\d+)/>", *args, **kwargs):
  """
  
  :param content: 
  :param page_pattern: Other common patterns r"[\s\S]+?\[\[([\d०-९]+)\]\]"
  :return: 
  """
  pages = list(regex.finditer(page_pattern, content))
  if len(pages) == 0:
    content = insert_page_breaks(content)
    pages = list(regex.finditer(page_pattern, content))

  for page in pages:
    page_id = page.group(1)
    page_text = page.group(0)
    page_text_fixed = regex.sub(REF_PATTERN, fr"[^\1_pg{page_id}]", page_text)
    content = regex.sub(regex.escape(page_text), page_text_fixed, content)
  return content


def make_ids_unique_per_def(content):
  content, definitions = extract_definitions(content)
  def_map = {}
  filtered_defs = []
  for definition in definitions:
    # Replaces duplicate definitions; accumulates unique definitions
    if definition.group(3).strip() in def_map:
      content = content.replace(definition.group(1), def_map[definition.group(3).strip()])
    else:
      filtered_defs.append(definition)
      def_map[definition.group(3).strip()] = definition.group(1)
  content = insert_definitions_near_use(content=content, definitions=filtered_defs)
  return content


def add_for_links(content, prefix="lnk", *args, **kwargs):
  # Find markdown links, add footnotes for each, so that they can be read when printed.
  link_pattern = r"\[([^\]]+)\]\(([^\)]+)\)"
  links = list(regex.finditer(link_pattern, content))

  footnotes = {}
  for index, link in enumerate(links):
    text = link.group(1)
    url = link.group(2)
    footnote = Footnote(id_str=f"{prefix}_{index + 1}", content=url)
    footnotes[index] = footnote

  result = ""
  last_match_end = 0
  for index, link in enumerate(links):
    footnote = footnotes[index]
    result += content[last_match_end:link.start()]
    result += f"{link.group(0)}{footnote.get_reference()}"
    last_match_end = link.end()
  result += content[last_match_end:]
  content = result

  for index, footnote in footnotes.items():
    content += footnote.to_definition()

  return content 
