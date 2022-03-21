import glob
import logging
import os
import shutil

from curation_projects.raamaayana import get_adhyaaya_id

from doc_curation.md.file import MdFile


def fix_title_names(base_dir, base_dir_ref, dry_run=False):
  paths = glob.glob(base_dir + "/**/*.md", recursive=True)
  paths = [path for path in paths if os.path.basename(path) != "_index.md"]
  paths_ref = glob.glob(base_dir_ref + "/**/*.md", recursive=True)
  sarga_id_to_path = {}

  for p in paths_ref:
    sarga_id = get_adhyaaya_id(p)
    if sarga_id is not None:
      sarga_id_to_path[sarga_id] = p

  for p in paths:
    sarga_id = get_adhyaaya_id(p)
    ref_md_path = sarga_id_to_path.get(sarga_id, None)
    if ref_md_path is None:
      continue
    dest_path = ref_md_path.replace(base_dir_ref, base_dir)
    logging.info("Moving to %s from %s", dest_path, p)
    if not dry_run:
      os.makedirs(os.path.dirname(dest_path), exist_ok=True)
      shutil.move(p, dest_path)
      ref_md_file = MdFile(file_path=ref_md_path)
      [metadata, _] = ref_md_file.read()
      md_file = MdFile(file_path=dest_path)
      [_, content] = md_file.read()
      md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)


