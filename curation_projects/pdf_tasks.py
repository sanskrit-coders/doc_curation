import logging

from doc_curation import pdf

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


if __name__ == '__main__':
    # pdf.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/kAvyam/Stotrarnava_MGOS.pdf", small_pdf_pages=25)
    pdf.split_and_ocr_all(dir_path="/home/vvasuki/Documents/books/granthasangrahaH/mImAmsA/laukika-nyAyAH", small_pdf_pages=15)
