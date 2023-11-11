import regex
from indic_transliteration import sanscript


def remove_fake_linebreaks(content, *args, **kwargs):
  """ Remove linebreaks which are treated as space within a paragraph when markdown is converted to html
  
  :param content: 
  :param args: 
  :param kwargs: 
  :return: 
  """
  # 
  content = regex.sub(r"(?<=\n|^)([^#\-*!<\s][^\n]+\S)\n(?=[^#\-*\s>!<])", r"\1 ", content)
  # Join markdown quotation lines
  content = regex.sub(r"(?<=\n|^)(>[^\n]+\S)\n(?=>)", r"\1 ", content)
  return content


def fix_indented_quotations(content, *args, **kwargs):
  from doc_curation.md.content_processor import footnote_helper
  # Footnote definitions use indentations - so better to extract those beforehand.
  content, definitions = footnote_helper.extract_definitions(content=content)
  content = regex.sub(r"(?<=\n|^)[ \t]+", r"> ", content)
  # Join the quotation lines
  content = regex.sub(r"(?<=\n|^)(>[^\n]+)\s*\n\n+(?=>)", r"\1  \n", content)
  content = footnote_helper.insert_definitions_near_use(content=content, definitions=definitions)
  return content


def markdownify_newlines(text):
  text = regex.sub(r"(?<=\S)\n(?=\S)", r"  \n", text)
  return text


def dehyphenate_interline_words(text):
  text = regex.sub("(ाह)-", r"\1 - ", text)
  text = regex.sub(r"(?<=[ँ-९])\- (?=[क-९])", "", text)
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
  
  # An empty line separating each verse. (But don't mess with quotations)
  text = regex.sub(r"॥ *(?=\n[^>]|$)", r"॥\n", text)
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


def dehyphenate_sanskrit_line_endings(content, script=sanscript.DEVANAGARI):
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
      if regex.fullmatch(r".+[\.।॥]",  previous_line):
        lines_out.append("")
        lines_out.append(line)
      else:
        if not regex.fullmatch(r"^[#>\-\*].+",  previous_line) and not regex.fullmatch(r".+[.।॥] *", previous_line) and previous_line.strip() != "":
          lines_out[-1] = "%s %s" % (previous_line, line)
          lines_out[-1] = lines_out[-1].strip()
        else:
          lines_out.append(line)
  return "\n".join(lines_out)


def fix_markup(text):
  text = text.replace("** **", " ")
  text = text.replace("* *", " ")
  text = regex.sub(r"\*\*([^*\n]+?) *\*\*", r"**\1** ", text)
  return text



def empty_line_around_quotes(content, after_too=False):
  """
  
  :param content: 
  :param after_too: Boolean. Valid markdown quote para lines (non-initial) may not start with >.
  :return: 
  """
  content = regex.sub("((\n|^)[^^>\n].+\n)>", "\\1\n\n>", content)
  if after_too:
    content = regex.sub("(>.+\n)(?=[^^>\n])", "\\1\n\n", content)
  return content
