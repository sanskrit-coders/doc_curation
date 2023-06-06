"""
# pdf_contrast.py
Modify contrast of pdf

"""
import os
from argparse import ArgumentParser
import io

from PIL import ImageEnhance
from PIL import Image
import img2pdf
import pdf2image
from tqdm import tqdm


def contrast_fixer(img, contrast: float):
  enhancer = ImageEnhance.Contrast(img)
  out_im = enhancer.enhance(contrast)
  return out_im

def threshold_adaptive(img, threshold=127, greyscale=False):
  import cv2
  import numpy
  img_arr_in = numpy.asarray(img)
  if greyscale:
    img_arr_in = cv2.cvtColor(img_arr_in, cv2.COLOR_BGR2GRAY)
  th, img_arr_out = cv2.threshold(img_arr_in,
                                  threshold,  # threshold value
                          255,  # maximum value assigned to pixel values exceeding the threshold
                          cv2.THRESH_BINARY)  # threshold method type
  out_im = Image.fromarray(img_arr_out)
  return out_im
  

def fix_images(input_file: str, output_file: str, fixer, *args, **kwargs):
  """
  Create a new pdf corresponding to the contrast multiplier

  `input_file`: name the of the input_file
  `contrast`: contrast multiplier. 1 corresponds to no change
  `output_file`: name of the file to be saved
  """

  print(f'Loading pdf {input_file}')
  input_images = pdf2image.convert_from_path(input_file)
  print(f'Pages: {len(input_images)}')

  output_images: list[bytes] = []
  for img in tqdm(input_images,
                  unit="pages"
                  ):
    out_im = fixer(img, *args, **kwargs)
    out_img_bytes = io.BytesIO()
    out_im.save(out_img_bytes, format="JPEG")
    output_images.append(out_img_bytes.getvalue())

  print(f'Saving pdf to {output_file}')
  with open(output_file, "wb") as outf:
    img2pdf.convert(*output_images, outputstream=outf)


def save_pdf(image_dir, pdf_path):

  images = [
    Image.open(os.path.join(image_dir, f))
    for f in os.listdir(image_dir)
    if os.path.splitext(f)[-1] in ["jpg", "png", "jpeg"]
  ]

  images[0].save(
      pdf_path, "PDF" ,resolution=100.0, save_all=True, append_images=images[1:]
  )