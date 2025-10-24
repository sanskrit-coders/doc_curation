import logging
import os
import pathlib
import shutil
from functools import lru_cache

import regex

from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper, get_md_files_from_path
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


def shift_contents(dir_path, substitute_content_offset, start_index=None, end_index=None, index_position=0, replacer=lambda md_file, content: md_file.replace_content_metadata(new_content=content, dry_run=False)):
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
        replacer(md_file, content)


def shift_details(dir_path, substitute_content_offset, detail_title, start_index=None, end_index=None, index_position=0, dry_run=False):
  from doc_curation.md.content_processor import details_helper
  def replacer(md_file, content):
    (_, detail) = details_helper.get_detail(content=content, metadata={}, title=detail_title)
    (metadata, md_content) = md_file.read()
    (detail_tag, md_detail) = details_helper.get_detail(content=content, metadata={}, title=detail_title)
    if md_detail is None:
      md_detail.content = detail.content
      md_file.transform(content_transformer=lambda c, *args, **kwargs: f"{c}\n\n{md_detail.to_md_html()}", dry_run=dry_run)
    else:
      md_file.transform(content_transformer=lambda c, *args, **kwargs: details_helper.transform_details_with_soup(content=c, metadata=m, content_str_transformer=details_helper.detail_content_replacer_soup, title=detail_title, replacement=detail.content), dry_run=dry_run)

  shift_contents(dir_path=dir_path, substitute_content_offset=substitute_content_offset, start_index=start_index, end_index=end_index, index_position=index_position, replacer=replacer)


def shift_indices(dir_path, new_index_offset, start_index=1, end_index=9999, index_position=0, dry_run=False):
  files = [os.path.join(dir_path, x) for x in os.listdir(dir_path) if x != "_index.md" and x.endswith(".md")]
  files.sort()
  index_to_md_file = get_index_to_md(dir_path=dir_path, index_position=index_position)
  for index, md_file in index_to_md_file.items():
    if start_index <= index and end_index >= index:
      new_index = index + new_index_offset
      name_parts = os.path.basename(md_file.file_path).split(".")[0].split("_")
      index_pattern = "%%0%dd" % len(name_parts[index_position])
      name_parts[index_position] = index_pattern % new_index
      new_file_path = os.path.join(os.path.dirname(md_file.file_path), "_".join(name_parts) + ".md")
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

def get_md_level(md_path, base_dir):
  md_path = str(md_path)
  if base_dir is not None:
    md_path = md_path.replace(base_dir, "")
  parts = [x for x in md_path.split("/") if x != ""]
  if parts[-1] == "_index.md":
    return len(parts) - 1
  else:
    return len(parts)


def get_sub_path_id(sub_path, basename_id_pattern=r"(.+?)(?=[_\.]|$)"):
  """ /1/2/3/4.md -> 1/2/3/4
  
  :param sub_path: 
  :param basename_id_pattern: 
  :return: 
  """
  id_parts = []
  for name in sub_path.split("/"):
    if name == "":
      continue
    elif name == "_index.md":
      # id_parts.append(name)
      pass
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
    md_file = MdFile(file_path=file_path)
    (index, basename) = md_file.get_index_basename()
    if index is not None:
      index_to_md_file[index] = md_file
  return index_to_md_file


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
        

def make_include_files(dest_dir, source_dir, start_index=None, end_index=None, dry_run=False):
  files = [os.path.join(source_dir, x) for x in os.listdir(source_dir) if x != "_index.md" and x.endswith(".md")]
  files.sort()
  index_to_md_file = get_index_to_md(dir_path=source_dir, index_position=0)

  dest_files = [os.path.join(dest_dir, x) for x in os.listdir(source_dir) if x != "_index.md" and x.endswith(".md")]
  dest_files.sort()
  index_to_md_file_dest = get_index_to_md(dir_path=dest_dir, index_position=0)
  start_index_dest = max(list(index_to_md_file_dest.keys()) + [0]) + 1
  for index, md_file in index_to_md_file.items():
    if (start_index is None or start_index <= index) and (end_index is None or end_index >= index):
      dest_index = index - start_index + start_index_dest
      (_, basename) = md_file.get_index_basename()
      base_name_dest = f"{dest_index:02d}" 
      if basename != "":
        base_name_dest = f"{base_name_dest}_{basename}"
      else:
        base_name_dest = f"{base_name_dest}.md"
      md_file_dest = MdFile(file_path=os.path.join(dest_dir, base_name_dest))
      (metadata, content) = md_file.read()
      index_str = sanscript.transliterate(f"{dest_index:02d}", _to=sanscript.DEVANAGARI, _from=sanscript.IAST)
      metadata["title"] = f"{index_str} {md_file.get_title()}"
      url = md_file.file_path.replace("/home/vvasuki/gitland/vishvAsa/", "/").replace("/static/", "/").replace("/content/", "/").replace("_index.md", "").replace(".md", "")
      md = f'<div class="js_include" url="{url}"  newLevelForH1="1" includeTitle="true">\n\n{content}\n</div>'
      md_file_dest.dump_to_file(metadata=metadata, content=md, dry_run=dry_run)


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


