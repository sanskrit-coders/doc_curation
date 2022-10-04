import logging
import os
import shutil

import regex

from curation_utils import file_helper

from curation_utils.file_helper import get_storage_name
from doc_curation.md import content_processor
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript
from doc_curation.utils import text_utils


def copy_contents(src_dir, dest_dir, detail_title=None, dest_content_condition=None, create_missing_files=True, dry_run=False):
  from doc_curation.md.library import arrangement
  sub_path_to_reference = arrangement.get_sub_path_to_reference_map(ref_dir=src_dir, sub_path_id_maker=None)
  src_md_files = arrangement.get_md_files_from_path(dir_path=src_dir)
  skipped_files = {}
  repalced_content_count = 0
  for src_md_file in src_md_files:
    path_suffix = regex.sub(f"{src_dir}/*(.+)", r"\1", src_md_file.file_path)
    dest_md_file = MdFile(file_path=os.path.join(dest_dir, path_suffix))
    (metadata_src, content_src) = src_md_file.read()
    if not os.path.exists(dest_md_file.file_path):
      if not create_missing_files:
        logging.info(f"Skipping {path_suffix} - Dest file missing.")
        continue
      else:
        dest_md_file.dump_to_file(metadata=metadata_src, content="", dry_run=dry_run)
    (metadata_dest, content_dest) = dest_md_file.read()
    score = text_utils.normalized_edit_distance(a=content_dest, b=content_src, strip_svaras=False)
    if score == 0:
      continue
    if dest_content_condition is not None and not dest_content_condition(content_dest):
      reg = lambda x: x.replace('\n', ' ')
      skipped_files[path_suffix] = f"{score}\n{reg(content_src)}\n{reg(content_dest)}" 
      logging.info(f"Skipping {path_suffix} - Condition not met.\n{skipped_files[path_suffix]}")
      continue
    if detail_title is not None:
      from doc_curation.md.content_processor import details_helper
      (tag, detail) = details_helper.get_detail(content=content_src, metadata=metadata_src, title=detail_title)
      new_content = detail.content
    else:
      new_content = content_src
    dest_md_file.replace_content_metadata(new_content=new_content, dry_run=dry_run)
    repalced_content_count += 1
  logging.info(f"Skipped {len(skipped_files)} files:\n{skipped_files}")

