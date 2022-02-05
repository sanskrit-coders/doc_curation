import logging
import os

import regex

from doc_curation.scraping.html_scraper import souper


def dump_series(start_url, out_path, dry_run=False):
  next_url_getter = lambda soup: souper.next_url_from_soup_css(soup=soup, css="div.order-3 a", base_url="https://www.wisdomlib.org/")
  title_maker = lambda soup, *args, **kwargs: souper.title_from_element(soup=soup, title_css_selector="h1")
  dumper = lambda url, outfile_path, title_prefix, dry_run: souper.dump_text_from_element(url=url, outfile_path=outfile_path, text_css_selector="#scontent", title_maker=title_maker, dry_run=dry_run)
  souper.dump_series(start_url=start_url, out_path=out_path, next_url_getter=next_url_getter, dumper=dumper, dry_run=dry_run)