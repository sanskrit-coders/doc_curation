import os

import doc_curation.utils.sanskrit_helper
import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, section_helper, details_helper, ocr_helper, footnote_helper, ambuda_helper
from doc_curation.utils import patterns
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript, aksharamukha_helper

BASE_DIR = "/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/strI-dharma-paddhatiH/"


def leslie():
  base_dir = os.path.join(BASE_DIR, "leslie")
  pass
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=base_dir, dry_run=False, source_script=None,  title_index_pattern=None)

  # base_dir = os.path.join(BASE_DIR, "leslie", "0.md")
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=base_dir, dry_run=False, source_script=None)

  # base_dir = os.path.join(BASE_DIR, "leslie", "0.md")
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=base_dir, dry_run=False, source_script=None)
  # base_dir = os.path.join(BASE_DIR, "leslie", "2_strIdharmapaddhati_of_tryambakayajvan/02_The_Daily_Duties_of_Women.md")
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=base_dir, dry_run=False, source_script=None)

def sarva_prastuti():
  base_dir = os.path.join(BASE_DIR, "sarva-prastutiH")
  # base_dir = os.path.join(BASE_DIR, "ambuda-raw.txt")
  # library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda c, m: ambuda_helper.replace_tags(c), dry_run=False)

  # library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda c, m: content_processor.separate_parts(c, exclusion_pattern=f"{patterns.TAMIL_ENG_DIGITS}+\s*{patterns.NON_DEV_PUNCT}*"), dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda c, m: details_helper.non_detail_parts_to_detail(c, title="तमिऴ्"), dry_run=False)
  # 
  # library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda c, m: details_helper.transliterate_details(c, source_script=sanscript.TAMIL, title="तमिऴ्"), dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda c, m: details_helper.insert_duplicate_before(c, m), dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda c, m: doc_curation.utils.sanskrit_helper.fix_lazy_anusvaara(c), dry_run=False)
  library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda x, y: aksharamukha_helper.manipravaalify(x), dry_run=False)


if __name__ == '__main__':
  # leslie()
  sarva_prastuti()
