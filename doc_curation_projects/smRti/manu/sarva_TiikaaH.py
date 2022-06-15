import os
from pathlib import Path

import regex

from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import combination, arrangement

STATIC_ROOT = "/home/vvasuki/vishvAsa/kalpAntaram/static/smRtiH/manuH"

def combine():
  subpaths = ["gangAnatha-mUlAnuvAdaH", "medhAtithiH", "gangAnatha-bhAShyAnuvAdaH", "gangAnatha-TippanyaH", "gangAnatha-tulya-vAkyAni", "kullUkaH", "bhAruchiH", "buhler"]
  subpaths = [os.path.join(STATIC_ROOT, subpath) for subpath in subpaths]

  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(STATIC_ROOT, "sarvASh_TIkAH"), dry_run=False)


if __name__ == '__main__':
  pass
  combine()