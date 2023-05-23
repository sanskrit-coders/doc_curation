import logging
import os
import shutil

import regex
from indic_transliteration import sanscript
from regex import Match

from curation_utils import file_helper
from tqdm import tqdm

from doc_curation.md.file import MdFile


def ensure_ordinal_in_title(dir_path, transliteration_target=sanscript.DEVANAGARI, first_file_index=1, dry_run=False, recursive=False, format=None):
  files = [os.path.join(dir_path, x) for x in os.listdir(dir_path) if x != "_index.md" and x.endswith(".md")]
  files.sort()
  for index, file in enumerate(files):
    md_file = MdFile(file_path=os.path.join(dir_path, file))
    title = md_file.get_title(omit_chapter_id=False)
    title = regex.sub(r"(^[\d०-९೦-೯ ]+ )", "", title)
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
    md_file = MdFile(file_path=os.path.join(dir_path, file))
    title = md_file.get_title()
    if title is None:
      return

    import regex
    new_title = regex.sub("(^[०-९][^०-९])", "०\\1", title)
    if title != new_title:
      logging.info("Changing '%s' to '%s'", title, new_title)
      md_file.set_title(title=new_title, dry_run=dry_run)


def set_filename_from_title(md_file, source_script=None, mixed_languages_in_titles=True, max_title_length=50, dry_run=False, skip_dirs=True, maybe_use_dravidian_variant="yes"):
  # logging.debug(md_file.file_path)
  if skip_dirs and str(md_file.file_path).endswith("_index.md"):
    logging.info("Special file %s. Skipping." % md_file.file_path)
    return
  title = md_file.get_title(omit_chapter_id=False)
  if source_script is None:
    from indic_transliteration import detect
    source_script_deduced = detect.detect(title)
    if source_script_deduced in sanscript.brahmic.SCHEMES:
      source_script = source_script_deduced

  if source_script is not None:
    title_in_file_name = file_helper.get_storage_name(text=title, source_script=source_script, maybe_use_dravidian_variant=maybe_use_dravidian_variant, mixed_languages_in_titles=mixed_languages_in_titles, max_length=max_title_length)
  else:
    title_in_file_name = title

  move_file(md_file=md_file, new_file_name=title_in_file_name, dry_run=dry_run)


def move_file(md_file, new_file_name, dry_run):
  if os.path.basename(md_file.file_path) == "_index.md":
    current_path = os.path.dirname(md_file.file_path)
    extension = ""
  else:
    current_path = md_file.file_path
    extension = ".md"
  file_name = file_helper.clean_file_path("%s%s" % (new_file_name, extension))
  if file_name.startswith("/"):
    file_path = file_name
  else:
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


def prepend_file_index_to_title(md_file, dry_run):
  if os.path.basename(md_file.file_path) == "_index.md":
    base_name = os.path.basename(os.path.dirname(md_file.file_path))
  else:
    base_name = os.path.basename(md_file.file_path)
  base_name = base_name.replace(".md", "")
  index = regex.sub("_.+", "", base_name)
  title = index + " " + md_file.get_title(omit_chapter_id=False)
  md_file.set_title(dry_run=dry_run, title=title)


def strip_index_from_title(md_file, dry_run):
  title = md_file.get_title(omit_chapter_id=True)
  if os.path.basename(md_file.file_path) == "_index.md":
    title = f"+{title}"
  md_file.set_title(dry_run=dry_run, title=title)


def add_init_words_to_title(md_file, num_words=3, target_title_length=50,script=sanscript.DEVANAGARI, replace_non_index_text=True, dry_run=False):
  (metadata, content) = md_file.read()
  title = metadata["title"]
  if replace_non_index_text:
    title = regex.sub("(?<=^[0-9०-९೦-೯_-]+) +.+", "", title)
  extra_title = title_from_text(text=content, num_words=num_words, target_title_length=target_title_length, script=script)
  if extra_title is not None:
    title = "%s %s" % (title.strip(), extra_title)
  md_file.set_title(title=title, dry_run=dry_run)


