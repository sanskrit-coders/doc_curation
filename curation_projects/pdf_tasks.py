import logging

import doc_curation.pdf.drive_ocr
from doc_curation import pdf

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def get_from_archive(item_id):
    pass


if __name__ == '__main__':
    doc_curation.pdf.drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/purANam/mahAbhAratam_gItA-press/mahabharata01ramauoft.pdf", small_pdf_pages=5, start_page=336, pdf_compression_power=2, detext=False)
    # doc_curation.pdf.drive_ocr.split_to_images_and_ocr(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/purANam/mahAbhAratam_gItA-press/mahabharata01ramauoft.pdf")
    # pdf.split_and_ocr_all(dir_path="/home/vvasuki/Documents/books/granthasangrahaH/vyAkaraNam/prathamAvRtti/", small_pdf_pages=10)
    # pdf.split_and_ocr_all(dir_path="/home/vvasuki/Documents/books/granthasangrahaH/vyAkaraNam/vAsu/", small_pdf_pages=10)

