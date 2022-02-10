import os

import regex

from doc_curation.md import library
from doc_curation.md.content_processor import include_helper


def fix_includes():
  md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/shrautam/sarva-prastutiH", file_pattern="**/[0-9][0-9]*.md")
  md_files = [f for f in md_files if os.path.basename(f.file_path) ]

  def include_fixer(match):
    return include_helper.alt_include_adder(match=match, source_dir="vishvAsa-prastutiH", alt_dirs=["muller", "thite", "mUlam"])

  for md_file in md_files:
    include_helper.transform_include_lines(md_file=md_file, transformer=include_helper.old_include_remover)
    include_helper.transform_include_lines(md_file=md_file, transformer=include_fixer)
    md_file.transform(content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)


if __name__ == '__main__':
  # migrate_and_include_sUtras()
  fix_includes()
  pass
