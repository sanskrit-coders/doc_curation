#! /path/to/virtualenv/where/you/installed/doc_curation
# 
# lalitaalaalitah:
# Copied from sample provided by vishvAsavAsukI and then changed here and there.
# 
# 
import logging
import os
from doc_curation import pdf
from doc_curation.pdf import drive_ocr
import sys
from pdf2image import pdfinfo_from_path, convert_from_path
from pikepdf import Pdf
from pathlib import Path
from curation_utils import list_helper
from curation_utils import file_helper
import shutil
# 
# 
# 
# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s",
)
#
# Break PDF to small original PDF-s : Copied from doc_curation utils and changed name of fn and a little change here and there.
def break_to_small_pdf_paths_original(
    pdf_path, output_directory=None, start_page=1, end_page=None, small_pdf_pages=25
):
    #   logging.info("Splitting %s into segments of %d", pdf_path, 25)
    pdf_name_stem = Path(pdf_path).stem
    if output_directory == None:
        output_directory = os.path.join(
            os.path.dirname(pdf_path), Path(pdf_path).stem + "_small_originals"
        )
    # noinspection PyArgumentList
    with Pdf.open(pdf_path) as pdf:
        if end_page == None:
            end_page = len(pdf.pages)
        pages = range(start_page, end_page + 1)
        page_sets = list_helper.divide_chunks(list_in=pages, n=small_pdf_pages)
        dest_pdfs = []
        for page_set in page_sets:
            pages = [pdf.pages[i - 1] for i in page_set]
            dest_pdf_path = os.path.join(
                output_directory,
                "%s_%04d-%04d.pdf" % (pdf_name_stem, page_set[0], page_set[-1]),
            )
            if not os.path.exists(dest_pdf_path):
                # noinspection PyArgumentList
                dest_pdf = Pdf.new()
                dest_pdf.pages.extend(pages)
                os.makedirs(os.path.dirname(dest_pdf_path), exist_ok=True)
                dest_pdf.save(filename_or_stream=dest_pdf_path)
            else:
                logging.warning("%s exists", dest_pdf_path)
            dest_pdfs.append(dest_pdf_path)
    return dest_pdfs
# 
# 
#
# Now OCR considering each broken PDF-s, having 25 pages, as pdf_path
def ocr_with_path(root_path):
    # Create a list of pdf_path
    if os.path.isdir(root_path):
        pdf_list = [
            os.path.join(root_path, item)
            for item in os.listdir(root_path)
            if item.endswith(".pdf")
        ]
    elif os.path.isfile(root_path) and root_path.endswith("pdf"):
        pdf_list = [root_path]
    # 
    # for each pdf in the pdf_list, do this
    for pdf_path in pdf_list:
        # final OCR file name
        ocr_file_for_pdf_path = pdf_path + ".txt"
        # 
        # break the pdf to small pdf of 25 pages using a fn
        small_pdf_paths = break_to_small_pdf_paths_original(
            pdf_path,
            output_directory=None,
            start_page=1,
            end_page=None,
            small_pdf_pages=25,
        )
        # a list for all ocr relaetd to each small_pdf_path
        small_pdf_final_ocr_path_list = []
        # for each 25 pages PDF related to each pdf_path, do this
        for each_small_pdf_path in small_pdf_paths:
            try:
              # get pdf page numbers
              pdf_info = pdfinfo_from_path(
                  each_small_pdf_path, userpw=None, poppler_path=None
              )
              maxPages = pdf_info["Pages"]
              # do ocr for each 25 page PDF by compressing and splitting in 5 pages PDF 
              drive_ocr.split_and_ocr_on_drive(
                  pdf_path=each_small_pdf_path,
                  google_key="/path/to/key.json",
                  small_pdf_pages=5,
                  # start_page=None,
                  # start_page=page,
                  # end_page = None,
                  # end_page = min(page+10-1, maxPages),
                  pdf_compression_power=1,#change it as desire for more/less compression of PDF
                  # detext=True
              )
              # add ocr of each 5 page PDF related to each 25 pages PDF to a list
              each_small_pdf_ocr_path = each_small_pdf_path + ".txt"
              small_pdf_final_ocr_path_list.append(each_small_pdf_ocr_path)
            except Exception as x:
                print(x)
                # print('trying another method now.')
                # drive_ocr.split_to_images_and_ocr(
                #     pdf_path=pdf_path,
                #     google_key="/path/to/key.json",
                #     # small_pdf_pages=10,
                #     # end_page = None,
                #     # pdf_compression_power=3,
                #     # start_page = 1,
                #     #detext=True
                #     )
                continue
        # Combine the ocr segments
        small_pdf_final_ocr_path_list.sort()
        file_helper.concatenate_files(
            input_path_list=small_pdf_final_ocr_path_list,
            output_path=ocr_file_for_pdf_path,
        )
        # clear useless characters
        file_helper.clear_bad_chars_in_file(file_path=ocr_file_for_pdf_path)
        # delete useless PDF and split ocr
        output_directory = os.path.join(
            os.path.dirname(pdf_path), Path(pdf_path).stem + "_small_originals"
        )
        if os.path.isdir(output_directory):
            shutil.rmtree(output_directory)


if __name__ == "__main__":
    print("usage : path_to_script path_to_dir/pdf")
    if len(sys.argv) > 1:
        if os.path.isdir(sys.argv[1]) or os.path.isfile(sys.argv[1]):
            root_path = sys.argv[1]
    else:
        root_path = input("enter either path of a folder having pdf\nor path of a pdf.")
    print(root_path)
    ocr_with_path(root_path)