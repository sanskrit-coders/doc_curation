import os
import shutil

import doc_curation.md.library
import regex
from bs4 import BeautifulSoup

import doc_curation_projects.veda.suutra
from doc_curation_projects import veda
from doc_curation.md import library
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper, combination, arrangement
from doc_curation.scraping import sacred_texts
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.wisdom_lib import para_translation
from doc_curation.scraping.sacred_texts import para_translation as para_translation_st, dump_meta_article
from indic_transliteration import sanscript

content_dir_base = "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/kauthumam/sUtram/gobhila-gRhyam/"
static_dir_base = content_dir_base.replace("content", "static")
ref_dir = os.path.join(static_dir_base, "mUlam")


def fix_includes():
  md_files = doc_curation.md.library.get_md_files_from_path(dir_path=os.path.join(content_dir_base, "sarva-prastutiH"), file_pattern="*/[0-9][0-9]*.md")
  md_files = [f for f in md_files if os.path.basename(f.file_path) ]
  dir_path = os.path.join(content_dir_base, "sarva-prastutiH")
  def include_fixer(inc, file_path):
    return include_helper.alt_include_adder(inc=inc, current_file_path=file_path, source_dir="vishvAsa-prastutiH", alt_dirs=["sarvASh_TIkAH"])


  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_helper.old_include_remover))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y, transformer=include_fixer))
  include_helper.prefill_includes(dir_path=dir_path)


def dump_oldenberg():
  base_dir = ref_dir.replace("mUlam", "oldenberg")
  # para_translation.dump_serially(start_url="https://www.wisdomlib.org/hinduism/book/gobhila-grihya-sutra/d/doc116692.html", base_dir=base_dir, dest_path_maker=oldenberg_dest_path_maker)
  # para_translation.split(base_dir=base_dir)
  shutil.rmtree(os.path.join(base_dir, "3/04"))
  sacred_texts.dump(url="https://www.sacred-texts.com/hin/sbe30/sbe30026.htm", main_content_extractor=para_translation_st.get_main_content, outfile_path=os.path.join(base_dir, "3/04.md"))
  library.apply_function(fn=MdFile.split_to_bits, dir_path=base_dir, dry_run=False, source_script=None, title_index_pattern=None)
  metadata_helper.copy_metadata_and_filename(dest_dir=ref_dir.replace("mUlam", "oldenberg"), ref_dir=ref_dir)
  # dump_meta_article(url="https://www.sacred-texts.com/hin/sbe30/sbe30003.htm", outfile_path=os.path.join(content_dir_base, "meta", "oldenberg.md"))


def oldenberg_dest_path_maker(url, base_dir):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  title = souper.title_from_element(soup, title_css_selector="h1")
  def deromanize(match):
    import roman
    return str(roman.fromRoman(match.group(1)))
  title = regex.sub("([IVX]+),", deromanize, title)
  subpath_parts = regex.sub("\D+", " ", title).strip().replace(" ", "_").split("_")
  subpath_parts = ["%02d" % int(x) for x in subpath_parts]
  subpath = "%s/%s" % (subpath_parts[0], subpath_parts[-1])
  return os.path.join(base_dir, subpath + ".md")


def migrate_and_include_sUtras():
  doc_curation_projects.veda.suutra.migrate_and_include_sUtras(dir_path=os.path.join(content_dir_base, "mUlam/"))


def dump_vishvaasa_sUtras():
  source_dir = os.path.join(content_dir_base, "vishvAsa-prastutiH")
  static_dir = os.path.join(static_dir_base, "vishvAsa-prastutiH")
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=source_dir, dry_run=False, source_script=sanscript.DEVANAGARI, title_index_pattern=None)
  # doc_curation_projects.veda.suutra.migrate_and_include_sUtras(dir_path=source_dir)
  metadata_helper.copy_metadata_and_filename(dest_dir=static_dir, ref_dir=ref_dir)


def combine():
  subpaths = ["mUlam", "oldenberg", ]
  subpaths = [os.path.join(static_dir_base, subpath) for subpath in subpaths]

  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(static_dir_base, "sarvASh_TIkAH"), dry_run=False)


if __name__ == '__main__':
  fix_includes()
  # fix_oldenberg()
  # dump_oldenberg()
  # dump_vishvaasa_sUtras()
  # combine()
  # fix_filenames()
  # migrate_and_include_sUtras()
  pass
