import logging
import os
import shutil

import regex
from curation_utils import file_helper

from curation_utils.file_helper import get_storage_name
from doc_curation.md import content_processor
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript


def ensure_ordinal_in_title(dir_path, transliteration_target=sanscript.DEVANAGARI, first_file_index=1, dry_run=False, recursive=False, format=None):
  files = [os.path.join(dir_path, x) for x in os.listdir(dir_path) if x != "_index.md" and x.endswith(".md")]
  files.sort()
  for index, file in enumerate(files):
    md_file = MdFile(file_path=os.path.join(dir_path, file))
    title = md_file.get_title(omit_chapter_id=False)
    title = regex.sub("(^[\d०-९೦-೯ ]+ )", "", title)
    # if regex.fullmatch("[+०-९0-9].+", title):
    #   return

    if format is None:
      format = "%%0%dd" % (len(str(len(files))))
    index = format % (index + first_file_index)
    if transliteration_target:
      index = sanscript.transliterate(index, sanscript.OPTITRANS, transliteration_target)
    title = "%s %s" % (index, title)
    md_file.set_title(title=title, dry_run=dry_run)
    set_filename_from_title(md_file=md_file, source_script=transliteration_target, dry_run=dry_run)

  if recursive:
    dirs = [os.path.join(dir_path, x) for x in os.listdir(dir_path) if os.path.isdir(os.path.join(dir_path, x))]
    for dir in dirs:
      ensure_ordinal_in_title(dir_path=dir, transliteration_target=transliteration_target, dry_run=dry_run, recursive=True, first_file_index=first_file_index, format=format)


def pad_title_numbering(dir_path, dry_run):
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


def set_filename_from_title(md_file, source_script=sanscript.DEVANAGARI, mixed_languages_in_titles=True, max_title_length=50, dry_run=False, skip_dirs=True):
  # logging.debug(md_file.file_path)
  if skip_dirs and str(md_file.file_path).endswith("_index.md"):
    logging.info("Special file %s. Skipping." % md_file.file_path)
    return
  title = md_file.get_title(omit_chapter_id=False)
  if source_script is not None:
    title_in_file_name = file_helper.get_storage_name(text=title, source_script=source_script, maybe_use_dravidian_variant=True, mixed_languages_in_titles=mixed_languages_in_titles, max_length=max_title_length)

  if os.path.basename(md_file.file_path) == "_index.md":
    current_path = os.path.dirname(md_file.file_path)
    extension = ""
  else:
    current_path = md_file.file_path
    extension = ".md"
  file_name = file_helper.clean_file_path("%s%s" % (title_in_file_name, extension))
  file_path = os.path.join(os.path.dirname(current_path), file_name)
  if str(current_path) != file_path:
    logging.info("Renaming %s to %s", current_path, file_path)
    if not dry_run:
      os.rename(src=current_path, dst=file_path)


def truncate_file_name(md_file, max_length=50, dry_run=False):
  basename = os.path.basename(md_file.file_path).replace(".md", "")
  basename = basename[:max_length] + ".md"
  new_path = os.path.join(os.path.dirname(md_file.file_path), basename)
  if md_file.file_path != new_path:
    logging.info("Renaming %s to %s", md_file.file_path, new_path)
    if not dry_run:
      os.rename(src=md_file.file_path, dst=new_path)
      md_file.file_path = new_path


def get_title_from_filename(file_path, transliteration_target, maybe_use_dravidian_variant=None):
  if os.path.basename(file_path) == "_index.md":
    dir_name = os.path.basename(os.path.dirname(file_path)).replace(".md", "")
    title_optitrans = "+" + dir_name
  else:
    title_optitrans = os.path.basename(file_path).replace(".md", "")
  title = title_optitrans.replace("_", " ")
  if transliteration_target is not None:
    title = title.replace("-dhyAyaH", ".adhyAyaH")
    title = sanscript.transliterate(data=title, _from=sanscript.OPTITRANS, _to=transliteration_target, maybe_use_dravidian_variant=maybe_use_dravidian_variant)
  else:
    title = title.capitalize()
  return title

def set_title_from_filename(md_file, transliteration_target=sanscript.DEVANAGARI, dry_run=False, maybe_use_dravidian_variant=None):
  # logging.debug(md_file.file_path)
  title = get_title_from_filename(file_path=md_file.file_path, transliteration_target=transliteration_target, maybe_use_dravidian_variant=maybe_use_dravidian_variant)
  md_file.set_title(dry_run=dry_run, title=title)


