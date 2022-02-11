import os

import regex
from bs4 import BeautifulSoup
from curation_projects import veda

from doc_curation.md.file import MdFile

from doc_curation.md import library

from doc_curation.md.content_processor import include_helper, section_helper
from doc_curation.md.library import metadata_helper
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.wisdom_lib import para_translation
from indic_transliteration import sanscript

static_dir_base = "/home/vvasuki/vishvAsa/vedAH/static/Rk/shAkalam/sUtram/AshvalAyanaH/gRhyam/"
content_dir_base = static_dir_base.replace("static/", "content/")
ref_dir = os.path.join(static_dir_base, "vishvAsa-prastutiH")
oldenberg_dir = os.path.join(static_dir_base, "oldenberg")


def prep_muula():
  # library.apply_function(fn=section_helper.autonumber, dir_path=os.path.join(content_dir_base, "mUlam.md"))
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(content_dir_base, "mUlam.md"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(content_dir_base, "mUlam/"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None)
  veda.migrate_and_include_sUtras(dir_path=os.path.join(content_dir_base, "mUlam/"))
  pass


def fix_includes():
  include_helper.include_core_with_commentaries(dir_path=os.path.join(content_dir_base,"sarva-prastutiH"), file_pattern="**/[0-9][0-9]*.md", alt_dirs=["oldenberg", "mUlam"], source_dir="vishvAsa-prastutiH")


def oldenberg_dest_path_maker(url, base_dir):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  title = souper.title_from_element(soup, title_css_selector="h1")
  title = title.replace(" I,", "1,").replace(" II,", "2,").replace(" III,", "3,").replace(" IV,", "4,")
  subpath = regex.sub("\D+", " ", title).strip().replace(" ", "_")
  subpath = "/".join(["%02d" % int(x) for x in subpath.split("_")])
  return os.path.join(base_dir, subpath + ".md")


def oldenberg_dump():
  # para_translation.dump_serially(start_url="https://www.wisdomlib.org/hinduism/book/asvalayana-grihya-sutra/d/doc116555.html", base_dir=oldenberg_dir, dest_path_maker=oldenberg_dest_path_maker)
  # split 4/7 and rearrange sUtras.
  # library.apply_function(fn=section_helper.autonumber, dir_path=os.path.join(oldenberg_dir, "04/08.md"), dest_script=sanscript.IAST)
  # para_translation.split(base_dir=oldenberg_dir)
  # library.apply_function(fn=metadata_helper.add_init_words_to_title, dir_path=os.path.join(ref_dir, "1/06"), target_title_length=30, num_words=2, dry_run=False)
  library.apply_function(fn=metadata_helper.set_filename_from_title, dir_path=os.path.join(ref_dir, "1/06"), dry_run=False)
  # metadata_helper.copy_metadata_and_filename(dest_dir=os.path.join(static_dir_base, "oldenberg"), ref_dir=ref_dir)
  pass


if __name__ == '__main__':
  # prep_muula()
  oldenberg_dump()
  pass