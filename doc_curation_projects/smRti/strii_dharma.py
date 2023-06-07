import os

import doc_curation.utils.sanskrit_helper
import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, section_helper, details_helper, ocr_helper, footnote_helper
from doc_curation.utils import patterns
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

BASE_DIR = "/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/strI-dharma-paddhatiH/"


if __name__ == '__main__':
  library.apply_function(fn=MdFile.transform, dir_path=BASE_DIR, content_transformer=lambda c, m: content_processor.separate_parts(c, exclusion_pattern=f"{patterns.TAMIL_ENG_DIGITS}+\s*{patterns.NON_DEV_PUNCT}*"), dry_run=False)
