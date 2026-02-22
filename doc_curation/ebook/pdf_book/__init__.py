import io
import logging
import os
import os.path

import regex
from pypdf import PdfReader, PdfWriter
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Frame
from doc_curation.md.file import MdFile

# If using your custom font, remember to register it once:
pdfmetrics.registerFont(TTFont('Tiro Devanagari Sanskrit', '/home/vvasuki/gitland/indic-transliteration/sanskrit-fonts/fonts/ttf-devanagari/TiroDevanagariSanskrit-Regular.ttf'))


def save_grid_a3_pdf(text, dest_file, num_cols=4, num_rows=1, font="Tiro Devanagari Sanskrit", font_size=12):
  """
  Creates an A3 Landscape PDF with a grid of columns and rows and automatic text wrapping.
  """
  # Handle markdown file reading if path is provided
  if os.path.exists(text):
    # Assuming MdFile is a custom class you have defined elsewhere
    md_file = MdFile(file_path=text)
    (_, text) = md_file.read()

  width, height = landscape(A3)
  can = canvas.Canvas(dest_file, pagesize=(width, height))

  # 1. Calculate Grid Dimensions
  padding = 15  # Internal padding within each cell
  col_width = width / num_cols
  row_height = height / num_rows

  # 2. Draw Column and Row Separators
  can.setStrokeColorRGB(0.7, 0.7, 0.7)  # Light grey lines
  can.setLineWidth(0.5)

  # Draw vertical lines
  for i in range(1, num_cols):
    x = i * col_width
    can.line(x, 0, x, height)

  # Draw horizontal lines
  for j in range(1, num_rows):
    y = j * row_height
    can.line(0, y, width, y)

  # 3. Define Paragraph Style
  style = ParagraphStyle(
    name='GridStyle',
    fontName=font,
    fontSize=font_size,
    leading=font_size * 1.4, # Adjusted for Sanskrit scripts
    alignment=TA_CENTER,
  )

  # 4. Fill the Grid
  for row in range(num_rows):
    for col in range(num_cols):
      # Calculate coordinates
      # Note: ReportLab Y starts from bottom (0). 
      # We want row 0 to be at the top.
      x_pos = col * col_width
      y_pos = (num_rows - 1 - row) * row_height

      # Create Frame for the specific cell
      f = Frame(
        x_pos + padding,
        y_pos + padding,
        col_width - (padding * 2),
        row_height - (padding * 2),
        showBoundary=False
      )

      # Create Paragraph and add to frame
      p = Paragraph(text, style)
      f.addFromList([p], can)

  can.save()
  logging.info(f"Grid PDF saved to: {dest_file} ({num_cols}x{num_rows})")

# --- Example Usage ---
# save_grid_a3_pdf("My Sanskrit Text", "output.pdf", num_cols=3, num_rows=2, font_size=18)


def insert_text_at_index(text, input_pdf_path, font_size=30, index=0, output_pdf_path=None ):
  """Inserts a custom text page into an existing PDF at the specified index."""
  if output_pdf_path is None:
    output_pdf_path = input_pdf_path

  reader = PdfReader(input_pdf_path)
  writer = PdfWriter()

  # Copy existing pages to writer
  writer.append_pages_from_reader(reader)

  # Get dimensions from the first page of the original PDF to match style
  # If PDF is empty, default to A4 (595 x 842)
  if len(reader.pages) > 0:
    width = float(reader.pages[0].mediabox.width)
    height = float(reader.pages[0].mediabox.height)
  else:
    width, height = 595.0, 842.0

  # Create the new page
  new_page = create_page(text, width, height, font_size=font_size)

  # Insert the page at the specified position
  # index 0 = start, -1 = end, or any middle integer
  writer.insert_page(new_page, index=index)

  # Save the result
  with open(output_pdf_path, "wb") as output_file:
    writer.write(output_file)

def create_page(text, width, height, font="Tiro Devanagari Sanskrit", font_size=30):
  """Creates a temporary PDF page with the specified text."""
  packet = io.BytesIO()
  can = canvas.Canvas(packet, pagesize=(width, height))

  # Set font and center the text
  can.setFont(font, size=font_size)
  can.drawCentredString(width / 2, height / 2, text)
  can.save()

  packet.seek(0)
  new_pdf = PdfReader(packet)
  return new_pdf.pages[0]


def trim_pdf_until_text(input_pdf_path, target_pattern, output_pdf_path=None, start_index=0, case_sensitive=False):
  """
  Skips all pages before start_index, then continues removing pages until 
  a page is found where the text starts with target_text.
  """
  if output_pdf_path is None:
    output_pdf_path = input_pdf_path
  reader = PdfReader(input_pdf_path)
  writer = PdfWriter()

  found_trigger = False
  total_pages = len(reader.pages)

  for i in range(total_pages):

    page = reader.pages[i]
    # 1. Skip pages physically located before the start_index
    if i < start_index:
      writer.add_page(page)
      continue

    # 2. If we haven't found the trigger text yet, keep checking
    if not found_trigger:
      text = (page.extract_text() or "").strip()

      # Setup comparison strings
      search_content = text if case_sensitive else text.lower()

      if regex.match(target_pattern, search_content, flags=regex.DOTALL):
        found_trigger = True
        logging.info(f"Trigger text found on page index {i}. Starting output from here.")
      else:
        # Still haven't found the text, skip this page
        continue

    # 3. Once found_trigger is True, all subsequent pages (and the trigger page) are added
    writer.add_page(page)

  if not found_trigger:
    logging.warning(f"The pattern '{target_pattern}' was not found at the start of any page after index {start_index}.")
    return

  # Save the result
  with open(output_pdf_path, "wb") as output_file:
    writer.write(output_file)

  print(f"Success! New PDF saved to {output_pdf_path}")


def get_page_index_with_pattern(target_pattern, pdf_path, start_index=0,search_direction=None):
  """
  Returns the 0-based index of the first page containing the regex pattern.
  Returns -1 if the pattern is not found.
  """
  reader = PdfReader(pdf_path)
  pages = list(reader.pages)
  num_pages = len(pages)
  if search_direction is not None:
    pages = reversed(pages)
  for i, page in enumerate(pages):
    if i < start_index:
      continue
    # Extract text from page (handle None if page is an image/empty)
    content = page.extract_text() or ""

    # re.DOTALL: allows '.' to match newlines (\n)
    # re.IGNORECASE: usually helpful for PDF text extraction
    if regex.search(target_pattern, content, flags=regex.DOTALL | regex.IGNORECASE):
      logging.info(f"Found {target_pattern} at {i} with direction {search_direction}")
      if search_direction is not None:
        return num_pages - 1 - i
      else:
        return i


  return -1