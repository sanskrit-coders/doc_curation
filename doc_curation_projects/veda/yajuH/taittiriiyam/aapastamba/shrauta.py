import os

import regex

from doc_curation.md import library
from doc_curation.md.content_processor import include_helper


def fix_includes():
  include_helper.include_core_with_commentaries(dir_path="/home/vvasuki/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/shrautam/sarva-prastutiH", file_pattern="**/[0-9][0-9]*.md", alt_dirs=["muller", "thite", "mUlam"], source_dir="vishvAsa-prastutiH")


if __name__ == '__main__':
  # migrate_and_include_sUtras()
  fix_includes()
  pass
