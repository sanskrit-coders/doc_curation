import os

from doc_curation.scraping.html import souper


def dump_text(start_url, out_path, dry_run=False):
  next_url_getter = lambda soup: souper.next_url_from_soup_css(soup=soup, css="div.gen_header_forelink a", base_url="https://sa.wikisource.org/")
  def html_fixer(soup):
    souper.tag_replacer(soup=soup, css_selector="big", tag_name="h2")
    souper.tag_replacer(soup=soup, css_selector="table", tag_name="div")
    souper.tag_replacer(soup=soup, css_selector="tbody", tag_name="div")
    souper.tag_remover(soup=soup, css_selector=".noprint")
  dumper = lambda url, outfile_path, title_prefix, dry_run: souper.dump_text_from_element(url=url, text_css_selector="div.mw-parser-output", outfile_path=outfile_path, title_css_selector="h1", html_fixer=html_fixer, title_prefix=title_prefix, dry_run=dry_run)
  souper.dump_series(start_url=start_url, out_path=out_path, dumper=dumper, next_url_getter=next_url_getter, dry_run=dry_run)