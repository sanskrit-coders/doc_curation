import os

import regex

from doc_curation.md import library

from doc_curation.md.library import arrangement
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

ROOT_DIR = "/home/vvasuki/gitland/vishvAsa/purANam/content/bhAgavatam/goraxapura-pAThaH"
HI_ROOT = os.path.join(ROOT_DIR, "hindy-anuvAdaH")


def fix_names():
  pass
  # library.apply_function(dir_path=ROOT_DIR, fn=metadata_helper.remove_adhyaaya_word_from_title, adhyaaya_pattern="ಸ್ಕಂಧ|स्कन्ध", dry_run=False)
  # library.apply_function(dir_path=ROOT_DIR, fn=metadata_helper.remove_adhyaaya_word_from_title, dry_run=False)
  # library.apply_function(fn=metadata_helper.set_title_from_content, dir_path=HI_ROOT, title_extractor=metadata_helper.iti_naama_title_extractor)
  # library.apply_function(fn=metadata_helper.set_title_from_content, dir_path=HI_ROOT, title_extractor= lambda x: metadata_helper.iti_saptamii_title_extractor(x, conclusion_pattern="इति.+स्कन्धे.+(ार्धे)? \S+ .+ऽध्यायः"), dry_run=False)


fix_names()