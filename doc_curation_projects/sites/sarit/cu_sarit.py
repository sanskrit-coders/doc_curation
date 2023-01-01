import logging
import os

from indic_transliteration import sanscript
from doc_curation.md.library import arrangement
from doc_curation.md import content_processor
from curation_utils.file_helper import clear_bad_chars
from doc_curation import tei
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper


def dump_cu_sarit_markdown(tei_path, md_path, xsl=os.path.join(os.path.dirname(__file__), "xslt/tei-to-markdown-cu-sarit.xsl"), overwrite=False, dry_run=False):
  # ALERT: Note that for this to work, it is essential that the below xmlns attribute be present:
  # <TEI xmlns="http://www.tei-c.org/ns/1.0">
  if os.path.exists(md_path) and not overwrite:
    logging.info("Skipping %s as it exists", md_path)
    return
  tei.dump_md(
    tei_path=tei_path,
    md_path=md_path,
    xsl=xsl)
  md_file = MdFile(file_path=md_path)
  md_file.transform(content_transformer=lambda x, y: clear_bad_chars(x), dry_run=dry_run)
  metadata_helper.set_title_from_filename(md_file=md_file, dry_run=dry_run)


def dump_naatyashaastra():
  for index in range(1, 38):
    dump_cu_sarit_markdown(tei_path="/home/vvasuki/sanskrit/raw_etexts/mixed/cu-sarit/Abhinavabhāratī/nāṭyaśāstra-%02d/abhinavabhāratī_%02d-dn.xml" % (index, index), md_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/shAstram/nATyam/nATyashAstram/abhinavabhAratI/%02d.md" % (index))
    dump_cu_sarit_markdown(tei_path="/home/vvasuki/sanskrit/raw_etexts/mixed/cu-sarit/Abhinavabhāratī/nāṭyaśāstra-%02d/nāṭyaśāstra_%02d-dn.xml" % (index, index), md_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/shAstram/nATyam/nATyashAstram/mUlam/%02d.md" % (index))

  arrangement.fix_index_files("/home/vvasuki/gitland/vishvAsa/kAvyam/content/shAstram/nATyam/", dry_run=False)


def dump_shRngaaraprakaasha():
  dump_cu_sarit_markdown(tei_path="/home/vvasuki/sanskrit/raw_etexts/mixed/sarit-raw/Śr̥ṅgāraprakāśa/srngaraprakasa-deva.xml", md_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxaNam/articles/bhoja-shRngAra-prakAshaH/_index.md", xsl="/home/vvasuki/sanskrit-coders/doc_curation/doc_curation/tei_xsl/markdown/tei-to-markdown.xsl")


def dump_miimaamsaa():
  # TODO : Fix tags first.
  dump_cu_sarit_markdown(tei_path="/home/vvasuki/sanskrit/raw_etexts/mixed/sarit-raw/Ślōkavārttika/kumārila-ślokavārttika-umveka_commentary-deva.xml", md_path="/home/vvasuki/gitland/vishvAsa/mImAMsA/content/pUrvA/granthAH/shloka-vArttikam/umbeka-TIkA.md")


def haravijaya():
  for chapter_number in range(1, ):
    dump_cu_sarit_markdown(tei_path="/home/vvasuki/sanskrit/raw_etexts/kAvyam/rathnAkara-TEI/haravijaya/%s/hv-%s-k.txt" % (id, id), md_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/haravijayaH/%s.md" % id)


def dump_brahmapuraana():
  md_path = "/home/vvasuki/gitland/vishvAsa/purANam/content/brahma-purANam.md"
  dir_path = md_path.replace(".md", "")
  # dump_cu_sarit_markdown(tei_path="/home/vvasuki/sanskrit/raw_etexts/mixed/sarit/brahmapurana.xml", md_path=md_path, xsl=os.path.join(os.path.dirname(__file__), "xslt/purANa.xsl"), overwrite=True)
  # library.apply_function(fn=content_processor.replace_texts, dir_path=md_path, patterns=["## (?=\d\n)"], replacement="## 0")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=md_path, patterns=["## (?=\d\d\n)"], replacement="## 0")
  # MdFile(file_path=md_path).split_to_bits(source_script=sanscript.IAST, title_index_pattern=None)
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: content_processor.transliterate(c, source_script=sanscript.IAST), dry_run=False)


if __name__ == '__main__':
  # dump_naatyashaastra()
  # dump_shRngaaraprakaasha()
  # dump_miimaamsaa()
  dump_brahmapuraana()