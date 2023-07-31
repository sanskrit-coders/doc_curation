import logging
import os

import regex
from doc_curation.md.file import MdFile

from indic_transliteration import sanscript
from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.library import combination
from doc_curation.scraping.html_scraper import souper
from curation_utils import scraping, file_helper


def _add_detail(type, content, details):
  if len(details) > 0 and details[-1].title == type:
    details[-1].content += "  \n" + content
  else:
    details.append(details_helper.Detail(title=type, content=content))

def parse_page(soup):
  """
  
  :param url: Example: https://www.gurugranthdarpan.net/hindi/0001.html 
  :return: 
  """
  details = []
  
  paras = soup.select("p")
  for para in paras:
    if "class" not in para.attrs:
      continue
    class_str = " ".join(para.attrs["class"]).lower()
    if "head2" in class_str:
      _add_detail(type="दर्पण-शीर्षक", content=para.text, details=details)
    elif "bhav" in class_str:
      _add_detail(type="दर्पण-भाव", content=para.text, details=details)
    elif "arath" in class_str:
      _add_detail(type="दर्पण-भाषार्थ", content=para.text, details=details)
    elif "note" in class_str or "baniref" in class_str:
      _add_detail(type="दर्पण-टिप्पनी", content=para.text, details=details)
    elif "padarath" in class_str:
      _add_detail(type="दर्पण-पदार्थ", content=para.text, details=details)
    elif "banihead" in class_str or "banicenter" in class_str or "bani" in class_str:
      _add_detail(type="विश्वास-प्रस्तुतिः", content=para.text, details=details)
      _add_detail(type="मूलम्", content=para.text, details=details)
  return details


def _next_url_getter(soup):
  next_img = soup.select_one("img[name='rollover8']")
  next_url = "https://www.gurugranthdarpan.net/hindi/" + next_img.parent["href"]
  return next_url


DEST_DIR = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/nAnaka-mArgaH/guru-granthaH/darpaNa/"


def dump_all(index=421):
  def _dumper(url, outfile_path, title_prefix, dry_run): 
    return souper.detail_dumper(url=url, outfile_path=outfile_path, title_prefix= title_prefix, dry_run=dry_run, detail_maker=parse_page)
  souper.dump_series(start_url="https://www.gurugranthdarpan.net/hindi/%04d.html" % index, out_path=DEST_DIR, dumper=_dumper, next_url_getter=_next_url_getter, end_url=None, index_format="%04d", index=index)
  pass




if __name__ == '__main__':
  # dump_all(1243)
  # combination.combine_files_in_dir(md_file=MdFile(file_path=os.path.join(DEST_DIR, "02_rAga.md")), title_format="[[%s]]\n", dry_run=False)
  library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/nAnaka-mArgaH/guru-granthaH/sarva-prastutiH/02_rAga.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, start_index=22) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/nAnaka-mArgaH/guru-granthaH/sarva-prastutiH/02_rAga", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI) # 
