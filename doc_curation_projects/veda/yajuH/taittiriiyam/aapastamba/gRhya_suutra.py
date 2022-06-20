import os

import regex
from bs4 import BeautifulSoup

import doc_curation.scraping.sacred_texts
from doc_curation.md import library
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement, metadata_helper, combination
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.wisdom_lib import para_translation

content_dir_base = "/home/vvasuki/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/"
static_dir_base = content_dir_base.replace("content", "static")
ref_dir = os.path.join(static_dir_base, "vishvAsa-prastutiH",)
oldenberg_dir = ref_dir.replace("vishvAsa-prastutiH", "oldenberg")

def fix_filenames():
  def sub_path_id_maker(x):
    x = str(x)
    base_name = os.path.basename(x)
    if base_name == "_index.md":
      return None
    elif "_" in base_name:
      return doc_curation.md.library.arrangement.get_sub_path_id(sub_path=regex.sub(".+/", "", str(x)), basename_id_pattern=r"(\d\du?_\d\d)")
    else:
      return "%s_%s" % (os.path.basename(os.path.dirname(x)), base_name.replace(".md", ""))
  metadata_helper.copy_metadata_and_filename(dest_dir="/home/vvasuki/vishvAsa/vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH/oldenberg", ref_dir=ref_dir, sub_path_id_maker=sub_path_id_maker)



def combine():
  subpaths = [os.path.join(static_dir_base, "sUtra-pAThaH", x) for x in ["oldenberg", "haradatta-prastAvaH", "haradattaH", "sudarshanaH",]]
  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(static_dir_base, "sUtra-pAThaH", "sarvASh_TIkAH"), dravidian_titles=False, dry_run=False)


def fix_includes():
  dest_dir = os.path.join(content_dir_base, "sUtra-TIkAH")
  
  def include_fixer(x, current_file_path, *args):
    return include_helper.alt_include_adder(x, current_file_path, source_dir="vishvAsa-prastutiH", alt_dirs=["mUlam", "sarvASh_TIkAH"])

  library.apply_function(fn=MdFile.transform, dir_path=dest_dir, content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_helper.old_include_remover))
  library.apply_function(fn=MdFile.transform, dir_path=dest_dir, content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_fixer))
  library.apply_function(fn=MdFile.transform, dir_path=dest_dir, content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)
  include_helper.prefill_includes(dir_path=dest_dir)


def oldenberg_dest_path_maker(url, base_dir):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  title = souper.title_from_element(soup, title_css_selector="h1")
  title = title.replace(" I,", "1,").replace(" II,", "2,")
  subpath = regex.sub("\D+", " ", title).strip().replace(" ", "_")
  subpath = "_".join(["%02d" % int(x) for x in subpath.split("_")])
  return os.path.join(base_dir, subpath + ".md")

def fix_oldenberg():
  # Off by 1 in 4 as well. Then:
  # base_dir = os.path.join(oldenberg_dir, "11")
  # Merge 11, 12
  # library.shift_contents(base_dir, start_index=12, new_content_offset=1)
  # library.shift_contents(base_dir, start_index=23, substitute_content_offset=1)
  # os.remove(os.path.join(base_dir, "25.md"))
  # os.remove(os.path.join(base_dir, "26.md"))

  # library.shift_contents(os.path.join(oldenberg_dir, "03_vaivAhikaviShayAH"), start_index=5, substitute_content_offset=-1, index_position=1)
  # library.shift_contents(os.path.join(oldenberg_dir, "04_vivAhaprakaraNam/tmp"), start_index=2, substitute_content_offset=1, index_position=1)
  doc_curation.md.library.arrangement.shift_contents(os.path.join(oldenberg_dir, "04_vivAhaprakaraNam/tmp"), start_index=11, substitute_content_offset=-2, index_position=1)


if __name__ == '__main__':
  # combine()
  fix_includes()
  # para_translation.dump_serially(start_url="https://www.wisdomlib.org/hinduism/book/apastamba-grihya-sutra/d/doc116791.html", base_dir="/home/vvasuki/vishvAsa/vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH/oldenberg/", dest_path_maker=oldenberg_dest_path_maker)
  # para_translation.split(base_dir="/home/vvasuki/vishvAsa/vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH/oldenberg/")
  # fix_oldenberg()
  # fix_filenames()

  # from doc_curation.scraping.sacred_texts import para_translation as para_translation_st
  # doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbe30/sbe30093.htm", outfile_path=os.path.join(content_dir_base, "meta", "oldenberg.md"))
  pass
