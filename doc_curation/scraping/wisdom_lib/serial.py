import logging
import os

import regex

from doc_curation.md import content_processor
from doc_curation.scraping import wisdom_lib

from doc_curation.scraping.html_scraper import souper




def dumper (url, outfile_path, title_prefix, dry_run):
  title_maker = lambda soup, *args, **kwargs: souper.title_from_element(soup=soup, title_css_selector="h1", title_prefix=title_prefix)
  def html_fixer(soup):
    souper.tag_remover(soup=soup, css_selector="section.footnotes")
    for element in soup.select("sup.ftnt"):
      text = element.get_text()
      text = text.replace("[", "[^")
      element.replaceWith(text)
  def md_fixer(content):
    return content.replace("\\[", "[").replace("\\]", "]")

  return souper.dump_text_from_element(url=url, outfile_path=outfile_path, text_css_selector="#scontent", title_maker=title_maker, html_fixer=html_fixer, md_fixer=md_fixer, footnote_definier=wisdom_lib.footnote_extractor, overwrite=True, dry_run=dry_run)


def dump_series(start_url, out_path, dumper=dumper, end_url=None, dry_run=False):
  next_url_getter = lambda soup: souper.anchor_url_from_soup_css(soup=soup, css="div.order-3 a", base_url="https://www.wisdomlib.org/")
  souper.dump_series(start_url=start_url, out_path=out_path, next_url_getter=next_url_getter, dumper=dumper, end_url=end_url, dry_run=dry_run)