import logging

from pypdf import PdfReader, PdfWriter, PageObject


def to_booklet(input_pdf_path, output_pdf_path):
  reader = PdfReader(input_pdf_path)
  writer = PdfWriter()

  # 1. Get original dimensions and page count
  num_pages = len(reader.pages)
  first_page = reader.pages[0]
  orig_width = float(first_page.mediabox.width)
  orig_height = float(first_page.mediabox.height)

  # 2. Pad PDF to a multiple of 4 (required for booklet folding)
  padded_pages = list(reader.pages)
  while len(padded_pages) % 4 != 0:
    padded_pages.append(writer.add_blank_page(width=orig_width, height=orig_height))

  total_padded = len(padded_pages)

  # 3. Rearrange and merge pages side-by-side
  # We create total_padded / 2 sheets (each sheet has 2 pages side-by-side)
  for i in range(total_padded // 2):
    # Determine Left and Right page indices based on booklet logic
    # Sequence: (Last, First), (Second, Last-1), (Last-2, Third), (Fourth, Last-3)...
    if i % 2 == 0:
      left_idx = total_padded - 1 - i
      right_idx = i
    else:
      left_idx = i
      right_idx = total_padded - 1 - i

    left_page = padded_pages[left_idx]
    right_page = padded_pages[right_idx]

    # Create a new blank double-wide page
    new_page = PageObject.create_blank_page(
      width=orig_width * 2,
      height=orig_height
    )

    # Merge the left and right logical pages onto the double-wide sheet
    new_page.merge_page(left_page)
    new_page.merge_transformed_page(
      right_page,
      [1, 0, 0, 1, orig_width, 0] # Shift right page by orig_width
    )

    writer.add_page(new_page)

  # 4. Save the result
  with open(output_pdf_path, "wb") as out_file:
    writer.write(out_file)
  logging.info(f"Booklet created: {output_pdf_path}")

# Example Usage:
# to_booklet("my_document.pdf", "my_booklet.pdf")



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
    padded_pages.append(writer.add_blank_page(width=orig_width, height=orig_height))

  total_padded = len(padded_pages)

  # 3. Create the duplicated booklet sheets
  # We iterate through sheets (each sheet represents one duplex pass)
  for i in range(total_padded // 2):
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
    output_pdf_path = input_pdf_path.replace(".pdf", "_dup_booklet.pdf")
  with open(output_pdf_path, "wb") as out_file:
    writer.write(out_file)
  logging.info(f"Duplicated booklet created: {output_pdf_path}")

# Example Usage:
# duplicated_booklet("my_document.pdf", "double_copy_booklet.pdf")