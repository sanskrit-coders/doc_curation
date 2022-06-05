import logging
from bs4 import BeautifulSoup, NavigableString

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


def remove_non_content_text(content, remove_parenthized_text=True):
  # For correct regex matching.
  content = "\n%s\n\n" % content
  from doc_curation.md.content_processor import patterns
  # remove footnote definitions
  content = regex.sub(patterns.FOOTNOTE_DEFINITION, "", content)
  # Remove footnote markers
  content = regex.sub(r"\[\^.+?\]", "", content)
  # Remove section titles
  content = regex.sub(r"\n#.+?\n", "\n", content)
  # Remove quote markers
  content = regex.sub(r"\n> +", "\n", content)
  # Remove js comments
  content = regex.sub(patterns.JS_COMMENTS, "", content)
  if remove_parenthized_text:
    # Remove paranthesized text
    content = regex.sub(r"\(.+?\)", "", content)
  # Remove final digits
  content = regex.sub(r"[\d०-९]+\s*$", "", content)

  # Undo initial additions
  content = regex.sub(r"^\n", "", content)
  content = regex.sub(r"\n\n$", "", content)
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


def transliterate(text, source_script=sanscript.IAST, dest_script=sanscript.DEVANAGARI, aksharamukha_pre_options=[], aksharamukha_post_options=[]):
  if source_script.lower() == "tamil":
    source_script = source_script.capitalize()
    dest_script = dest_script.capitalize()
    aksharamukha_pre_options = ["TamilTranscribe"]
  if len(aksharamukha_pre_options) + len(aksharamukha_post_options) > 0:
    import aksharamukha
    c = aksharamukha.transliterate.process(src=source_script, tgt=dest_script, txt=text, nativize = True, pre_options = aksharamukha_pre_options, post_options = aksharamukha_post_options)
  else:
    c = sanscript.transliterate(text, source_script, dest_script)
    c = sanscript.SCHEMES[dest_script].dot_for_numeric_ids(c)
  if dest_script == sanscript.DEVANAGARI:
    c = c.replace(":", "-")
  return c


def fix_bad_anunaasikas(text):
  # Beware of निम्न नृम्ण etc..
  replacements = {r"म्([च-ञ])": r"ञ्\1", r"म्([क-ङ])": r"ङ्\1", r"म्([ट-ढ])": r"ण्\1", r"म्([त-ध])": r"न्\1"}
  c = text
  for pattern, replacement in replacements.items():
    c = regex.sub(pattern, replacement, c)
  return c


def set_audio_caption_from_filename(text, prefix):
  """
  
  Example: replace <div class="audioEmbed"  src="https://archive.org/download/tiruppAvai_vibhA/30__Vangakkadal_kadainda__suruTTi.mp3" caption=""></div>
  with 
  <div class="audioEmbed"  src="https://archive.org/download/tiruppAvai_vibhA/30__Vangakkadal_kadainda__suruTTi.mp3" caption="vibhA - 30 - Vangakkadal kadainda - suruTTi"></div>

  :param text: 
  :param prefix: 
  :return: 
  """
  def transformer(match):
    return "%s.mp3\" caption=\"%s - %s\"" % (match.group(1), prefix, match.group(1).replace("__", " - ").replace("_", " "))

  c = regex.sub(r"(?<=audioEmbed.+/)([^/]+?).mp3\" +caption=\".*?\"", transformer, text)
  
  return c


def replace_texts(md_file, patterns, replacement, dry_run=False):
  logging.info("Processing %s", md_file.file_path)
  [metadata, content] = md_file.read()
  for text_pattern in patterns:
    content = regex.sub(text_pattern, replacement, content)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


def numerify_shloka_numbering(text, encoding="कखगघङचछजझञ"):
  def transformer(match):
    return "॥%s.%d॥" % (match.group(1), encoding.index(match.group(2)) + 1)
  c = regex.sub(r"॥ *(\d+)[ (]*([%s])[ )]*॥" % encoding, transformer, text)
  return c


def fix_google_ocr(text):
  text = text.replace("^-+", "")
  text = text.replace("\n", "\n\n")
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


def _make_content_from_soup(soup):
  new_content = ""
  for x in soup.select_one("body").contents:
    if isinstance(x, NavigableString) and "<" in x:
      x = str(x).replace("<", "&lt;")
    new_content = new_content + str(x)
  new_content = new_content.replace("&amp;", "&").replace("open=\"\"", "open")
  return new_content

def _soup_from_content(content, metadata):
  strange_lt_sign = regex.search("<(?! *[/dsiahfu])", content)
  if strange_lt_sign is not None:
    logging.warning(f"Not confident about content in {metadata['_file_path']} at {strange_lt_sign.start()}, before {content[strange_lt_sign.start():strange_lt_sign.start()+16]} - returning")
    return None
  soup = BeautifulSoup(f"<body>{content}</body>", features="html.parser")
  return soup

