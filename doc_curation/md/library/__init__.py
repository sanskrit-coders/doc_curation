import glob
import logging
import os

import regex
from indic_transliteration import sanscript

from curation_utils import file_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper


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


def get_md_files_from_path(dir_path, file_pattern="**/*.md", file_name_filter=lambda x: True, frontmatter_type=None):
  from pathlib import Path
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  md_file_paths = sorted(filter(file_name_filter, Path(dir_path).glob(file_pattern)))
  return [MdFile(path, frontmatter_type=frontmatter_type) for path in md_file_paths]


def apply_function(fn, dir_path, file_pattern="**/*.md", file_name_filter=None, frontmatter_type="toml", start_file=None, *args,
                   **kwargs):
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  if os.path.isfile(dir_path):
    logging.warning("Got a file actually. processing it!")
    md_files = [MdFile(file_path=dir_path)]
  else:
    md_files = get_md_files_from_path(dir_path=dir_path, file_pattern=file_pattern,
                                             file_name_filter=file_name_filter, frontmatter_type=frontmatter_type)
  start_file_reached = False

  logging.info("Processing %d files.", len(md_files))
  from tqdm import tqdm
  for md_file in tqdm(md_files):
    if start_file is not None and not start_file_reached:
      if str(md_file.file_path) != start_file:
        continue
      else:
        start_file_reached = True
    logging.info("Processing %s", md_file)
    fn(md_file, *args, **kwargs)


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
  files = glob.glob(dir_path + "/**/_index.md")
  for file in files:
    parent = os.path.dirname(file)
    if len(os.listdir(parent)) == 1:
      dest_file_path = parent + ".md"
      logging.info("Moving %s to %s", str(file), dest_file_path)
      if not dry_run:
        os.rename(src=file, dst=dest_file_path)
        md_file = MdFile(file_path=dest_file_path)
        (metadata, _) = md_file.read()
        title = metadata["title"]
        if title.startswith("+"):
          title = title[1:]
        md_file.set_title(title=title, dry_run=False)
        os.rmdir(parent)


def combine_select_files_in_dir(md_file, source_fname_list, dry_run=False):
  dir_path = os.path.dirname(md_file.file_path)
  source_mds = [MdFile(file_path=os.path.join(dir_path, x)) for x in source_fname_list if x in os.listdir(dir_path)]
  md_file.append_content_from_mds(source_mds=source_mds, dry_run=dry_run)
  if not dry_run:
    for source_md in source_mds:
      os.remove(source_md.file_path)


def combine_files_in_dir(md_file, dry_run=False):
  dir_path = os.path.dirname(md_file.file_path)
  source_mds = [MdFile(file_path=os.path.join(dir_path, x)) for x in sorted(os.listdir(dir_path)) if x != os.path.basename(md_file.file_path) ]
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


def get_sub_path_id(sub_path, basename_id_pattern="(.+?)[_\.]"):
  basename = os.path.basename(sub_path)
  if basename == "_index.md":
    return sub_path
  base_id_match = regex.search(basename_id_pattern, basename)
  if base_id_match is None:
    return None
  else:
    return os.path.join(os.path.dirname(sub_path), base_id_match.group(1))