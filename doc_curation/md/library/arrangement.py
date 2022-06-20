import logging
import os
import shutil
from functools import lru_cache

import regex

from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


def defolderify_single_md_dirs(dir_path, dry_run=False):
  while dir_path.endswith("/"):
    dir_path = dir_path[:-1]
  contents = os.listdir(dir_path)
  for possible_subdir in contents:
    subpath = os.path.join(dir_path, possible_subdir)
    if os.path.isdir(subpath):
      defolderify_single_md_dirs(dir_path=subpath, dry_run=dry_run)
  if len(contents) != 1:
    return
  if not contents[0] == "_index.md":
    return 
  index_file_path = os.path.join(dir_path, contents[0])
  dest_file_path = dir_path + ".md"
  logging.info("Moving %s to %s", str(index_file_path), dest_file_path)
  if not dry_run:
    os.rename(src=index_file_path, dst=dest_file_path)
    md_file = MdFile(file_path=dest_file_path)
    (metadata, _) = md_file.read()
    title = metadata["title"]
    if title.startswith("+"):
      title = title[1:]
    md_file.set_title(title=title, dry_run=False)
    os.rmdir(dir_path)


def shift_contents(dir_path, substitute_content_offset, start_index=None, end_index=None, index_position=0, dry_run=False):
  files = [os.path.join(dir_path, x) for x in os.listdir(dir_path) if x != "_index.md" and x.endswith(".md")]
  files.sort()
  index_to_content_original = {}
  index_to_md_file = get_index_to_md(dir_path=dir_path, index_position=index_position)

  for index, md_file in index_to_md_file.items():
    (_, content) = md_file.read()
    index_to_content_original[index] = content

  min_index = min(index_to_content_original.keys())
  max_index = max(index_to_content_original.keys())
  if start_index is None:
    start_index = min_index
  if end_index is None:
    end_index = max_index
  for index, content in index_to_content_original.items():
    if start_index <= index and end_index >= index:
      offset_index = index + substitute_content_offset
      logging.info("Shifting %d to %d", offset_index, index)
      if offset_index in index_to_content_original.keys():
        content = index_to_content_original[offset_index]
        md_file = index_to_md_file[index]
        md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


def shift_indices(dir_path, new_index_offset, start_index=1, end_index=9999, index_position=0, dry_run=False):
  files = [os.path.join(dir_path, x) for x in os.listdir(dir_path) if x != "_index.md" and x.endswith(".md")]
  files.sort()
  index_to_md_file = get_index_to_md(dir_path=dir_path, index_position=index_position)
  for index, md_file in index_to_md_file.items():
    if start_index <= index and end_index >= index:
      new_index = index + new_index_offset
      name_parts = os.path.basename(md_file.file_path).split("_")
      index_pattern = "%%0%dd" % len(name_parts[index_position])
      name_parts[index_position] = index_pattern % new_index
      new_file_path = os.path.join(os.path.dirname(md_file.file_path), "_".join(name_parts))
      logging.info("Shifting %d to %d, %s to %s", index, new_index, md_file.file_path, new_file_path)
      if not dry_run:
        shutil.move(md_file.file_path, new_file_path)


def remove_file_by_index(dir_path, indices, index_position=0):
  index_to_md_file = get_index_to_md(dir_path=dir_path, index_position=index_position)
  for index, md_file in index_to_md_file.items():
    if index in indices:
      os.remove(md_file.file_path)


@lru_cache(maxsize=2)
def get_sub_path_to_reference_map(ref_dir, sub_path_id_maker=None):
  ref_md_files = get_md_files_from_path(dir_path=ref_dir)
  sub_path_to_reference = {}
  if sub_path_id_maker is None:
    sub_path_id_maker = lambda x: get_sub_path_id(sub_path=str(x).replace(ref_dir, ""))
  for md_file in ref_md_files:
    sub_path_id = sub_path_id_maker(md_file.file_path)
    if sub_path_id is not None:
      sub_path_to_reference[sub_path_id] = md_file
  return sub_path_to_reference


