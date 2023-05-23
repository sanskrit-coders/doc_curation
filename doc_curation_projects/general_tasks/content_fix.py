import os

import doc_curation.utils.sanskrit_helper
import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, section_helper, details_helper, ocr_helper, footnote_helper
from doc_curation.utils import patterns
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


def migrate_and_include_shlokas():

  library.apply_function(fn=include_helper.migrate_and_replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/smRtiH/manuH/12.md",
                         title_maker=lambda text, index: metadata_helper.shloka_title_maker(text=text), title_before_include="### %s", dry_run=False)
  

def migrate_and_include_sections():
  text_processor = lambda x: regex.sub("## .+?\n", "", x)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH/", text_patterns = ["## सूत्रम्\s*?\n[\\s\\S]+?(?=\n#|$)"], destination_path_maker=lambda title, original_path: include_helper.static_include_path_maker(title, original_path, path_replacements={"content": "static", "sUtra-pAThaH": "sUtra-pAThaH/vishvAsa-prastutiH"}), migrated_text_processor=text_processor, replacement_maker=lambda x: include_helper.vishvAsa_include_maker(x, h1_level=4, classes=["collapsed"], title="विश्वास-प्रस्तुतिः"),
                         title_maker=lambda text, index, file_title: file_title, dry_run=False)

def add_init_words_to_includes():
  def transformer(match):
    footnote_text = match.group(1)
    return "[%s]" % sanscript.transliterate(footnote_text, sanscript.OPTITRANS, sanscript.DEVANAGARI)
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/smRtiH/manuH/04.md", content_transformer=lambda x, y: include_helper.transform_include_lines(x, transformer=transformer), dry_run=False)
  

def fix_footnotes(dir_path):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.define_footnotes_near_use(c), dry_run=False)
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.fix_intra_word_footnotes(c), dry_run=False)


def devanaagarify(dir_path, source_script):
  def content_transformer(c, m):
    c = footnote_helper.define_footnotes_near_use(c)
    c = content_processor.transliterate(text=c, source_script=source_script)
    c = doc_curation.utils.sanskrit_helper.fix_lazy_anusvaara(c)
    c = regex.sub(r"\n\*\*(\s+)", "\n\\1**", c)
    c = regex.sub(r"\*\* *(\n+)\*\*", "  \n", c)
    c = regex.sub(r"(?<=[^:])\n+[\t	 ]+", "\n> ", c)
    for x in range(1, 20):
      c = regex.sub("\n(>.+)\n\n+>", "\n\\1  \n>", c)
    return c
  
  library.apply_function(
    fn=MdFile.transform, dir_path=dir_path, 
    content_transformer=content_transformer,
    metadata_transformer=None,
  dry_run=False)
  


def fix_audio_tags():
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/4k-divya-prabandha/02_tiruppAvai/_index.md", content_transformer=lambda x, y: doc_curation.md.content_processor.embed_helper.set_audio_caption_from_filename(x, prefix="vibhA"), dry_run=False, silent_iteration=True)


def prefill_vishvAsa_includes():
  import doc_curation_projects
  dirs = doc_curation_projects.vishvAsa_projects
  
  include_helper.prefill_includes(dir_path="/home/vvasuki/gitland/vishvAsa/kannaDa/content/padya/kumAra-vyAsa-bhArata/04_virATa/02.md")
  
  import itertools
  dirs = list(itertools.dropwhile(lambda x: x != "bhAShAntaram", dirs))
  for dir in dirs:
    dir_path = os.path.join("/home/vvasuki/gitland/vishvAsa/", dir)
    include_helper.prefill_includes(dir_path=os.path.join(dir_path, "static"))
    include_helper.prefill_includes(dir_path=os.path.join(dir_path, "content"))


def shloka_formatting():
  pass
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/skanda-purANam/8_ambikA-khaNDaH", content_transformer=lambda c, m: doc_curation.md.content_processor.line_helper.make_md_verse_lines(text=c))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/rAmacharitamAnasa/TIkA", content_transformer=lambda x, y: content_processor.numerify_shloka_numbering(x))


def details_fix():


  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/mudgala-purANam/5_lambodara-charitam/25.md", content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/rUpakam/sankalpa-sUryodayaH/1.md", content_transformer=details_helper.insert_duplicate_before)


  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/mahAbhAratam/goraxapura-pAThaH/01_Adiparva/01_anukramaNikAparva/001_anukramaNikAparva.md", content_transformer=lambda c, m: details_helper.transform_details_with_soup(content=c, metadata=m, transformer=details_helper.vishvAsa_sanskrit_transformer))

  pass

