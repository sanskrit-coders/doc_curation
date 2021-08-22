import os

import regex

from curation_utils import file_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


def get_canonical_verse_number(verse_num, chapter_id):
  verse_maps = {
    "08": {248: 250, 250: 248 }
  }
  verse_map = verse_maps.get(chapter_id, {})
  verse_num = verse_map.get(verse_num, verse_num)
  if chapter_id == "03" and verse_num >= 57:
    verse_num += 10
  return verse_num


def migrate_and_include_commentary(chapter_id):
  text_processor = lambda x: regex.sub("^.+?\n", "", x)
  def title_maker(text_matched, index, file_title):
    id_in_text = regex.match("\.([०-९]+)", text_matched).group(1)
    verse_num = get_canonical_verse_number(verse_num=int(id_in_text), chapter_id=chapter_id)
    title_id = "%03d" % verse_num
    return title_id

  def replacement_maker(text_matched, dest_path):
    id_line = regex.match("(\.[०-९]+?.+?)\n", text_matched).group(1)
    include_line = include_helper.vishvAsa_include_maker(dest_path, h1_level=4, classes=["collapsed"], title="मेधातिथिः")
    return "%s\n%s" % (id_line, include_line)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH/%02d.md" % chapter_id, text_patterns = ["\.[०-९]+? *॥.+\n[^>][\\s\\S]+?(?=\n>|$)"], migrated_text_processor=text_processor, replacement_maker=replacement_maker,
                         title_maker=title_maker, dry_run=False)


def fix_footnotes():
  library.apply_function(fn=MdFile.transform_content, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH/", content_transformer=content_processor.define_footnotes_near_use, dry_run=False)


if __name__ == '__main__':
  pass
  # library.combine_files_in_dir(md_file=MdFile(file_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH/08/_index.md"))
  # library.defolderify_single_md_dirs(dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH")
  migrate_and_include_commentary(chapter_id=8)