def get_sub_path_id(sub_path, basename_id_pattern=r"(.+?)(?=[_\.]|$)"):
  id_parts = []
  for name in sub_path.split("/"):
    if name == "":
      continue
    elif name == "_index.md":
      id_parts.append(name)
    else:
      base_id_match = regex.search(basename_id_pattern, name)
      if base_id_match is None:
        logging.fatal("No match in %s", sub_path)
      id_parts.append(base_id_match.group(1))
  return "/".join(id_parts)


def get_index_to_md(dir_path, index_position=0):
  files = [os.path.join(dir_path, x) for x in os.listdir(dir_path) if x != "_index.md" and x.endswith(".md")]
  files.sort()
  index_to_md_file = {}
  for index, file_path in enumerate(files):
    base_name = os.path.basename(file_path)
    try:
      index = int(base_name.replace(".md", "").split("_")[index_position])
    except ValueError:
      logging.warning(f"Skipping file with irregular index- {file_path}")
    md_file = MdFile(file_path=file_path)
    index_to_md_file[index] = md_file
  return index_to_md_file


def get_md_files_from_path(dir_path, file_pattern="**/*.md", file_name_filter=lambda x: True):
  from pathlib import Path
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  md_file_paths = sorted(filter(file_name_filter, Path(dir_path).glob(file_pattern)))
  md_file_paths = [f for f in md_file_paths if os.path.isfile(f)]
  return [MdFile(path) for path in md_file_paths]


def migrate(files, location_computer, dry_run=False):
  """Migrate a bunch of files to a new location (dynamically computed by location_computer function.)"""
  logging.info("Processing %d files", len(files))
  for f in files:
    new_path = location_computer(str(f))
    if new_path is not None:
      logging.info("Moving %s to %s", str(f), new_path)
      if not dry_run:
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        os.rename(src=f, dst=new_path)


def fix_index_files(dir_path, frontmatter_type=MdFile.TOML, transliteration_target=sanscript.DEVANAGARI, overwrite=False, dry_run=False):
  logging.info("Fixing index files")
  # Get all non hidden directories.
  dirs = [x[0] for x in os.walk(dir_path) if "/." not in x[0]]
  # set([os.path.dirname(path) for path in Path(dir_path).glob("**/")])
  for dir in dirs:
    index_file = MdFile(file_path=os.path.join(dir, "_index.md"), frontmatter_type=frontmatter_type)
    if not os.path.exists(index_file.file_path):
      index_file.dump_to_file(metadata={}, content="", dry_run=dry_run)
      metadata_helper.set_title_from_filename(index_file, transliteration_target=transliteration_target, dry_run=dry_run)
    elif overwrite:
      metadata_helper.set_title_from_filename(index_file, transliteration_target=transliteration_target, dry_run=dry_run)


def get_parent_md(md_file):
  if os.path.basename(md_file.file_path) == "_index.md":
    parent_dir = os.path.dirname(os.path.dirname(md_file.file_path))
  else:
    parent_dir = os.path.dirname(md_file.file_path)
  file_path = os.path.join(parent_dir, "_index.md")
  if os.path.exists(file_path):
    return MdFile(file_path=file_path)
  else:
    return None


def migrate_and_include(files, location_computer, new_url_computer, dry_run=False):
  """Migrate contents of a given file to a new location and include it in the original file"""
  logging.info("Processing %d files", len(files))
  migrate(files=files, location_computer=location_computer)
  for f in files:
    md_file = MdFile(file_path=f)
    (metadata, _) = md_file.read()
    md = """<div class="js_include" url="%s"  newLevelForH1="1" includeTitle="true"> </div>""" % new_url_computer(str(f))
    logging.info("Inclusion in old file : %s", md)
    md_file.dump_to_file(metadata=metadata, content=md, dry_run=dry_run)
