"""
Curate and process pdf files.
"""
import errno
import logging
import os
import shutil
import subprocess
from pathlib import Path

from pikepdf import Pdf

from curation_utils import list_helper

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def _get_ocr_dir(pdf_path):
  return os.path.join(os.path.dirname(pdf_path), Path(pdf_path).stem + "_splits")


def split_into_small_pdfs(pdf_path, output_directory=None, start_page=1, end_page=None, small_pdf_pages=25):
  logging.info("Splitting %s into segments of %d", pdf_path)
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
  image_segments = [str(pdf_segment) for pdf_segment in Path(_get_ocr_dir(input_file_path)).glob("*.jpg")]
  if len(image_segments) > 0:
    logging.info("%d images already exist! So not dumping afresh.", len(image_segments))
    return 
  logging.info("Splitting to images: %s to %s", input_file_path, output_path)
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
