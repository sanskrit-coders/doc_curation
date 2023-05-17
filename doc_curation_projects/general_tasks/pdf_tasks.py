import logging

from doc_curation.pdf import drive_ocr, image_ops

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
    # drive_ocr.ocr_all(dir_path="")
    # drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/kalpaH/shUdra-kamalAkaraH_sAnuvAdaH.pdf", small_pdf_pages=1, start_page=1, detext=True)
    # drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/meta-books/sanskrit-vANmay-bRhat-itihAs/", small_pdf_pages=10, start_page=1, detext=False)
    # drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/vedAntam/vedAnta_kalpataruH_parimalA.pdf", small_pdf_pages=5, start_page=1, detext=False, pdf_compression_power=3)
    # for i in range(1,4):
    #     drive_ocr.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/history/New-History-Of-The-Marathas-Vol%d.pdf" % i,  small_pdf_pages=10, start_page=1, detext=False)
    # drive_ocr.split_and_ocr_on_drive(pdf_path="", small_pdf_pages=10, detext=False)
    # drive_ocr.split_and_ocr_all(dir_path="/home/vvasuki/Documents/books/granthasangrahaH/kAvyam/stotram/shrIvaiShNavAH/4kDivyaPrabandham", small_pdf_pages=10, detext=True)
    # drive_ocr.split_and_ocr_all( dir_path="/run/media/vvasuki/vData/text/granthasangrahaH/AgamaH/brAhmaH/mAdhavIya-shankara-digvijaya.pdf", small_pdf_pages=10, detext=False)
    # drive_ocr.split_and_ocr_all(dir_path="/run/media/vvasuki/vData/text/granthasangrahaH/AgamaH/shrIvaiShNavaH", small_pdf_pages=10, detext=False)


    # image_ops.fix_images(input_file="/run/media/vvasuki/vData/text/granthasangrahaH/gaNitam/child-texts/dav/Mathematics class 2.pdf", output_file="/run/media/vvasuki/vData/text/granthasangrahaH/gaNitam/child-texts/dav/c2.pdf", fixer=image_ops.threshold_adaptive, threshold=60)
