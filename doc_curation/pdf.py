"""
Curate and process pdf files.
"""
import logging
import os

from pikepdf import Pdf
from pathlib import Path

from curation_utils import list_helper


def _get_ocr_dir(pdf_path):
    return os.path.join(os.path.dirname(pdf_path), Path(pdf_path).stem + "_splits")

def split_and_ocr_on_drive(pdf_path, google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json', 
        small_pdf_pages=25, start_page=1, end_page=None):
    """
    OCR some pdf with google drive. Automatically splits into 25 page bits and ocrs them individually.
    
    Sometimes, the operation may time out, or you might get an Internal service error. In that case, try reducing small_pdf_pages.
    
    :param pdf_path:
    :param google_key: A json key which can be obtained from https://console.cloud.google.com/iam-admin/serviceaccounts (create a project, generate a key via "Actions" column.). 
    :param small_pdf_pages: Number of pages per segment - an argument used for splitting the pdf into small bits for OCR-ing. 
    :return: 
    """
    # TODO: If a PDF has layers, google drive ocr fails. Need to print into a pdf in such a case. 
    from curation_utils.google.drive import DriveClient
    drive_client = DriveClient(google_key=google_key)
    split_into_small_pdfs(pdf_path=pdf_path, small_pdf_pages=small_pdf_pages, 
        start_page=start_page, end_page=end_page)
    pdf_segments = Path(_get_ocr_dir(pdf_path)).glob("*.pdf")
    for pdf_segment in sorted(pdf_segments):
        drive_client.ocr_file(local_file_path=str(pdf_segment))
        os.remove(str(pdf_segment))


def split_into_small_pdfs(pdf_path, output_directory=None, start_page=1, end_page=None, small_pdf_pages=25):

    pdf_name_stem = Path(pdf_path).stem
    if output_directory == None:
        output_directory = _get_ocr_dir(pdf_path)
    # noinspection PyArgumentList
    with Pdf.open(pdf_path) as pdf:
        if end_page == None:
            end_page = len(pdf.pages)
        pages = range(start_page, end_page+1)
        page_sets = list_helper.divide_chunks(list_in=pages, n=small_pdf_pages)
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


