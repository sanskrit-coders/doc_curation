import os

import regex

from curation_utils import file_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


def migrate_and_include_shlokas():

  library.apply_function(fn=include_helper.migrate_and_replace_texts, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/12.md",
                         title_maker=lambda text, index: metadata_helper.shloka_title_maker(text=text), title_before_include="### %s", dry_run=False)


def migrate_and_include_commentary():
  text_processor = lambda x: regex.sub("^.+?\n", "", x)
  def title_maker(text_matched, index, file_title):
    id_in_text = regex.match("\.([०-९]+)", text_matched).group(1)
    title_id = "%03d" % int(id_in_text)
    return title_id

  def replacement_maker(text_matched, dest_path):
    id_line = regex.match("(\.[०-९]+?.+?)\n", text_matched).group(1)
    include_line = include_helper.vishvAsa_include_maker(dest_path, h1_level=4, classes=["collapsed"], title="मेधातिथिः")
    return "%s\n%s" % (id_line, include_line)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH/12/_index.md", text_patterns = ["\.[०-९]+? *॥.+\n[^>][\\s\\S]+?(?=\n>)"], destination_path_maker=lambda title, original_path: include_helper.static_include_path_maker(title, original_path, path_replacements={"content": "static", "_index.md": ""}), migrated_text_processor=text_processor, replacement_maker=replacement_maker,
                         title_maker=title_maker, dry_run=False)


def fix_footnotes():
  library.apply_function(fn=MdFile.transform_content, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH/", content_transformer=content_processor.define_footnotes_near_use, dry_run=False)


if __name__ == '__main__':
  pass
  # migrate_and_include_commentary()