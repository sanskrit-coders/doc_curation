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
    pass
    # doc_curation.pdf.drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/kalpaH/shUdra-kamalAkaraH_sAnuvAdaH.pdf", small_pdf_pages=1, start_page=1, detext=True)
    # doc_curation.pdf.drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/kalpaH/nirNaya-sindhuH_sAnuvAdaH.pdf", small_pdf_pages=1, start_page=1, detext=False)
    doc_curation.pdf.drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/kalpaH/dharma-sindhuH_kannaDa.pdf", small_pdf_pages=10, start_page=1, detext=False)
    doc_curation.pdf.drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/kalpaH/BodhayanaBramhakarma.pdf", small_pdf_pages=10, start_page=1, detext=True)
    # doc_curation.pdf.drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/kalpaH/saMskAra-dIpikA-2.pdf", small_pdf_pages=10, start_page=1, detext=True)
    # doc_curation.pdf.drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/kalpaH/saMskAra-dIpikA-3.pdf", small_pdf_pages=10, start_page=1, detext=True)
    # doc_curation.pdf.drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/kalpaH/shUdrAchAra-shiromaNI-2.pdf", small_pdf_pages=10, start_page=1, detext=True)
    # doc_curation.pdf.drive_ocr.split_to_images_and_ocr(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/purANam/mahAbhAratam_gItA-press/mahabharata01ramauoft.pdf")
    # doc_curation.pdf.drive_ocr.split_and_ocr_all(dir_path="/home/vvasuki/Documents/books/granthasangrahaH/history/deshpaNDe-mAdhavaH", small_pdf_pages=10)
    # doc_curation.pdf.drive_ocr.split_and_ocr_all(dir_path="/home/vvasuki/Documents/books/granthasangrahaH/vedaH/dANDekaraH", small_pdf_pages=10)

