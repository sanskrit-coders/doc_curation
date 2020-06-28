import logging
from pathlib import Path

from doc_curation import tei
import os

from doc_curation.md_helper import MdFile

def dump_markdown(src_dir, dest_dir):
    file_paths = sorted(Path(src_dir).glob("*.xml"))
    for file_path in file_paths:
        file_path = str(file_path)
        md_path = os.path.join(dest_dir, os.path.dirname(file_path.replace(src_dir, dest_dir)), os.path.basename(file_path).replace(".xml", ".md"))
        logging.info("Converting %s to %s", file_path, md_path)
        tei.dump_md(tei_path=file_path, md_path=md_path, xsl=os.path.join(os.path.dirname(__file__), "xslt/tei-to-markdown-sarit.xsl"))


dump_markdown(src_dir="/home/vvasuki/sanskrit/raw_etexts/mixed/sarit/", dest_dir="/home/vvasuki/sanskrit/raw_etexts/mixed/sarit-md/")

# tei.dump_md(tei_path="/home/vvasuki/sanskrit/SARIT-corpus/kumarila-tantravarttika.xml", md_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/tantravArtikam.md", xsl=os.path.join(os.path.dirname(__file__), "tantra-vArtikam.xsl"))
# MdFile(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/tantravArtikam.md").dump_mediawiki("/home/vvasuki/sanskrit/raw_etexts/mImAMsA/tantravArtikam.wiki")