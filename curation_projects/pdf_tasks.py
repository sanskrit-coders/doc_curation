import logging

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
    # pdf.split_and_ocr_on_drive(pdf_path="//home/vvasuki/Documents/books/granthasangrahaH/jyotiSham/Hamlet's Mill - An Essay on Myth and the Frame of Time - Giorgio de Santillana and Hertha von Dechend (1969).pdf", small_pdf_pages=5, start_page=1)
    pdf.split_and_ocr_all(dir_path="/home/vvasuki/Documents/books/granthasangrahaH/vyAkaraNam/prathamAvRtti/", small_pdf_pages=10)
    # pdf.split_and_ocr_all(dir_path="/home/vvasuki/Documents/books/granthasangrahaH/vyAkaraNam/vAsu/", small_pdf_pages=10)

