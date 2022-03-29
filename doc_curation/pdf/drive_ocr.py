import logging
from curation_utils.google import drive
import os
import time
from pathlib import Path

from curation_utils import file_helper
from doc_curation import pdf
from doc_curation.pdf import compress_with_gs, detext_via_jpg, split_into_small_pdfs, _get_ocr_dir


def split_and_ocr_all(dir_path, small_pdf_pages=25, file_pattern="*.pdf", detext=False):
  if os.path.isfile(dir_path):
    logging.warning("Got a file actually. processing it!")
    file_paths = [dir_path]
  else:
    file_paths = sorted(Path(dir_path).glob(file_pattern))
  file_paths = [f for f in file_paths if not (str(f).endswith("_detexted.pdf") or str(f).endswith("_tiny.pdf"))]
  for file_path in file_paths:
    split_and_ocr_on_drive(pdf_path=str(file_path), small_pdf_pages=small_pdf_pages, detext=detext)

 
def split_and_ocr_on_drive(pdf_path,
                           google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json',
                           small_pdf_pages=25, start_page=1, end_page=None, pdf_compression_power=0, detext=None):
  """
  OCR some pdf with google drive. Automatically splits into 25 page bits and ocrs them individually.
  
  We compress the pdf provided (if compression_power>0) because:

   -  If drive API detects text in your pdf it won't OCR the image and will just return the text it found
   - If a PDF has layers, google drive ocr fails. Need to print into a pdf in such a case. 
   - One does not need insane resolution to OCR. I guessed that file size and/or resolution is a critical factor in determining if OCR via Drive API succeeds.

  However, pdf compression results in reduction in OCR accuracy. So, beware that tradeoff.

  Still, sometimes, the operation may time out, or you might get an Internal service error. In that case, try reducing small_pdf_pages or increasing the compression power.
  
  :param pdf_path:
  :param google_key: A json key which can be obtained from https://console.cloud.google.com/iam-admin/serviceaccounts (create a project, generate a key via "Actions" column, enable Drive API and perhaps Vision APIs.). PS: Google drive takes some time (few hours?) before you can use it for the first time in a project - till then you will get an error.
  :param small_pdf_pages: Number of pages per segment - an argument used for splitting the pdf into small bits for OCR-ing. 
  :param pdf_compression_power: 0,1,2,3,4
  :return: 
  """
  final_ocr_path = pdf_path + ".txt"
  if os.path.exists(final_ocr_path):
    logging.warning("Skipping %s: %s exists", pdf_path, final_ocr_path)
    return

  altered_pdf_path = _prepare_pdf(detext, pdf_compression_power, pdf_path)

  pdf_segments = split_into_small_pdfs(pdf_path=altered_pdf_path, small_pdf_pages=small_pdf_pages, start_page=start_page,
                        end_page=end_page)

  # Do the OCR
  ocr_segments = _ocr_pdf_segments(google_key, pdf_segments)

  # Combine the ocr segments
  file_helper.concatenate_files(input_path_list=ocr_segments, output_path=final_ocr_path)
  file_helper.clear_bad_chars_in_file(file_path=final_ocr_path)


def _prepare_pdf(detext, pdf_compression_power, pdf_path):
  altered_pdf_path = pdf_path.replace(".pdf", "_tiny.pdf")
  if pdf_compression_power == 0:
    altered_pdf_path = pdf_path
  else:
    if not os.path.exists(altered_pdf_path):
      logging.info("Compressing with power %d" % pdf_compression_power)
      compress_with_gs(input_file_path=pdf_path, output_file_path=altered_pdf_path, power=pdf_compression_power)
  if detext:
    logging.info("Detexting")
    altered_pdf_path = pdf_path.replace(".pdf", "_detexted.pdf")
    if not os.path.exists(altered_pdf_path):
      # compress_with_pdfimages(input_file_path=pdf_path, output_file_path=compressed_pdf_path)
      detext_via_jpg(input_file_path=pdf_path, output_file_path=altered_pdf_path)
  return altered_pdf_path


def ocr_all(dir_path, file_name_filter=None, google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json'):
  logging.info("Do the OCR")
  drive_client = drive.get_cached_client(google_key=google_key)
  for f in os.listdir(dir_path):
    if f.endswith(".txt"):
      continue
    if file_name_filter is None or file_name_filter(f):
      local_file_path = str(os.path.join(dir_path, f))
      if os.path.exists(local_file_path + ".txt"):
        logging.info("Skipping %s", str(local_file_path))
      else:
        drive_client.ocr_file(local_file_path=local_file_path)
        time.sleep(1)


def _ocr_pdf_segments(google_key, pdf_segments):
  logging.info("Do the OCR")
  drive_client = drive.get_cached_client(google_key=google_key)
  ocr_segments = sorted([pdf_segment + ".txt" for pdf_segment in pdf_segments])
  for pdf_segment in sorted(pdf_segments):
    if os.path.exists(pdf_segment + ".txt"):
      logging.info("Skipping %s", str(pdf_segment))
    else:
      drive_client.ocr_file(local_file_path=str(pdf_segment))
      time.sleep(1)
    os.remove(pdf_segment)
  return ocr_segments


def split_to_images_and_ocr(pdf_path,
                            google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json'):
  final_ocr_path = pdf_path + ".txt"
  if os.path.exists(final_ocr_path):
    logging.warning("Skipping %s: %s exists", pdf_path, final_ocr_path)
    return
  image_directory = _get_ocr_dir(pdf_path)
  os.makedirs(image_directory, exist_ok=True)
  pdf.dump_images(pdf_path, image_directory)
  image_segments = [str(pdf_segment) for pdf_segment in Path(_get_ocr_dir(pdf_path)).glob("*.jpg")]
  ocr_segments = sorted([img + ".txt" for img in image_segments])
  drive_client = drive.get_cached_client(google_key=google_key)
  for image_segment in sorted(image_segments):
    drive_client.ocr_file(local_file_path=str(image_segment))
    # os.remove(image_segment)
    time.sleep(1)

  # Combine the ocr segments
  file_helper.concatenate_files(input_path_list=ocr_segments, output_path=final_ocr_path)
  file_helper.clear_bad_chars_in_file(file_path=final_ocr_path)
