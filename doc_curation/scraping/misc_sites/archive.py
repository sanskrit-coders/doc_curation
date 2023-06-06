import json
import logging
import os
import time
import traceback

from selenium.webdriver.common.by import By

from doc_curation import book_data
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.scraping.html_scraper import selenium
from doc_curation.scraping.html_scraper.selenium import click_link_by_text
from indic_transliteration import sanscript
from selenium.common.exceptions import NoSuchElementException

from curation_utils import scraping, file_helper

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

configuration = {}
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_config.json'), 'r') as handle:
  configuration = json.load(handle)


def get_logged_in_browser(headless=True):
  configuration_archive = configuration['archive']
  browser = scraping.get_selenium_chrome(headless=headless)
  browser.get("https://archive.org/account/login")
  username = browser.find_element(By.NAME, "username")
  username.send_keys(configuration_archive["user"])
  browser.find_element(By.NAME, "password").send_keys(configuration_archive["pass"])
  browser.find_element(By.NAME, "submit-to-login").click()
  return browser



def download_images(url, dest_dir):
  # Use credentials in case of borrowed books.
  browser = get_logged_in_browser(headless=False)
  browser.get(url=url)
  # document.querySelector("ia-book-actions").shadowRoot.querySelector("collapsible-action-group").shadowRoot.querySelector("button") 
  # works in js. But .shandow_root.find_element(By.CSS_SELECTOR, "button") fails in python.
  time.sleep(10)
  button = browser.find_element(By.CSS_SELECTOR, "ia-book-actions").shadow_root.find_element(By.CSS_SELECTOR, "collapsible-action-group")
  button.click()
  time.sleep(10)
  
  item_id = [x for x in url.split("/") if x != ""][-1]

  # Example images: https://ia804700.us.archive.org/BookReader/BookReaderImages.php?zip=/1/items/indianfreedomfig0000nair/indianfreedomfig0000nair_jp2.zip&file=indianfreedomfig0000nair_jp2/indianfreedomfig0000nair_0276.jp2&id=indianfreedomfig0000nair&scale=2&rotate=0
  
  
  url_base = f"https://ia804700.us.archive.org/BookReader/BookReaderImages.php?zip=/1/items/{item_id}/{item_id}_jp2.zip&id={item_id}&scale=2&rotate=0&file={item_id}_jp2/{item_id}_%04d.jp2"
  # TODO: Directly using the urls does not work. Should open a nearby page in the reader first.
  for image_id in range(1,9999):
    url = url_base % image_id
    browser.get(url=url)
    
    
    if "Error serving request:" in browser.page_source:
      logging.info(f"Could not get page {image_id}. Exiting.")
      break
    browser.save_screenshot(os.path.join(dest_dir, f"{image_id:04d}.png"))

  pass


def get_pdf(url, dest_path):
  tmp_dir = os.path.join(os.path.dirname(dest_path), f"tmp_{os.path.basename(dest_path)}").replace(".pdf", "")
  download_images(url=url, dest_dir=tmp_dir)
  from doc_curation.pdf import image_ops
  image_ops.save_pdf(image_dir=tmp_dir, pdf_path=dest_path)


if __name__ == '__main__':
  get_pdf(url="https://archive.org/details/indianfreedomfig0000nair/", dest_path="/run/media/vvasuki/vData/text/granthasangrahaH/history/indian_freedom_japan_am_nair.pdf")