import logging
from bs4 import BeautifulSoup, NavigableString

import regex

from indic_transliteration import sanscript, aksharamukha_helper


def transliterate(text, source_script=sanscript.IAST, dest_script=sanscript.DEVANAGARI, aksharamukha_pre_options=[], aksharamukha_post_options=[], *args, **kwargs):
  if source_script.lower().startswith("tamil"):
    if source_script.lower() == sanscript.TAMIL_SUB:
      text = sanscript.SCHEMES[sanscript.TAMIL].transliterate_subscripted(text=text, _to=dest_script)
    dest_script = dest_script.capitalize()
    c = aksharamukha_helper.transliterate_tamil(text=text, dest_script=dest_script)
  else:
    text = regex.sub(r"(?<=\+\+\+\()(.+?)(?=\)\+\+\+)", r"{{\1}}", text)
    # Quotes should not be mistaken for transliteration togglers. 
    text = regex.sub("(?<=\n|^)>", r"≫", text)

    if sanscript.SCHEMES[source_script].is_roman:
      text = regex.sub("(?<=<details><summary>)(.*Eng.*)</summary>([\s\S]+?)(?=</details>)", r"{{\1}}</summary>{{\2}}", text)
    c = sanscript.transliterate(text, source_script, dest_script, suspend_on=set(("<", "{{")), suspend_off=set((">", "}}")))
    c = sanscript.SCHEMES[dest_script].dot_for_numeric_ids(c)
    c = c.replace("{{", "").replace("}}", "")
    c = c.replace("≫", ">")
  if dest_script == sanscript.DEVANAGARI:
    c = regex.sub("(?<=[ँ-ॿ]):", "-", c)
    c = regex.sub(r"\\?[\|।] *\\?[\|।]", "॥", c)
    c = regex.sub(r"\\?[\|।]", "।", c)
  return c


def replace_texts(md_file, patterns, replacement, dry_run=False):
  logging.info("Processing %s", md_file.file_path)
  [metadata, content] = md_file.read()
  for text_pattern in patterns:
    content = regex.sub(text_pattern, replacement, content)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


def _make_content_from_soup(soup):
  new_content = ""
  for x in soup.select_one("body").contents:
    if isinstance(x, NavigableString) and "<" in x:
      x = str(x).replace("<", "&lt;")
    new_content = new_content + str(x)
  new_content = new_content.replace("&amp;", "&").replace("open=\"\"", "open")
  return new_content

def _soup_from_content(content, metadata=None):
  strange_lt_sign = regex.search("<(?! *[/dsiahfu])", content)
  if strange_lt_sign is not None:
    if metadata is None:
      metadata = {}
      metadata['_file_path'] = "UNK"
    logging.warning(f"Not confident about content in {metadata['_file_path']} at {strange_lt_sign.start()}, before {content[strange_lt_sign.start():strange_lt_sign.start()+16]} - returning")
    return None
  soup = BeautifulSoup(f"<body>{content}</body>", features="html.parser")
  return soup


def fix_special_tags(content):
  # Underline
  ## Used for Google docs to markdown plugin outputs.
  content = regex.sub(r"<span style=\"text-decoration:underline;\">([\s\S]+?)</span>", r"<u>\1</u>", content)
  content = regex.sub(r'<p style="text-align: right">([\s\S]+?)</p>', r"\1", content)
  content = regex.sub(r'<strong>([\s\S]+?)</strong>', r"**\1**", content)
  
  return content


def fix_bold_italics(content):
  def _fix_markup(content, toggler_pattern, uniform_markup):
    content = regex.sub(toggler_pattern, "≼", content)
    content = list(content)
    markup_status = False
    for i in range(0, len(content)):
      if content[i] in ["≼"]:
        if markup_status == False:
          markup_status = True
        else:
          markup_status = False
          content[i] = '≽'
    content = "".join(content)
    content = regex.sub(r"(\s*)≽", rf"{uniform_markup}\1", content)
    content = regex.sub(r"≼(\s*)", rf"\1{uniform_markup}", content)
    return content
  content = _fix_markup(content=content, toggler_pattern="\*\*|__", uniform_markup="**")
  
  # Fix lists and italics
  content = regex.sub(r"(?<=^|\n)\* ", "- ", content)
  content = _fix_markup(content=content, toggler_pattern="r(?<=[^\*_]|^)(\*|_)(?=[^\*_]|$)", uniform_markup="_")
  return content


def get_quasi_section_int_map(content, pattern):
  """
  
  :param content: 
  :param pattern: Pattern to find with an int id. Common patterns:
      (?<=\n|^)([\d०-९೦-೯]+).+\n
  :return: 
  """
  source_matches = list(regex.finditer(pattern, content))
  source_match_map = {}
  for source_match in source_matches:
    index_str = sanscript.transliterate(source_match.group(1), _to=sanscript.IAST)
    if index_str.isnumeric():
      source_match_map[int(index_str)] = source_match
    else:
      logging.warning("Could not get index for: %s", source_match.group())
  logging.info(f"Got {len(source_match_map)} source matches ")
  return source_match_map
