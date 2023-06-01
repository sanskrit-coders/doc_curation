import os

import doc_curation.utils.sanskrit_helper
import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, section_helper, details_helper, ocr_helper, \
  footnote_helper, line_helper
from doc_curation.utils import patterns
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


BASE_DIR = "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/tattvam/jIva-gosvAmI/ShaT-sandarbhaH/sarva-prastutiH"

def fix_all(dir_path=BASE_DIR):
  pass
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: content_processor.fix_special_tags(content=c))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: line_helper.fix_indented_quotations(content=c))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.define_footnotes_near_use(c), dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.fix_intra_word_footnotes(c), dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: content_processor.transliterate(c, source_script="iast_iso_m"), dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: content_processor.fix_bold_italics(c), dry_run=False)
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: line_helper.make_md_verse_lines(c), dry_run=False)


if __name__ == '__main__':
  fix_all()
  pass

