import os

import regex

from doc_curation.md import library
from doc_curation.md.content_processor import include_helper
from doc_curation.md.library import metadata_helper

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



if __name__ == '__main__':
  # fix_filenames()
  fix_includes()
  pass
