import os
from pathlib import Path
from doc_curation_projects.veda.atharva import shaunakam

import regex

from indic_transliteration import sanscript
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import combination, arrangement, metadata_helper, content_helper
from doc_curation.utils import patterns, text_utils


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
  dir_path = shaunakam.MULA_DIR
  # library.apply_function(fn=metadata_helper.add_init_words_to_title, num_words=2, dir_path=dir_path, file_name_filter=lambda x: not os.path.basename(x).startswith("_")) 
  # library.apply_function(dir_path=dir_path, fn=metadata_helper.set_filename_from_title, source_script=sanscript.DEVANAGARI, file_name_filter=lambda x: not os.path.basename(x).startswith("_"), dry_run=dry_run)
  # 
  # metadata_helper.copy_metadata_and_filename(dest_dir=shaunakam.TIKA_DIR, ref_dir=shaunakam.MULA_DIR, dry_run=dry_run)
  metadata_helper.copy_metadata_and_filename(dest_dir=os.path.join(shaunakam.MULA_DIR, "../vishvAsa-prastutiH"), ref_dir=shaunakam.MULA_DIR, dry_run=dry_run)
  

def copy_to_vishvas(dry_run=False):
  content_helper.copy_contents(src_dir=shaunakam.MULA_DIR, dest_dir=shaunakam.MULA_DIR.replace("mUlam", "vishvAsa-prastutiH"), detail_title="मूलम् (VS)", dest_content_condition=lambda x: not text_utils.detect_vishvaasa_mods(content=x)[0], dry_run=dry_run)


if __name__ == '__main__':
  pass
  # fix_typos()
  copy_to_vishvas(dry_run=False)
  # fix_names(dry_run=False)
