import os

import regex

from doc_curation.md import library

from doc_curation.md.library import arrangement
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

ROOT_DIR = "/home/vvasuki/gitland/vishvAsa/purANam/"


def fix_names(dir_path, conclusion_pattern="इति.+ऽध्यायः"):
  pass
  library.apply_function(fn=metadata_helper.set_title_from_content, dir_path=dir_path, title_extractor=lambda x: metadata_helper.iti_naama_title_extractor(x, conclusion_pattern=conclusion_pattern))
  # library.apply_function(fn=metadata_helper.set_title_from_content, dir_path=dir_path, title_extractor= lambda x: metadata_helper.iti_saptamii_title_extractor(x, conclusion_pattern="इति.+महाभारते.+पर्वणि.+ \S+ .+ऽध्यायः"), dry_run=False)


# dump()
# fix_names(dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/saura-purANam", conclusion_pattern="\nइति[\s\S]+?ऽध्यायः")
fix_names(dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/skanda-purANam", conclusion_pattern="\nइति[\s\S]+?ध्यायः")
