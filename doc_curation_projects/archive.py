from curation_utils import archive_utility
import logging
from urllib.error import HTTPError
import wget, os


# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


BASE = "/home/vvasuki/Documents/books/granthasangrahaH/"



if __name__ == '__main__':
  archive_utility.update_item(item_id="rahasya-traya-sAraH_cm-vijayarAghavaH", dir_path="/media/vvasuki/vData/text/granthasangrahaH/AgamaH/vaiShNavaH/shrIvaiShNavaH/venkaTanAtha/rts/cmv")