def section_fix():
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/kentum/mediterranian/articles/durant_caesar_and_christ", content_transformer=lambda x, y: section_helper.derominize_section_numbers(x))

  base_dir = "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/mahAbhAratam/goraxapura-pAThaH/hindy-anuvAdaH/13_anushAsanaparva/01_dAna-dharma-parva/149_viShNu-sahasra-nAma-stotram/TIkA/sarva-prastutiH"
  # library.apply_function(fn=section_helper.autonumber, dir_path=os.path.join(base_dir, "_index.md"), start_index=1)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(base_dir), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 

  # section_helper.merge_sections(md_files=[MdFile(file_path=os.path.join(base_dir, "en.md")), MdFile(file_path=os.path.join(base_dir, "bhagavadguNadarpaNam.md")), ], section_hasher=section_helper.section_hash_by_index)

  title_post_processor = None
  # title_post_processor = lambda x: regex.sub("^मन्त्रः +", "", x)
  # title_post_processor = lambda x: regex.sub("[०-९]", "", x)
  # library.apply_function(fn=section_helper.add_init_words_to_section_titles, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/1/4/8.md", dry_run=False, title_post_processor=title_post_processor, num_words=2)


if __name__ == '__main__':
  # devanaagarify(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/tattvam/temp", source_script="iast_iso_m")
  # fix_audio_tags()
  # prefill_vishvAsa_includes()
  # shloka_formatting()
  # section_fix()
  details_fix()

  pass
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/", content_transformer=lambda x, y: content_processor.fix_bad_anunaasikas(x), dry_run=False, silent_iteration=True, file_name_filter=lambda x: "documentation-theme" not in str(x))
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/sanskrit/", content_transformer=lambda x, y: content_processor.fix_bad_anunaasikas(x), dry_run=False, silent_iteration=True, file_name_filter=lambda x: False not in [y not in str(x) for y in ["sarit", "gitasupersite", "wellcome", "dhaval", "wikisource", "vishvAsa"]])
  
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/rUpakam/sankalpa-sUryodayaH/meta/upodghAtaH.md", content_transformer=lambda x, y: sanscript.SCHEMES[sanscript.DEVANAGARI].fix_lazy_anusvaara(x, ignore_padaanta=True, omit_yrl=True), dry_run=False)
  # doc_curation.clear_bad_chars(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/mImAMsA-naya-manjarI.md", dry_run=False)

  # library.apply_function(fn=MdFile.transform, content_transformer=content_processor.make_paras, dir_path="/home/vvasuki/hindu-comm/weblogs/aryaakasha")

  # library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m:content_processor.markdownify_newlines(c), dir_path="/home/vvasuki/sanskrit/raw_etexts/vedaH/yajur/taittirIya/sAyaNa")

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/articles/winternitz-Apastamba-mantra-pATha.md", content_transformer=lambda x, y: ocr_helper.fix_google_ocr_iast_iso(x))
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/tarkasangrahaH/TIkA-mUlAni", content_transformer=lambda x, y: ocr_helper.fix_google_ocr(x))
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/pAdma-saMhitA/", content_transformer=lambda x, y: ocr_helper.misc_sanskrit_typos(x))
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/pAdma-saMhitA/", content_transformer=lambda x, y: ocr_helper.fix_mid_shloka_empty_lines(x))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/social-cultivation/violence/articles/Sacred-ground_Bakker", content_transformer=lambda x, y: content_processor.fix_iast_gb(x))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/articles/homa-variations", content_transformer=lambda x, y: footnote_helper.fix_plain_footnotes(x))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/pAdma-saMhitA/", content_transformer=lambda x, y: footnote_helper.fix_plain_footnotes(x, def_pattern=r"\((\d+)[\. ]*([^\d\)][^\)]+)\) *", def_replacement_pattern=r"\n[^\1]: \2\n", ref_pattern=r"\((\d+)\)"))


  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/pAdma-saMhitA/", patterns=["। *\n"], replacement="।  \n")

  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/kAraNAgamaH/", patterns=["ळ"], replacement="ल")

  # migrate_and_include_shlokas()
  # add_init_words_to_includes()
  # md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH", file_pattern="**/_index.md")  
  # devanaagarify()
  # fix_footnotes(dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/rUpakam/sankalpa-sUryodayaH/02.md")

  # fix_footnotes("/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/champUH/vishva-guNAdarshaH.md")