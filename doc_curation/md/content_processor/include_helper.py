import os

import regex

from curation_utils import file_helper
from doc_curation.md import content_processor, library
from indic_transliteration import sanscript

PATTERN_SHLOKA = r"\n[^#\s<>\[\(][\s\S]+?॥\s*[०-९\d\.]+\s*॥.*?(?=\n|$)"


def static_include_path_maker(title, original_path, path_replacements={"content": "static", ".md": ""}, use_preexisting_file_with_prefix=True):
  include_path = str(original_path)
  for key, value in path_replacements.items():
    include_path = include_path.replace(key, value)
  if include_path.endswith(".md"):
    return include_path
  else:
    dest_basename = file_helper.get_storage_name(text=title)
    if use_preexisting_file_with_prefix and os.path.exists(include_path):
      similar_files = [x for x in os.listdir(include_path) if x.startswith(dest_basename)]
      if len(similar_files) > 0:
        dest_basename = similar_files[0].replace(".md", "")
    return os.path.join(include_path, "%s.md" % dest_basename)


def vishvAsa_include_maker(file_path, h1_level=4, classes=None, title=None, ):
  url = file_path.replace("/home/vvasuki/vishvAsa/", "/").replace("/static/", "/")
  from doc_curation.md import library
  return library.get_include(url=url, h1_level=h1_level, classes=classes, title=title)


def init_word_title_maker(text_matched, index, file_title):
  title = content_processor.title_from_text(text=text_matched, num_words=2, target_title_length=None,
                                            title_id="%02d"  % (index + 1))
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
    if text_path is not None:
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
  [_, content] = md_file.read()
  content = regex.sub(r"<div.+js_include.+url=['\"](.+?)['\"][\s\S]+?</div>", transformer, content)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


def old_include_remover(match):
  """To be used with transform_include_lines.
  
  :param match: 
  :return: 
  """
  url = match.group(1)
  if "includeTitle" not in match.group(0):
    return ""
  else:
    return match.group(0)


def alt_include_adder(match, source_dir, alt_dirs, hugo_base_dir="/home/vvasuki/vishvAsa"):
  """To be used with transform_include_lines.
  
  :param match: 
  :param source_dir: Eg. "vishvAsa-prastutiH"
  :param alt_dirs: Eg: ["commentary-1", "commentary-2"]
  :return: 
  """
  def make_alt_include(url, file_path, target_dir, h1_level, source_dir=source_dir, classes=["collapsed"], title=None):
    alt_file_path = file_path.replace(source_dir, target_dir)
    alt_url = url.replace(source_dir, target_dir)
    if title is None:
      title = sanscript.transliterate(target_dir, sanscript.OPTITRANS, sanscript.DEVANAGARI)
    if os.path.exists(alt_file_path):
      return library.get_include(url=alt_url, h1_level=h1_level, classes=classes, title=title)
    return None


  url = match.group(1)
  file_path = file_path_from_url(url=url, hugo_base_dir=hugo_base_dir)
  main_include = match.group(0)
  h1_level = regex.search(r"newLevelForH1=['\"](\d)['\"]", main_include).group(1)
  h1_level = int(h1_level) + 1
  include_lines = [main_include]
  include_lines.extend([make_alt_include(url=url, file_path=file_path, h1_level=h1_level, target_dir=x) for x in alt_dirs])
  include_lines = [x for x in include_lines if x is not None]
  return "\n".join(include_lines)


def file_path_from_url(url, hugo_base_dir):
  file_path = regex.sub(r"(/.+?)(/.+)", "%s\\1/static\\2" % hugo_base_dir, url)
  return file_path


def include_basename_fixer(match, ref_dir):
  """To be used with transform_include_lines.
  
  :param match: 
  :param ref_dir: 
  :return: 
  """
  sub_path_to_reference = library.get_sub_path_to_reference_map(ref_dir=ref_dir)
  url = match.group(1)
  sub_path_id = library.get_sub_path_id(regex.sub(".+?/%s(/.+)" % os.path.basename(ref_dir), "\\1", url))
  base_url = regex.sub("(.+?/%s)/.+" % os.path.basename(ref_dir), "\\1", url)
  new_sub_path = regex.sub(".+?/%s(/.+)" % os.path.basename(ref_dir), "\\1", str(sub_path_to_reference[sub_path_id].file_path))
  new_url = os.path.abspath(base_url + new_sub_path)
  return match.group(0).replace(url, new_url)

