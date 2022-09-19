import os
from pathlib import Path
from doc_curation_projects.veda import atharva

import regex

from indic_transliteration import sanscript
from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import combination, arrangement, metadata_helper
from doc_curation.utils import patterns


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


def fix_padapaatha():
  # library.apply_function(fn=MdFile.transform, dir_path=atharva.TIKA_DIR, content_transformer=lambda c, m: details_helper.transform_details_with_soup(content=c, metadata=m, transformer=details_helper.detail_content_replacer_soup, title="पदपाठः", replacement=lambda x: x.replace(":", "ः")))
  library.apply_function(fn=MdFile.transform, dir_path=atharva.TIKA_DIR, content_transformer=lambda c, m: details_helper.transform_details_with_soup(content=c, metadata=m, transformer=details_helper.detail_content_replacer_soup, title="पदपाठः", replacement=lambda x: regex.sub(f"([यव]{patterns.DEVANAGARI_MATRA_YOGAVAHA}*)", r"\1᳡", x)))
  library.apply_function(fn=MdFile.transform, dir_path=atharva.TIKA_DIR, content_transformer=lambda c, m: details_helper.transform_details_with_soup(content=c, metadata=m, transformer=details_helper.detail_content_replacer_soup, title="पदपाठः", replacement=lambda x: regex.sub("᳡([ःं])", r"\1᳡", x)))


def fix_names(dry_run=False):
  pass
  # dir_path = os.path.join(STATIC_ROOT, "mUlam/10/005_vijayaprAptiH")
  # arrangement.shift_indices(dir_path=dir_path, start_index=20, new_index_offset=-1, dry_run=dry_run)
  # library.apply_function(dir_path=dir_path, fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=dry_run)
  # library.apply_function(fn=metadata_helper.add_init_words_to_title, num_words=2, dir_path=dir_path) 
  # library.apply_function(dir_path=dir_path, fn=metadata_helper.set_filename_from_title, source_script=sanscript.DEVANAGARI, dry_run=dry_run)

  # dir_path = os.path.join(STATIC_ROOT, "mUlam/10/008_jyeShThabrahmavarNanam")
  # arrangement.shift_indices(dir_path=dir_path, start_index=29, new_index_offset=-1, dry_run=dry_run)
  # arrangement.shift_indices(dir_path=dir_path, start_index=42, new_index_offset=-1, dry_run=dry_run)
  # library.apply_function(dir_path=dir_path, fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=dry_run)
  dir_path = atharva.MULA_DIR
  # library.apply_function(fn=metadata_helper.add_init_words_to_title, num_words=2, dir_path=dir_path, file_name_filter=lambda x: not os.path.basename(x).startswith("_")) 
  # library.apply_function(dir_path=dir_path, fn=metadata_helper.set_filename_from_title, source_script=sanscript.DEVANAGARI, file_name_filter=lambda x: not os.path.basename(x).startswith("_"), dry_run=dry_run)
  # 
  metadata_helper.copy_metadata_and_filename(dest_dir=os.path.join(STATIC_ROOT, "sarvASh_TIkAH"), ref_dir=atharva.MULA_DIR, dry_run=dry_run)
  metadata_helper.copy_metadata_and_filename(dest_dir=os.path.join(STATIC_ROOT, "vishvAsa-prastutiH"), ref_dir=atharva.MULA_DIR, dry_run=dry_run)


if __name__ == '__main__':
  pass
  fix_names(dry_run=False)
  # insert_anukramaNis()
  # fix_padapaatha()