def fix_mistaken_nines(dir_path, digit_from_last=1, iterations=20):
  # Consider the sequence of files listed in alphanumerical order - 057_31.md, 058_32.md, 059_33.md, 060_33.md, 061_34.md, 062_35.md, 063_34.md, 064_36.md, 065_37.md, 066_36.md, 067_37.md, 068_38.md, 069_38.md, 070_38.md, 071_36.md, 072_40.md.  
  # In a given filename, where the last digit in the base name is 6, if it preceeds a file with basename ending with 0 or 9, the 6 in that filename should be replaced with 9. 
  
  for iteration in range(iterations):
    # Get a list of all files in the directory
    files = os.listdir(dir_path)
  
    # Sort the files in alphanumerical order
    files.sort()
    # Iterate through the files
    for i in range(len(files)):
      # Skip the first and last files
      if i == 0 or i == len(files) - 1:
        continue
  
      # Get the current and next filenames
      curr_file = files[i]
      next_file = files[i+1]
  
      # Extract the base names of the files
      curr_base = os.path.splitext(curr_file)[0]
      next_base = os.path.splitext(next_file)[0]
  
      # Check if the last digit of the current file is 6
      digit = curr_base[-digit_from_last]
      if digit == '6':
        next_file_digit = next_base[-digit_from_last]
        # Check if the next file ends with 0 or 9
        if next_file_digit == '0' or next_file_digit == '9':
          # Replace the 6 with 9 in the current filename
          new_base = curr_base[:-digit_from_last] + '9' + curr_base[-(digit_from_last-1):]  # Replace only nth digit
          new_file = new_base + os.path.splitext(curr_file)[1]
          new_path = os.path.join(dir_path, new_file)
          curr_path = os.path.join(dir_path, curr_file)
          os.rename(curr_path, new_path)
          logging.info(f"Renamed {curr_file} to {new_file}")


def highlight_out_of_order_files(dir_path, id_pattern=r".+_(\d+)\.", fix_sequence="No"):
  # Get a list of all files in the directory
  files = os.listdir(dir_path)

  # Sort the files in alphanumerical order
  files.sort()
  out_of_order_files = []
  # Iterate through the files
  for i in range(len(files)):
    # Skip the first and last files
    if i == 0:
      continue

    # Get the current and next filenames
    curr_file = files[i]
    prev_file = files[i-1]

    if regex.match(id_pattern, curr_file) and regex.match(id_pattern, prev_file):
      curr_id = int(regex.match(id_pattern, curr_file).group(1))
      prev_id = int(regex.match(id_pattern, prev_file).group(1))
      if curr_id < prev_id:
        out_of_order_files.append(curr_file)
        if fix_sequence != "No":
          new_file = curr_file.split("_")[0] + "_" + str(prev_id) + ".md"
          new_path = os.path.join(dir_path, new_file)
          curr_path = os.path.join(dir_path, curr_file)
          logging.info(f"Renamed {curr_file} to {new_file}")
          if fix_sequence != "dry_run":
            os.rename(curr_path, new_path)
        
  logging.warning(f"{out_of_order_files} are out of order")
  return out_of_order_files



def stage_md_files(source_dir, tmp_path: pathlib.Path):
  md_files = sorted(
    list(pathlib.Path(source_dir).rglob("*.md"))
  )
  # Copy MD files to tmp directory
  for md_file in md_files:
    # Keep same relative path under tmp directory
    rel_path = md_file.relative_to(source_dir)
    dest_path = tmp_path / rel_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(md_file.read_text(), encoding="utf-8")


def natural_sort_key(s):
  s = str(s)
  base = os.path.basename(s)
  if base == "_index.md":
    base = f"00__{base}"
  else:
    base = f"01__{base}"
  key = [os.path.dirname(s), base]
  return key


def rename_subfolders(ref_map, dest_path='.', dry_run=True, ref_map_mode=None):
  """
  Rename subfolders.
  
  Args:
      ref_map: ALERT - ensure top level folders appear later!
      dest_path (str): Base directory containing the numbered folders
      dry_run (bool): If True, show what would be renamed without actually renaming 
  Returns:
      dict: Dictionary with 'success', 'failed', and 'skipped' lists
  """
  dest_path = str(pathlib.Path(dest_path).absolute()) + "/"

  if isinstance(ref_map, str):
    if not ref_map.endswith("/"):
      ref_map = ref_map + "/"
    dirs = [x[0].replace(ref_map, "") for x in os.walk(ref_map) if "/." not in x[0]]
    ref_map = {get_sub_path_id(x): x for x in dirs}


  for dirpath, dirnames, filenames in os.walk(dest_path, topdown=False):
    sub_path = dirpath.replace(dest_path, "")
    id = get_sub_path_id(sub_path)
    target_subpath = ref_map.get(id, None)
    if target_subpath is None:
      logging.info(f"Skipping {dirpath}")
      continue
    if ref_map_mode == "basedir":
      target_subpath = os.path.basename(target_subpath)
      target_path = os.path.join(os.path.dirname(dirpath), target_subpath)
    else:
      target_path = os.path.join(dest_path, target_subpath)
    if dirpath != target_path:
      if not dry_run:
        os.rename(dirpath, target_path)
        md_path = os.path.join(target_path, "_index.md")
        if os.path.exists(md_path):
          md_file = MdFile(md_path) 
          metadata_helper.set_title_from_filename(md_file)
      logging.info(f"✓ RENAMED:\n  {dirpath} → {target_path}")
