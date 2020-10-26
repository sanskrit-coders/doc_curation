import os

import regex

from doc_curation.scraping.html import souper


def dump_text_serially(start_url, out_path, dry_run=False):
  next_url_getter = lambda soup: souper.next_url_from_soup_css(soup=soup, css="div.order-3 a", base_url="https://www.wisdomlib.org/")
  def html_fixer(soup):
    pass

  def title_maker(soup, title_prefix):
    title = souper.title_from_element(soup=soup, title_css_selector="h1", title_prefix=title_prefix)
    # title = regex.sub(" .+/", "", title)
    return title
  dumper = lambda url, outfile_path, title_prefix, dry_run: souper.dump_text_from_element(url=url, outfile_path=outfile_path, text_css_selector="#scontent", title_maker=title_maker, title_prefix=title_prefix, html_fixer=html_fixer, dry_run=dry_run)
  souper.dump_series(start_url=start_url, out_path=out_path, dumper=dumper, next_url_getter=next_url_getter, dry_run=dry_run)
  

