import codecs
import logging
import os

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.remote_connection import LOGGER

from curation_utils import scraping
from doc_curation.md import library
from doc_curation.scraping.html_scraper import souper


from doc_curation.md.library import metadata_helper
from doc_curation.md.file import MdFile, file_helper
from doc_curation.md.content_processor import ocr_helper
import logging
import os, regex


LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger

urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

browser = scraping.get_selenium_chrome(headless=False)


def dump_text(url, out_path, overwrite=True):
  if overwrite == False and os.path.exists(out_path):
    logging.info("Not overwriting %s to %s", url, out_path)
    return
  logging.info("Dumping %s to %s", url, out_path)
  browser.get(url)
  text_elements = browser.find_elements(By.CSS_SELECTOR, "div.sam")
  if len(text_elements) == 0:
    text_elements = [browser.find_elements(By.CSS_SELECTOR, "table")[-1]]
  os.makedirs(os.path.dirname(out_path), exist_ok=True)
  page_header = f"[[Source: [SS]({url})]]"
  text = f"{page_header}\n\n"
  for text_element in text_elements:
    text += text_element.text.replace("\n", "  \n") + "\n"
  md_file = MdFile(file_path=out_path)
  md_file.dump_to_file(metadata={"title": f""}, content=text, dry_run=False)
  metadata_helper.set_title_from_filename(md_file=md_file, dry_run=False)


def dump_book(init_url, out_path, overwrite=True):
  logging.info("Dumping %s to %s", init_url, out_path)
  browser.get(init_url)

  divs = browser.find_elements(By.CSS_SELECTOR, "div")
  divs = [div for div in divs if
          (div.get_attribute("class") and "Links" in div.get_attribute("class")) or
          (div.get_attribute("id") and "left" in div.get_attribute("id"))]

  book_part_links = []
  for div in divs:
    book_part_links.extend(div.find_elements(By.CSS_SELECTOR, "a"))

  if len(book_part_links) == 0:
    logging.error("Could not get book part links!")
  part_urls = [part.get_attribute("href") for part in book_part_links]
  for url in part_urls:
    file_name = url.split("/")[-1].split(".")[0] + ".md"
    dump_text(url=url, out_path=os.path.join(out_path, file_name), overwrite=overwrite)
  library.fix_index_files(os.path.dirname(os.path.dirname(out_path)))
