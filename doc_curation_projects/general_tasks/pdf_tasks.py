import logging

from doc_curation.llm import gemini
from doc_curation import pdf, llm
from doc_curation.pdf import drive_ocr, image_ops, llm as pdf_llm

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
  drive_ocr.split_and_ocr_all( dir_path="/media/vvasuki/vData/text/granthasangrahaH/itihAsaH/india/vaiShNava/shrIvaiShNavam/ahobilam", small_pdf_pages=5, detext=False, file_pattern="[!_]*.pdf")
  # llm.pymupdf_to_markdown("/media/vvasuki/vData/text/granthasangrahaH/AgamaH/vaiShNavaH/gauDIyam/navadvipa-dhama-mahatmya_1st_eng.pdf", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAgAnuga-bhakti-parAH/kAvyam/bhakti-vinodaH/navadvIpa-dhAma-mAhAtmyam/sarva-prastutiH.md")

  # gemini.process_pdf_chunks_with_keys(file_in="/media/vvasuki/vData/text/granthasangrahaH/AgamaH/vaiShNavaH/shrIvaiShNavaH/lokAchAryAdi/svb_mImAMsA-bhAShyam.pdf", dest_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/lokAchArya-shAkhA/lokAchAryaH/shrI-vachana-bhUShaNam/vyAkhyA/mImAMsA/mUlam.md", prompt=llm.get_prompt("/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/Sanskrit_devanAgarI_markdown.md"))

  # pdf.compress_with_gs(input_file_path="/media/vvasuki/vData/text/granthasangrahaH/AgamaH/vaiShNavaH/shrIvaiShNavaH/ahobilam/Adhyatma-Chintamani_vAdikesari_nArAyaNa_muniH.pdf")

  # pdf.crop_pdf_with_json(input_pdf_path="/media/vvasuki/vData/text/granthasangrahaH/AgamaH/vaiShNavaH/pAncharAtram/Pancharatra-pAramyam.pdf", output_pdf_path="/media/vvasuki/vData/text/granthasangrahaH/AgamaH/vaiShNavaH/pAncharAtram/Pancharatra-pAramyam-out.pdf", )

  # drive_ocr.split_to_images_and_ocr(pdf_path="/media/vvasuki/vData/text/granthasangrahaH/AgamaH/vaiShNavaH/shrIvaiShNavaH/venkaTanAtha/rts/cmv/cmv_08-10.pdf")

  # TODO
  # drive_ocr.split_and_ocr_all(dir_path="/media/vvasuki/vData/text/granthasangrahaH/mixed/jIvAnanda-vidyAsAgaraH", small_pdf_pages=10, detext=False, file_pattern="[!_]*.pdf")

  # image_ops.fix_images(input_file="/media/vvasuki/vData/text/granthasangrahaH/gaNitam/child-texts/dav/Mathematics class 2.pdf", output_file="/media/vvasuki/vData/text/granthasangrahaH/gaNitam/child-texts/dav/c2.pdf", fixer=image_ops.threshold_adaptive, threshold=60)
  