"""
Curate and process pdf files.
"""
import errno
import logging
import os
import shutil
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
import random
from bs4 import BeautifulSoup


import json
import pypdf
import os
from pikepdf import Pdf

from curation_utils import list_helper

## To thwart DecompressionBombError: Image size (268216326 pixels) exceeds limit of 178956970 pixels, could be decompression bomb DOS attack.
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

# Common page sizes in points (1 pt = 1/72 inch)
PAGE_SIZES = {
  "a5": (420, 595),   # 148 x 210 mm
  "a4": (595, 842),   # 210 x 297 mm
  "letter": (612, 792) # 8.5 x 11 in
}




def get_page_margins(pdf_path, page_num, page_size="a5"):
  """Compute margins for a single page using pdftotext -bbox-layout (HTML)."""
  width_pt, height_pt = PAGE_SIZES[page_size]
  cmd = ["pdftotext", "-bbox-layout", "-f", str(page_num), "-l", str(page_num), pdf_path, "-"]
  result = subprocess.run(cmd, capture_output=True, text=True, check=True)

  soup = BeautifulSoup(result.stdout, "html.parser")
  words = soup.find_all("word")
  if not words:
    return None

  xmins, xmaxs, ymins, ymaxs = [], [], [], []
  for w in words:
    try: 
      x_min = float(w.get("xmin")) 
      y_min = float(w.get("ymin")) 
      x_max = float(w.get("xmax")) 
      y_max = float(w.get("ymax")) 
      xmins.append(x_min); 
      xmaxs.append(x_max) 
      ymins.append(y_min); ymaxs.append(y_max) 
    except (TypeError, ValueError): 
      continue
  pt_to_mm = 0.3528
  return {
    "left_mm": min(xmins) * pt_to_mm,
    "right_mm": (width_pt - max(xmaxs)) * pt_to_mm,
    "top_mm": min(ymins) * pt_to_mm,
    "bottom_mm": (height_pt - max(ymaxs)) * pt_to_mm
  }

def sample_pdf_margins(pdf_path, n=50, page_size="a5", page_type="all"):
  """Sample n pages (odd/even/all) and compute average margins."""
  # Get total pages
  cmd = ["pdfinfo", pdf_path]
  result = subprocess.run(cmd, capture_output=True, text=True, check=True)
  pages = 0
  for line in result.stdout.splitlines():
    if line.startswith("Pages:"):
      pages = int(line.split()[1])
      break

  # Select candidate pages
  if page_type == "odd":
    candidates = [p for p in range(1, pages+1) if p % 2 == 1]
  elif page_type == "even":
    candidates = [p for p in range(1, pages+1) if p % 2 == 0]
  else:
    candidates = list(range(1, pages+1))

  sample_pages = random.sample(candidates, min(n, len(candidates)))
  margins_list = []

  for p in sample_pages:
    m = get_page_margins(pdf_path, p, page_size)
    if m:
      margins_list.append(m)

  # Compute averages
  avg = {k: sum(m[k] for m in margins_list)/len(margins_list) for k in margins_list[0]}
  logging.info(f"{page_size} {page_type} {avg}")
  return avg, sample_pages


def _get_ocr_dir(pdf_path, small_pdf_pages=None):
  if small_pdf_pages is None:
    return os.path.join(os.path.dirname(pdf_path), f"{Path(pdf_path).stem}_splits")
  else:
    return os.path.join(os.path.dirname(pdf_path), f"{Path(pdf_path).stem}_{small_pdf_pages}_splits")


def split_into_small_pdfs(pdf_path, output_directory=None, start_page=1, end_page=None, small_pdf_pages=25):
  logging.info("Splitting %s into segments of %d", pdf_path, small_pdf_pages)
  pdf_name_stem = Path(pdf_path).stem
  if output_directory == None:
    output_directory = _get_ocr_dir(pdf_path, small_pdf_pages)
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
        logging.debug("%s exists", dest_pdf_path)
      dest_pdfs.append(dest_pdf_path)
  return dest_pdfs


# Adapted from https://github.com/theeko74/pdfc/blob/master/pdf_compressor.py
def compress_with_gs(input_file_path, output_file_path, quality='screen'):
  """
    Compress PDF using Ghostscript.
    quality: 'screen' (72 dpi, smallest), 'ebook' (150 dpi), 'logging.infoer' (300 dpi), 'prepress', 'default'
    """

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
  # If output_file_path == input_file_path, the command will fail. Hence the below.
  output_file_path_tmp = output_file_path.replace(".pdf", ".tmp.pdf")
  try:
    subprocess.call(['gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4',
                     f'-dPDFSETTINGS=/{quality}',
                     '-dFILTERTEXT',
                     '-dNOPAUSE', '-dQUIET', '-dBATCH',
                     f'-sOutputFile={output_file_path_tmp}',
                     input_file_path]
                    )
    shutil.move(output_file_path_tmp, output_file_path)
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


def dump_images(input_file_path, output_path, poppler_path="/usr/bin"):
  from pdf2image import convert_from_path
  image_segments = [str(pdf_segment) for pdf_segment in Path(_get_ocr_dir(input_file_path, 1)).glob("*.jpg")]
  if len(image_segments) > 0:
    logging.info("%d images already exist! So not dumping afresh.", len(image_segments))
    return
  logging.info("Splitting to images: %s to %s", input_file_path, output_path)
  convert_from_path(input_file_path, fmt="jpeg", output_folder=output_path,
                    output_file=os.path.splitext(os.path.basename(input_file_path))[0] + "_", poppler_path=poppler_path)


