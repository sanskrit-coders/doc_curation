import logging

from doc_curation import pdf
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
    # drive_ocr.split_and_ocr_on_drive(pdf_path="/media/vvasuki/vData/text/granthasangrahaH/kAvyam/bannanje/tarka-kesarI_paDamunnUru-nArAyaNAchAryaH.pdf", small_pdf_pages=10, start_page=1, detext=False)

    # drive_ocr.split_and_ocr_on_drive(pdf_path="/media/vvasuki/vData/text/granthasangrahaH/kAvyam/bannaje/tarka-kesarI_paDamunnUru-nArAyaNAchAryaH.pdf", small_pdf_pages=10, start_page=264, end_page=None, detext=True)
    # for i in range(1,4):
    #     drive_ocr.split_and_ocr_on_drive(pdf_path="/media/vvasuki/vData/text/granthasangrahaH/history/New-History-Of-The-Marathas-Vol%d.pdf" % i,  small_pdf_pages=10, start_page=1, detext=False)
    # drive_ocr.split_and_ocr_on_drive(pdf_path="/media/vvasuki/vData/text/granthasangrahaH/koshaH/upasarga-artha-candrika. vol. 1 (pra-sam).pdf", small_pdf_pages=10, detext=True, end_page=71)    
    # drive_ocr.split_and_ocr_all(dir_path="/media/vvasuki/vData/text/granthasangrahaH/koshaH/upasarga-artha-candrika. vol. 1 (pra-sam).pdf", small_pdf_pages=10, detext=False)
    # drive_ocr.split_and_ocr_all( dir_path="/media/vvasuki/vData/text/granthasangrahaH/vedAH/sb", small_pdf_pages=10, detext=False, )
    # pdf.detext_via_jpg(input_file_path="/media/vvasuki/vData/text/granthasangrahaH/AgamaH/vaiShNavaH/shrIvaiShNavaH/yAmuna/AGAMA PRAMANYAM_sa.pdf")
    drive_ocr.split_and_ocr_all(dir_path="/media/vvasuki/vData/text/granthasangrahaH/AgamaH/vaiShNavaH", small_pdf_pages=10, detext=True, file_pattern="[!_]*.pdf")
    
    # TODO
    # drive_ocr.split_and_ocr_all(dir_path="/media/vvasuki/vData/text/granthasangrahaH/mixed/jIvAnanda-vidyAsAgaraH", small_pdf_pages=10, detext=False, file_pattern="[!_]*.pdf")

 
    # image_ops.fix_images(input_file="/media/vvasuki/vData/text/granthasangrahaH/gaNitam/child-texts/dav/Mathematics class 2.pdf", output_file="/media/vvasuki/vData/text/granthasangrahaH/gaNitam/child-texts/dav/c2.pdf", fixer=image_ops.threshold_adaptive, threshold=60)
    
