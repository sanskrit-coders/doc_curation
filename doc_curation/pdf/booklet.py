import os

from fpdf import FPDF

leaves = 8
page_width = 297
page_height = 420
card_width = page_width / 2
card_height = page_height / 2
pdf = FPDF(orientation="P", unit="mm", format="A3")
lang = "Bangla"
dir = "শ্রীকৃষ্ণলীলাস্তবঃ-4"
dir_path = f"{lang}{os.sep}{dir}"
files = os.listdir(dir_path)
_, ext = os.path.splitext(files[0])
pages = len(files)
set_pages = leaves * 4
sets = pages // set_pages
# Iterates sets; adds images to PDF pages; increments indices
for set_in in range(sets):
  start = set_in * set_pages
  end = ((set_in + 1) * set_pages) - 1
  for leaf in range(leaves):
    print(end, start)
    pdf.add_page()
    pdf.image(f"{dir_path}{os.sep}{dir}_{end}{ext}", 0, 0, card_width, card_height)
    pdf.image(f"{dir_path}{os.sep}{dir}_{start}{ext}", card_width, 0, card_width, card_height)
    pdf.image(f"{dir_path}{os.sep}{dir}_{end}{ext}", 0, card_height, card_width, card_height)
    pdf.image(f"{dir_path}{os.sep}{dir}_{start}{ext}", card_width, card_height, card_width, card_height)
    start += 1
    end -= 1
    print(start, end)
    pdf.add_page()
    pdf.image(f"{dir_path}{os.sep}{dir}_{start}{ext}", 0, 0, card_width, card_height)
    pdf.image(f"{dir_path}{os.sep}{dir}_{end}{ext}", card_width, 0, card_width, card_height)
    pdf.image(f"{dir_path}{os.sep}{dir}_{start}{ext}", 0, card_height, card_width, card_height)
    pdf.image(f"{dir_path}{os.sep}{dir}_{end}{ext}", card_width, card_height, card_width, card_height)
    start += 1
    end -= 1
pdf_path = f"{lang}{os.sep}{dir}-{leaves}-blkt-A3.pdf"
print(pdf_path)
pdf.output(pdf_path)
