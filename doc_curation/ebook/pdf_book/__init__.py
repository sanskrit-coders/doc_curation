import logging, regex

from pypdf import PdfReader, PdfWriter, PageObject
from pypdf import Transformation
from reportlab.pdfgen import canvas
import io


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
  can.setFont(font, font_size=40)
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