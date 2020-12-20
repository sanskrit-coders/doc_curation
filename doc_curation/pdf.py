"""
Curate and process pdf files.
"""
import errno
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from pikepdf import Pdf

import doc_curation
from curation_utils import list_helper, file_helper

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def _get_ocr_dir(pdf_path):
  return os.path.join(os.path.dirname(pdf_path), Path(pdf_path).stem + "_splits")


def split_and_ocr_all(dir_path, small_pdf_pages=25, file_pattern="*.pdf"):
  file_paths = sorted(Path(dir_path).glob(file_pattern))
  for file_path in file_paths:
    split_and_ocr_on_drive(pdf_path=str(file_path), small_pdf_pages=small_pdf_pages)


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
  :param google_key: A json key which can be obtained from https://console.cloud.google.com/iam-admin/serviceaccounts (create a project, generate a key via "Actions" column.). PS: Google drive takes some time (few hours?) before you can use it for the first time in a project - till then you will get an error.
  :param small_pdf_pages: Number of pages per segment - an argument used for splitting the pdf into small bits for OCR-ing. 
  :param pdf_compression_power: 0,1,2,3,4
  :return: 
  """
  final_ocr_path = pdf_path + ".txt"
  if os.path.exists(final_ocr_path):
    logging.warning("Skipping %s: %s exists", pdf_path, final_ocr_path)
    return
  compressed_pdf_path = pdf_path.replace(".pdf", "_tiny.pdf")
  if pdf_compression_power == 0:
    compressed_pdf_path = pdf_path
  else:
    if not os.path.exists(compressed_pdf_path):
      compress_with_gs(input_file_path=pdf_path, output_file_path=compressed_pdf_path, power=pdf_compression_power)

  if detext:
    compressed_pdf_path = pdf_path.replace(".pdf", "_detexted.pdf")
    # compress_with_pdfimages(input_file_path=pdf_path, output_file_path=compressed_pdf_path)
    detext_via_jpg(input_file_path=pdf_path, output_file_path=compressed_pdf_path)

  split_into_small_pdfs(pdf_path=compressed_pdf_path, small_pdf_pages=small_pdf_pages, start_page=start_page,
                        end_page=end_page)

  # Do the OCR
  from curation_utils.google import drive
  drive_client = drive.get_cached_client(google_key=google_key)
  pdf_segments = [str(pdf_segment) for pdf_segment in Path(_get_ocr_dir(compressed_pdf_path)).glob("*.pdf")]
  ocr_segments = sorted([pdf_segment + ".txt" for pdf_segment in pdf_segments])
  for pdf_segment in sorted(pdf_segments):
    drive_client.ocr_file(local_file_path=str(pdf_segment))
    os.remove(pdf_segment)
    time.sleep(1)

  # Combine the ocr segments
  file_helper.concatenate_files(input_path_list=ocr_segments, output_path=final_ocr_path)
  file_helper.clear_bad_chars_in_file(file_path=final_ocr_path)


def split_into_small_pdfs(pdf_path, output_directory=None, start_page=1, end_page=None, small_pdf_pages=25):
  pdf_name_stem = Path(pdf_path).stem
  if output_directory == None:
    output_directory = _get_ocr_dir(pdf_path)
  # noinspection PyArgumentList
  with Pdf.open(pdf_path) as pdf:
    if end_page == None:
      end_page = len(pdf.pages)
    pages = range(start_page, end_page + 1)
    page_sets = list_helper.divide_chunks(list_in=pages, n=small_pdf_pages)
    dest_pdfs = []
    for page_set in page_sets:
      pages = [pdf.pages[i - 1] for i in page_set]
      dest_pdf_path = os.path.join(output_directory, "%s_%04d-%04d.pdf" % (pdf_name_stem, page_set[0], page_set[-1]))
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


# Adapted from https://github.com/theeko74/pdfc/blob/master/pdf_compressor.py
def compress_with_gs(input_file_path, output_file_path, power=3):
  """Function to compress PDF and remove text via Ghostscript command line interface
  
  :param power: 0,1,2,3,4
  """
  quality = {
    0: '/default',
    1: '/prepress',
    2: '/printer',
    3: '/ebook',
    4: '/screen'
  }

  # Basic controls
  # Check if valid path
  if not os.path.isfile(input_file_path):
    logging.fatal("Error: invalid path for input PDF file")
    return

    # Check if file is a PDF by extension
  if input_file_path.split('.')[-1].lower() != 'pdf':
    logging.fatal("Error: input file is not a PDF")
    return

  logging.info("Compress PDF...")
  initial_size = os.path.getsize(input_file_path)
  try:
    subprocess.call(['gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4',
                     '-dPDFSETTINGS={}'.format(quality[power]),
                     '-dFILTERTEXT',
                     '-dNOPAUSE', '-dQUIET', '-dBATCH',
                     '-sOutputFile={}'.format(output_file_path),
                     input_file_path]
                    )
  except OSError as e:
    if e.errno == errno.ENOENT:
      # handle file not found error.
      logging.error("ghostscript not found. Proceeding without compression.")
      shutil.copyfile(input_file_path, output_file_path)
      return
    else:
      # Something else went wrong while trying to run the command
      raise
  final_size = os.path.getsize(output_file_path)
  ratio = 1 - (final_size / initial_size)
  logging.info("Compression by {0:.0%}.".format(ratio))
  logging.info("Final file size is {0:.1f}MB".format(final_size / 1000000))
  return ratio


def detext_via_ps(input_file_path, output_file_path):
  os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
  ps_path = input_file_path.replace(".pdf", ".ps")
  subprocess.call(["pdf2ps", input_file_path, ps_path])
  subprocess.call(["ps2pdf", ps_path, output_file_path])


def dump_images(input_file_path, output_path):
  from pdf2image import convert_from_path
  convert_from_path(input_file_path, fmt="jpeg", output_folder=output_path, output_file=os.path.splitext(os.path.basename(input_file_path))[0])


def images_to_pdf(image_dir, output_path):
  import img2pdf
  with open(output_path,"wb") as f:
    imgs = []
    image_files = os.listdir(image_dir)
    image_files.sort()
    for fname in image_files:
      if not fname.endswith(".jpg"):
        continue
      path = os.path.join(image_dir, fname)
      if os.path.isdir(path):
        continue
      imgs.append(path)
    f.write(img2pdf.convert(imgs))


def detext_via_jpg(input_file_path, output_file_path):
  image_directory = _get_ocr_dir(input_file_path)
  os.makedirs(image_directory, exist_ok=True)
  dump_images(input_file_path, image_directory)
  images_to_pdf(image_directory, output_file_path)


def detext_with_pdfimages(input_file_path, output_file_path):
  """
  
  Sometimes does not work satisfactorily - just outputs 2 pages of many.
  :param input_file_path: 
  :param output_file_path: 
  :return: 
  """
  image_directory = _get_ocr_dir(input_file_path)
  os.makedirs(image_directory, exist_ok=True)
  subprocess.call(["pdfimages", "-j", input_file_path, image_directory + "/page"])
  # subprocess.call(["convert", input_file_path, image_directory  + "/page%04.jpg"])
  subprocess.call(["convert", image_directory + "/*", output_file_path])
  shutil.rmtree(image_directory)
