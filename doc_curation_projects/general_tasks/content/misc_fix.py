import os

import doc_curation.utils.sanskrit_helper
import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, section_helper, details_helper, ocr_helper, footnote_helper, space_helper
from doc_curation.utils import patterns
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript, aksharamukha_helper


def fix_audio_tags():
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/4k-divya-prabandha/02_tiruppAvai/_index.md", content_transformer=lambda x, y: doc_curation.md.content_processor.embed_helper.set_audio_caption_from_filename(x, prefix="vibhA"), dry_run=False, silent_iteration=True)


def details_fix(dir_path):


  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c, pattern=patterns.PATTERN_MULTI_LINE_SHLOKA))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/rUpakam/sankalpa-sUryodayaH/1.md", content_transformer=details_helper.insert_duplicate_before)


  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/rAmAyaNam/goraxapura-pAThaH/hindy-anuvAdaH", content_transformer=lambda c, m: details_helper.transform_details_with_soup(content=c, metadata=m, transformer=details_helper.sanskrit_tag_transformer, title_pattern="विश्वास.*|मूल.*"))

  pass


def fix_whitespaces(dir_path):
  library.apply_function(fn=MdFile.transform, content_transformer=space_helper.make_paras, dir_path=dir_path)

  # library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m:space_helper.remove_fake_linebreaks(c), dir_path=dir_path)

  # library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m:space_helper.markdownify_newlines(c), dir_path=dir_path)


  pass


def misc_typos(dir_path):
  # doc_curation.clear_bad_chars(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/mImAMsA-naya-manjarI.md", dry_run=False)

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/strI-dharma-paddhatiH/leslie", content_transformer=lambda x, y: ocr_helper.fix_google_ocr_iast_iso(x))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/tarkasangrahaH/TIkA-mUlAni", content_transformer=lambda x, y: ocr_helper.fix_google_ocr(x))

  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.misc_sanskrit_typos(x))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.fix_google_ocr(x))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/social-cultivation/violence/articles/Sacred-ground_Bakker", content_transformer=lambda x, y: content_processor.fix_iast_gb(x))


  pass


if __name__ == '__main__':
  # fix_audio_tags()
  misc_typos("/home/vvasuki/gitland/vishvAsa/vedAH/content/meta/kalpaH/shrautam/articles/yajna-tattva-prakAshaH/")
  # fix_whitespaces(dir_path="/home/vvasuki/gitland/vishvAsa/english/content/prose/hindu/indologist/jones-william/discourse_3.md")
  # section_fix()
  # details_fix(dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/subhAShitam/shrIvaiShNava-muktaka-sangrahaH.md")


  pass
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/pAdma-saMhitA/", content_transformer=lambda x, y: ocr_helper.fix_mid_shloka_empty_lines(x))


  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/agni-purANam", patterns=[r"॥॥"], replacement=r"॥")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/bhAgavatam/gauDIya-prastutiH/", patterns=[r"\\?[\|।] *\\?[\|।]"], replacement="॥")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/bhAgavatam/gauDIya-prastutiH/", patterns=[r"\\?[\|।]"], replacement="।")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/bhAgavatam/gauDIya-prastutiH/", patterns=[r"\n[\*\\॥। ]+\n"], replacement="\n------------------------------\n")

  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/kAraNAgamaH/", patterns=["ळ"], replacement="ल")

  # migrate_and_include_shlokas()
  # add_init_words_to_includes()
  # md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH", file_pattern="**/_index.md")  
  # devanaagarify()
  # fix_footnotes(dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/rUpakam/sankalpa-sUryodayaH/02.md")

  # fix_footnotes("/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/sarit-markdown")

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/satem/indo-iranian/indo-aryan/jAti-varNa-practice/v1/articles/sons_of_sarasvatI", content_transformer=lambda x, y: ocr_helper.fix_iast_for_pdfs(x), dry_run=False)
