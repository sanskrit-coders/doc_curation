import logging

import regex

from doc_curation.scraping.html import souper
from indic_transliteration import sanscript


def dump_item(item_url, outfile_path, title_maker):
  logging.info(item_url)
  def html_fixer(soup):
    souper.tag_replacer(soup=soup, css_selector="table", tag_name="div")
    souper.tag_remover(soup=soup, css_selector="div.view-filters")

  def md_fixer(md):
    md = md.replace("।।", " ॥ ")
    # md = md.replace(".", " - ")
    md = md.replace(":", "ः")
    md = md.replace("\n  \n", "\n\n")
    md = regex.sub("\n{3, 13}", "\n\n", md)
    md = sanscript.transliterate(md, sanscript.IAST, sanscript.DEVANAGARI)
    return md

  souper.dump_text_from_element(url=item_url, outfile_path=outfile_path, text_css_selector="div.content", title_maker=title_maker, title_prefix="", html_fixer=html_fixer, md_fixer=md_fixer, dry_run=False)


