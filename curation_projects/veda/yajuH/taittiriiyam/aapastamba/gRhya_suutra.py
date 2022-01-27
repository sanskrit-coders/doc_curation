import os

import regex
from bs4 import BeautifulSoup

from doc_curation.md import library
from doc_curation.md.content_processor import include_helper
from doc_curation.md.library import metadata_helper
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.wisdom_lib import para_translation

ref_dir = "/home/vvasuki/vishvAsa/vedAH/static/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH/vishvAsa-prastutiH"


def fix_filenames():
  sub_path_id_maker = lambda x: library.get_sub_path_id(sub_path=regex.sub(".+/", "", str(x)), basename_id_pattern=r"(\d\du?_\d\d)")
  metadata_helper.copy_metadata_and_filename(dest_dir="/home/vvasuki/vishvAsa/vedAH/static/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH/oldenberg", ref_dir=ref_dir, sub_path_id_maker=sub_path_id_maker)


def fix_includes():
  md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-TIkAH", file_pattern="[0-9][0-9]*.md")
  md_files = [f for f in md_files if os.path.basename(f.file_path) ]
  
  def include_fixer(match):
    return include_helper.alt_include_adder(match=match, source_dir="vishvAsa-prastutiH", alt_dirs=["haradattaH", "sudarshanaH", "oldenberg"])

  for md_file in md_files:
    include_helper.transform_include_lines(md_file=md_file, transformer=include_helper.old_include_remover)
    include_helper.transform_include_lines(md_file=md_file, transformer=include_fixer)
    md_file.transform(content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)


def oldenberg_dest_path_maker(url, base_dir):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  title = souper.title_from_element(soup, title_css_selector="h1")
  title = title.replace(" I,", "1,").replace(" II,", "2,")
  subpath = regex.sub("\D+", " ", title).strip().replace(" ", "_")
  subpath = "_".join(["%02d" % int(x) for x in subpath.split("_")])
  return os.path.join(base_dir, subpath + ".md")


if __name__ == '__main__':
  # fix_filenames()
  # fix_includes()
  para_translation.dump_serially(start_url="https://www.wisdomlib.org/hinduism/book/apastamba-grihya-sutra/d/doc116791.html", base_dir="/home/vvasuki/vishvAsa/vedAH/static/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH/oldenberg_with_fn/", dest_path_maker=oldenberg_dest_path_maker)
  pass
