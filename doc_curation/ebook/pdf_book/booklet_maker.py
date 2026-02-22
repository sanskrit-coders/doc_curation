import logging

from doc_curation.ebook import pdf_book
from pypdf import PdfReader, PdfWriter, PageObject
from pypdf import Transformation
from pypdf.annotations import Line
from tqdm import tqdm
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm  # Import cm for easy conversion
from reportlab.lib.pagesizes import portrait
import io




def get_page_separator_overlay(w, h, mid_width=True, mid_height=True, stitch_points=False):
  packet = io.BytesIO()
  can = canvas.Canvas(packet, pagesize=(w, h))
  can.setStrokeColorRGB(0, 0, 0) # Black
  can.setLineWidth(0.5)

  # Draw crosshair
  if mid_width:
    can.line(w/2, 0, w/2, h)
  if mid_height:
    can.line(0, h/2, w, h/2)

  # Draw Stitch Points
  if stitch_points:
    # Radius of the hole (in points)
    radius = 2
    # X position is the middle width
    x = w / 2
    # Define 4 Y positions along the vertical spine
    # 1 cm offset from the center of each pair results in a 2 cm gap
    offset = 1.5 * cm

    # Calculate Y positions
    # Pair 1: centered at 25% (h * 0.25)
    # Pair 2: centered at 75% (h * 0.75)
    y_positions = [
      (h * 0.25) - offset, (h * 0.25) + offset,
      (h * 0.75) - offset, (h * 0.75) + offset
    ]
    for y in y_positions:
      # Draw an unfilled circle to represent a punch hole
      can.circle(x, y, radius, stroke=1, fill=0)

      # Add a small cross inside the circle for high-precision alignment
      can.line(x - radius, y, x + radius, y)
      can.line(x, y - radius, x, y + radius)

  can.save()
  packet.seek(0)
  return PdfReader(packet).pages[0]


def to_booklet(input_pdf_path, output_pdf_path=None, max_sheets=None, signature_title=None):
  """
  :param input_pdf_path: Path to source PDF.
  :param output_pdf_path: Path to save result.
  :param max_sheets: Max physical sheets per signature (4 pages per sheet).
  :param signature_title: String prefix for the separator page (e.g. "Part"). 
                          If None, no separator is added.
  """
  reader = PdfReader(input_pdf_path)
  writer = PdfWriter()

  first_page = reader.pages[0]
  orig_width = float(first_page.mediabox.width)
  orig_height = float(first_page.mediabox.height)
  sheet_width = orig_width * 2

  # 1. Pad the entire PDF to a multiple of 4 first
  pages_in = list(reader.pages)
  total_padded = len(pages_in)

  # 2. Determine pages per signature
  if max_sheets:
    pages_per_sig = max_sheets * 4
  else:
    pages_per_sig = total_padded

  # 3. Process signatures
  sig_count = 1
  # Wrap range in tqdm for a progress bar
  for sig_start in tqdm(range(0, total_padded, pages_per_sig), desc="Signatures"):
    sig_end = min(sig_start + pages_per_sig, total_padded)
    sig_pages = pages_in[sig_start:sig_end]

    # --- Add Title Page if prefix is provided ---
    if sig_start != 0 and signature_title is not None:
      title_text = f"{signature_title} {sig_count}"
      # Add the front of the separator sheet
      writer.add_page(pdf_book.create_page(title_text, orig_width, orig_height))
      # Add a blank back for the separator sheet
      writer.add_page(PageObject.create_blank_page(width=orig_width, height=orig_height))

    # Ensure current signature slice is a multiple of 4 (for the final chunk)
    while len(sig_pages) % 4 != 0:
      blank = PageObject.create_blank_page(width=orig_width, height=orig_height)
      sig_pages.append(blank)

    sig_len = len(sig_pages)
    num_sheets_in_sig = sig_len // 2 # 2 pages (logical) per side of sheet

    indices = list(range(num_sheets_in_sig))
    # 4. Rearrange pages within this signature
    for i in tqdm(indices):
      # Booklet logic: alternates (Last, First) then (Second, Last-1)
      if i % 2 == 0:
        left_idx = sig_len - 1 - i
        right_idx = i
      else:
        left_idx = i
        right_idx = sig_len - 1 - i

      left_page = sig_pages[left_idx]
      right_page = sig_pages[right_idx]

      new_page = PageObject.create_blank_page(width=sheet_width, height=orig_height)
      new_page.merge_page(left_page)
      new_page.merge_transformed_page(
        right_page,
        [1, 0, 0, 1, orig_width, 0]
      )
      if i in [indices[0], indices[-1]]:
        overlay = get_page_separator_overlay(w=sheet_width, h=orig_height, mid_width=True, mid_height=False, stitch_points=True)
        new_page.merge_page(overlay)
      else:
        overlay = get_page_separator_overlay(w=sheet_width, h=orig_height, mid_width=False, mid_height=False, stitch_points=True)
        new_page.merge_page(overlay)
        

      writer.add_page(new_page)

    sig_count += 1

  # 5. Save the result
  if output_pdf_path is None:
    output_pdf_path = input_pdf_path.replace(".pdf", "_LandShortEdge_booklet.pdf")
  # 4. Save the result
  with open(output_pdf_path, "wb") as out_file:
    writer.write(out_file)

  logging.info(f"Created booklet with {sig_count-1} signatures at: {output_pdf_path}")


