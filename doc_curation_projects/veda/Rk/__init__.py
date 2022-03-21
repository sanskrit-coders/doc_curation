import glob
import logging
import os
from functools import lru_cache

import regex

from doc_curation.md.file import MdFile


SAMHITA_DIR_STATIC = "/home/vvasuki/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/"
comment_dirs = ["vishvAsa-prastutiH", "mUlam", "pada-pAThaH", "anukramaNikA", "sAyaNa-bhAShyam",  "jamison_brereton", "griffith", "wilson", "hellwig_grammar"]


@lru_cache
def get_Rk_id_to_name_map_from_muulam():
  Rk_paths = glob.glob(os.path.join(SAMHITA_DIR_STATIC, "mUlam/*/*/*.md"), recursive=True)
  Rk_paths = sorted(Rk_paths)
  Rk_id_to_name_map = {}
  for Rk_path in Rk_paths:
    Rk_name = os.path.basename(Rk_path).replace(".md", "")
    Rk_id_numerical = "/".join(Rk_path.split("/")[-3:-1]) + "/" + Rk_name.split("_")[0]
    Rk_id_to_name_map[Rk_id_numerical] = Rk_name
  return Rk_id_to_name_map


def fix_Rk_file_names(dest_path, ignore_missing=False, dry_run=True):
  Rk_id_to_name_map = get_Rk_id_to_name_map_from_muulam()
  fix_dir_names(dest_path)
  for id in Rk_id_to_name_map.keys():
    id_parts = id.split("/")
    Rk_number_str = id_parts[-1].split("_")[0]
    suukta_number_str = id_parts[-2].split("_")[0]
    mandala_number_str = id_parts[-3].split("_")[0]
    sUkta_id = "/".join([mandala_number_str, suukta_number_str])
    file_path = os.path.join(dest_path, sUkta_id, Rk_number_str + ".md")
    file_path_new = os.path.join(dest_path, "/".join(id.split("/")[:-1]), Rk_id_to_name_map[id] + ".md")
    if os.path.exists(file_path_new):
      logging.info("%s exists. Skipping", file_path_new)
      if os.path.exists(file_path):
        os.remove(file_path)
      # logging.fatal(file_path)
    else:
      if not os.path.exists(file_path):
        if ignore_missing or ("geldner" in dest_path and sUkta_id in ["01/070"]):
          continue
        else:
          logging.fatal("Could not find %s at %s", id, file_path)
          exit()
      logging.info("Moving %s to %s", file_path, file_path_new)
      if not dry_run:
        os.rename(file_path, file_path_new)


def fix_dir_names(dir_path, dry_run=False):
  def fix_dir_paths(dir_paths):
    for old_path in dir_paths:
      old_path = os.path.normpath(old_path)
      basename = os.path.basename(old_path)
      new_path = os.path.join(os.path.dirname(old_path), basename.split("_")[0])
      if new_path != old_path:
        logging.info("Moving %s to %s", old_path, new_path)
        if not dry_run:
          os.rename(old_path, new_path)
  
  dir_paths = glob.glob(f'{dir_path}/*/', recursive=False)
  fix_dir_paths(dir_paths=dir_paths)
  dir_paths = glob.glob(f'{dir_path}/*/*/', recursive=False)
  fix_dir_paths(dir_paths=dir_paths)


def include_multi_file_comments(multi_file_comment_path_pattern, file_range_regex, target_file_computer, include_generator, dry_run=True):
  multi_file_comment_paths = glob.glob(multi_file_comment_path_pattern, recursive=True)
  for multi_file_comment_path in multi_file_comment_paths:
    multi_file_basename = os.path.basename(multi_file_comment_path)
    match = regex.match(file_range_regex, multi_file_basename)
    file_start = int(match.group(1))
    file_end = int(match.group(2))
    file_id_format = "%%0%dd" % len(match.group(1))
    for file_id in range(file_start, file_end + 1):
      file_id_str = file_id_format % file_id
      target_file = target_file_computer(multi_file_comment_path, file_id_str)
      logging.info("Will include %s in %s", multi_file_comment_path, target_file)
      md_file = MdFile(file_path=target_file)
      if os.path.exists(target_file):
        (metadata, content) = md_file.read()
      else:
        if target_file.endswith("_index.md"):
          title = "+" + file_id_str
        else:
          title = file_id_str
        (metadata, content) = ({"title": title}, "")
      content = "%s\n\n%s" % (content, include_generator(multi_file_comment_path))
      md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)


def include_multi_Rk_comments(dest_path, include_generator, dry_run=True):
  def Rk_target_file_computer(multi_file_comment_path, file_id_str):
    multi_file_basename = os.path.basename(multi_file_comment_path)
    target_file = os.path.join(os.path.dirname(multi_file_comment_path), "%s.md" % file_id_str)
    dir_files = os.listdir(os.path.dirname(multi_file_comment_path))
    dir_files = [file for file in dir_files if file.startswith(file_id_str) and file != multi_file_basename and "-" not in file]
    if len(dir_files) == 1:
      target_file = os.path.join(os.path.dirname(multi_file_comment_path), dir_files[0])
    return target_file
  
  include_multi_file_comments(multi_file_comment_path_pattern="%s/*/*/[0-9][0-9]-[0-9][0-9]*.md" % dest_path, target_file_computer=Rk_target_file_computer, file_range_regex=r"^(\d\d)-(\d\d).+", include_generator=include_generator, dry_run=dry_run)


def include_multi_suukta_comments(dest_path, include_generator, dry_run=True):
  def suukta_target_file_computer(multi_file_comment_path, file_id_str):
    target_file = os.path.join(os.path.dirname(multi_file_comment_path), "%s/_index.md" % file_id_str)
    return target_file

  include_multi_file_comments(multi_file_comment_path_pattern="%s/*/[0-9][0-9][0-9]-[0-9][0-9][0-9]*.md" % dest_path, target_file_computer=suukta_target_file_computer, file_range_regex=r"^(\d+)-(\d+).+", include_generator=include_generator, dry_run=dry_run)