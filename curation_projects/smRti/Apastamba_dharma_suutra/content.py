import os

import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from indic_transliteration import sanscript


def fix_includes():
  md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/dharma-sUtram/vishvAsa-prastutiH", file_pattern="[0-9][0-9]*.md")

  for md_file in md_files:
    include_helper.transform_include_lines(md_file=md_file, transformer=old_include_remover)
    include_helper.transform_include_lines(md_file=md_file, transformer=include_fixer)
    md_file.transform(content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)

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
  migrate_and_include_shlokas()
  # fix_includes()