def transliterate_title(md_file, transliteration_target=sanscript.DEVANAGARI, dry_run=False):
  # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
  logging.debug(md_file.file_path)
  title_fixed = sanscript.transliterate(data=md_file.get_title(omit_chapter_id=False, omit_plus=False), _from=sanscript.OPTITRANS,
                                        _to=transliteration_target)
  md_file.set_title(title=title_fixed, dry_run=dry_run)



def remove_post_numeric_title_text(md_file, removal_allower=lambda x:True, rename=True, set_in_content=False, dry_run=False):
  title = md_file.get_title(omit_chapter_id=False)
  match = regex.fullmatch(r"([\d०-९೦-೯-]+) +(\S.+)", title)
  if match is None:
    logging.warning(f"No match! Skipping {md_file.file_path}")
    return 
  title_numeric = match.group(1)
  title_remainder = match.group(2)
  if not removal_allower(title_remainder):
    logging.info(f"Not allowing removal of {title_remainder} in {md_file.file_path}")
    return 
  (metadata, content) = md_file.read()
  if md_file.file_path.endswith("_index.md"):
    metadata["title"] = f"+{title_numeric}"
  else:
    metadata["title"] = title_numeric
  if set_in_content:
    content = f"[{title_remainder}]\n\n{content}"
  logging.info(f"Title change: {title} → {title_numeric}")
  md_file.dump_to_file(content=content, metadata=metadata, dry_run=dry_run)
  if rename:
    set_filename_from_title(md_file=md_file, skip_dirs=False, dry_run=dry_run)


def remove_adhyaaya_word_from_title(md_file, adhyaaya_pattern="([अऽ]ध्याय|[ಅಽ]ಧ್ಯಾಯ)", rename=True, set_in_content=True, dry_run=False):
  remove_post_numeric_title_text(
    md_file=md_file, 
    removal_allower=lambda x: len(list(regex.finditer(adhyaaya_pattern, x))) > 0, 
    set_in_content=set_in_content, rename=rename, dry_run=dry_run)
  
def set_title_from_content(md_file, title_extractor, rename=True, log_level=logging.INFO, dry_run=False):
  [metadata, content] = md_file.read()
  title = metadata["title"]
  if regex.fullmatch(r"[\d०-९೦-೯\- ]+", title):
    title_extracted = title_extractor(content)
    if title_extracted is not None:
      title = f"{title.strip()} {title_extracted}"
      md_file.set_title(title=title, dry_run=dry_run)
    else:
      if log_level <= logging.WARNING:
        # pass
        logging.warning(f"Could not extact title from: {md_file.file_path}")
  else:
    if log_level <= logging.DEBUG:
      logging.debug(f"Preexisting title, skipping: {md_file.file_path}")
  if rename:
    set_filename_from_title(md_file=md_file, skip_dirs=False, dry_run=dry_run)


