import os

import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from indic_transliteration import sanscript


def fix_includes():
  md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/sarva-prastutiH", file_pattern="[0-9][0-9]*.md")
  md_files = [f for f in md_files if os.path.basename(f.file_path) > "05.md" ]
  def include_fixer(match):
    return include_helper.alt_include_adder(match=match, source_dir="vishvAsa-prastutiH", alt_dirs=["gangAnatha-mUlAnuvAdaH", "medhAtithiH", "gangAnatha-bhAShyAnuvAdaH", "gangAnatha-TippanyaH", "gangAnatha-tulya-vAkyAni", "kullUkaH", "bhAruchiH", "buhler"])

  for md_file in md_files:
    include_helper.transform_include_lines(md_file=md_file, transformer=include_helper.old_include_remover)
    include_helper.transform_include_lines(md_file=md_file, transformer=include_fixer)
    md_file.transform(content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)

def get_title_id(text_matched):
  long_id_match = regex.search("\.([०-९]+)\.([०-९]+)\s+॥", text_matched)
  if long_id_match is not None:
    id_in_text = long_id_match.group(1)
    title_id = "%03d-%s" % (int(id_in_text), long_id_match.group(2))
  else:
    id_in_text = regex.search("\.([०-९]+)", text_matched).group(1)
    title_id = "%03d" % int(id_in_text)
  return title_id

def title_maker(text_matched, index, file_title):
  title_id = get_title_id(text_matched=text_matched)
  title = content_processor.title_from_text(text=text_matched, num_words=2, target_title_length=None,
                                            title_id=title_id)
  return title


def migrate_and_include_shlokas(chapter_id):

  def replacement_maker(text_matched, dest_path):
    return include_helper.vishvAsa_include_maker(dest_path, h1_level=3, title="FILE_TITLE")

  def destination_path_maker(title, original_path):
    return include_helper.static_include_path_maker(title, original_path, path_replacements={"content": "static", ".md": "", "manuH": "manuH/vishvAsa_prastutiH"}, use_preexisting_file_with_prefix=False)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, text_patterns=[include_helper.PATTERN_SHLOKA], dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/%02d.md" % chapter_id, destination_path_maker=destination_path_maker, title_maker=title_maker, replacement_maker=replacement_maker, dry_run=False)


if __name__ == '__main__':
  # migrate_and_include_shlokas(chapter_id=7)
  fix_includes()