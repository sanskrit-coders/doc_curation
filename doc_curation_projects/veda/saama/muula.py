import os
from pathlib import Path
from doc_curation_projects.veda import saama

import regex

from indic_transliteration import sanscript
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import combination, arrangement, metadata_helper, content_helper
from doc_curation.utils import patterns, text_utils


def fix_names(dry_run=False):
  pass

  dir_path = saama.MULA_DIR
  # library.apply_function(fn=metadata_helper.add_init_words_to_title, num_words=2, dir_path=dir_path, file_name_filter=lambda x: not os.path.basename(x).startswith("_")) 
  # library.apply_function(dir_path=dir_path, fn=metadata_helper.set_filename_from_title, source_script=sanscript.DEVANAGARI, file_name_filter=lambda x: not os.path.basename(x).startswith("_"), dry_run=dry_run)
  # 
  # metadata_helper.copy_metadata_and_filename(dest_dir=os.path.join(saama.SAMHITA_DIR_STATIC, "sarvASh_TIkAH"), ref_dir=saama.MULA_DIR, dry_run=dry_run)
  metadata_helper.copy_metadata_and_filename(dest_dir=os.path.join(saama.SAMHITA_DIR_STATIC, "vishvAsa-prastutiH"), ref_dir=saama.MULA_DIR, dry_run=dry_run)


def copy_to_vishvas(dry_run=False):
  content_helper.copy_contents(src_dir=saama.MULA_DIR, dest_dir=saama.MULA_DIR.replace("mUlam", "vishvAsa-prastutiH"), dest_content_condition=lambda x: not text_utils.detect_vishvaasa_mods(content=x)[0], dry_run=dry_run)


if __name__ == '__main__':
  pass
  # copy_to_vishvas(dry_run=False)
  fix_names(dry_run=False)
