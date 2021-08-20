import logging
import os

import regex

from curation_utils.file_helper import get_storage_name
from doc_curation.md import content_processor
from doc_curation.md.file import MdFile
from doc_curation.md.library import apply_function
from indic_transliteration import sanscript


def ensure_ordinal_in_title(dir_path, transliteration_target, dry_run):
  files = [x for x in os.listdir(dir_path) if x != "_index.md" and x.endswith(".md")]
  files.sort()
  for index, file in enumerate(files):
    md_file = os.path.join(dir_path, file)
    title = md_file.get_title(omit_chapter_id=False)
    if regex.fullmatch("[+०-९0-9].+", title):
      return

    index = files.index(os.path.basename(md_file.file_path))
    format = "%%0%dd" % (len(str(len(files))))
    index = format % index
    if transliteration_target:
      index = sanscript.transliterate(index, sanscript.OPTITRANS, transliteration_target)
    title = "%s %s" % (index, title)
    md_file.set_title(title=title, dry_run=dry_run)


def fix_title_numbering(dir_path, dry_run):
  files = [x for x in os.listdir(dir_path) if x != "_index.md" and x.endswith(".md")]
  files.sort()
  for index, file in enumerate(files):
    md_file = os.path.join(dir_path, file)
    title = md_file.get_title()
    if title is None:
      return

    import regex
    new_title = regex.sub("(^[०-९][^०-९])", "०\\1", title)
    if title != new_title:
      logging.info("Changing '%s' to '%s'", title, new_title)
      md_file.set_title(title=new_title, dry_run=dry_run)


def set_filename_from_title(md_file, transliteration_source=sanscript.DEVANAGARI, dry_run=False, skip_dirs=True):
  # logging.debug(md_file.file_path)
  if skip_dirs and str(md_file.file_path).endswith("_index.md"):
    logging.info("Special file %s. Skipping." % md_file.file_path)
    return
  title = md_file.get_title(omit_chapter_id=False)
  if transliteration_source is not None:
    title = sanscript.transliterate(data=title, _from=transliteration_source, _to=sanscript.OPTITRANS)
  if os.path.basename(md_file.file_path) == "_index.md":
    current_path = os.path.dirname(md_file.file_path)
    extension = ""
  else:
    current_path = md_file.file_path
    extension = ".md"
  file_name = get_storage_name(text=title) + extension
  file_path = os.path.join(os.path.dirname(current_path), file_name)
  if str(current_path) != file_path:
    logging.info("Renaming %s to %s", current_path, file_path)
    if not dry_run:
      os.rename(src=current_path, dst=file_path)


def set_title_from_filenames(md_file, transliteration_target=sanscript.DEVANAGARI, dry_run=False):
  # logging.debug(md_file.file_path)
  if os.path.basename(md_file.file_path) == "_index.md":
    dir_name = os.path.basename(os.path.dirname(md_file.file_path)).replace(".md", "")
    title_optitrans = "+" + dir_name
  else:
    title_optitrans = os.path.basename(md_file.file_path).replace(".md", "")
  title = title_optitrans.replace("_", " ")
  if transliteration_target is not None:
    title = sanscript.transliterate(data=title, _from=sanscript.OPTITRANS, _to=transliteration_target)
  md_file.set_title(dry_run=dry_run, title=title)


def prepend_file_indexes_to_title(md_file, dry_run):
  if os.path.basename(md_file.file_path) == "_index.md":
    return
  else:
    index = regex.sub("_.+", "", os.path.basename(md_file.file_path))
  title = index + " " + md_file.get_title(omit_chapter_id=False)
  md_file.set_title(dry_run=dry_run, title=title)


def add_init_words_to_titles(md_file, num_words=2, target_title_length=None, dry_run=False):
  (metadata, content) = md_file.read_md_file()
  title = metadata["title"]
  extra_title = content_processor.title_from_text(text=content, num_words=num_words, target_title_length=target_title_length)
  if extra_title is not None:
    title = "%s %s" % (title.strip(), extra_title)
  md_file.set_title(title=title, dry_run=dry_run)


def devanaagarify_title(md_file, dry_run=False):
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


def shloka_title_maker(text):
  id_in_text = sanscript.transliterate(regex.search("॥\s*([०-९\d\.]+)\s*॥", text).group(1), sanscript.DEVANAGARI, sanscript.OPTITRANS)
  id_in_text = regex.search("\.?\s*(\d+)\s*$", id_in_text).group(1)
  title_id = "%03d" % int(id_in_text)
  title = content_processor.title_from_text(text=text, num_words=2, target_title_length=None, depunctuate=True,
                                            title_id=title_id)
  return title


