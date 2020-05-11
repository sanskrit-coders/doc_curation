from doc_curation import tei
import os

tei.dump_md(tei_path="/home/vvasuki/sanskrit/SARIT-corpus/kumarila-tantravarttika.xml", md_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/tantravArtikam.md", xsl=os.path.join(os.path.dirname(__file__), "tantra-vArtikam.xsl"))
# tei.dump_wiki(tei_path="/home/vvasuki/sanskrit/SARIT-corpus/kumarila-tantravarttika.xml", md_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/tantravArtikam.md")