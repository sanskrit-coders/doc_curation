"""
Detect PDFs whose pages contain two photographed book pages (two-up scans).
"""
import logging
from dataclasses import dataclass

import cv2
import numpy as np
import pymupdf

logger = logging.getLogger(__name__)

RENDER_DPI = 150
MIN_ASPECT_RATIO = 1.05
MIN_HALF_CONTENT = 0.05
GUTTER_RANGE = (0.45, 0.55)
GUTTER_DARKNESS_RATIO = 0.9
GUTTER_CONTENT_RATIO = 0.6
GUTTER_BAND = 0.02
CONTENT_PIXEL_RATIO = 0.15


def _as_gray(image):
  if image.ndim == 3:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
  return image


def render_page_gray(page, dpi=RENDER_DPI):
  pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
  return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def find_page_gutter(image):
  """
  Return the horizontal position of the gutter as a fraction of the page width.
  Falls back to the centre when no dark central seam is found.
  """
  image = _as_gray(image)
  height, width = image.shape
  if width < height * MIN_ASPECT_RATIO:
    return 0.5

  columns = image.astype(np.float32).mean(axis=0)
  smooth_size = max(3, width // 100)
  columns = np.convolve(columns, np.ones(smooth_size) / smooth_size, mode="same")

  low, high = int(width * GUTTER_RANGE[0]), int(width * GUTTER_RANGE[1])
  candidate = low + int(np.argmin(columns[low:high]))

  reference_columns = np.concatenate((
    columns[int(width * 0.35):int(width * 0.44)],
    columns[int(width * 0.56):int(width * 0.65)],
  ))
  reference = np.median(reference_columns)
  if reference > 0 and columns[candidate] < reference * GUTTER_DARKNESS_RATIO:
    return candidate / width
  return 0.5


def _content_ink(image):
  image = _as_gray(image).astype(np.float32)
  high_pass = np.abs(image - cv2.GaussianBlur(image, (0, 0), 3))
  scale = np.percentile(high_pass, 99)
  if scale <= 0:
    return None
  return high_pass / scale > CONTENT_PIXEL_RATIO


def _half_content_scores(image, gutter=0.5):
  ink = _content_ink(image)
  if ink is None:
    return 0.0, 0.0

  _, width = ink.shape
  margin = max(1, int(width * 0.02))
  split = int(width * gutter)
  left = ink[:, :max(1, split - margin)].mean()
  right = ink[:, split + margin:].mean()
  return float(left), float(right)


def _gutter_content_score(image, gutter=0.5):
  ink = _content_ink(image)
  if ink is None:
    return 0.0

  _, width = ink.shape
  margin = max(1, int(width * GUTTER_BAND))
  split = int(width * gutter)
  return float(ink[:, max(0, split - margin):split + margin].mean())


@dataclass(frozen=True)
class PageLayout:
  is_double_page: bool
  rotation: int = 0
  gutter: float = 0.5


def _rotate_gray(image, rotation):
  if rotation == 90:
    return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
  if rotation == 180:
    return cv2.rotate(image, cv2.ROTATE_180)
  if rotation == 270:
    return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
  return image


def detect_double_page_layout(image, min_half_content=MIN_HALF_CONTENT,
                              min_aspect_ratio=MIN_ASPECT_RATIO):
  """
  Detect whether `image` is a two-page spread, trying upright and sideways
  orientations. The returned rotation is the clockwise rotation needed to make
  the spread upright before splitting.
  """
  image = _as_gray(image)
  for rotation in (0, 90, 270):
    rotated = _rotate_gray(image, rotation)
    height, width = rotated.shape
    if width < height * min_aspect_ratio:
      continue

    gutter = find_page_gutter(rotated)
    left, right = _half_content_scores(rotated, gutter)
    is_two_up = min(left, right) >= min_half_content
    if is_two_up and rotation != 0:
      gutter_content = _gutter_content_score(rotated, gutter)
      is_two_up = gutter_content <= GUTTER_CONTENT_RATIO * min(left, right)
    if is_two_up:
      return PageLayout(True, rotation, gutter)
  return PageLayout(False)


def is_double_page_image(image, min_half_content=MIN_HALF_CONTENT,
                         min_aspect_ratio=MIN_ASPECT_RATIO):
  """
  Return True if `image` looks like two book pages photographed side by side.
  """
  return detect_double_page_layout(
    image,
    min_half_content=min_half_content,
    min_aspect_ratio=min_aspect_ratio,
  ).is_double_page


def _sample_page_indices(total_pages, sample_size):
  if sample_size is None or sample_size >= total_pages:
    return list(range(total_pages))
  return sorted(set(np.linspace(0, total_pages - 1, sample_size, dtype=int).tolist()))


def get_double_page_pages(pdf_path, sample_size=None, dpi=RENDER_DPI,
                          min_half_content=MIN_HALF_CONTENT,
                          min_aspect_ratio=MIN_ASPECT_RATIO):
  """
  Return the 1-based numbers of pages that look like two-page spreads.
  """
  with pymupdf.open(pdf_path) as doc:
    indices = _sample_page_indices(len(doc), sample_size)
    pages = []
    for index in indices:
      image = render_page_gray(doc[index], dpi=dpi)
      if is_double_page_image(image, min_half_content=min_half_content,
                              min_aspect_ratio=min_aspect_ratio):
        pages.append(index + 1)
  return pages


def is_double_page_pdf(pdf_path, sample_size=20, min_double_fraction=0.5,
                       dpi=RENDER_DPI, min_half_content=MIN_HALF_CONTENT,
                       min_aspect_ratio=MIN_ASPECT_RATIO):
  """
  Return True if a sufficient fraction of sampled pages are two-page spreads.
  """
  with pymupdf.open(pdf_path) as doc:
    if len(doc) == 0:
      return False
    indices = _sample_page_indices(len(doc), sample_size)
    double_pages = 0
    for index in indices:
      image = render_page_gray(doc[index], dpi=dpi)
      if is_double_page_image(image, min_half_content=min_half_content,
                              min_aspect_ratio=min_aspect_ratio):
        double_pages += 1

  fraction = double_pages / len(indices)
  logger.info("Double-page fraction for %s: %.2f (%d/%d)",
               pdf_path, fraction, double_pages, len(indices))
  return fraction >= min_double_fraction
