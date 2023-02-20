import os

import regex

import doc_curation.md.library.arrangement
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement, metadata_helper
from doc_curation.scraping.html_scraper import souper


def html_fixer(soup):
  souper.tag_replacer(soup=soup, css_selector="big", tag_name="h2")
  souper.tag_replacer(soup=soup, css_selector="table", tag_name="div")
  souper.tag_replacer(soup=soup, css_selector="tbody", tag_name="div")
  souper.tag_replacer(soup=soup, css_selector="span[style*=\"font-weight:bold;\"]", tag_name="b")
  souper.element_remover(soup=soup, css_selector=".noprint")


# Alternatives for next_url_css:
# [style="width:200%; text-align:right;font-size:0.9em;"] a
#   as in https://sa.wikisource.org/s/1snc
# a.mw-redirect - https://sa.wikisource.org/s/13lq
def dump_text(start_url, out_path, title_maker=None, index_format="%02d", text_css_selector="div.mw-parser-output", base_url="https://sa.wikisource.org/", next_url_css="div.gen_header_forelink a", transliteration_source=None, dumper=None, dry_run=False):
  next_url_getter = lambda soup: souper.anchor_url_from_soup_css(soup=soup, css=next_url_css, base_url=base_url)
  
  if title_maker is None:
    def title_maker(soup, title_prefix):
      title = souper.title_from_element(soup=soup, title_css_selector="h1", title_prefix=title_prefix)
      title = regex.sub(" .+/", " ", title).strip()
      return title
  if dumper is None:
    def dumper(url, outfile_path, title_prefix, dry_run): 
      return souper.dump_text_from_element(url=url, outfile_path=outfile_path, text_css_selector=text_css_selector, title_maker=title_maker, title_prefix=title_prefix, html_fixer=html_fixer, dry_run=dry_run)
  souper.dump_series(start_url=start_url, out_path=out_path, dumper=dumper, index_format=index_format, next_url_getter=next_url_getter, dry_run=dry_run)
  arrangement.fix_index_files(dir_path=out_path, dry_run=dry_run, transliteration_target=transliteration_source, overwrite=True)
  library.apply_function(dir_path=out_path, fn=metadata_helper.set_filename_from_title, source_script=transliteration_source, dry_run=False)
