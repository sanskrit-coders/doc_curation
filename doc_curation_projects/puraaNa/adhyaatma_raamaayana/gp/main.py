import os

import regex

from doc_curation.md import library

from doc_curation.md.library import arrangement
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

def fix_names():
  pass
  library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/adhyAtma-rAmAyaNam", fn=metadata_helper.remove_adhyaaya_word_from_title, adhyaaya_pattern="ಸರ್ಗ|सर्ग", dry_run=False)


fix_names()