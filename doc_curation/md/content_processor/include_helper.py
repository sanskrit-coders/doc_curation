import os

import regex

from curation_utils import file_helper
from doc_curation.md import content_processor


PATTERN_SHLOKA = "\n[^#\s<][\s\S]+?॥\s*[०-९\d\.]+\s*॥.*?"


def static_include_path_maker(title, original_path, path_replacements={"content": "static", ".md": ""}):
  include_path = str(original_path)
  for key, value in path_replacements.items():
    include_path = include_path.replace(key, value)
  if include_path.endswith(".md"):
    return include_path
  else:
    return os.path.join(include_path, "%s.md" % file_helper.get_storage_name(text=title))


def vishvAsa_include_maker(shloka_path, h1_level=4, classes=None, title=None, ):
  url = shloka_path.replace("/home/vvasuki/vishvAsa/", "/").replace("/static/", "/")
  from doc_curation.md import library
  return library.get_include(url=url, h1_level=h1_level, classes=classes, title=title)


def migrate_and_replace_texts(md_file, text_patterns, replacement_maker=vishvAsa_include_maker, migrated_text_processor=None, destination_path_maker=static_include_path_maker, title_maker=None, dry_run=False):
  [metadata, content] = md_file.read_md_file()
  # For some regexes to work prefectly.
  content = "\n" + content
  matches = []
  for text_pattern in text_patterns:
    matches.extend(regex.findall(text_pattern, content))
  if title_maker is None:
    def title_maker(text, index, file_title):
      title = content_processor.title_from_text(text=text, num_words=2, target_title_length=None, depunctuate=True,
                                                title_id=index)
      return title
  for index, text_matched in enumerate(matches):
    text = text_matched
    if migrated_text_processor is not None:
      text = migrated_text_processor(text)
    title = title_maker(text=text_matched, index=index, file_title=metadata["title"])
    text_path = destination_path_maker(title, md_file.file_path)
    from doc_curation.md.file import MdFile
    md_file_dest = MdFile(file_path=text_path)
    md_file_dest.dump_to_file(metadata={"title": title}, content=text, dry_run=dry_run)
    include_text = replacement_maker(text_path)
    content = content.replace(text_matched.strip(), "%s\n" % include_text)
  md_file.replace_content(new_content=content, dry_run=dry_run)


def transform_include_lines(md_file, transformer, dry_run=False):
  [metadata, content] = md_file.read_md_file()
  content = regex.sub("<div.+js_include.+url=['\"](.+?)['\"][\s\S]+?</div>", transformer, content)
  md_file.replace_content(new_content=content, dry_run=dry_run)
