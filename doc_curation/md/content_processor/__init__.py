import logging

import regex

from indic_transliteration import sanscript


def make_paras(content):
  lines = content.splitlines(keepends=False)
  lines_out = [""]
  for line in lines:
    line = line.rstrip()
    previous_line = lines_out[-1]
    if line == "":
      lines_out.append(line)
    elif regex.fullmatch(r"^[#>\-\+\*].+",  line):
      if not regex.fullmatch(r"^[#>\-\*].+",  previous_line):
        lines_out.append("")
      lines_out.append(line)
    else:
      if regex.fullmatch(r".+\.",  previous_line):
        lines_out.append("")
        lines_out.append(line)
      else:
        if not regex.fullmatch(r"^[#>\-\*].+[^.]",  previous_line) and previous_line.strip() != "":
          lines_out[-1] = "%s %s" % (previous_line, line)
          lines_out[-1] = lines_out[-1].strip()
        else:
          lines_out.append(line)
  return "\n".join(lines_out)


def transform_footnote_marks(content, transformer):
  content = regex.sub(r"\[\^(.+?)\]", transformer, content)
  return content


def define_footnotes_near_use(content):
  # For correct regex matching.
  content = "\n%s\n\n" % content
  definition_pattern = r"\n(\[\^.+?\]):[\s\S]+?\n(?=[\n\[])"
  definitions = regex.finditer(definition_pattern, content)
  content = regex.sub(definition_pattern, "", content)
  for definition in definitions:
    content = regex.sub(r"%s[\s\S]+?\n\n" % regex.escape(definition.group(1)), r"\g<0>%s\n" % definition.group(0), content)
  # Undo initial additions
  content = regex.sub("^\n", "", content)
  content = regex.sub("\n\n$", "", content)
  return content


def remove_non_content_text(content):
  # For correct regex matching.
  content = "\n%s\n\n" % content
  definition_pattern = r"\n(\[\^.+?\]):[\s\S]+?\n(?=[\n\[])"
  content = regex.sub(definition_pattern, "", content)
  content = regex.sub("\n#.+?\n", "\n", content)
  content = regex.sub("\n> +", "\n", content)
  content = regex.sub("\+\+\+\([\s\S]+?\)\+\+\+", "", content)
  # Undo initial additions
  content = regex.sub("^\n", "", content)
  content = regex.sub("\n\n$", "", content)
  return content


def title_from_text(text, num_words=2, target_title_length=50, title_id=None, script=sanscript.DEVANAGARI):
  text = remove_non_content_text(content=text)
  from doc_curation import text_utils
  title = text_utils.title_from_text(text=text, num_words=num_words, target_title_length=target_title_length, title_id=title_id, script=script)
  return title


def get_comparison_text(text):
  text = sanscript.SCHEMES[sanscript.DEVANAGARI].remove_numerals(in_string=text)
  text = title_from_text(text=text, num_words=40, target_title_length=1000, title_id=None)
  return text.strip()


def devanaagarify(text, source_scheme=sanscript.IAST):
  c = sanscript.transliterate(text, sanscript.IAST, sanscript.DEVANAGARI)
  c = sanscript.SCHEMES[sanscript.DEVANAGARI].dot_for_numeric_ids(c)
  c = c.replace(":", "-")
  return c


def fix_bad_anunaasikas(text):
  # Beware of निम्न नृम्ण etc..
  replacements = {r"म्([च-ञ])": r"ञ्\1", r"म्([क-ङ])": r"ङ्\1", r"म्([ट-ढ])": r"ण्\1", r"म्([त-ध])": r"न्\1"}
  c = text
  for pattern, replacement in replacements.items():
    c = regex.sub(pattern, replacement, c)
  return c


def numerify_shloka_numbering(text, encoding="कखगघङचछजझञ"):
  def transformer(match):
    return "॥%s.%d॥" % (match.group(1), encoding.index(match.group(2)) + 1)
  c = regex.sub("॥ *(\d+)[ (]*([%s])[ )]*॥" % encoding, transformer, text)
  return c


def fix_google_ocr(text):
  text = text.replace("^-+", "")
  text = text.replace("\n", "\n\n")
  return text