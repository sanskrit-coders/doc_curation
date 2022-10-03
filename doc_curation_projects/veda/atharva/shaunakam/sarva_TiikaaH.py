import os
from pathlib import Path
from doc_curation_projects.veda.atharva import shaunakam

import regex

from indic_transliteration import sanscript
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import combination, arrangement, metadata_helper
from doc_curation.utils import patterns

STATIC_ROOT = shaunakam.STATIC_ROOT


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


def fix_padapaatha():
  # library.apply_function(fn=MdFile.transform, dir_path=shaunakam.TIKA_DIR, content_transformer=lambda c, m: details_helper.transform_details_with_soup(content=c, metadata=m, transformer=details_helper.detail_content_replacer_soup, title="पदपाठः", replacement=lambda x: x.replace(":", "ः")))
  library.apply_function(fn=MdFile.transform, dir_path=shaunakam.TIKA_DIR, content_transformer=lambda c, m: details_helper.transform_details_with_soup(content=c, metadata=m, transformer=details_helper.detail_content_replacer_soup, title="पदपाठः", replacement=lambda x: regex.sub(f"([यव]{patterns.DEVANAGARI_MATRA_YOGAVAHA}*)", r"\1᳡", x)))
  library.apply_function(fn=MdFile.transform, dir_path=shaunakam.TIKA_DIR, content_transformer=lambda c, m: details_helper.transform_details_with_soup(content=c, metadata=m, transformer=details_helper.detail_content_replacer_soup, title="पदपाठः", replacement=lambda x: regex.sub("᳡([ःं])", r"\1᳡", x)))


def fix_typos():
  library.apply_function(fn=content_processor.replace_texts, dir_path=shaunakam.TIKA_DIR, patterns=["details open"], replacement="details")

# Griffith Name: Comment

if __name__ == '__main__':
  pass
  # insert_anukramaNis()
  # fix_padapaatha()
  fix_typos()