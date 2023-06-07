import regex


DEFINITION_PATTERN = r"\n(\[\^.+?\]):[\s\S]+?(?=$|\n\[\^)"


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
    content = regex.sub(r"(%s[\s\S]+?\n)(\n|</details)" % regex.escape(definition.group(1)),
                        r"\g<1>%s\n\g<2>" % definition.group(0), content)
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
  content = regex.sub(def_pattern, def_replacement_pattern, content)
  content = regex.sub(ref_pattern, r"[^\1]", content)
  return content

def comments_to_footnotes(content):
  definitions_unfiltered = [x.group(1) for x in regex.finditer(r"\+\+\+\(([\s\S]+?)\)\+\+\+", content)]
  definitions = []
  for definition in definitions_unfiltered:
    if definition not in definitions:
      definitions.append(definition)

  for index, definition in enumerate(definitions):
    content = content.replace(f"+++({definition})+++", f"[^{index+ 1}]")
  for index, definition in enumerate(definitions):
    content += f"\n\n[^{index + 1}]: {definition}"
  return content