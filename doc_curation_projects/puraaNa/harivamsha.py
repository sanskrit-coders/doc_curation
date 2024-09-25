from urllib.parse import urljoin
import os

import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import ocr_helper, details_helper

from doc_curation.md.library import arrangement
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript
from doc_curation.utils import patterns

BASE_DIR = "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/harivaMshaH/sarva-prastutiH/"

def dump():
  from doc_curation.scraping import wikisource
  from doc_curation.scraping.wikisource import enumerated, serial
  from indic_transliteration import sanscript
  base_url = urljoin("https://sa.wikisource.org/wiki", "हरिवंशपुराणम्/पर्व_१_(हरिवंशपर्व)/अध्यायः_०१")
  # serial.dump_text(start_url="https://sa.wikisource.org/s/1ae2", out_path=os.path.join(BASE_DIR, "1_hari-vaMsha-parva"), next_url_css='[style="width:200%; text-align:right;font-size:0.9em;"] a', transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)
  
  # enumerated.dump_text(url_base="हरिवंशपुराणम्/पर्व_१_(हरिवंशपर्व)/अध्यायः_", num_parts=55, dir_path=os.path.join(BASE_DIR, "1_hari-vaMsha-parva"), url_id_padding="%02d")
  # enumerated.dump_text(url_base="हरिवंशपुराणम्/पर्व_२_(विष्णुपर्व)/अध्यायः_", num_parts=128, dir_path=os.path.join(BASE_DIR, "2_viShNu-parva"), url_id_padding="%03d")
  enumerated.dump_text(url_base="हरिवंशपुराणम्/पर्व_३_(भविष्यपर्व)/अध्यायः_", num_parts=135, dir_path=os.path.join(BASE_DIR, "3_bhaviShya-parva"), url_id_padding="%03d")

  # serial.dump_text(start_url="https://sa.wikisource.org/s/gzf", out_path="/home/vvasuki/sanskrit/raw_etexts/purANam/skanda-purANam/1_mAheshvara-khaNDaH/1_kedAra-khaNDaH", next_url_css='[style="width:200%; text-align:right;font-size:0.9em;"] a', transliteration_source=sanscript.DEVANAGARI, base_url="http://sa.wikisource.org/", dry_run=False)

def fix_content(dir_path=BASE_DIR):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.misc_sanskrit_typos(x))

  pass



if __name__ == '__main__':
  # dump()
  # fix_content()
  library.apply_function(fn=MdFile.transform, dir_path=BASE_DIR, content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c, pattern=patterns.PATTERN_MULTI_LINE_SHLOKA))

