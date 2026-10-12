import logging
import os

import doc_curation.md.library.metadata_helper
import regex
from bs4 import BeautifulSoup
from curation_utils import file_helper
from doc_curation.md.content_processor.include.model import Include
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript


def static_include_path_maker(title, original_path, path_replacements={"content": "static", ".md": ""}, use_preexisting_file_with_prefix=True):
  include_path = str(original_path)
  for key, value in path_replacements.items():
    include_path = regex.sub(key, value, include_path)
  if include_path.endswith(".md"):
    return include_path
  else:
    dest_basename = file_helper.get_storage_name(text=title)
    if use_preexisting_file_with_prefix and os.path.exists(include_path):
      similar_files = [x for x in os.listdir(include_path) if x.startswith(dest_basename)]
      if len(similar_files) > 0:
        dest_basename = similar_files[0].replace(".md", "")
    return os.path.join(include_path, "%s.md" % dest_basename)

def vishvAsa_include_maker(file_path, h1_level=4, classes=None, title=None, extra_attributes=None):
  if not os.path.exists(file_path):
    logging.info(f"Does not exist - {file_path} . Skipping")
    return 
  url = file_path.replace("/home/vvasuki/gitland/vishvAsa/", "/").replace("/static/", "/")
  return Include(url=url, h1_level=h1_level, classes=classes, title=title, extra_attributes=extra_attributes).to_html_str()

def init_word_title_maker(text_matched, index, file_title):
  title = doc_curation.md.library.metadata_helper.title_from_text(text=text_matched, num_words=2, target_title_length=None,
                                                                  title_id="%02d"  % (index + 1))
  return title

def migrate_and_replace_texts(md_file, text_patterns, replacement_maker=vishvAsa_include_maker, migrated_text_processor=None, destination_path_maker=static_include_path_maker, title_maker=init_word_title_maker,
                              migration_mode="append", dry_run=False):
  """
  
  :param md_file: 
  :param text_patterns: 
  :param replacement_maker: 
  :param migrated_text_processor: 
  :param destination_path_maker: To not have migration, pass: lambda x, y: None 
  :param title_maker: 
  :param dry_run: 
  :return: 
  """
  logging.info("Processing %s", md_file.file_path)
  [metadata, content] = md_file.read()
  # For some regexes to work prefectly.
  content = "\n" + content
  matches = []
  for text_pattern in text_patterns:
    matches.extend(regex.finditer(text_pattern, content))
  for index, match in enumerate(matches):
    text_matched = match.group(0)
    text = text_matched.strip()
    if migrated_text_processor is not None:
      text = migrated_text_processor(text)
    title = title_maker(text_matched=text_matched, index=index, file_title=metadata["title"])
    text_path = destination_path_maker(title, md_file.file_path)
    if text_path is not None:
      from doc_curation.md.file import MdFile
      md_file_dest = MdFile(file_path=text_path)
      if os.path.exists(md_file_dest.file_path):
        if migration_mode == "append":
          md_file_dest.replace_content_metadata(new_content=lambda x: f"{x}\n\n{text}", dry_run=dry_run)
        else:
          md_file_dest.replace_content_metadata(new_content=text, dry_run=dry_run)
      else:
        md_file_dest.dump_to_file(metadata={"title": title}, content=text, dry_run=dry_run)
    include_text = replacement_maker(text_matched, text_path)
    content = content.replace(text_matched.strip(), "%s\n" % include_text, 1)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)

def make_alt_include(url, file_path, target_dir, h1_level, source_dir, classes=["collapsed"], title=None):
  alt_file_path = file_path.replace(source_dir, target_dir)
  if source_dir not in url:
    logging.fatal("%s %s - no %s found", url, file_path, source_dir)
  alt_url = url.replace(source_dir, target_dir)
  if title is None:
    index_file_path = regex.sub("%s/.+" % target_dir, "%s/_index.md" % target_dir, alt_file_path)
    if os.path.exists(index_file_path):
      md_file = MdFile(file_path=index_file_path)
      title = md_file.get_title()
    else:
      title = sanscript.transliterate(target_dir, sanscript.OPTITRANS, sanscript.DEVANAGARI)
  if os.path.exists(alt_file_path):
    html = Include(url=alt_url, h1_level=h1_level, classes=classes, title=title).to_html_str()
    html = f"<body>{html}</body>"
    return BeautifulSoup(html, 'html.parser').select_one("div")
  else:
    logging.error(f"{alt_file_path} not found!")
    return None
