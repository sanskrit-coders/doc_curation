import regex


def transform_footnote_marks(content, transformer):
  content = regex.sub(r"\[\^(.+?)\]", transformer, content)
  return content


def define_footnotes_near_use(content, *args, **kwargs):
  # For correct regex matching.
  content = "\n%s\n\n" % content
  definition_pattern = r"\n(\[\^.+?\]):[\s\S]+?(?=$|\n\[\^)"
  definitions = list(regex.finditer(definition_pattern, content))
  definitions.reverse()
  content = regex.sub(definition_pattern, "", content)
  for definition in definitions:
    content = regex.sub(r"(%s[\s\S]+?\n)(\n|</details)" % regex.escape(definition.group(1)), r"\g<1>%s\n\g<2>" % definition.group(0), content)
  # Undo initial additions
  content = regex.sub(r"^\n", "", content)
  content = regex.sub(r"\n\n$", "", content)
  return content


def fix_plain_footnotes(text, definiton_pattern="(?<=\n)(\d+)\.?(?= )"):
  text = regex.sub(definiton_pattern, r"[^\1]:", text)
  text = regex.sub("r(?<=[^\s\d\^\-,\(\);:])(\d+)(?=\D)", r"[^\1]", text)
  return text
