import functools
import os

import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript
import functools
import logging

@functools.lru_cache
def get_suutra_id_to_md():
  suutra_id_to_md = {}
  md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/vedAH/static/yajuH/taittirIyam/sUtram/ApastambaH/dharma-sUtram/vishvAsa-prastutiH", file_pattern="**/[0-9][0-9]*.md")
  for md_file in md_files:
    file_path = str(md_file.file_path)
    match = regex.search(pattern=r"(\d)/(\d\d)/(\d\d)/(\d\d)_", string=file_path)
    suutra_id = match.group(1) + str(int(match.group(2))) + str(int(match.group(3))) + str(int(match.group(4)))
    if suutra_id in suutra_id_to_md:
      logging.warning("suutra_id duplicate: %s, %s, %s", suutra_id, suutra_id_to_md[suutra_id], file_path)
    suutra_id_to_md[suutra_id] = md_file
  return suutra_id_to_md

def fix_includes():
  md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/dharma-sUtram/vishvAsa-prastutiH", file_pattern="[0-9][0-9]*.md")

  for md_file in md_files:
    include_helper.transform_include_lines(md_file=md_file, transformer=old_include_remover)
    include_helper.transform_include_lines(md_file=md_file, transformer=include_fixer)
    md_file.transform(content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)


def suutra_include_maker(suutra_id_dev, text_path, *args, **kwargs):
  """
  
  ११११ → 1/01/01/01
  ११११० → 1/01/01/10
  १३१०११ → 1/3/10/11
  १११३१२२ → 1/11/31/22
  
  :param suutra_id_dev: 
  :return: 
  """
  suutra_id = sanscript.transliterate(suutra_id_dev, _from=sanscript.DEVANAGARI, _to=sanscript.IAST).strip()
  suutra_id_to_md = get_suutra_id_to_md()
  if suutra_id not in suutra_id_to_md:
    logging.fatal("%s from %s not found", suutra_id, text_path)
  return include_helper.vishvAsa_include_maker(file_path=suutra_id_to_md[suutra_id].file_path, h1_level=4, classes=None, title=None, )


def replace_suutraid_with_includes():
  md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/dharma-sUtram/viShaya-vibhAgaH")
  for md_file in md_files:
    include_helper.migrate_and_replace_texts(md_file=md_file, text_patterns=[r"(?<=[^०-९]|^)[०-९]+(?=[^०-९]|$)"], replacement_maker=suutra_include_maker, migrated_text_processor=None, destination_path_maker=lambda *args, **kwargs: None, title_maker=lambda *args, **kwargs: None, dry_run=False)


def get_title_id(text_matched):
  id_in_text = regex.search("([०-९]+) *$", text_matched).group(1)
  title_id = "%02d" % int(sanscript.transliterate(id_in_text, sanscript.DEVANAGARI, sanscript.IAST))
  return title_id

def title_maker(text_matched, index, file_title):
  title_id = get_title_id(text_matched=text_matched)
  text_without_id = regex.sub(" *([०-९]+) *$", "", text_matched)
  title = content_processor.title_from_text(text=text_without_id, num_words=3, target_title_length=None,
                                            title_id=title_id)
  return title


def migrate_and_include_shlokas():

  def replacement_maker(text_matched, dest_path):
    return include_helper.vishvAsa_include_maker(dest_path, h1_level=3, title="FILE_TITLE")

  PATTERN_SUTRA = "\n[^#\s<>\[\(][\s\S]+? \s*[०-९\d\.]+\s*?(?=\n|$)"
  library.apply_function(fn=include_helper.migrate_and_replace_texts, text_patterns=[PATTERN_SUTRA], dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/dharma-sUtram/vishvAsa-prastutiH", replacement_maker=replacement_maker, title_maker=title_maker, dry_run=False)


if __name__ == '__main__':
  # migrate_and_include_shlokas()
  # fix_includes()
  replace_suutraid_with_includes()