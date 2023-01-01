import os

import regex

from doc_curation.md import library
from doc_curation.md.library import combination
from doc_curation.md.content_processor import include_helper


STATIC_ROOT = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/shrautam"
CONTENT_ROOT = STATIC_ROOT.replace("static", "content")

def combine():
  subpaths = ["muller", "thite", ]
  subpaths = [os.path.join(STATIC_ROOT, subpath) for subpath in subpaths]

  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(STATIC_ROOT, "sarvASh_TIkAH"), dry_run=False)


def fix_includes():
  include_helper.include_core_with_commentaries(dir_path=os.path.join(CONTENT_ROOT, "sarva-prastutiH"), file_pattern="**/[0-9][0-9]*.md", alt_dirs=["mUlam", "sarvASh_TIkAH"], source_dir="vishvAsa-prastutiH")


if __name__ == '__main__':
  # combine()
  fix_includes()
  pass
