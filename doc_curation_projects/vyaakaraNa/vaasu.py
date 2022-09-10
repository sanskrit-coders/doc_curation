import itertools
import os

import doc_curation.md.content_processor.embed_helper
import doc_curation.md.content_processor.footnote_helper
import doc_curation.md.content_processor.line_helper
import doc_curation.md.content_processor.sanskrit_helper
import regex

from curation_utils import file_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, section_helper, details_helper, patterns
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


def fix_suutra_ids(dir_path):
  pass
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"([VI]+)\. *(\d+)\. *(\d+)"], replacement=r"\1.\2.\3")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"([VI]+)\. *I\. *(\d+)"], replacement=r"\1.1.\2")
  def deromanize(match):
    import roman
    return str(roman.fromRoman(match.group(0)))
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"[VI]+(?=\.\d+\.\d+)"], replacement=deromanize)



if __name__ == '__main__':
  pass
  fix_suutra_ids(dir_path="/home/vvasuki/sanskrit/raw_etexts/vyAkaraNam/aShTAdhyAyI_central-repo/vAsu")
