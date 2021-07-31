import email
import logging
import os
from urllib.parse import urlsplit
from urllib.request import urlopen
from urllib.parse import urljoin
import time
import datetime


import regex
from bs4 import BeautifulSoup

from curation_utils import file_helper
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript, detect


for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")





months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def get_storage_name(text):
  text_optitrans = text
  if detect.detect(text_optitrans) == 'IAST':
    text_optitrans = sanscript.transliterate(text_optitrans, _from=sanscript.IAST, _to=sanscript.OPTITRANS)
  elif detect.detect(text_optitrans) == 'Devanagari':
    text_optitrans = sanscript.transliterate(text_optitrans, _from=sanscript.DEVANAGARI, _to=sanscript.OPTITRANS)
  storage_name = file_helper.clean_file_path(text_optitrans)[:20]
  return storage_name


def scrape_message(url, message_index, dest_dir, list_id, dry_run=False):
  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')

  subject = soup.find("h1").text.replace(list_id, "")
  author = soup.find("b").text
  date_string = soup.find("i").text
  message_time = time.mktime(email.utils.parsedate(date_string))
  date_string_cleaned = datetime.datetime.fromtimestamp(message_time).strftime('%Y-%m-%d')
  post_html = "<p>[Archive link](%s)</p>\n%s" % (url,soup.find("pre").encode_contents())

  file_name = "%s__%s.md" % (message_index, get_storage_name(author))
  dest_path = os.path.join(dest_dir, get_storage_name(text=subject), file_name)
  md_file = MdFile(file_path=dest_path)
  metadata = {"title": subject[:30], "date": date_string_cleaned, "upstream_url": url}
  md_file.import_content_with_pandoc(metadata=metadata, content=post_html, source_format="html",
                                     dry_run=dry_run)


def scrape_messages_for_month(url, dest_dir_base, list_id, dry_run=False):

  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  [month_str, year] = soup.find("h1").text.split()[:2]
  month_index = months.index(month_str) + 1

  dest_dir = os.path.join(dest_dir_base, year, "%02d" % month_index)
  dir_files = [x[0] for x in os.walk(dest_dir)]
  if len(dir_files) > 0:
    logging.info("Skipping %s", dest_dir)
    return


  tags = soup.select("a")
  post_anchors = [tag for tag in tags if list_id in tag.text]
  for message_index, anchor in enumerate(post_anchors):
    post_url = urljoin(url, anchor["href"])
    scrape_message(url=post_url, message_index=message_index, dest_dir=dest_dir, list_id=list_id, dry_run=dry_run)


def delete_last_month(dest_dir_base):
  import glob
  files = glob.glob(os.path.join(dest_dir_base, '**/*.md'), recursive=True)
  files = [file for file in files if files != "_index.md"]
  files = sorted(files, reverse=True)
  if len(files) > 0:
    os.rmdir(os.path.dirname(files[0]))


def scrape_messages(url, dest_dir_base, list_id="[INDOLOGY] ", dry_run=False):
  delete_last_month(dest_dir_base)

  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  tags = soup.select("a")
  month_anchors = [tag for tag in tags if "Subject" in tag.text]
  for anchor in month_anchors:
    month_url = urljoin(url, anchor["href"])
    scrape_messages_for_month(url=month_url, dest_dir_base=dest_dir_base, list_id=list_id, dry_run=dry_run)
    