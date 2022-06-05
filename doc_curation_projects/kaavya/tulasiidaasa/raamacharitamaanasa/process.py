import os

import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


def fix_includes():
  md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/yAjJNavalkyaH/prastutiH", file_pattern="[0-9][0-9]*.md")

  for md_file in md_files:
    include_helper.transform_include_lines(md_file=md_file, transformer=include_helper.old_include_remover)
    include_helper.transform_include_lines(md_file=md_file, transformer=include_fixer)
    md_file.transform(content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)


def get_title_id(text_matched, index, file_title):
  if "चौपाई" not in file_title:
    id_in_text = regex.search("॥ *(\d+) *॥", text_matched).group(1)
    title_id = "%02d" % int(id_in_text)
  else:
    title_id = "%02d" % index
  return title_id


def title_maker_shloka(text_matched, index, file_title):
  title_id = get_title_id(text_matched, index, file_title)
  title = content_processor.title_from_text(text=text_matched, num_words=2, target_title_length=None,
                                            title_id=title_id)
  return title


def title_maker_TIkA(text_matched, index, file_title):
  title_id = get_title_id(text_matched, index, file_title)
  return title_id


def migrate_and_include_TIkA():

  def replacement_maker(text_matched, dest_path):
    return include_helper.vishvAsa_include_maker(dest_path, h1_level=3, title="भावार्थ")

  def destination_path_maker(title, original_path):
    return include_helper.static_include_path_maker(title, original_path, path_replacements={"TIkA": "hindI-bhAvArtha", ".md": ""}, use_preexisting_file_with_prefix=False)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, text_patterns=["\nभावार्थ[\s\S]+?॥\s*[०-९\d\.]+\s*॥.*?(?=\n|$)"], dir_path="/home/vvasuki/vishvAsa/bhAShAntaram/static/prakIrNAryabhAShAH/padya/rAmacharitamAnasa/TIkA", destination_path_maker=destination_path_maker, title_maker=title_maker_TIkA, replacement_maker=replacement_maker, dry_run=False)


def fix_paths(dest_dir):
  def sub_path_id_maker(file_path):
    return regex.sub(".+?/(\d\d_.+?)/.*(\d\d\d).+\.md", "\\1/\\2", file_path)
  metadata_helper.copy_metadata_and_filename(ref_dir="/home/vvasuki/vishvAsa/kalpAntaram/static/smRtiH/yAjJNavalkyaH/mUlam/", dest_dir=dest_dir, sub_path_id_maker=sub_path_id_maker)


if __name__ == '__main__':
  pass
  migrate_and_include_TIkA()
  # migrate_and_include_shlokas(chapter_id="02_vyavahAraH")
  # migrate_and_include_shlokas(chapter_id="03_prAyashchittam")
  # fix_paths(dest_dir="/home/vvasuki/vishvAsa/kalpAntaram/static/smRtiH/yAjJNavalkyaH/vishvAsa-prastutiH")
  # fix_includes()
