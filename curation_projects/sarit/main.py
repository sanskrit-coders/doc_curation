from doc_curation import tei
import os

from doc_curation.md_helper import MdFile

# tei.dump_md(tei_path="/home/vvasuki/sanskrit/SARIT-corpus/kumarila-tantravarttika.xml", md_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/tantravArtikam.md", xsl=os.path.join(os.path.dirname(__file__), "tantra-vArtikam.xsl"))
MdFile(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/tantravArtikam.md").dump_mediawiki("/home/vvasuki/sanskrit/raw_etexts/mImAMsA/tantravArtikam.wiki")