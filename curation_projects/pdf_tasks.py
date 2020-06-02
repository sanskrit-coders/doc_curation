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
    pdf.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/history/kShatriyas_in_kali_gAgAbhaTTa_opponents_mAdhav_deshpanDe.pdf", small_pdf_pages=10, start_page=1)
    # pdf.split_and_ocr_all(dir_path="/home/vvasuki/Documents/books/granthasangrahaH/mImAmsA/laukika-nyAyAH", small_pdf_pages=10)
