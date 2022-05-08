import regex

from doc_curation_projects.smRti.manu import content
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile


def get_canonical_verse_number(verse_num, chapter_id):
  verse_maps = {
    "08": {248: 250, 250: 248 }
  }
  verse_map = verse_maps.get(chapter_id, {})
  verse_num = verse_map.get(verse_num, verse_num)
  if chapter_id == "03" and verse_num >= 57:
    verse_num += 10
  if chapter_id == "05":
    if verse_num >= 61 and verse_num <= 121:
      verse_num += 1
    elif verse_num >= 122:
      verse_num += 2
  return verse_num


def title_maker(text_matched, index, file_title):
  title_id = content.get_title_id(text_matched=text_matched)
  return title_id + "_"


def migrate_and_include_commentary(chapter_id):
  text_processor = lambda x: regex.sub("^.+?\n", "", x)

  def replacement_maker(text_matched, dest_path):
    id_line = regex.match("(.+॥.+\n)\n", text_matched).group(1)
    include_line = include_helper.vishvAsa_include_maker(dest_path, h1_level=4, classes=["collapsed"], title="मेधातिथिः")
    return "%s\n%s" % (id_line, include_line)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH/%s.md" % chapter_id, text_patterns = ["[॥ ०-९]+\.[०-९\.]+? *॥.+\n[^>][\\s\\S]+?(?=\n>|$)"], migrated_text_processor=text_processor, replacement_maker=replacement_maker,
                         title_maker=title_maker, dry_run=False)


def fix_footnotes():
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH/", content_transformer=content_processor.define_footnotes_near_use, dry_run=False)


if __name__ == '__main__':
  pass
  # library.combine_files_in_dir(md_file=MdFile(file_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH/08/_index.md"))
  # library.defolderify_single_md_dirs(dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH")
  migrate_and_include_commentary(chapter_id="%02d" % 7)
  # logging.info(get_canonical_verse_number(248, "08"))
  # logging.info(get_canonical_verse_number(178, "03"))