def prepend_file_indexes_to_title(md_file, dry_run):
  if os.path.basename(md_file.file_path) == "_index.md":
    return
  else:
    index = regex.sub("_.+", "", os.path.basename(md_file.file_path))
  title = index + " " + md_file.get_title(omit_chapter_id=False)
  md_file.set_title(dry_run=dry_run, title=title)


def add_init_words_to_title(md_file, num_words=3, target_title_length=50,script=sanscript.DEVANAGARI, replace_non_index_text=True, dry_run=False):
  (metadata, content) = md_file.read()
  title = metadata["title"]
  if replace_non_index_text:
    title = regex.sub("(?<=^[0-9०-९೦-೯]+) +.+", "", title)
  extra_title = content_processor.title_from_text(text=content, num_words=num_words, target_title_length=target_title_length, script=script)
  if extra_title is not None:
    title = "%s %s" % (title.strip(), extra_title)
  md_file.set_title(title=title, dry_run=dry_run)


def transliterate_title(md_file, transliteration_target=sanscript.DEVANAGARI, dry_run=False):
  # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
  logging.debug(md_file.file_path)
  title_fixed = sanscript.transliterate(data=md_file.get_title(), _from=sanscript.OPTITRANS,
                                        _to=transliteration_target)
  md_file.set_title(title=title_fixed, dry_run=dry_run)



def remove_post_numeric_title_text(md_file, dry_run=False):
  logging.debug(md_file.file_path)
  title_fixed = regex.sub("([\d०-९೦-೯-]+ ).+", "\\1", md_file.get_title())
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
  logging.info("Getting metadata from %s field of %d files", field_name, len(md_files))
  for md_file in md_files:
    # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
    logging.debug(md_file.file_path)
    (metadata, md) = md_file.read()
    yield metadata[field_name]


def shloka_title_maker(text):
  id_in_text = sanscript.transliterate(regex.search("॥\s*([०-९\d\.]+)\s*॥", text).group(1), sanscript.DEVANAGARI, sanscript.OPTITRANS)
  id_in_text = regex.search("\.?\s*(\d+)\s*$", id_in_text).group(1)
  title_id = "%03d" % int(id_in_text)
  title = content_processor.title_from_text(text=text, num_words=2, target_title_length=None, depunctuate=True, title_id=title_id)
  return title


def copy_metadata_and_filename(dest_dir, ref_dir, insert_missign_ref_files=False, sub_path_id_maker=None, dry_run=False):
  from doc_curation.md import library
  sub_path_to_reference = library.get_sub_path_to_reference_map(ref_dir=ref_dir, sub_path_id_maker=sub_path_id_maker)
  dest_md_files = library.get_md_files_from_path(dir_path=dest_dir)
  if sub_path_id_maker is None:
    sub_path_id_maker = lambda x: library.get_sub_path_id(sub_path=str(x).replace(dest_dir, ""))
  for md_file in dest_md_files:
    sub_path_id = sub_path_id_maker(md_file.file_path)
    if sub_path_id is None:
      continue
    if sub_path_id not in sub_path_to_reference:
      if sub_path_id.endswith("_index.md"):
        pass
        # logging.warning("Could not find %s in ref_dir. Skipping", sub_path_id)
        continue
      if insert_missign_ref_files:
        target_path = os.path.join(ref_dir, sub_path_id + ".md")
        logging.warning(fr"Inserting missing ref: {sub_path_id}. Fix and rerun.")
        shutil.copy(md_file.file_path, target_path)
        continue
    ref_md = sub_path_to_reference[sub_path_id]
    sub_file_path_ref = str(ref_md.file_path).replace(ref_dir, "")
    (ref_metadata, _) = ref_md.read()
    md_file.replace_content_metadata(new_metadata=ref_metadata, dry_run=dry_run, silent=True)
    target_path = os.path.abspath("%s/%s" % (dest_dir, sub_file_path_ref))
    if dry_run:
      logging.info("Moving %s to %s", md_file.file_path, target_path)
    else:
      os.makedirs(os.path.dirname(target_path), exist_ok=True)
      shutil.move(md_file.file_path, target_path)


def add_value_to_field(metadata, field, value): 
  metadata[field] = value
  return metadata