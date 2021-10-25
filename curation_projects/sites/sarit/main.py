import logging
import os
from pathlib import Path

from curation_utils.file_helper import clear_bad_chars
from doc_curation import tei
from doc_curation.md.file import MdFile


def dump_sarit_markdown(src_dir, dest_dir):
  file_paths = sorted(Path(src_dir).glob("*.xml"))
  for file_path in file_paths:
    file_path = str(file_path)
    md_path = os.path.join(dest_dir, os.path.dirname(file_path.replace(src_dir, dest_dir)),
                           os.path.basename(file_path).replace(".xml", ".md"))
    logging.info("Converting %s to %s", file_path, md_path)
    tei.dump_md(tei_path=file_path, md_path=md_path,
                xsl=os.path.join(os.path.dirname(__file__), "xslt/tei-to-markdown-sarit.xsl"))




# dump_markdown(src_dir="/home/vvasuki/sanskrit/raw_etexts/mixed/sarit/", dest_dir="/home/vvasuki/sanskrit/raw_etexts/mixed/sarit-md/")

# tei.dump_md(tei_path="/home/vvasuki/sanskrit/SARIT-corpus/kumarila-tantravarttika.xml", md_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/tantravArtikam.md", xsl=os.path.join(os.path.dirname(__file__), "tantra-vArtikam.xsl"))

# tei.dump_md(tei_path=os.path.join(os.path.dirname(__file__), "xslt/test.xml"), md_path="/home/vvasuki/vishvAsa/kAvyam/content/shAstram/nATyam/abhinavabhAratI/01.md", xsl=os.path.join(os.path.dirname(__file__), "xslt/tei-to-markdown-cu-sarit.xsl"))


# MdFile(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/tantravArtikam.md").dump_mediawiki("/home/vvasuki/sanskrit/raw_etexts/mImAMsA/tantravArtikam.wiki")
