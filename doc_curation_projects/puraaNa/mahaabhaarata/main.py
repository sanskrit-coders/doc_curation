import os

import regex

from doc_curation.md import library

from doc_curation.md.library import arrangement
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

ROOT_DIR = "/home/vvasuki/gitland/vishvAsa/purANam/content/mahAbhAratam/goraxapura-pAThaH/"
HI_ROOT = os.path.join(ROOT_DIR, "hindy-anuvAdaH")


def fix_names():
  pass
  # library.apply_function(fn=metadata_helper.set_title_from_content, dir_path=HI_ROOT, title_extractor=metadata_helper.iti_naama_title_extractor)
  library.apply_function(fn=metadata_helper.set_title_from_content, dir_path=HI_ROOT, title_extractor= lambda x: metadata_helper.iti_saptamii_title_extractor(x, conclusion_pattern="इति.+महाभारते.+पर्वणि.+ \S+ .+ऽध्यायः"), dry_run=False)


fix_names()