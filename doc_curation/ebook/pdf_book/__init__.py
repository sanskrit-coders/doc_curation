import io
import logging
import os
import os.path

import regex
from pypdf import PdfReader, PdfWriter

import io
from fpdf import FPDF
from pypdf import PdfReader

from doc_curation.md.file import MdFile


SKT_FONT = '/home/vvasuki/gitland/indic-transliteration/sanskrit-fonts/fonts/ttf-devanagari/TiroDevanagariSanskrit-Regular.ttf'

try:
  import uharfbuzz
  logging.info("HarfBuzz detected! Sanskrit shaping is ACTIVE.")
except ImportError:
  logging.warning("HarfBuzz NOT detected. Sanskrit shaping will be BROKEN.")
  logging.warning("Please run: pip install uharfbuzz")



def save_grid_a3_pdf(text, dest_file, num_cols=4, num_rows=1, font_path=SKT_FONT, font_size=12):
  """
  Creates an A3 Landscape PDF with a grid using fpdf2 for correct Sanskrit shaping.
  """
  # 1. Handle input text (Markdown or String)
  if os.path.exists(text):
    try:
      # Assuming your custom MdFile class exists
      md_file = MdFile(file_path=text)
      (_, text) = md_file.read()
    except Exception as e:
      logging.error(f"Failed to read file: {e}")

  # 2. Setup FPDF for A3 Landscape
  # unit="pt" matches your previous logic (points)
  pdf = FPDF(orientation="L", unit="pt", format="A3")
  pdf.set_text_shaping(True)

  # Register the Unicode font (Crucial for Sanskrit shaping)
  pdf.add_font("Tiro", style="", fname=font_path)
  pdf.set_font("Tiro", size=font_size)
  pdf.add_page()

  # Get page dimensions
  width = pdf.w
  height = pdf.h

  # 3. Calculate Grid Dimensions
  padding = 15
  col_width = width / num_cols
  row_height = height / num_rows
  line_height = font_size * 1.4

  # 4. Draw Column and Row Separators
  pdf.set_draw_color(180, 180, 180)  # Light grey (RGB)
  pdf.set_line_width(0.5)

  for i in range(1, num_cols):
    x = i * col_width
    pdf.line(x, 0, x, height)

  for j in range(1, num_rows):
    y = j * row_height
    pdf.line(0, y, width, y)

  # 5. Fill the Grid
  for row in range(num_rows):
    for col in range(num_cols):
      # Inner width for text
      inner_w = col_width - (padding * 2)
      lines = pdf.multi_cell(w=inner_w, text=text, split_only=True)
      total_text_height = len(lines) * line_height
      
      # Set X and Y relative to the cell
      start_x = (col * col_width) + padding
      start_y = (row * row_height) + (row_height - total_text_height) / 2
      
      pdf.set_xy(start_x, start_y)
      pdf.multi_cell(w=inner_w, h=line_height, text=text, align="C")

  # 6. Save
  pdf.output(dest_file)
  logging.info(f"Sanskrit Grid PDF saved to: {dest_file} ({num_cols}x{num_rows})")



# --- Example Usage ---
# save_grid_a3_pdf("My Sanskrit Text", "output.pdf", num_cols=3, num_rows=2, font_size=18)


def create_page(text, width, height, font_path=SKT_FONT, font_size=30):
  # 1. Initialize FPDF in 'points' to match your PDF dimensions
  # 'L' for landscape, 'pt' for points
  pdf = FPDF(orientation="L", unit="pt", format=(width, height))
  pdf.set_margins(0, 0, 0)
  pdf.set_auto_page_break(False)

  pdf.set_text_shaping(True)
  # 2. Register the font (Mandatory for Sanskrit)
  # The 'fname' must point to your .ttf file
  pdf.add_font("Tiro", style="", fname=font_path)
  pdf.set_font("Tiro", size=font_size)

  pdf.add_page()

  # 3. Calculate Vertical Centering
  # In multi_cell, 'h' is the height of a SINGLE line. 
  # We use a standard line height of ~1.2x font size.
  line_height = font_size * 1.2

  # Use split_only=True to see how many lines the text will occupy
  lines = pdf.multi_cell(w=width, text=text, split_only=True)
  total_text_height = len(lines) * line_height

  # 3. Calculate the starting Y position for vertical centering
  start_y = (height - total_text_height) / 2
  pdf.set_y(start_y)

  # 4. Draw the text
  # w=width (full page width) + align="C" ensures horizontal center
  pdf.multi_cell(w=width, h=line_height, text=text, align="C")


# 5. Convert to pypdf Page object
  pdf_bytes = pdf.output()
  reader = PdfReader(io.BytesIO(pdf_bytes))
  return reader.pages[0]



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