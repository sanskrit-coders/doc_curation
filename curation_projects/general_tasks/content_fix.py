import os

import regex

from curation_utils import file_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, section_helper
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
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/04.md", content_transformer=lambda x, y: include_helper.transform_include_lines(x, transformer=transformer), dry_run=False)
  

def fix_footnotes():
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/hindutva/hindutva-hugo/content/rivals/academia/articles/witzel-dossier.md", content_transformer=lambda c, m: content_processor.define_footnotes_near_use(c), dry_run=False)


def devanaagarify(dir_path):
  def content_transformer(c, m): 
    c = content_processor.devanaagarify(text=c)
    c = regex.sub("\n\*\*(\s+)", "\n\\1**", c)
    c = regex.sub("\n[\t	 ]+", "\n> ", c)
    for x in range(1, 20):
      c = regex.sub("\n(>.+)\n\n+>", "\n\\1  \n>", c)
    return c
  
  library.apply_function(
    fn=MdFile.transform, dir_path=dir_path, 
    content_transformer=content_transformer,
    metadata_transformer=None,
  dry_run=False)


if __name__ == '__main__':
  # devanaagarify(dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/bhAruchiH")
  pass
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/", content_transformer=lambda x, y: content_processor.fix_bad_anunaasikas(x), dry_run=False, silent_iteration=True, file_name_filter=lambda x: "documentation-theme" not in str(x))
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/sanskrit/", content_transformer=lambda x, y: content_processor.fix_bad_anunaasikas(x), dry_run=False, silent_iteration=True, file_name_filter=lambda x: False not in [y not in str(x) for y in ["sarit", "gitasupersite", "wellcome", "dhaval", "wikisource", "vishvAsa"]])

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/vedAH/static/Rk/shAkalam/saMhitA/sAyaNa-bhAShyam/", content_transformer=lambda x, y: sanscript.SCHEMES[sanscript.DEVANAGARI].fix_lazy_anusvaara(x, ignore_padaanta=True, omit_yrl=True), dry_run=False)
  # doc_curation.clear_bad_chars(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/mImAMsA-naya-manjarI.md", dry_run=False)
  # library.apply_function(fn=MdFile.replace_in_content_lines, dir_path="/home/vvasuki/vishvAsa/purANam/static/rAmAyaNam/audIchya-pAThaH/vishvAsa-prastutiH", pattern="^[a-zA-Z-].+", replacement="", dry_run=False)
  # library.apply_function(fn=MdFile.drop_sections, dir_path="/home/vvasuki/vishvAsa/purANam/static/rAmAyaNam/audIchya-pAThaH/vishvAsa-prastutiH", title_condition=lambda x: x != "मूलम्")
  # library.apply_function(fn=MdFile.make_paras, dir_path="/home/vvasuki/vishvAsa/vedAH/static/Rk/shAkalam/saMhitA/jamison_brereton_notes")
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/rAmacharitamAnasa/TIkA", content_transformer=lambda x, y: content_processor.numerify_shloka_numbering(x))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/kANe", content_transformer=lambda x, y: content_processor.fix_google_ocr(x))

  title_post_processor = None
  # title_post_processor = lambda x: regex.sub("^मन्त्रः +", "", x)
  # title_post_processor = lambda x: regex.sub("[०-९]", "", x)
  # library.apply_function(fn=section_helper.add_init_words_to_section_titles, dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/1/4/8.md", dry_run=False, title_post_processor=title_post_processor, num_words=2)


  # migrate_and_include_shlokas()
  # add_init_words_to_includes()
  # md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH", file_pattern="**/_index.md")  
  # devanaagarify()
  # fix_footnotes()

  # library.shift_contents(dir_path="/home/vvasuki/vishvAsa/purANam/static/mahAbhAratam/06-bhIShma-parva/02-bhagavad-gItA-parva/saMskRtam/abhinava-guptaH/mUlam/02_sAnkhya-yogaH_sarva-", start_index=49, offset=1)