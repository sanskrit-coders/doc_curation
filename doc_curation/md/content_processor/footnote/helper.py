import textwrap

import regex
import logging

REF_PATTERN = r"\[\^([^\]\n]+?) *\]"
# One definition block: `[^id]:` first line, its lazy continuation lines, then
# further blank-separated paragraphs which must be indented (Goldmark footnote
# semantics). Matches single-line, pure multi-line and hybrid definitions
# whole, so multi-paragraph notes are never split from their continuations.
# Groups: 1=reference ([^id]), 2=id, 3=content.
DEFINITION_PATTERN = (
  r"(?m)^(?P<ref>\[\^(?P<id>[^\]\n]+?) *\]):"
  r"(?P<content>[^\n]*"
  r"(?:\n(?![ \t]*\n)(?!\[\^)(?!#)(?!<)[^\n]*)*"
  r"(?:(?:\n[ \t]*)+\n(?: {3,}|\t)[^\n]*"
  r"(?:\n(?![ \t]*\n)(?!\[\^)(?!#)(?!<)[^\n]*)*)*)"
)


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
      def repl(match):
        return f"{match.group(1)}\n{definition.group(0)}\n{match.group(2)}"  
      content = regex.sub(ref_para_pattern, repl, content, count=1, timeout=1)

    except TimeoutError:
      logging.warning(f"Regex sub timed out trying to find {definition.group(1)}")
      pass
    if old_content == content:
      logging.warning(f"Could not find {definition.group(1)} with {ref_para_pattern}")
      content += "\n\n" + definition.group(0)
  content = regex.sub("\n\n\n+", "\n\n", content)
  return content


def extract_definitions(content):
  # Single pass with the block pattern: each definition (however many
  # paragraphs) is one match. Identical texts are still deduplicated.
  seen_matches = set()
  definitions = []
  for match in regex.finditer(DEFINITION_PATTERN, content):
    if match.group(0) not in seen_matches:
      seen_matches.add(match.group(0))
      definitions.append(match)
  content = regex.sub(DEFINITION_PATTERN, "", content)
  return content, definitions


def transform_definitions(content, transformer, *args, **kwargs):
  content = regex.sub(DEFINITION_PATTERN, transformer, content)
  return content


def to_latex_footnotes(content):
  content, definitions = extract_definitions(content=content)
  for definition in definitions:
    content = content.replace(definition.group(1), f"\\footnote{{{definition.group(3).strip()}}}")
  return content


def fix_intra_word_footnotes(content, *args, **kwargs):
  content = regex.sub(r"(\[\^[\d-]+?\])([^:\[\s]+)", "\\2\\1", content)
  return content

PLAIN_FN_REF_GUTEN = r"\[\\\[(\d+)\\\]\]\(#Foot.+?\)"
PLAIN_FN_DEF_GUTEN = r"\[\\\[(\d+)\\\]\]\(#FN.+?\)"
PLAIN_FN_REF_2SQ = r"\[\\?\[(\d+)\\?\]\]\(#.+?\)"
PLAIN_FN_DEF_2SQ = r"(?<=\n)\[\\?\[(\d+)\\?\]\]\(#.+?\)"

def fix_plain_footnotes(content, def_pattern=r"(?<=\n)(\d+)\.?(?= )", def_replacement_pattern=r"[^\1]:", ref_pattern=r"(?<=[^\s\d\^\-,\(\);:])(\d+)(?=\D)"):
  """
  
  
  :param content: 
  :param def_pattern: 
  :return: 
  """
  # ref_patterns: r"(?<=[^\s\d\^\-,\(\);:])(\d+)(?=\D)" to r"[^\1]"
  #   r"\((\d+)\)"  
  #   
  # Common def_patterns: r"(?<=\n)(\d+)\.?(?= )" to r"[^\1]:"
  #   r"\((\d+)[\. ]*([^\d\)][^\)]+)\) *" to r"\n[^\1]: \2\n"
  #   Also see variables above.

  if def_pattern is not None:
    logging.info(f"Replacing definitions of pattern {def_pattern}")
    content = regex.sub(def_pattern, def_replacement_pattern, content)
  if ref_pattern is not None:
    logging.info(f"Replacing references of pattern {ref_pattern}")
    content = regex.sub(ref_pattern, r"[^\1]", content)
  return content


def to_plain_footnotes(content):
  content = regex.sub(r"\[\^", "[#", content)
  # [label]: URL "optional title" is a markdown link reference definition. Avoid that confusion.
  content = regex.sub(r"(?<=\n)\[([^\]]+)\]:", r"- \1 : ", content)
  return content


import re
import html


def fix_sup_footnotes(content: str, *args, **kwargs) -> str:
  """
  Convert pymupdf4llm-style HTML/Markdown hybrid footnotes
  into standard Markdown footnotes.
  """

  # Decode &lt;sup&gt; etc.
  content = html.unescape(content)

  # <sup>137</sup> -> [^137]
  content = re.sub(
    r"<sup>\s*(\d+)\s*</sup>",
    r"[^\1]",
    content,
    flags=re.I,
  )

  # <em>foo</em> -> *foo*
  content = re.sub(
    r"<em[^>]*>(.*?)</em>",
    r"*\1*",
    content,
    flags=re.I | re.S,
  )

  lines = content.splitlines()

  footnotes = []
  body = []

  i = 0
  while i < len(lines):
    line = lines[i]

    m = re.match(r"^\s*>\s*(\d+)\s+(.*)$", line)

    if not m:
      body.append(line)
      i += 1
      continue

    num = m.group(1)
    content = [m.group(2).strip()]

    i += 1

    while i < len(lines):
      nxt = lines[i]

      if re.match(r"^\s*>\s*\d+\s+", nxt):
        break

      if (
          nxt.strip()
          and not re.fullmatch(r"\d+", nxt.strip())
      ):
        content.append(nxt.strip())

      i += 1

    footnotes.append(
      f"[^{num}]: {' '.join(content)}"
    )

  result = "\n".join(body)

  # Remove standalone page numbers
  result = re.sub(
    r"\n\s*\d{1,4}\s*\n",
    "\n",
    result,
  )

  if footnotes:
    result += "\n\n---\n\n" + "\n\n".join(footnotes)

  return result


def fix_footnotes_llm(content):
  prompt = "Convert footnotes to markdown format"
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
  :param page_pattern: 
  :return: 
  """
  # Other common patterns r"[\s\S]+?\[\[([\d०-९]+)\]\]"
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
    result += f"{link.group(0)} {footnote.get_reference()}"
    last_match_end = link.end()
  result += content[last_match_end:]
  content = result

  for index, footnote in footnotes.items():
    content += footnote.to_definition()

  return content 
