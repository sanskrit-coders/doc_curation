import os
import shutil

import regex
from bs4 import BeautifulSoup

from doc_curation_projects import veda
from doc_curation_projects.veda import suutra
from doc_curation.md import library
from doc_curation.md.content_processor import section_helper, include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.scraping import sacred_texts
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.wisdom_lib import para_translation
from indic_transliteration import sanscript

static_dir_base = "/home/vvasuki/vishvAsa/vedAH_yajuH/static/vAjasaneyam/sUtram/pAraskara-gRhyam"
content_dir_base = static_dir_base.replace("static/", "content/")
ref_dir = os.path.join(static_dir_base, "mUlam")



def oldenberg_dest_path_maker(url, base_dir):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  title = souper.title_from_element(soup, title_css_selector="h1")
  def deromanize(match):
    import roman
    return str(roman.fromRoman(match.group(1)))
  title = regex.sub("([IVX]+),", deromanize, title)
  subpath_parts = regex.sub("\D+", " ", title).strip().replace(" ", "_").split("_")
  subpath_parts = [int(x) for x in subpath_parts]
  subpath = "%d/%02d" % (subpath_parts[0], subpath_parts[-1])
  return os.path.join(base_dir, subpath + ".md")


def dump_oldenberg():
  # para_translation.dump_serially(start_url="https://www.wisdomlib.org/hinduism/book/paraskara-grihya-sutra/d/doc116613.html", base_dir=ref_dir.replace("vishvAsa-prastutiH", "oldenberg"), dest_path_maker=oldenberg_dest_path_maker)
  # para_translation.split(base_dir=ref_dir.replace("vishvAsa-prastutiH", "oldenberg"))
  # sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbe29/sbe29154.htm", outfile_path=os.path.join(content_dir_base, "meta", "oldenberg.md"))
  metadata_helper.copy_metadata_and_filename(dest_dir=ref_dir.replace("mUlam", "oldenberg"), ref_dir=ref_dir, insert_missign_ref_files=True)


def dump_muulam():
  # library.apply_function(fn=section_helper.autonumber, dir_path=os.path.join(content_dir_base, "mUlam.md"))
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(content_dir_base, "mUlam.md"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(content_dir_base, "mUlam"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None)
  # veda.migrate_and_include_sUtras(dir_path=os.path.join(content_dir_base, "mUlam"))
  # shutil.move(os.path.join(content_dir_base, "mUlam"), os.path.join(content_dir_base, "sarva-prastutiH"))
  # metadata_helper.ensure_ordinal_in_title(dir_path=ref_dir, recursive=True, format="%02d")
  library.apply_function(fn=metadata_helper.add_init_words_to_title, num_words=3, dir_path=ref_dir)

  # library.shift_indices(dir_path=os.path.join(ref_dir, "2/01"), new_index_offset=-1, start_index=4)
  pass


def fix_oldenberg():
  
  
  """
  Manual fixes:
  1/18/07
  2/01/25
  3/06/02
  3/08/15
  3/15/24
  3/15/25
  """
  base_dir = ref_dir.replace("mUlam", "oldenberg")

  work_dir = os.path.join(base_dir, "3/15")
  # library.shift_contents(work_dir, start_index=8, substitute_content_offset=1)
  metadata_helper.copy_metadata_and_filename(dest_dir=ref_dir.replace("mUlam", "oldenberg"), ref_dir=ref_dir, insert_missign_ref_files=True)
  pass


if __name__ == '__main__':
  # dump_oldenberg()
  # fix_oldenberg()
  # dump_muulam()
  # suutra.set_basic_content(static_dir_base=static_dir_base)
  # include_helper.include_core_with_commentaries(dir_path=os.path.join(content_dir_base, "sarva-prastutiH"), alt_dirs=["oldenberg"])
  pass
