import glob
import logging
import os
import shutil
from functools import lru_cache
from pathlib import Path

import regex

from curation_utils import file_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


def import_md_recursive(source_dir, file_extension, source_format=None, dry_run=False):
  from pathlib import Path
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  source_paths = sorted(Path(source_dir).glob("**/*." + file_extension))
  if source_format is None:
    source_format = file_extension
  for source_path in source_paths:
    md_path = str(source_path).replace("." + file_extension, ".md")
    md_path = file_helper.clean_file_path(md_path)
    if os.path.exists(md_path):
      logging.info("Skipping %s", md_path)
      continue
    logging.info("Processing %s to %s", source_path, md_path)
    md_file = MdFile(file_path=md_path, frontmatter_type=MdFile.TOML)
    md_file.import_with_pandoc(source_file=source_path, source_format=source_format, dry_run=dry_run)


def make_full_text_md(source_dir, dry_run=False):
  """Create a text - by include-directives - which includes all md files within the directory."""
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  content = ""
  title = "पूर्णपाठः"
  rel_url = "../"

  num_md_files = 0

  index_md_path = os.path.join(source_dir, "_index.md")
  if os.path.exists(index_md_path):
    index_md = MdFile(file_path=index_md_path)
    (index_yml, _) = index_md.read()
    title = "%s (%s)" % (index_yml["title"], title)
    content = "%s\n%s" % (content, """<div class="js_include" url="%s"  newLevelForH1="1" includeTitle="false"> </div>""" % (rel_url).strip())
    num_md_files = num_md_files + 1


  for subfile in sorted(os.listdir(source_dir)):
    subfile_path = os.path.join(source_dir, subfile)
    if os.path.isdir(subfile_path):
      if subfile not in ["images"]:
        make_full_text_md(source_dir=subfile_path)
        sub_md_file_path = os.path.join(subfile, "full.md")
      else:
        continue
    else:
      if subfile in ("full.md", "_index.md") or not str(subfile).endswith(".md"):
        continue
      sub_md_file_path = subfile

    num_md_files = num_md_files + 1
    rel_url = os.path.join("..", regex.sub("\.md", "/", sub_md_file_path))
    content = "%s\n%s" % (content, """<div class="js_include" url="%s"  newLevelForH1="1" includeTitle="true"> </div>""" % (rel_url).strip())
  
  if num_md_files > 0:
    full_md_path = os.path.join(source_dir, "full.md")
    full_md = MdFile(file_path=full_md_path)
    full_md.dump_to_file(content=content, metadata={"title": title}, dry_run=dry_run)
  else:
    logging.info("No md files found in %s. Skipping.", source_dir)


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


def migrate(files, location_computer, dry_run=False):
  """Migrate a bunch of files to a new location (dynamically computed by location_computer function.)"""
  logging.info("Processing %d files", len(files))
  for f in files:
    new_path = location_computer(str(f))
    logging.info("Moving %s to %s", str(f), new_path)
    md_file = MdFile(file_path=f)
    (metadata, _) = md_file.read()
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


def get_md_files_from_path(dir_path, file_pattern="**/*.md", file_name_filter=lambda x: True):
  from pathlib import Path
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  md_file_paths = sorted(filter(file_name_filter, Path(dir_path).glob(file_pattern)))
  md_file_paths = [f for f in md_file_paths if os.path.isfile(f)]
  return [MdFile(path) for path in md_file_paths]


def apply_function(fn, dir_path, file_pattern="**/*.md", file_name_filter=None, frontmatter_type="toml", start_file=None, silent_iteration=True, *args,
                   **kwargs):
  if not silent_iteration:
    logging.debug(list(Path(dir_path).glob(file_pattern)))
  if os.path.isfile(dir_path):
    logging.warning("Got a file actually. processing it!")
    md_files = [MdFile(file_path=dir_path)]
  else:
    md_files = get_md_files_from_path(dir_path=dir_path, file_pattern=file_pattern,
                                             file_name_filter=file_name_filter)
  start_file_reached = False

  logging.info("Processing %d files.", len(md_files))
  from tqdm import tqdm
  results_map = {}
  for md_file in tqdm(md_files):
    if start_file is not None and not start_file_reached:
      if str(md_file.file_path) != start_file:
        continue
      else:
        start_file_reached = True
    if md_file.get_title() is not None:
      # logging.info("Processing %s", md_file)
      result = fn(md_file, *args, **kwargs)
      results_map[md_file.file_path] = result
  return results_map


def get_audio_file_urls(md_files):
  # logging.debug(adhyaaya_to_mp3_map)
  logging.info("Getting audio file locations from %d files", len(md_files))
  for md_file in md_files:
    # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
    logging.debug(md_file.file_path)
    (metadata, md) = md_file.read()
    match = regex.match("<div class=\"audioEmbed\".+ src=\"([^\"]+)\"", md)
    if match:
      yield match.group(1)


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


