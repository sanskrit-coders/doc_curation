from doc_curation import pdf

if __name__ == '__main__':
    pdf.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/vyAkaraNam/dIxita-puShpA/Astadhyayi Sahajabodha - I -Dr. Pushpa Dixit..pdf", small_pdf_pages=15)
    pdf.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/vyAkaraNam/dIxita-puShpA/Astadhyayi Sahajabodha - II -Dr. Pushpa Dixit.pdf")
    pdf.split_and_ocr_on_drive(pdf_path="/home/vvasuki/Documents/books/granthasangrahaH/vyAkaraNam/dIxita-puShpA/Astadhyayi Sahajabodha - III -Dr. Pushpa Dixit.pdf")