def images_to_pdf(image_dir, output_path):
  import img2pdf

  with open(output_path, "wb") as f:
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


def detext_via_jpg(input_file_path, output_file_path=None):
  image_directory = _get_ocr_dir(input_file_path, 1)
  os.makedirs(image_directory, exist_ok=True)
  dump_images(input_file_path, image_directory)
  if output_file_path is None:
    output_file_path = input_file_path.replace(".pdf", "_detexted.pdf")
  images_to_pdf(image_directory, output_file_path)


def detext_with_pdfimages(input_file_path, output_file_path):
  """
  
  Sometimes does not work satisfactorily - just outputs 2 pages of many.
  :param input_file_path: 
  :param output_file_path: 
  :return: 
  """
  image_directory = _get_ocr_dir(input_file_path, 1)
  os.makedirs(image_directory, exist_ok=True)
  subprocess.check_output(["/usr/bin/pdfimages", "-j", input_file_path, image_directory + "/page"], shell=True)
  # subprocess.call(["convert", input_file_path, image_directory  + "/page%04.jpg"])
  subprocess.check_output(["convert", image_directory + "/*", output_file_path], shell=True)
  shutil.rmtree(image_directory)



def crop_pdf_with_json(input_pdf_path, output_pdf_path, json_path="/home/vvasuki/gitland/sanskrit-coders/doc_curation/doc_curation_projects/general_tasks/pdf_boxes.json", ):
  """
  Crops pages of a PDF based on coordinates from a JSON file.

  Args:
      input_pdf_path (str): Path to the source PDF file.
      json_path (str): Path to the JSON file with cropping data.
      output_pdf_path (str): Path to save the new, cropped PDF file.
  """
  logging.info(f"Loading JSON data from: {json_path}")
  try:
    with open(json_path, 'r') as f:
      crop_data = json.load(f)
  except FileNotFoundError:
    logging.info(f"Error: JSON file not found at '{json_path}'")
    return
  except json.JSONDecodeError:
    logging.info(f"Error: Could not parse JSON file. Please check its format.")
    return

  logging.info(f"Opening source PDF: {input_pdf_path}")
  try:
    reader = pypdf.PdfReader(input_pdf_path)
  except FileNotFoundError:
    logging.info(f"Error: Input PDF not found at '{input_pdf_path}'")
    return

  writer = pypdf.PdfWriter()

  logging.info(f"Processing {len(crop_data)} pages as defined in the JSON file...")

  for item in crop_data:
    # JSON page numbers are typically 1-based, while list indices are 0-based.
    page_index = item['page'] - 1
    box = item['box_2d']

    if not (0 <= page_index < len(reader.pages)):
      logging.info(f"  - Warning: Page {page_index + 1} requested in JSON, but it's out of bounds for the PDF. Skipping.")
      continue

    # Get the specific page object
    page = reader.pages[page_index]

    # Original page dimensions are needed for coordinate conversion
    original_height = page.mediabox.height

    # --- Coordinate Conversion ---
    # The JSON 'box_2d' is [x_min, y_min, width, height] from the TOP-LEFT corner.
    # PDF coordinates originate from the BOTTOM-LEFT corner.
    json_x, json_y, json_w, json_h = box

    # Calculate the four corners for the PDF crop box
    left = json_x
    right = json_x + json_w
    top = original_height - json_y
    bottom = original_height - (json_y + json_h)

    # Apply the new coordinates to the page's CropBox
    # A page's CropBox is what is visible to the user.
    page.cropbox.lower_left = (left, bottom)
    page.cropbox.upper_right = (right, top)

    # It's also good practice to set the MediaBox to the CropBox
    # This removes any hidden data outside the visible area.
    page.mediabox = page.cropbox

    # Add the modified (cropped) page to our new PDF
    writer.add_page(page)
    logging.info(f"  - Cropped and added page {page_index + 1}")

  # Save the newly created PDF to a file
  try:
    with open(output_pdf_path, 'wb') as f_out:
      writer.write(f_out)
    logging.info(f"\nSuccessfully created cropped PDF: '{output_pdf_path}'")
  except Exception as e:
    logging.info(f"\nError: Could not save the output PDF. Reason: {e}")


def from_latex(latex_body: str, dest_path: str):
  """
  Wrap LaTeX body into a full book-style document and compile to PDF.
  """
  doc_template = r"""
\documentclass[12pt]{book}
\usepackage{fontspec} % Unicode support
\usepackage{tcolorbox}
\usepackage{hyperref}
\setmainfont{Noto Serif}

\begin{document}
\tableofcontents
\newpage

%s

\end{document}
""" % latex_body

  import subprocess, tempfile, os
  with tempfile.TemporaryDirectory() as tmpdir:
    tex_path = os.path.join(tmpdir, "doc.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
      f.write(doc_template)

    subprocess.run(["xelatex", "-interaction=nonstopmode", tex_path], cwd=tmpdir)
    subprocess.run(["xelatex", "-interaction=nonstopmode", tex_path], cwd=tmpdir)

    pdf_path = os.path.join(tmpdir, "doc.pdf")
    if os.path.exists(pdf_path):
      os.replace(pdf_path, dest_path)
      logging.info(f"PDF generated: {dest_path}")
    else:
      raise RuntimeError("PDF generation failed")
