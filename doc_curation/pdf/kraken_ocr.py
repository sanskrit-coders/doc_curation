import os

from kraken import kraken


model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/grantha_kraken.mlmodel')


def ocr(pdf_path, dest_path):
  kraken.ocr(model=model_path, )