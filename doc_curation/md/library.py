import logging
import os

import regex

from curation_utils import file_helper
from doc_curation.md.file import MdFile
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
  from pathlib import Path
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  md = ""
  title = "पूर्णपाठः"
  rel_url = "../"

  num_md_files = 0

  index_md_path = os.path.join(source_dir, "_index.md")
  if os.path.exists(index_md_path):
    index_md = MdFile(file_path=index_md_path)
    (index_yml, _) = index_md.read_md_file()
    title = "%s (%s)" % (index_yml["title"], title)
    md = "%s\n%s" % (md, """<div class="js_include" url="%s"  newLevelForH1="1" includeTitle="false"> </div>""" % (rel_url).strip())
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
    md = "%s\n%s" % (md, """<div class="js_include" url="%s"  newLevelForH1="1" includeTitle="true"> </div>""" % (rel_url).strip())
  
  if num_md_files > 0:
    full_md_path = os.path.join(source_dir, "full.md")
    full_md = MdFile(file_path=full_md_path)
    full_md.dump_to_file(md=md, metadata={"title": title}, dry_run=dry_run)
  else:
    logging.info("No md files found in %s. Skipping.", source_dir)


def migrate_and_include(files, location_computer, new_url_computer, dry_run=False):
  logging.info("Processing %d files", len(files))
  for f in files:
    new_path = location_computer(str(f))
    logging.info("Moving %s to %s", str(f), new_path)
    md_file = MdFile(file_path=f)
    (metadata, _) = md_file.read_md_file()
    if not dry_run:
      os.makedirs(os.path.dirname(new_path), exist_ok=True)
      os.rename(src=f, dst=new_path)
    md = """<div class="js_include" url="%s"  newLevelForH1="1" includeTitle="true"> </div>""" % new_url_computer(str(f))
    logging.info("Inclusion in old file : %s", md)
    md_file.dump_to_file(metadata=metadata, md=md, dry_run=dry_run)


def fix_index_files(dir_path, frontmatter_type=MdFile.TOML, transliteration_target=sanscript.DEVANAGARI, overwrite=False, dry_run=False):
  logging.info("Fixing index files")
  # Get all non hidden directories.
  dirs = [x[0] for x in os.walk(dir_path) if "/." not in x[0]]
  # set([os.path.dirname(path) for path in Path(dir_path).glob("**/")])
  for dir in dirs:
    index_file = MdFile(file_path=os.path.join(dir, "_index.md"), frontmatter_type=frontmatter_type)
    if not os.path.exists(index_file.file_path):
      index_file.dump_to_file(metadata={}, md="", dry_run=dry_run)
      index_file.set_title_from_filename(transliteration_target=transliteration_target, dry_run=dry_run)
    elif overwrite:
      index_file.set_title_from_filename(transliteration_target=transliteration_target, dry_run=dry_run)


def get_md_files_from_path(dir_path, file_pattern, file_name_filter=None, frontmatter_type="yaml"):
  from pathlib import Path
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  md_file_paths = sorted(filter(file_name_filter, Path(dir_path).glob(file_pattern)))
  return [MdFile(path, frontmatter_type=frontmatter_type) for path in md_file_paths]


def apply_function(fn, dir_path, file_pattern="**/*.md", file_name_filter=None, frontmatter_type="yaml", start_file=None, *args,
                   **kwargs):
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  if os.path.isfile(dir_path):
    logging.warning("Got a file actually. processing it!")
    md_files = [MdFile(file_path=dir_path)]
  else:
    md_files = get_md_files_from_path(dir_path=dir_path, file_pattern=file_pattern,
                                             file_name_filter=file_name_filter, frontmatter_type=frontmatter_type)
  start_file_reached = False

  from tqdm import tqdm
  for md_file in tqdm(md_files):
    if start_file is not None and not start_file_reached:
      if str(md_file.file_path) != start_file:
        continue
      else:
        start_file_reached = True
    logging.info("Processing %s", md_file)
    fn(md_file, *args, **kwargs)


def set_titles_from_filenames(dir_path, transliteration_target, file_pattern="**/*.md", dry_run=False):
  apply_function(fn=MdFile.set_title_from_filename, dir_path=dir_path, file_pattern=file_pattern,
                     transliteration_target=transliteration_target, dry_run=dry_run)


def set_filenames_from_titles(dir_path, transliteration_source, file_pattern="**/*.md", file_name_filter=None,
                              dry_run=False):
  apply_function(fn=MdFile.set_filename_from_title, dir_path=dir_path, file_pattern=file_pattern,
                     transliteration_source=transliteration_source, dry_run=dry_run,
                     file_name_filter=file_name_filter)


def devanaagarify_titles(md_files, dry_run=False):
  logging.info("Fixing titles of %d files", len(md_files))
  for md_file in md_files:
    # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
    logging.debug(md_file.file_path)
    title_fixed = sanscript.transliterate(data=md_file.get_title(), _from=sanscript.OPTITRANS,
                                          _to=sanscript.DEVANAGARI)
    md_file.set_title(title=title_fixed, dry_run=dry_run)


def fix_field_values(md_files,
                     spreadhsheet_id, worksheet_name, id_column, value_column,
                     md_file_to_id, md_frontmatter_field_name="title", google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json', post_process_fn=None,
                     dry_run=False):
  # logging.debug(adhyaaya_to_mp3_map)
  logging.info("Fixing titles of %d files", len(md_files))
  from curation_utils.google import sheets
  doc_data = sheets.IndexSheet(spreadhsheet_id=spreadhsheet_id, worksheet_name=worksheet_name, google_key=google_key,
                               id_column=id_column)
  for md_file in md_files:
    # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
    logging.debug(md_file.file_path)
    adhyaaya_id = md_file_to_id(md_file)
    if adhyaaya_id != None:
      logging.debug(adhyaaya_id)
      value = doc_data.get_value(adhyaaya_id, column_name=value_column)
      if post_process_fn is not None:
        value = post_process_fn(value)
      if value != None:
        md_file.set_frontmatter_field_value(field_name=md_frontmatter_field_name, value=value, dry_run=dry_run)



def get_metadata_field_values(md_files, field_name):
  # logging.debug(adhyaaya_to_mp3_map)
  logging.info("Getting metadata from %s field of %d files", field_name, len(md_files))
  for md_file in md_files:
    # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
    logging.debug(md_file.file_path)
    (metadata, md) = md_file.read_md_file()
    yield metadata[field_name]



def get_audio_file_urls(md_files):
  # logging.debug(adhyaaya_to_mp3_map)
  logging.info("Getting audio file locations from %d files", len(md_files))
  for md_file in md_files:
    # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
    logging.debug(md_file.file_path)
    (metadata, md) = md_file.read_md_file()
    match = regex.match("<div class=\"audioEmbed\".+ src=\"([^\"]+)\"", md)
    if match:
      yield match.group(1)



