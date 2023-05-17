import logging
import os

import regex
from doc_curation.md.file import MdFile
from doc_curation.utils import sanskrit_helper

from indic_transliteration import sanscript
from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.library import combination, metadata_helper
from doc_curation.scraping.html_scraper import souper
from curation_utils import scraping, file_helper



def _next_url_getter(soup):
  next_a = soup.select_one('[rel="next"]')
  next_url = "https://www.transliteral.org" + next_a["href"]
  return next_url


def dump_all(url, dest_dir):
  def md_fixer(c):
    c = c.replace("‍", "").replace(":", "ः").replace("फ़", "फ").replace("व्द", "द्व")
    c = sanskrit_helper.fix_lazy_anusvaara(c)
    return c
  def _dumper(url, outfile_path, title_prefix, dry_run):
    return souper.dump_text_from_element(url=url, outfile_path=outfile_path, md_fixer=md_fixer, text_css_selector="#tabs-1",title_prefix=title_prefix, dry_run=dry_run)
  # souper.dump_series(start_url=url, out_path=dest_dir, dumper=_dumper, next_url_getter=_next_url_getter, end_url=None, index_format="%02d", index=1)
  # library.apply_function(dir_path=dest_dir, fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)
  # library.fix_index_files(dir_path=os.path.dirname(dest_dir), overwrite=False, dry_run=False)
  library.apply_function(fn=MdFile.transform, dir_path=dest_dir, content_transformer=lambda c, m: md_fixer(c=c))
  pass


if __name__ == '__main__':
  dump_all(url="https://www.transliteral.org/pages/z180118051000/view", dest_dir="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/paramparA/shankara-digvijayaH/mAdhavIyaH/")