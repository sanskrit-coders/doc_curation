import os

from pikepdf import Pdf
from pathlib import Path


def split_into_small_pdfs(pdf_path, output_directory=None, start_page=1, end_page=None, small_pdf_pages=25):
    def split(list_in, n):
        k, m = divmod(len(list_in), n)
        return (list_in[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))

    pdf_name_stem = Path(pdf_path).stem
    if output_directory == None:
        output_directory = os.path.join(os.path.dirname(pdf_path), pdf_name_stem + "_splits")
    with Pdf.open(pdf_path) as pdf:
        if end_page == None:
            end_page = len(pdf.pages)
        pages = range(start_page, end_page+1)
        page_sets = split(list_in=pages, n=small_pdf_pages)
        for page_set in page_sets:
            pages = [pdf.pages[i-1] for i in page_set]
            dest_pdf = Pdf.new()
            dest_pdf.pages.extend(pages)
            dest_pdf_path = os.path.join(output_directory, "%s_%04d-%04d.pdf" % (pdf_name_stem, page_set[0], page_set[-1]))
            os.makedirs(os.path.dirname(dest_pdf_path), exist_ok=True)
            dest_pdf.save(filename=dest_pdf_path)
