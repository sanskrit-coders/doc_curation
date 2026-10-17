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


DESCRIPTION_BASE = """
पठन-सौकर्याय-रक्ष्यमाणम् अत्र।  
भवद्-योगदानं‌ काङ्क्ष्यते - https://sanskrit.github.io/groups/dyuganga/
"""


if __name__ == '__main__':
  pass
  archive_utility.update_item(item_id="rahasya-traya-sAraH_cm-vijayarAghavaH", dir_path="/media/vvasuki/vData/text/granthasangrahaH/AgamaH/vaiShNavaH/shrIvaiShNavaH/venkaTanAtha/rts/cmv", metadata={"title": "रहस्य-त्रय-सार-भाष्यम् - कन्नडेन", "description": "विजय-राघवाचार्य-कृतोऽनुवादः। पुरा हॆब्बार्-श्रीवैष्णव-सभया प्रकाशितः।\n\n" + DESCRIPTION_BASE})
  archive_utility.update_item(item_id="bhagavad-gItA_cm-vijayarAghavaH", dir_path="/media/vvasuki/vData/text/granthasangrahaH/AgamaH/vaiShNavaH/shrIvaiShNavaH/rAmAnuja/gItA-bhASHyam/cmv", metadata={"title": "भगवद्-गीता-भाष्यम् - कन्नडेन। पुरा हॆब्बार्-श्रीवैष्णव-सभया प्रकाशितः।", "description": "विजय-राघवाचार्य-कृतोऽनुवादः\n\n" + DESCRIPTION_BASE})
