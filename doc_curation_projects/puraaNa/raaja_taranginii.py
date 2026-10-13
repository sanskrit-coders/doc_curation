import os
from doc_curation import sanskrit as sanskrit_helper
import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor.footnote import helper as footnote_helper
from doc_curation.md.content_processor import include as include_helper, section_helper, details as details_helper, ocr_helper
from doc_curation import sanskrit as sanskrit_helper
from doc_curation.utils import patterns
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


ROOT_DIR = "/home/vvasuki/gitland/vishvAsa/purANam/content/aitihyam/kalhaNa-rAjatarangiNI"

def content_fix():
  # library.apply_function(fn=MdFile.transform, dir_path=ROOT_DIR, content_transformer=lambda x, y: sanskrit_helper.fix_lazy_anusvaara(x), dry_run=False)
  # library.apply_function(fn=content_processor.replace_texts, dir_path=ROOT_DIR, patterns=[r"KRT_\d_",], replacement="")

  
  library.apply_function(fn=MdFile.transform, dir_path=ROOT_DIR, content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c, pattern=r"(?<=\n)([^\n]+ab  +\n[^\n]+cd +)"))


if __name__ == '__main__':
  content_fix()
