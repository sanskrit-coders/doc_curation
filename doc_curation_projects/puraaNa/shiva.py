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

def dump():
  pass
  library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/shiva-purANam", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 



fix_names(dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/shiva-purANam/7_vAyavIya-saMhitA", conclusion_pattern=r"इति .+संहिताया.+ध्यायः")