def fix_field_values(md_files,
                     spreadhsheet_id, worksheet_name, id_column, value_column,
                     md_file_to_id, md_frontmatter_field_name="title", google_key='/home/vvasuki/gitland/vvasuki-git/sysconf/kunchikA/google/sanskritnlp/service_account_key.json', post_process_fn=None,
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
  id_in_text = sanscript.transliterate(regex.search(r"॥\s*([०-९\d\.]+)\s*॥", text).group(1), sanscript.DEVANAGARI, sanscript.OPTITRANS)
  id_in_text = regex.search(r"\.?\s*(\d+)\s*$", id_in_text).group(1)
  title_id = "%03d" % int(id_in_text)
  title = title_from_text(text=text, num_words=2, target_title_length=None, depunctuate=True, title_id=title_id)
  return title


def copy_metadata_and_filename(dest_dir, ref_dir, insert_missing_ref_files=False, sub_path_id_maker=None, dry_run=False):
  from doc_curation.md.library import arrangement
  sub_path_to_reference = arrangement.get_sub_path_to_reference_map(ref_dir=ref_dir, sub_path_id_maker=sub_path_id_maker)
  dest_md_files = arrangement.get_md_files_from_path(dir_path=dest_dir)
  if sub_path_id_maker is None:
    sub_path_id_maker = lambda x: arrangement.get_sub_path_id(sub_path=str(x).replace(dest_dir, ""))
  for md_file in tqdm(dest_md_files):
    sub_path_id = sub_path_id_maker(md_file.file_path)
    if sub_path_id is None:
      continue
    if sub_path_id not in sub_path_to_reference:
      if sub_path_id.endswith("_index.md"):
        pass
        # logging.warning("Could not find %s in ref_dir. Skipping", sub_path_id)
        continue
      if insert_missing_ref_files:
        target_path = os.path.join(ref_dir, sub_path_id + ".md")
        logging.warning(fr"Inserting missing ref: {sub_path_id}. Fix and rerun.")
        shutil.copy(md_file.file_path, target_path)
        continue
      else:
        logging.warning("Could not find %s in ref_dir. Skipping", sub_path_id)
        continue
    ref_md = sub_path_to_reference[sub_path_id]
    sub_file_path_ref = str(ref_md.file_path).replace(ref_dir, "").replace("_index.md", "").replace(".md", "")
    (ref_metadata, _) = ref_md.read()
    md_file.replace_content_metadata(new_metadata=ref_metadata, dry_run=dry_run, silent=True)
    target_path = os.path.abspath("%s/%s" % (dest_dir, sub_file_path_ref))
    
    move_file(md_file=md_file, new_file_name=target_path, dry_run=dry_run)


def add_value_to_field(metadata, field, value): 
  metadata[field] = value
  return metadata


def iti_naama_title_extractor(text, conclusion_pattern="इति.+\n?.+ऽध्यायः"):
  """
  Example conclusion line: ॥ ॐ तत्सदिति श्रीमदान्त्ये पुराणोपनिषदि श्रीमन्मौद्गले महापुराणेपञ्चमे खण्डे लम्बोदरचरिते शेषातिदुःखवर्णनन्नाम षोडशोऽध्यायः ॥
  
  :param text: 
  :param conclusion_pattern: 
  :return: 
  """
  matches: list[Match] = list(regex.finditer(conclusion_pattern, text))
  if len(matches) == 0:
    return None
  else:
    final_line = matches[-1].group(0).replace("\n", " ")
    final_line = regex.sub("न्नाम", "ं नाम", final_line)
    final_line = regex.sub(r"(?<=ो|र्)नाम(?=.+ध्यायः)", " नाम", final_line)
    matches = list(regex.finditer(r".+ +(\S+)( *)(?=नाम)", final_line))
    if len(matches) == 0:
      return None
    else:
      title = matches[-1].group(1)
    
    title = regex.sub("ं$", "म्", title)
    title = regex.sub("ो$", "ः", title)
    title = regex.sub("र्$", "ः", title)
    return title



def iti_saptamii_title_extractor(text, conclusion_pattern="इति.+ऽध्यायः"):
  matches = list(regex.finditer(conclusion_pattern, text))
  if len(matches) == 0:
    return None
  else:
    final_line = matches[-1].group(0).replace("\n", " ")
    final_line = regex.sub(" (च|तु) ", " ", final_line)
    matches = list(regex.finditer(r".+ +(\S+)(?= \S+ *ऽ?ध्यायः)", final_line))
    if len(matches) == 0:
      return None
    else:
      title = matches[-1].group(1)
    title = regex.sub("ं$", "म्", title)
    return title


def title_from_text(text, num_words=2, target_title_length=50, title_id=None, depunctuate=True, script=sanscript.DEVANAGARI):
  from doc_curation.md.content_processor.stripper import remove_non_content_text
  text = remove_non_content_text(content=text)
  from doc_curation.utils import text_utils
  title = text_utils.title_from_text(text=text, num_words=num_words, target_title_length=target_title_length, title_id=title_id, script=script, depunctuate=depunctuate)
  return title
