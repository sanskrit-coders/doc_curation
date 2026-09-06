import pymupdf4llm

from doc_curation.md.content_processor import footnote_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper


def pymupdf_to_markdown(pdf_path, md_path):
  content = pymupdf4llm.to_markdown(pdf_path)
  content = footnote_helper.fix_sup_footnotes(content)
  md_file = MdFile(file_path=md_path)
  md_file.dump_to_file(content=content, metadata={"title": "UNK"}, dry_run=False)
  metadata_helper.set_title_from_filename(md_file=md_file, dry_run=False)


