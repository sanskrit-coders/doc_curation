import os

import regex

from curation_utils import file_helper
from doc_curation.md import content_processor


PATTERN_SHLOKA = "\n[^#\s<>\[\(][\s\S]+?॥\s*[०-९\d\.]+\s*॥.*?(?=\n|$)"


def static_include_path_maker(title, original_path, path_replacements={"content": "static", ".md": ""}, use_preexisting_file_with_prefix=True):
  include_path = str(original_path)
  for key, value in path_replacements.items():
    include_path = include_path.replace(key, value)
  if include_path.endswith(".md"):
    return include_path
  else:
    dest_basename = file_helper.get_storage_name(text=title)
    if use_preexisting_file_with_prefix:
      similar_files = [x for x in os.listdir(include_path) if x.startswith(dest_basename)]
      if len(similar_files) > 0:
        dest_basename = similar_files[0].replace(".md", "")
    return os.path.join(include_path, "%s.md" % dest_basename)


def vishvAsa_include_maker(shloka_path, h1_level=4, classes=None, title=None, ):
  url = shloka_path.replace("/home/vvasuki/vishvAsa/", "/").replace("/static/", "/")
  from doc_curation.md import library
  return library.get_include(url=url, h1_level=h1_level, classes=classes, title=title)


def init_word_title_maker(text_matched, index, file_title):
  title = content_processor.title_from_text(text=text_matched, num_words=2, target_title_length=None,
                                            title_id=index)
  return title


def migrate_and_replace_texts(md_file, text_patterns, replacement_maker=vishvAsa_include_maker, migrated_text_processor=None, destination_path_maker=static_include_path_maker, title_maker=init_word_title_maker, dry_run=False):
  [metadata, content] = md_file.read()
  # For some regexes to work prefectly.
  content = "\n" + content
  matches = []
  for text_pattern in text_patterns:
    matches.extend(regex.findall(text_pattern, content))
  for index, text_matched in enumerate(matches):
    text = text_matched.strip()
    if migrated_text_processor is not None:
      text = migrated_text_processor(text)
    title = title_maker(text_matched=text_matched, index=index, file_title=metadata["title"])
    text_path = destination_path_maker(title, md_file.file_path)
    from doc_curation.md.file import MdFile
    md_file_dest = MdFile(file_path=text_path)
    if os.path.exists(md_file_dest.file_path):
      md_file_dest.replace_content_metadata(new_content=text, dry_run=dry_run)
    else:
      md_file_dest.dump_to_file(metadata={"title": title}, content=text, dry_run=dry_run)
    include_text = replacement_maker(text_matched, text_path)
    content = content.replace(text_matched.strip(), "%s\n" % include_text)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


def transform_include_lines(md_file, transformer, dry_run=False):
  [metadata, content] = md_file.read()
  content = regex.sub("<div.+js_include.+url=['\"](.+?)['\"][\s\S]+?</div>", transformer, content)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)
