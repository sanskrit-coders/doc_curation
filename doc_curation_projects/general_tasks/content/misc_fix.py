import doc_curation.utils.sanskrit_helper

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile


def fix_audio_tags():
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/4k-divya-prabandha/02_tiruppAvai/_index.md", content_transformer=lambda x, y: doc_curation.md.content_processor.embed_helper.set_audio_caption_from_filename(x, prefix="vibhA"), dry_run=False, silent_iteration=True)


def details_fix():


  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/mudgala-purANam/5_lambodara-charitam/25.md", content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/rUpakam/sankalpa-sUryodayaH/1.md", content_transformer=details_helper.insert_duplicate_before)


  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/mahAbhAratam/goraxapura-pAThaH/01_Adiparva/01_anukramaNikAparva/001_anukramaNikAparva.md", content_transformer=lambda c, m: details_helper.transform_details_with_soup(content=c, metadata=m, transformer=details_helper.vishvAsa_sanskrit_transformer))

  pass


def fix_whitespaces(dir_path):
  # library.apply_function(fn=MdFile.transform, content_transformer=content_processor.make_paras, dir_path="/home/vvasuki/hindu-comm/weblogs/aryaakasha")

  # library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m:content_processor.markdownify_newlines(c), dir_path="/home/vvasuki/sanskrit/raw_etexts/vedaH/yajur/taittirIya/sAyaNa")


  pass


def misc_typos(dir_path):
  # doc_curation.clear_bad_chars(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/mImAMsA-naya-manjarI.md", dry_run=False)

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/strI-dharma-paddhatiH/leslie", content_transformer=lambda x, y: ocr_helper.fix_google_ocr_iast_iso(x))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/tarkasangrahaH/TIkA-mUlAni", content_transformer=lambda x, y: ocr_helper.fix_google_ocr(x))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/pAdma-saMhitA/", content_transformer=lambda x, y: ocr_helper.misc_sanskrit_typos(x))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/social-cultivation/violence/articles/Sacred-ground_Bakker", content_transformer=lambda x, y: content_processor.fix_iast_gb(x))


  pass


if __name__ == '__main__':
  # devanaagarify(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/paramparA/articles/kalai-quarrel/tenkalai-tAtAchArya-diatribe.md", source_script="tamil")
  # fix_audio_tags()
  # prefill_vishvAsa_includes()
  # shloka_formatting()
  # section_fix()
  # details_fix()

  pass
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/pAdma-saMhitA/", content_transformer=lambda x, y: ocr_helper.fix_mid_shloka_empty_lines(x))


  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/pAdma-saMhitA/", patterns=["। *\n"], replacement="।  \n")
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
