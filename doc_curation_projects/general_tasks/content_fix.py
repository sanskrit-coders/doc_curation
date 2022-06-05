import itertools
import os

import regex

from curation_utils import file_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, section_helper, details_helper
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
  

def fix_footnotes(dir_path):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: content_processor.define_footnotes_near_use(c), dry_run=False)


def devanaagarify(dir_path, source_script):
  def content_transformer(c, m): 
    c = content_processor.transliterate(text=c, source_script=source_script)
    c = sanscript.SCHEMES[sanscript.DEVANAGARI].fix_lazy_anusvaara(c, omit_sam=True, omit_yrl=True, ignore_padaanta=True)
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


def fix_audio_tags():
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/bhAShAntaram/content/tamiL/4k-divya-prabandha/02_tiruppAvai/_index.md", content_transformer=lambda x, y: content_processor.set_audio_caption_from_filename(x, prefix="vibhA"), dry_run=False, silent_iteration=True)


def prefill_vishvAsa_includes():
  import doc_curation_projects
  dirs = doc_curation_projects.vishvAsa_projects
  
  include_helper.prefill_includes(dir_path="/home/vvasuki/vishvAsa/kannaDa/content/padya/kumAra-vyAsa-bhArata/04_virATa/02.md")
  
  import itertools
  dirs = list(itertools.dropwhile(lambda x: x != "bhAShAntaram", dirs))
  for dir in dirs:
    dir_path = os.path.join("/home/vvasuki/vishvAsa/", dir)
    include_helper.prefill_includes(dir_path=os.path.join(dir_path, "static"))
    include_helper.prefill_includes(dir_path=os.path.join(dir_path, "content"))





if __name__ == '__main__':
  # devanaagarify(dir_path="/home/vvasuki/vishvAsa/purANam/content/rAmAyaNam/goraxapura-pAThaH/hindy-anuvAdaH/5_sundarakANDam/06-vana-nAshaH/044_rAvaNena_jambumAliprexaNam.md", source_script=sanscript.KANNADA)
  # fix_audio_tags()

  # prefill_vishvAsa_includes()
  pass
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/", content_transformer=lambda x, y: content_processor.fix_bad_anunaasikas(x), dry_run=False, silent_iteration=True, file_name_filter=lambda x: "documentation-theme" not in str(x))
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/sanskrit/", content_transformer=lambda x, y: content_processor.fix_bad_anunaasikas(x), dry_run=False, silent_iteration=True, file_name_filter=lambda x: False not in [y not in str(x) for y in ["sarit", "gitasupersite", "wellcome", "dhaval", "wikisource", "vishvAsa"]])

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/vedAH/static/Rk/shAkalam/saMhitA/sAyaNa-bhAShyam/", content_transformer=lambda x, y: sanscript.SCHEMES[sanscript.DEVANAGARI].fix_lazy_anusvaara(x, ignore_padaanta=True, omit_yrl=True), dry_run=False)
  # doc_curation.clear_bad_chars(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/mImAMsA-naya-manjarI.md", dry_run=False)
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/hiraNyakeshI/paddhatiH/saMskAraratnamAlA", patterns=[r"(?<=\n) (?=\S)"], replacement="", dry_run=False)

  # library.apply_function(fn=section_helper.create_sections_from_terminal_digits, dir_path="/home/vvasuki/vishvAsa/vedAH/content/Rk/shAkalam/aitareya-brAhmaNam/", dry_run=False)

  # library.apply_function(fn=details_helper.interleave_from_file, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/TIkA/padyam/madhurA-vijayam/sarva-prastutiH/4.md", source_file=lambda x: x.replace("sarva-prastutiH", "AnglAnuvAdaH"), detail_title="tiruvenkaTAchAri (Eng)", dry_run=False)

  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/laxaNam/articles/bhoja-shRngAra-prakAshaH/_index.md")
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
  fix_footnotes(dir_path="/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/articles/self-possessed/1_Orthodoxies_Madness_and_Method/1_Academic_and_Brahmanical_Orthodoxies/01_Sanskritic_Culture_and_the_Culture_of_Possession.md")

  # library.shift_contents(dir_path="/home/vvasuki/vishvAsa/purANam/static/mahAbhAratam/06-bhIShma-parva/02-bhagavad-gItA-parva/saMskRtam/rAmAnujaH/mUlam/13_xetra-xetrajna-yogaH", start_index=2, substitute_content_offset=-1)

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/purANam/content/mahAbhAratam/goraxapura-pAThaH/01_Adiparva/01_anukramaNikAparva/001_anukramaNikAparva.md", content_transformer=lambda c, m: details_helper.transform_details_with_soup(content=c, metadata=m, transformer=details_helper.vishvAsa_sanskrit_transformer))
