from doc_curation.ebook import calibre_helper
from doc_curation.ebook.pdf_book import booklet_maker
from doc_curation.ebook import pdf_book
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript
import os, regex


def make_script_pdfs(epub_path, scripts, booklets, metadata, *args, **kwargs):
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
    
    # A pdf for online viewing
    calibre_helper.to_pdf(epub_path=epub_path_min, paper_size="a4")
  
    # Not moving TOC here - https://bugs.launchpad.net/calibre/+bug/2141822
    # Instead setting init_note later.
    a4_path = calibre_helper.to_pdf(epub_path=epub_path_min_2cols, paper_size="a4", move_toc=True)
    a5_path = calibre_helper.to_pdf(epub_path=epub_path_min_notoc, paper_size="a5", move_toc=True)
  
    for booklet in booklets:
      sig_pages = None
      if "_" in booklet:
        sig_pages = booklet.split("_")[-1].split(":")
        sig_pages = [int(x) for x in sig_pages]
      if "a4" in booklet:
        booklet_maker.to_booklet(input_pdf_path=a4_path, output_pdf_path=None, sig_pages=sig_pages, signature_title="Part ", metadata=metadata)
      elif "a5:dup" in booklets:
        booklet_maker.duplicated_booklet(input_pdf_path=a5_path, output_pdf_path=None, sig_pages=sig_pages, signature_title="Part ")

    make_deprecated = False
    if make_deprecated:
      from doc_curation.ebook.pdf_book import latex
      a5_latex_path = regex.sub("(_min.*)?.epub", f"_A5.latex", epub_path_min_notoc)
      md_path_min = epub_path_min.replace("_min.epub", "_min.md")
      (metadata, content) = MdFile(md_path_min).read()
      latex_body = latex.from_md(content=content)
      latex.to_pdf(latex_body=latex_body, dest_path=a5_path.replace(".pdf", "_latex_local.pdf"), metadata=metadata)




def from_epub(epub_path, scripts=[sanscript.ISO], *args, **kwargs):
  make_script_pdfs(epub_path=epub_path, scripts=[None] + scripts, *args, **kwargs)
