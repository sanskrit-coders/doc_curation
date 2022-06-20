import functools
import os

import regex
from bs4 import BeautifulSoup

import doc_curation.md.library.arrangement
from curation_utils import dir_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper, combination
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.wisdom_lib import para_translation
from indic_transliteration import sanscript
import functools
import logging

content_dir_base = "/home/vvasuki/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/dharma-sUtram"
static_dir_base = content_dir_base.replace("content", "static")
ref_dir = os.path.join(static_dir_base, "vishvAsa-prastutiH")

@functools.lru_cache
def get_suutra_id_to_md():
  suutra_id_to_md = {}
  md_files = doc_curation.md.library.arrangement.get_md_files_from_path(dir_path=ref_dir, file_pattern="**/[0-9][0-9]*.md")
  for md_file in md_files:
    file_path = str(md_file.file_path)
    match = regex.search(pattern=r"(\d)/(\d\d)/(\d\d)/(\d\d)_", string=file_path)
    suutra_id = match.group(1) + str(int(match.group(2))) + str(int(match.group(3))) + str(int(match.group(4)))
    if suutra_id in suutra_id_to_md:
      logging.warning("suutra_id duplicate: %s, %s, %s", suutra_id, suutra_id_to_md[suutra_id], file_path)
    suutra_id_to_md[suutra_id] = md_file
  return suutra_id_to_md


def combine():
  subpaths = [os.path.join(static_dir_base, x) for x in ["buhler", "haradatta-TIkA", "shankarAchArya-vivaraNam", ]]
  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(static_dir_base, "sarvASh_TIkAH"), dravidian_titles=False, dry_run=False)


def fix_includes():
  dest_dir = os.path.join(content_dir_base, "sarva-prastutiH")

  def include_fixer(x, current_file_path, *args):
    return include_helper.alt_include_adder(x, current_file_path, source_dir="vishvAsa-prastutiH", alt_dirs=["sarvASh_TIkAH"])

  library.apply_function(fn=MdFile.transform, dir_path=dest_dir, content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_helper.old_include_remover))
  library.apply_function(fn=MdFile.transform, dir_path=dest_dir, content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_fixer))
  library.apply_function(fn=MdFile.transform, dir_path=dest_dir, content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)
  include_helper.prefill_includes(dir_path=dest_dir)



def suutra_include_maker(suutra_id_dev, text_path, *args, **kwargs):
  """
  
  ११११ → 1/01/01/01
  ११११० → 1/01/01/10
  १३१०११ → 1/3/10/11
  १११३१२२ → 1/11/31/22
  
  :param suutra_id_dev: 
  :return: 
  """
  suutra_id = sanscript.transliterate(suutra_id_dev, _from=sanscript.DEVANAGARI, _to=sanscript.IAST).strip()
  suutra_id_to_md = get_suutra_id_to_md()
  if suutra_id not in suutra_id_to_md:
    logging.fatal("%s from %s not found", suutra_id, text_path)
  return include_helper.vishvAsa_include_maker(file_path=suutra_id_to_md[suutra_id].file_path, h1_level=4, classes=None, title=None, )



def replace_suutraid_with_includes():
  md_files = doc_curation.md.library.arrangement.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/dharma-sUtram/viShaya-vibhAgaH")
  for md_file in md_files:
    include_helper.migrate_and_replace_texts(md_file=md_file, text_patterns=[r"(?<=[^०-९]|^)[०-९]+(?=[^०-९]|$)"], replacement_maker=suutra_include_maker, migrated_text_processor=None, destination_path_maker=lambda *args, **kwargs: None, title_maker=lambda *args, **kwargs: None, dry_run=False)


def get_title_id(text_matched):
  id_in_text = regex.search("([०-९]+) *$", text_matched).group(1)
  title_id = "%02d" % int(sanscript.transliterate(id_in_text, sanscript.DEVANAGARI, sanscript.IAST))
  return title_id


def migrate_and_include_shlokas():

  def replacement_maker(text_matched, dest_path):
    return include_helper.vishvAsa_include_maker(dest_path, h1_level=3, title="FILE_TITLE")

  PATTERN_SUTRA = "\n[^#\s<>\[\(][\s\S]+? \s*[०-९\d\.]+\s*?(?=\n|$)"
  # library.apply_function(fn=include_helper.migrate_and_replace_texts, text_patterns=[PATTERN_SUTRA], dir_path="/home/vvasuki/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/dharma-sUtram/vishvAsa-prastutiH", replacement_maker=replacement_maker, title_maker=title_maker, dry_run=False)
  pass


def buhler_dest_path_maker(url, base_dir):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  title = souper.title_from_element(soup, title_css_selector="h1")
  title = title.replace(" I,", "1,").replace(" II,", "2,")
  subpath = regex.sub("\D+", " ", title).strip().replace(" ", "/") + ".md"
  return os.path.join(base_dir, subpath)


def fix_buhler():

  # library.shift_contents(os.path.join(base_dir, "2/06/13/"), start_index=3, substitute_content_offset=1)
  # os.remove(os.path.join(base_dir, "2/06/13/13.md"))

  # library.shift_contents(os.path.join(buhler_dir, "2/05/10/"), start_index=4, substitute_content_offset=-1)
  # doc_curation.md.library.arrangement.shift_contents(os.path.join(buhler_dir, "1/02/08/"), start_index=24, substitute_content_offset=-1)
  # os.remove(os.path.join(base_dir, "2/06/13/13.md"))
  pass

if __name__ == '__main__':
  # migrate_and_include_shlokas()
  # fix_buhler()
  # combine()
  fix_includes()
  # para_translation.dump_serially(start_url="https://www.wisdomlib.org/hinduism/book/apastamba-dharma-sutra/d/doc116233.html", base_dir=base_dir, dest_path_maker=buhler_dest_path_maker)
  # dir_helper.remove_empty_directories(base_dir)
  # para_translation.split(base_dir=base_dir)
  # metadata_helper.copy_metadata_and_filename(dest_dir=ref_dir.replace("vishvAsa-prastutiH", "buhler"), ref_dir=ref_dir, sub_path_id_maker=None)
  pass
  # replace_suutraid_with_includes()