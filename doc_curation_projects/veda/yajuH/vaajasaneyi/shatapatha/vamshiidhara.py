
import logging
import os, regex

from doc_curation_projects.veda.yajuH.vaajasaneyi import shatapatha
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes import brahmic
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.scraping.misc_sites import titus
from doc_curation.md import library, content_processor
from doc_curation.md.library import metadata_helper
from doc_curation import book_data
from doc_curation.md.file import MdFile
from doc_curation_projects.veda.yajuH.vaajasaneyi.shatapatha import WEBER_EXTRA_ACCENTS

base_dir = os.path.join(shatapatha.CONTENT_BASE, "vaMshIdhara-pAThaH/sasvaram")
devanagari = sanscript.SCHEMES[sanscript.DEVANAGARI]






if __name__ == '__main__':
  library.apply_function(fn=content_processor.replace_texts, dir_path=base_dir, patterns=[f"[{WEBER_EXTRA_ACCENTS}]+"], replacement="᳘")
  pass
