"""
Curate and process pdf files.
"""
import logging
import os

from pikepdf import Pdf
from pathlib import Path

def _get_ocr_dir(pdf_path):
    return os.path.join(os.path.dirname(pdf_path), Path(pdf_path).stem + "_splits")

def ocr(pdf_path, google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json'):
    """
    OCR some pdf with google drive. Automatically splits into 25 page bits and ocrs them individually.
    
    :param pdf_path:
    :param google_key: A json key which can be obtained from https://console.cloud.google.com/iam-admin/serviceaccounts (create a project, generate a key via "Actions" column.). 
    :return: 
    """
    split_into_small_pdfs(pdf_path=pdf_path)
    from curation_utils.google.drive import DriveClient
    drive_client = DriveClient(google_key=google_key)
    pdf_segments = Path(_get_ocr_dir(pdf_path)).glob("*.pdf")
    for pdf_segment in sorted(pdf_segments):
        drive_client.ocr_file(local_file_path=str(pdf_segment))

def split_into_small_pdfs(pdf_path, output_directory=None, start_page=1, end_page=None, small_pdf_pages=25):
    def split(list_in, n):
        k, m = divmod(len(list_in), n)
        return (list_in[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))

    pdf_name_stem = Path(pdf_path).stem
    if output_directory == None:
        output_directory = _get_ocr_dir(pdf_path)
    # noinspection PyArgumentList
    with Pdf.open(pdf_path) as pdf:
        if end_page == None:
            end_page = len(pdf.pages)
        pages = range(start_page, end_page+1)
        page_sets = split(list_in=pages, n=small_pdf_pages)
        for page_set in page_sets:
            pages = [pdf.pages[i-1] for i in page_set]
            dest_pdf_path = os.path.join(output_directory, "%s_%04d-%04d.pdf" % (pdf_name_stem, page_set[0], page_set[-1]))
            if not os.path.exists(dest_pdf_path):
                # noinspection PyArgumentList
                dest_pdf = Pdf.new()
                dest_pdf.pages.extend(pages)
                os.makedirs(os.path.dirname(dest_pdf_path), exist_ok=True)
                dest_pdf.save(filename=dest_pdf_path)
            else:
                logging.warning("%s exists", dest_pdf_path)


