import logging
from bs4 import BeautifulSoup, NavigableString

import regex

from indic_transliteration import sanscript


def transliterate(text, source_script=sanscript.IAST, dest_script=sanscript.DEVANAGARI, aksharamukha_pre_options=[], aksharamukha_post_options=[]):
  if source_script.lower() == "tamil":
    source_script = source_script.capitalize()
    dest_script = dest_script.capitalize()
    aksharamukha_pre_options = ["TamilTranscribe"]
  if len(aksharamukha_pre_options) + len(aksharamukha_post_options) > 0:
    import aksharamukha
    c = aksharamukha.transliterate.process(src=source_script, tgt=dest_script, txt=text, nativize = True, pre_options = aksharamukha_pre_options, post_options = aksharamukha_post_options)
  else:
    text = text.replace("+++(", "<<").replace(")+++", ">>")
    c = sanscript.transliterate(text, source_script, dest_script, suspend_on=set(("<", "{{")), suspend_off=set((">", "}}")))
    c = sanscript.SCHEMES[dest_script].dot_for_numeric_ids(c)
    c = c.replace("<<", "+++(").replace(">>", ")+++")
  if dest_script == sanscript.DEVANAGARI:
    c = c.replace(":", "-")
    c = c.replace("||", "॥")
    c = c.replace("|", "।")
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

def _soup_from_content(content, metadata):
  strange_lt_sign = regex.search("<(?! *[/dsiahfu])", content)
  if strange_lt_sign is not None:
    logging.warning(f"Not confident about content in {metadata['_file_path']} at {strange_lt_sign.start()}, before {content[strange_lt_sign.start():strange_lt_sign.start()+16]} - returning")
    return None
  soup = BeautifulSoup(f"<body>{content}</body>", features="html.parser")
  return soup
