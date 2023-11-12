import textwrap

import regex
import logging
from collections import defaultdict

DEFINITION_PATTERN_SINGLE_LINE = r"\n(\[\^(.+?)\]):(\s*\S[\s\S]+?(?=$|\n\[\^|\n<|\n#|\n\n)"
DEFINITION_PATTERN_MULTI_LINE = r"\n(\[\^(.+?)\]): *\n(   .*|\n)+?(?=$|\n\[\^|\n<|\n#))"
DEFINITION_PATTERN = r"\n(\[\^(.+?)\]):(\s*\S[\s\S]+?(?=$|\n\[\^|\n<|\n#|\n\n)| *\n(   .*|\n)+?(?=$|\n\[\^|\n<|\n#))"
REF_PATTERN = r"\[\^(.+?) *\]"


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
  content = "\n%s\n\n" % content
  content, definitions = extract_definitions(content)
  content = insert_definitions_near_use(content, definitions)
  # Undo initial additions
  content = regex.sub(r"^\n", "", content)
  content = regex.sub(r"\n\n$", "", content)
  return content


def insert_definitions_near_use(content, definitions):
  definitions.reverse()
  for definition in definitions:
    old_content = content
    content = regex.sub(r"(%s[\s\S]+?\n)(\n|</details|#)" % regex.escape(definition.group(1)),
                        r"\g<1>%s\n\g<2>" % definition.group(0), content)
    if old_content == content:
      logging.warning(f"Could not find {definition.group(1)}")
      content += "\n\n" + definition.group(0)
  return content


def extract_definitions(content):
  definitions = list(regex.finditer(DEFINITION_PATTERN, content))
  content = regex.sub(DEFINITION_PATTERN, "", content)
  return content, definitions


def fix_intra_word_footnotes(content, *args, **kwargs):
  content = regex.sub(r"(\[\^[\d-]+?\])([^:\[\s]+)", "\\2\\1", content)
  return content


def fix_plain_footnotes(content, def_pattern="(?<=\n)(\d+)\.?(?= )", def_replacement_pattern=r"[^\1]:", ref_pattern=r"(?<=[^\s\d\^\-,\(\);:])(\d+)(?=\D)"):
  """
  Common def_patterns: (?<=\n)(\d+)\.?(?= ) to r"[^\1]:"
  r"\((\d+)[\. ]*([^\d\)][^\)]+)\) *" to r"\n[^\1]: \2\n"
  
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


def inline_comments_to_footnotes(content, pattern=r"\[([^\^][^\]]+)?\]"):
  definitions_unfiltered = regex.finditer(pattern, content)
  definitions = []
  for definition in definitions_unfiltered:
    if definition not in definitions:
      definitions.append(definition)

  footnotes = {}
  for index, definition in enumerate(definitions):
    footnote = Footnote(id_str=f"{index + 1}", content=definition.group(1))
    footnotes[index] = footnote

  for index, definition in enumerate(definitions):
    footnote = footnotes[index]
    content = content.replace(f"{definition.group(0)}", footnote.get_reference())
  for index, footnote in footnotes.items():
    content += footnote.to_definition()
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


def add_page_id_to_ref_ids(content, page_pattern="[\s\S]+?<dg (\d+)/>"):
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

def make_ids_unique_to_be_fixed(content):
  # TODO - fix this.
  content, definitions = extract_definitions(content=content)
  definitions_map = defaultdict(list)
  for definition in definitions:
    definitions_map[definition.group(2)].append(definition)

  references = list(regex.finditer(REF_PATTERN, content))
  ref_ids = list(set([x.group(1) for x in references]))
  ref_id_count = {id: ref_ids.count(id) for id in ref_ids}

  unmatched_ids = []
  for ref_id, count in ref_id_count.items():
    if count != len(definitions_map[ref_id]):
      unmatched_ids.append(ref_id)
    else:
      for i in range (1, count+1):
        content = regex.sub(fr"\[\^{ref_id}\]", f"[^{ref_id}__{i}]", content, count=1)
        definition = definitions_map[ref_id].pop(0)
        content = f"{content}\n\n[^{definition.group(2)}__{i}]: {definition.group(3)}"

  if len(unmatched_ids) > 0:
    logging.warning(f"Unmatched ids: {unmatched_ids}")
    for ref_id in unmatched_ids:
      content = f"{content}\n\n[//]: # (ALERT!! UNMATCHED FOOTNOTE IDS.)\n\n" + "\n\n".join([definition.group(0) for definition in definitions_map[ref_id]])
  
  return content