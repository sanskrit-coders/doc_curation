import logging
import os

from curation_utils.file_helper import clear_bad_chars
from doc_curation import tei
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper


def dump_cu_sarit_markdown(tei_path, md_path, overwrite=False, dry_run=False):
  if os.path.exists(md_path) and not overwrite:
    logging.info("Skipping %s as it exists", md_path)
    return
  tei.dump_md(
    tei_path=tei_path,
    md_path=md_path,
    xsl=os.path.join(os.path.dirname(__file__), "xslt/tei-to-markdown-cu-sarit.xsl"))
  md_file = MdFile(file_path=md_path)
  md_file.transform(content_transformer=lambda x, y: clear_bad_chars(x), dry_run=dry_run)
  metadata_helper.set_title_from_filename(md_file=md_file, dry_run=dry_run)


def dump_naatyashaastra():
  for index in range(1, 38):
    dump_cu_sarit_markdown(tei_path="/home/vvasuki/sanskrit/raw_etexts/mixed/cu-sarit/Abhinavabhāratī/nāṭyaśāstra-%02d/abhinavabhāratī_%02d-dn.xml" % (index, index), md_path="/home/vvasuki/vishvAsa/kAvyam/content/shAstram/nATyam/nATyashAstram/abhinavabhAratI/%02d.md" % (index))
    dump_cu_sarit_markdown(tei_path="/home/vvasuki/sanskrit/raw_etexts/mixed/cu-sarit/Abhinavabhāratī/nāṭyaśāstra-%02d/nāṭyaśāstra_%02d-dn.xml" % (index, index), md_path="/home/vvasuki/vishvAsa/kAvyam/content/shAstram/nATyam/nATyashAstram/mUlam/%02d.md" % (index))

  library.fix_index_files("/home/vvasuki/vishvAsa/kAvyam/content/shAstram/nATyam/", dry_run=False)


if __name__ == '__main__':
  dump_naatyashaastra()