def duplicated_booklet(input_pdf_path, output_pdf_path=None):
  # Speed - 23 min for 400 pg A3.
  reader = PdfReader(input_pdf_path)
  writer = PdfWriter()

  # 1. Get original dimensions and page count
  num_pages = len(reader.pages)
  first_page = reader.pages[0]
  orig_width = float(first_page.mediabox.width)
  orig_height = float(first_page.mediabox.height)

  # 2. Pad PDF to a multiple of 4
  padded_pages = list(reader.pages)
  while len(padded_pages) % 4 != 0:
    blank = PageObject.create_blank_page(width=orig_width, height=orig_height)
    padded_pages.append(blank)

  total_padded = len(padded_pages)

  # 3. Create the duplicated booklet sheets
  # We iterate through sheets (each sheet represents one duplex pass)
  for i in tqdm(range(total_padded // 2)):
    # Determine Left and Right page indices for the booklet spread
    if i % 2 == 0:
      left_idx = total_padded - 1 - i
      right_idx = i
    else:
      left_idx = i
      right_idx = total_padded - 1 - i

    left_page = padded_pages[left_idx]
    right_page = padded_pages[right_idx]

    # Create a blank sheet twice as wide and twice as high (2x2 grid)
    new_page = PageObject.create_blank_page(
      width=orig_width * 2,
      height=orig_height * 2
    )

    # --- TOP ROW (Row 1) ---
    # Place left_page at (0, orig_height)
    new_page.merge_transformed_page(
      left_page, [1, 0, 0, 1, 0, orig_height]
    )
    # Place right_page at (orig_width, orig_height)
    new_page.merge_transformed_page(
      right_page, [1, 0, 0, 1, orig_width, orig_height]
    )

    # --- BOTTOM ROW (Row 2 - Duplicated) ---
    # Place left_page at (0, 0)
    new_page.merge_transformed_page(
      left_page, [1, 0, 0, 1, 0, 0]
    )
    # Place right_page at (orig_width, 0)
    new_page.merge_transformed_page(
      right_page, [1, 0, 0, 1, orig_width, 0]
    )

    writer.add_page(new_page)

  # 4. Save the result
  if output_pdf_path is None:
    output_pdf_path = input_pdf_path.replace(".pdf", "_dup_PortLongEdge_booklet.pdf")
  with open(output_pdf_path, "wb") as out_file:
    writer.write(out_file)
  logging.info(f"Duplicated booklet created: {output_pdf_path}")

# Example Usage:
# duplicated_booklet("my_document.pdf", "double_copy_booklet.pdf")


def two_column_page_booklet(input_pdf_path, output_pdf_path=None):
  reader = PdfReader(input_pdf_path)
  writer = PdfWriter()

  num_pages = len(reader.pages)
  if num_pages == 0:
    return

  first_page = reader.pages[0]
  orig_width = float(first_page.mediabox.width)
  orig_height = float(first_page.mediabox.height)

  # 1. Pad PDF to a multiple of 8 (each 2-sided sheet holds 8 pages)
  padded_pages = list(reader.pages)
  while len(padded_pages) % 8 != 0:
    blank = PageObject.create_blank_page(width=orig_width, height=orig_height)
    padded_pages.append(blank)

  total_padded = len(padded_pages)
  num_sheets = total_padded // 8

  # Dimensions for the A3-style landscape sheet
  # 1. Transpose Sheet Dimensions to Portrait
  sheet_w = orig_width * 2
  sheet_h = orig_height * 2

  for i in tqdm(range(num_sheets), desc="Generating Booklet"):
    # --- FRONT SIDE (Odd Output Page) ---
    front_page = writer.add_blank_page(width=sheet_w, height=sheet_h)

    # Indices
    idx_tl_f = total_padded - 2 - 4*i
    idx_tr_f = total_padded - 1 - 4*i
    idx_bl_f = 4*i
    idx_br_f = 4*i + 1

    # Front Rotation: 0 degrees (Facing Up)
    # TL: x=0, y=orig_height | BL: x=0, y=0 | TR: x=orig_width, y=orig_height | BR: x=orig_width, y=0
    front_page.merge_transformed_page(padded_pages[idx_tl_f], Transformation().translate(tx=0, ty=orig_height))
    front_page.merge_transformed_page(padded_pages[idx_bl_f], Transformation().translate(tx=0, ty=0))
    front_page.merge_transformed_page(padded_pages[idx_tr_f], Transformation().translate(tx=orig_width, ty=orig_height))
    front_page.merge_transformed_page(padded_pages[idx_br_f], Transformation().translate(tx=orig_width, ty=0))



    # --- BACK SIDE (Even Output Page) ---
    back_page = writer.add_blank_page(width=sheet_w, height=sheet_h)

    # Indices 
    idx_tl_b = total_padded - 3 - 4*i
    idx_tr_b = total_padded - 4 - 4*i
    idx_bl_b = 4*i + 3
    idx_br_b = 4*i + 2

    # Back Rotation: 180 degrees (Opposite direction to 0)
    # Note: rotate(180) moves coords to (-x, -y). We translate back into the positive slots.
    # Slot TL: tx=orig_width, ty=sheet_h
    back_page.merge_transformed_page(padded_pages[idx_tl_b], Transformation().rotate(180).translate(tx=orig_width, ty=sheet_h))
    # Slot BL: tx=orig_width, ty=orig_height
    back_page.merge_transformed_page(padded_pages[idx_bl_b], Transformation().rotate(180).translate(tx=orig_width, ty=orig_height))
    # Slot TR: tx=sheet_w, ty=sheet_h
    back_page.merge_transformed_page(padded_pages[idx_tr_b], Transformation().rotate(180).translate(tx=sheet_w, ty=sheet_h))
    # Slot BR: tx=sheet_w, ty=orig_height
    back_page.merge_transformed_page(padded_pages[idx_br_b], Transformation().rotate(180).translate(tx=sheet_w, ty=orig_height))

    # Add lines 
    overlay = get_page_separator_overlay(sheet_w, sheet_h, mid_width=True, mid_height=True)
    front_page.merge_page(overlay)
    back_page.merge_page(overlay)


  if output_pdf_path is None:
    output_pdf_path = input_pdf_path.replace(".pdf", "_2col_PortLongEdge_booklet.pdf")
  with open(output_pdf_path, "wb") as out_file:
    writer.write(out_file)
  logging.info(f"Booklet created: {output_pdf_path}")