def combine_select_files_in_dir(md_file, source_fname_list, dry_run=False):
  dir_path = os.path.dirname(md_file.file_path)
  source_mds = [MdFile(file_path=os.path.join(dir_path, x)) for x in source_fname_list if x in os.listdir(dir_path)]
  md_file.append_content_from_mds(source_mds=source_mds, dry_run=dry_run)
  if not dry_run:
    for source_md in source_mds:
      os.remove(source_md.file_path)


def combine_files_in_dir(md_file, dry_run=False):
  dir_path = os.path.dirname(md_file.file_path)
  source_mds = [MdFile(file_path=os.path.join(dir_path, x)) for x in sorted(os.listdir(dir_path)) if os.path.isfile(os.path.join(dir_path, x)) and x.endswith(".md") and x != os.path.basename(md_file.file_path) ]
  md_file.append_content_from_mds(source_mds=source_mds, dry_run=dry_run)
  if not dry_run:
    for source_md in source_mds:
      os.remove(source_md.file_path)


def get_include(url, field_names=None, classes=None, title=None, h1_level=2, extra_attributes=""):
  field_names_str = ""
  if field_names is not None:
    field_names_str = "fieldNames=\"%s\"" % (",".join(field_names))
  classes_str = ""
  if classes is not None:
    classes_str = " ".join(classes)
  extra_attributes =  "%s %s" % (extra_attributes, " ".join([field_names_str]))
  if title == "FILE_TITLE":
    title_str = 'includeTitle="true"'
  elif title is not None:
    title_str = "title=\"%s\"" % title
  else:
    title_str = None
  if title_str is not None:
    extra_attributes = "%s %s" % (title_str, extra_attributes)
  return """<div class="js_include %s" url="%s"  newLevelForH1="%d" %s> </div>"""  % (classes_str,url, h1_level, extra_attributes)


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


def make_per_src_folder_content_files(dest_path, main_source_path, aux_source_list, source_script=sanscript.DEVANAGARI, h1_level=3, dry_run=False):
  md_files = get_md_files_from_path(dir_path=main_source_path, file_pattern="**/*.md")
  dest_file_path_to_source_paths = {}
  for md_file in md_files:
    dest_file_path = os.path.dirname(md_file.file_path).replace(main_source_path, dest_path) + ".md"
    main_source_paths = dest_file_path_to_source_paths.get(dest_file_path, [])
    main_source_paths.append(md_file.file_path)
    dest_file_path_to_source_paths[dest_file_path] = main_source_paths
  
  main_source_dir = os.path.basename(main_source_path)
  from doc_curation.md.content_processor import include_helper
  from doc_curation.md.library import metadata_helper
  for dest_file_path, main_source_paths in dest_file_path_to_source_paths.items():
    md_file = MdFile(file_path=dest_file_path)
    content = ""
    for main_source_path in main_source_paths:
      include_line = include_helper.vishvAsa_include_maker(file_path=main_source_path, h1_level=h1_level, classes=None, title="FILE_TITLE",)
      content = "%s\n\n%s" % (content, include_line)
      
      for aux_source in aux_source_list:
        aux_path = os.path.abspath(main_source_path.replace(main_source_dir, aux_source))
        if os.path.exists(aux_path):
          title = sanscript.transliterate(aux_source, _from=sanscript.OPTITRANS, _to=source_script, maybe_use_dravidian_variant=True)
          include_line = include_helper.vishvAsa_include_maker(file_path=aux_path, h1_level=h1_level+1, classes=["collapsed"], title=title,)
          content = "%s\n%s" % (content, include_line)

      md_file.dump_to_file(metadata={"title": metadata_helper.get_title_from_filename(file_path=md_file.file_path, transliteration_target=source_script)}, content=content, dry_run=dry_run)
  fix_index_files(dir_path=dest_path, transliteration_target=source_script, dry_run=dry_run)


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


def dump_word_cloud(src_path, dest_path, stop_words=None, font_path='siddhanta'):
  from collections import Counter
  from doc_curation.md.content_processor import patterns
  from wordcloud import WordCloud, STOPWORDS
  if stop_words is not None:
    stop_words = set(stop_words)
    stop_words.update(STOPWORDS)
  wc = WordCloud(width=1600, height=800, font_path=font_path, stopwords=stop_words, regexp=patterns.DEVANAGARI_OR_LATIN_WORD)
  counts_map = apply_function(fn=patterns.get_word_count, dir_path=src_path, wc=wc)
  counts = Counter()
  for file_path, file_counts in counts_map.items():
    counts.update(file_counts)
  wc.generate_from_frequencies(counts)
  if not dest_path.startswith("/"):
    dest_path = os.path.join(src_path, dest_path)
  os.makedirs(os.path.dirname(dest_path), exist_ok=True)
  wc.to_file(dest_path)
  return counts


