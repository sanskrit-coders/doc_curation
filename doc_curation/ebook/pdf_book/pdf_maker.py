from doc_curation.ebook import calibre_helper
from doc_curation.ebook.pdf_book import booklet_maker
from indic_transliteration import sanscript
import os


def make_script_pdfs(epub_path, scripts, booklets):
  for script in scripts:
    if script is None:
      script_dir = os.path.dirname(epub_path)
    else:
      script_dir = os.path.join(os.path.dirname(epub_path), script)
    script_epub_path = os.path.join(script_dir, os.path.basename(epub_path))
    os.makedirs(script_dir, exist_ok=True)
    epub_path_min = script_epub_path.replace(".epub", "_min.epub")
    epub_path_min_notoc = script_epub_path.replace(".epub", "_min_notoc.epub")
    epub_path_min_2cols = script_epub_path.replace(".epub", "_min_notoc_2cols.epub")
    calibre_helper.to_pdf(epub_path=epub_path_min, paper_size="a4")
  
    # Not moving TOC here - https://bugs.launchpad.net/calibre/+bug/2141822
    a4_path = calibre_helper.to_pdf(epub_path=epub_path_min_2cols, paper_size="a4", move_toc=False)
    a5_path = calibre_helper.to_pdf(epub_path=epub_path_min_notoc, paper_size="a5", move_toc=True)
  
    if "a4" in booklets:
      booklet_maker.to_booklet(input_pdf_path=a4_path, output_pdf_path=None)
    if "a5_dup" in booklets:
      booklet_maker.duplicated_booklet(input_pdf_path=a5_path, output_pdf_path=a5_path.replace(".pdf", "_dup_booklet.pdf"))


def from_epub(epub_path, scripts=[sanscript.ISO], booklets=["a4"]):
  make_script_pdfs(epub_path=epub_path, scripts=[None] + scripts, booklets=booklets)
