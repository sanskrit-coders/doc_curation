import regex
from indic_transliteration import sanscript


def remove_fake_linebreaks(text):
  text = regex.sub(r"(?<=\n|^)([^#-*!<\s][^\n]+\S)\n(?=[^#-*\s>!<])", r"\1 ", text)
  text = regex.sub(r"(?<=\n|^)(>[^\n]+\S)\n(?=>)", r"\1 ", text)
  return text


def markdownify_newlines(text):
  text = regex.sub(r"(?<=\S)\n(?=\S)", r"  \n", text)
  return text


def make_md_verse_lines(text):
  """
  
  खगकूजितजृम्भणैः शनैः तनुजाड्यं जहतीव तन्द्रिलाः ।\n\n\nनगरोपवनस्थपादपाः प्रथमार्कारुणरश्मिचुम्बिताः ॥ १ ॥ 
  to 
  खगकूजितजृम्भणैः शनैः तनुजाड्यं जहतीव तन्द्रिलाः ।  \nनगरोपवनस्थपादपाः प्रथमार्कारुणरश्मिचुम्बिताः ॥ १ ॥
  
  :param text: 
  :return: 
  """
  text = regex.sub(r"(?<=\n|^)([^#-*!<\[>\s][^\n]+\S) *\n+(?=[^#-*\s>!<\[>])", r"\1  \n", text)
  text = regex.sub(r"॥ *(?=\n|$)", r"॥\n", text)
  text = regex.sub("\n\n\n+", "\n\n", text) ## Be careful not to mess with two new lines after detail tag opening.
  return text


def make_lines_end_with_pattern(content, full_line_pattern):
  lines = content.split("\n")
  lines_out = []
  last_line_complete = True
  for line in lines:
    line = line.rstrip()
    if line == "":
      if last_line_complete:
        lines_out.append(line)
        continue
      else:
        continue
    if line.startswith("#") or regex.match(" *<", line):
      last_line_complete = True
      current_line_complete = True
    current_line_complete = regex.fullmatch(full_line_pattern, line)
    if not last_line_complete:
      lines_out[-1] = f"{lines_out[-1]} {line}"
    else:
      lines_out.append(line)
    last_line_complete = current_line_complete
  return "  \n".join(lines_out)


def rehyphenate_sanskrit_line_endings(content, script=sanscript.DEVANAGARI):
  text = sanscript.transliterate(content, _from=script, _to=sanscript.DEVANAGARI)
  dev_scheme = sanscript.SCHEMES[sanscript.DEVANAGARI]
  def nn_replacer(match):
    letters = dev_scheme.split_vyanjanas_and_svaras(match.group(2))
    return "न्" + letters[0] + match.group(1) + dev_scheme.join_strings(letters[1:])
  text = regex.sub("-( *\n *)न्(न.)", nn_replacer, text)
  text = regex.sub("-( *\n *)स्(?=[तथस])", r"स्\1", text)
  text = regex.sub("-( *\n *)श्(?=[चछश])", r"श्\1", text)
  text = regex.sub("-( *\n *)ष्(?=[टठष])", r"ष्\1", text)
  text = regex.sub("(?<=[ि-ौ])-( *\n *)र्(?=[गघङजझञदधनडढणबभमयलवह])", r"र्\1", text)
  def generic_replacer(match):
    letters = dev_scheme.split_vyanjanas_and_svaras(match.group(2))
    return letters[0] + match.group(1) + dev_scheme.join_strings(letters[1:])
  text = regex.sub("-( *\n *)(म.)", generic_replacer, text)
  text = regex.sub("-( *\n *)(र[ि-ौ]?)", generic_replacer, text)
  return sanscript.transliterate(text, _from=sanscript.DEVANAGARI, _to=script)


def make_paras(content, *args, **kwargs):
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
