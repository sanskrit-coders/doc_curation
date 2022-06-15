import os
from pathlib import Path

import regex

from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import combination, arrangement

STATIC_ROOT = "/home/vvasuki/vishvAsa/vedAH/static/atharva/shaunakam/rUDha-saMhitA"

def combine():
  subpaths = ["whitney/notes", "griffith", ]
  subpaths = [os.path.join(STATIC_ROOT, subpath) for subpath in subpaths]

  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(STATIC_ROOT, "sarvASh_TIkAH"), dry_run=False)


def insert_anukramaNis():
  # md_file_paths = sorted(Path(os.path.join(STATIC_ROOT, "whitney/anukramaNikA")).glob("**/*.md"))
  # arrangement.migrate(files=md_file_paths, location_computer=lambda x: x.replace(".md", "/_index.md"))
  # md_file_paths = sorted(Path(os.path.join(STATIC_ROOT, "info_vh")).glob("**/*.md"))
  # arrangement.migrate(files=md_file_paths, location_computer=lambda x: x.replace(".md", "/_index.md"))
  subpaths = ["info_vh", "whitney/anukramaNikA", ]
  subpaths = [os.path.join(STATIC_ROOT, subpath) for subpath in subpaths]

  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(STATIC_ROOT, "sarvASh_TIkAH"), mode="prepend", dry_run=False)


if __name__ == '__main__':
  pass
  insert_anukramaNis()