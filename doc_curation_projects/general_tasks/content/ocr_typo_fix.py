import os

import doc_curation.utils.sanskrit_helper
import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, section_helper, details_helper, ocr_helper, footnote_helper, space_helper
from doc_curation.utils import patterns
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript, aksharamukha_helper

def ocr_fix(dir_path):
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.fix_google_ocr_iast_iso(x))
  # 
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.fix_google_ocr(x))


def foxit_ocr_fix(dir_path):
  pass
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.fix_foxit(x))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.fix_dangling_maatraas(x))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: space_helper.fix_markup(x))

def misc_typos(dir_path):
  # doc_curation.clear_bad_chars(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/mImAMsA-naya-manjarI.md", dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: space_helper.fix_markup(x))

  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.misc_sanskrit_typos(x))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.fix_avagraha_quotations(x))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/social-cultivation/violence/articles/Sacred-ground_Bakker", content_transformer=lambda x, y: content_processor.fix_iast_gb(x))


  pass


if __name__ == '__main__':
  pass
  # ocr_fix("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/parichaya-sanxepAH/yatIndra-mata-dIpikA/laghu-vArtikam")
  # foxit_ocr_fix("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/svAmi-nArAyaNa-sampradAyaH/vaDatAla-paramparA/darshana-sAra-sangrahaH")
  # misc_typos("/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/abheda-darshanam/praty-abhijnA/utpaladevaH_Ishvara-pratyabhiJNA-kArikA/abhinavagupta-vimarshinI")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/pAdma-saMhitA/", patterns=["। *\n"], replacement="।  \n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/bhAgavatam/gauDIya-prastutiH/", patterns=[r"\\?[\|।] *\\?[\|।]"], replacement="॥")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/bhAgavatam/gauDIya-prastutiH/", patterns=[r"\\?[\|।]"], replacement="।")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/bhAgavatam/gauDIya-prastutiH/", patterns=[r"\n[\*\\॥। ]+\n"], replacement="\n------------------------------\n")

  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/kAraNAgamaH/", patterns=["ळ"], replacement="ल")


  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/satem/indo-iranian/indo-aryan/jAti-varNa-practice/v1/articles/sons_of_sarasvatI", content_transformer=lambda x, y: ocr_helper.fix_iast_for_pdfs(x), dry_run=False)
