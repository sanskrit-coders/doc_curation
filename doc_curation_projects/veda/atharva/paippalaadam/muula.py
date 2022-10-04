import os
from pathlib import Path
from doc_curation_projects.veda.atharva import paippalaadam

import regex

from indic_transliteration import sanscript
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import details_helper, include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import combination, arrangement, metadata_helper, content_helper
from doc_curation.utils import patterns, text_utils


def import_from_wiki_dump(src_dir=paippalaadam.CONTENT_DIR):
  PATTERN_RK = "\n[^#\s<>\[\(][\s\S]+? ॥ *[०-९\d\.]+ *॥\s*?(?=\n|$)"
  def replacement_maker(text_matched, dest_path):
    return text_matched
  # library.apply_function(fn=include_helper.migrate_and_replace_texts, text_patterns=[PATTERN_RK], dir_path=paippalaadam.CONTENT_DIR, replacement_maker=replacement_maker, dry_run=False)


def set_gretil():
  library.apply_function(fn=metadata_helper.add_init_words_to_title, num_words=3, dir_path=paippalaadam.MULA_DIR)
  library.apply_function(fn=metadata_helper.set_filename_from_title, dir_path=paippalaadam.MULA_DIR)
  library.apply_function(fn=MdFile.transform, dir_path=paippalaadam.MULA_DIR, content_transformer=lambda c, m: details_helper.wrap_into_detail(c, title="मूलम् (GR)"))

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
  dir_path = paippalaadam.MULA_DIR
  # library.apply_function(fn=metadata_helper.add_init_words_to_title, num_words=2, dir_path=dir_path, file_name_filter=lambda x: not os.path.basename(x).startswith("_")) 
  # library.apply_function(dir_path=dir_path, fn=metadata_helper.set_filename_from_title, source_script=sanscript.DEVANAGARI, file_name_filter=lambda x: not os.path.basename(x).startswith("_"), dry_run=dry_run)
  # 
  # metadata_helper.copy_metadata_and_filename(dest_dir=paippalaadam.TIKA_DIR, ref_dir=paippalaadam.MULA_DIR, dry_run=dry_run)
  metadata_helper.copy_metadata_and_filename(dest_dir=os.path.join(paippalaadam.MULA_DIR, "../vishvAsa-prastutiH"), ref_dir=paippalaadam.MULA_DIR, dry_run=dry_run)


def copy_to_vishvas(dry_run=False):
  content_helper.copy_contents(src_dir=paippalaadam.MULA_DIR, dest_dir=paippalaadam.MULA_DIR.replace("mUlam", "vishvAsa-prastutiH"), detail_title="मूलम् (GR)", dest_content_condition=lambda x: not text_utils.detect_vishvaasa_mods(content=x)[0], dry_run=dry_run)

def copy_to_tiikaas(dry_run=False):
  content_helper.copy_contents(src_dir=paippalaadam.MULA_DIR, dest_dir=paippalaadam.TIKA_DIR, detail_title="मूलम् (GR)", dest_content_condition=lambda x: not text_utils.detect_vishvaasa_mods(content=x)[0], dry_run=dry_run)
  library.apply_function(fn=content_processor.replace_texts, dir_path=paippalaadam.TIKA_DIR, patterns=[".+"], replacement="")


if __name__ == '__main__':
  pass
  # set_gretil()
  # fix_typos()
  copy_to_vishvas(dry_run=False)
  copy_to_tiikaas(dry_run=False)
  # fix_names(dry_run=False)
