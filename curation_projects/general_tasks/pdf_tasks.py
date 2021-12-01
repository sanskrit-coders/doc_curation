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
    # doc_curation.pdf.drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/AgamaH/Abhinavagupta-An-Historical-and-Philosophical-Study-K-C-Pandey.pdf", small_pdf_pages=10, start_page=1, detext=False)
    # doc_curation.pdf.drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/vedAntam/vedAnta_kalpataruH_parimalA.pdf", small_pdf_pages=5, start_page=1, detext=False, pdf_compression_power=3)
    # for i in range(1,4):
    #     doc_curation.pdf.drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/history/New-History-Of-The-Marathas-Vol%d.pdf" % i,  small_pdf_pages=10, start_page=1, detext=False)
    # doc_curation.pdf.drive_ocr.split_and_ocr_on_drive(pdf_path="", small_pdf_pages=10, detext=False)
    # doc_curation.pdf.drive_ocr.split_and_ocr_all(dir_path="/home/vvasuki/Documents/books/granthasangrahaH/kalpaH/AgamaH/pratyabhijJNA-hRdayam", small_pdf_pages=10, detext=False)
    doc_curation.pdf.drive_ocr.split_and_ocr_all(dir_path="/home/vvasuki/Documents/books/granthasangrahaH/kAvyam/shAstram/alankAra-tattva_MA-hegDe.pdf", small_pdf_pages=10, detext=False)
