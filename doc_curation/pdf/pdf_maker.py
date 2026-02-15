from doc_curation.ebook import calibre_helper


def from_epub(epub_path):
  epub_path_min = epub_path.replace(".epub", "_min.epub")
  epub_path_min_notoc = epub_path.replace(".epub", "_min_notoc.epub")
  calibre_helper.to_pdf(epub_path=epub_path_min, paper_size="a4")

  a4_path = calibre_helper.to_pdf(epub_path=epub_path_min_notoc, paper_size="a4", move_toc=True)
  a5_path = calibre_helper.to_pdf(epub_path=epub_path_min_notoc, paper_size="a5", move_toc=True)
  # booklet.duplicated_booklet(input_pdf_path=a5_path, output_pdf_path=a5_path.replace(".pdf", "_dup_booklet.pdf"))

  return a4_path, a5_path