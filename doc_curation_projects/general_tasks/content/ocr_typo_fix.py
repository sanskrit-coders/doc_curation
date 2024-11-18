import os

import doc_curation.utils.sanskrit_helper
import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, section_helper, details_helper, ocr_helper, footnote_helper, space_helper
from doc_curation.utils import patterns, sanskrit_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

def ocr_fix_iast(dir_path):
  pass
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.fix_google_ocr_iast_iso(x))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: space_helper.make_paras(x))

def ocr_fix_dev(dir_path, keep_lines=False):
  pass
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.fix_google_ocr_devanaagarii(x, keep_lines=keep_lines))
  

def foxit_ocr_fix(dir_path):
  pass
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.fix_foxit(x))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.fix_dangling_maatraas(x))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: space_helper.fix_markup(x))

def fix_en_ocr(dir_path):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: space_helper.make_paras(x))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.strip_word_continuation_dashes(x))

def misc_typos(dir_path):
  # doc_curation.clear_bad_chars(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/mImAMsA-naya-manjarI.md", dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: space_helper.fix_markup(x))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: space_helper.markdownify_newlines(x))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: space_helper.remove_fake_linebreaks(x))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.strip_word_continuation_dashes(x))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.misc_sanskrit_typos(x))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.misc_manipravaala_typs(x))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.fix_avagraha_quotations(x))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.fix_pandoc_md(x))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/social-cultivation/violence/articles/Sacred-ground_Bakker", content_transformer=lambda x, y: content_processor.fix_iast_gb(x))


  pass


if __name__ == '__main__':
  # pass
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/rahasya-traya-sAraH/sAra-bodhinI", content_transformer=lambda x, y: sanskrit_helper.fix_lazy_anusvaara(x), dry_run=False, silent_iteration=False)

  # ocr_fix_dev("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/rahasya-traya-sAraH/sAra-bodhinI", keep_lines=False)
  # fix_en_ocr("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/paramparA/articles/shAttAdas_Lester.md")
  ocr_fix_iast("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/kriyA/govindaH_yati-dharma-samuchchayaH/en.md")
  # foxit_ocr_fix("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/svAmi-nArAyaNa-sampradAyaH/vaDatAla-paramparA/darshana-sAra-sangrahaH")
  # misc_typos("/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/rAmacharitamAnasa/rAmabhadra-TIkA")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/pAdma-saMhitA/", patterns=["। *\n"], replacement="।  \n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/bhAgavatam/gauDIya-prastutiH/", patterns=[r"\\?[\|।] *\\?[\|।]"], replacement="॥")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/bhAgavatam/gauDIya-prastutiH/", patterns=[r"\\?[\|।]"], replacement="।")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/bhAgavatam/gauDIya-prastutiH/", patterns=[r"\n[\*\\॥। ]+\n"], replacement="\n------------------------------\n")

  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/kAraNAgamaH/", patterns=["ळ"], replacement="ल")


  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/rUpakam/sankalpa-sUryodayaH/meta/nArAyaNa-raghunAthau", content_transformer=lambda x, y: ocr_helper.fix_iast_for_pdfs(x), dry_run=False)
