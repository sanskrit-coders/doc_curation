import logging
import os
from pathlib import Path

from curation_utils.file_helper import clear_bad_chars
from doc_curation import tei
from doc_curation.md import content_processor
from doc_curation.md.file import MdFile
from doc_curation.md.library import content_helper
from indic_transliteration import sanscript


def dump_paippalaada():
  src_path = "/home/vvasuki/sanskrit/raw_etexts/mixed/gretil/gretil.sub.uni-goettingen.de/gretil/corpustei/sa_paippalAdasaMhitA.xml"


  md_path = "/home/vvasuki/sanskrit/raw_etexts/vedaH/atharva/paippalAda/saMhitA/gretil_22.md"
  # tei.dump_md(tei_path=src_path, md_path=md_path, xsl=os.path.join(os.path.dirname(__file__), "xslt/paippalaada.xsl"))
  md_file = MdFile(file_path=md_path)
  md_file.transform(content_transformer=lambda c, m: content_processor.transliterate(c, source_script=sanscript.IAST), dry_run=False)


if __name__ == '__main__':
  dump_paippalaada()

# dump_markdown(src_dir="/home/vvasuki/sanskrit/raw_etexts/mixed/sarit/", dest_dir="/home/vvasuki/sanskrit/raw_etexts/mixed/sarit-md/")