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
  

def migrate_and_include_sections():
  text_processor = lambda x: regex.sub("## .+?\n", "", x)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH/", text_patterns = ["## सूत्रम्\s*?\n[\\s\\S]+?(?=\n#|$)"], destination_path_maker=lambda title, original_path: include_helper.static_include_path_maker(title, original_path, path_replacements={"content": "static", "sUtra-pAThaH": "sUtra-pAThaH/vishvAsa-prastutiH"}), migrated_text_processor=text_processor, replacement_maker=lambda x: include_helper.vishvAsa_include_maker(x, h1_level=4, classes=["collapsed"], title="विश्वास-प्रस्तुतिः"),
                         title_maker=lambda text, index, file_title: file_title, dry_run=False)

def add_init_words_to_includes():
  def transformer(match):
    footnote_text = match.group(1)
    return "[%s]" % sanscript.transliterate(footnote_text, sanscript.OPTITRANS, sanscript.DEVANAGARI)
  library.apply_function(fn=MdFile.transform_content, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/04.md", content_transformer=lambda x, y: include_helper.transform_include_lines(x, transformer=transformer), dry_run=False)
  

def fix_footnotes():
  library.apply_function(fn=MdFile.transform_content, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH/", content_transformer=content_processor.define_footnotes_near_use, dry_run=False)


if __name__ == '__main__':
  pass
  # library.apply_function(fn=MdFile.fix_lazy_anusvaara, dir_path="/home/vvasuki/sanskrit/raw_etexts/kalpaH/shUdra-kamalAkaraH_sAnuvAdaH_ocr.md", dry_run=False, ignore_padaanta=True, omit_yrl=True)
  # doc_curation.clear_bad_chars(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/mImAMsA-naya-manjarI.md", dry_run=False)
  # library.apply_function(fn=MdFile.transliterate_content, dir_path="/home/vvasuki/vishvAsa/vedAH/static/Rk/shAkalam/saMhitA/thomson_solcum", source_scheme=sanscript.IAST)
  # library.apply_function(fn=MdFile.replace_in_content_lines, dir_path="/home/vvasuki/vishvAsa/purANam/static/rAmAyaNam/audIchya-pAThaH/vishvAsa-prastutiH", pattern="^[a-zA-Z-].+", replacement="", dry_run=False)
  # library.apply_function(fn=MdFile.drop_sections, dir_path="/home/vvasuki/vishvAsa/purANam/static/rAmAyaNam/audIchya-pAThaH/vishvAsa-prastutiH", title_condition=lambda x: x != "मूलम्")
  # library.apply_function(fn=MdFile.make_paras, dir_path="/home/vvasuki/vishvAsa/vedAH/static/Rk/shAkalam/saMhitA/jamison_brereton_notes")
  # migrate_and_include_shlokas()
  # add_init_words_to_includes()
  # library.apply_function(fn=library.combine_files_in_dir, dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH", file_pattern="**/_index.md", dry_run=False)
  # library.defolderify_single_md_dirs(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH", dry_run=False)
  # md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH", file_pattern="**/_index.md")  
  # migrate_and_include_sections()
  migrate_and_include_commentary()