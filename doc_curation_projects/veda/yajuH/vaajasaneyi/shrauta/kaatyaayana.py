import os
import shutil

import regex
from bs4 import BeautifulSoup

import doc_curation.md.library.arrangement
import doc_curation.scraping.sacred_texts
from doc_curation_projects import veda
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, section_helper, space_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.sacred_texts import para_translation
from indic_transliteration import sanscript

content_dir_base = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/sUtram/kAtyAyanaH/shrautam"
static_dir_base = content_dir_base.replace("content", "static")
ref_dir = os.path.join(static_dir_base, "mUlam")


def dump_muulam():
  pass
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(os.path.dirname(content_dir_base), "khAdira-gRhyam.md"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 
  # library.apply_function(fn=section_helper.autonumber, dir_path=os.path.join(content_dir_base, "mUlam"))

  library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m: space_helper.make_lines_end_with_pattern(c, ".+[०-९]+"), dir_path=os.path.join(content_dir_base, "mUlam"))
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(content_dir_base, "mUlam"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None)
  # veda.migrate_and_include_sUtras(dir_path=os.path.join(content_dir_base, "mUlam"))
  # shutil.move(os.path.join(content_dir_base, "mUlam"), os.path.join(content_dir_base, "sarva-prastutiH"))
  # shutil.copytree(os.path.join(static_dir_base, "mUlam"), os.path.join(static_dir_base, "vishvAsa-prastutiH"))
  # library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m: c.replace("mUlam", "vishvAsa-prastutiH"), dir_path=os.path.join(content_dir_base, "sarva-prastutiH"))



if __name__ == '__main__':
  dump_muulam()
  # dump_oldenberg()
  # fix_oldenberg()
  # fix_includes()
  # fix_filenames()
  pass
