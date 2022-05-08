import os

import regex
from bs4 import BeautifulSoup
from doc_curation_projects import veda

from doc_curation.md.file import MdFile

from doc_curation.md import library
from doc_curation.md.content_processor import include_helper, section_helper
from doc_curation.md.library import metadata_helper
from doc_curation.scraping import sacred_texts
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.wisdom_lib import para_translation
from indic_transliteration import sanscript

static_dir_base = "/home/vvasuki/vishvAsa/vedAH_yajuH/static/taittirIyam/sUtram/hiraNyakeshI/gRhyam/"
content_dir_base = static_dir_base.replace("static/", "content/")
ref_dir = os.path.join(static_dir_base, "vishvAsa-prastutiH")
oldenberg_dir = os.path.join(static_dir_base, "oldenberg")


def fix_filenames():
  def sub_path_id_maker(x):
    x = str(x)
    base_name = os.path.basename(x)
    if base_name == "_index.md":
      return None
    elif "_" in base_name:
      return library.get_sub_path_id(sub_path=regex.sub(".+/", "", str(x)), basename_id_pattern=r"(\d\du?_\d\d)")
    else:
      return "%s_%s" % (os.path.basename(os.path.dirname(x)), base_name.replace(".md", ""))
  metadata_helper.copy_metadata_and_filename(dest_dir="/home/vvasuki/vishvAsa/vedAH_yajuH/static/taittirIyam/sUtram/hiraNyakeshI/gRhyam/oldenberg", ref_dir=ref_dir, sub_path_id_maker=sub_path_id_maker)


def oldenberg_dest_path_maker(url, base_dir):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  title = souper.title_from_element(soup, title_css_selector="h1")
  title = title.replace(" I,", "1,").replace(" II,", "2,")
  subpath_parts = regex.sub("\D+", " ", title).strip().replace(" ", "_").split("_")
  subpath_parts = ["%02d" % int(x) for x in subpath_parts]
  subpath = "%s/%s" % (subpath_parts[0], subpath_parts[-1]) 
  return os.path.join(base_dir, subpath + ".md")


def oldenberg_fix():
  # base_dir = os.path.join(oldenberg_dir, "1/07")
  # library.shift_contents(base_dir, start_index=9, substitute_content_offset=12-9)
  # for index in range(23, 26):
  #   os.remove(os.path.join(base_dir, "%02d.md" % index))
  
  # Merge and fix 1/29/02-04

  # base_dir = os.path.join(oldenberg_dir, "2/06")
  # library.shift_contents(base_dir, start_index=11, substitute_content_offset=1)
  # for index in range(20, 21):
  #   os.remove(os.path.join(base_dir, "%02d.md" % index))

  # Next fix some sUtra files missing (ie combined) in oldenberg but present in mUla.
  base_dir = os.path.join(oldenberg_dir, "1/26")
  # library.shift_contents(base_dir, start_index=8, substitute_content_offset=-2)
  library.shift_contents(base_dir, start_index=14, substitute_content_offset=-2)

  pass

def oldenberg_dump():
  # para_translation.dump_serially(start_url="https://www.wisdomlib.org/hinduism/book/hiranyakesi-grihya-sutra/d/doc116737.html", base_dir=os.path.join(static_dir_base, "oldenberg"), dest_path_maker=oldenberg_dest_path_maker)
  # para_translation.split(base_dir=os.path.join(static_dir_base, "oldenberg"))
  oldenberg_fix()
  # metadata_helper.copy_metadata_and_filename(dest_dir=os.path.join(static_dir_base, "oldenberg"), ref_dir=ref_dir)
  # fix_filenames()
  pass


def prep_muula():
  # library.apply_function(fn=section_helper.autonumber, dir_path=os.path.join(content_dir_base, "mUlam.md"))
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(content_dir_base, "mUlam.md"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(content_dir_base, "mUlam/"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None)
  # veda.migrate_and_include_sUtras(dir_path=os.path.join(content_dir_base, "mUlam/"))
  pass


def fix_includes():
  include_helper.include_core_with_commentaries(dir_path=os.path.join(content_dir_base,"sarva-prastutiH"), file_pattern="**/[0-9][0-9]*.md", alt_dirs=["oldenberg", "mUlam"], source_dir="vishvAsa-prastutiH")


if __name__ == '__main__':
  # fix_includes()
  # oldenberg_dump()
  # prep_muula()
  # fix_includes()
  sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbe30/sbe30043.htm", outfile_path=os.path.join(content_dir_base, "meta", "oldenberg.md"))

  pass
