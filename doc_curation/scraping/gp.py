import codecs
import logging
import os
import time

import regex
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, \
  ElementNotInteractableException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from tqdm import tqdm

from curation_utils import scraping


def generator():
  while True:
    yield

def get_book_browser(url):
  # NOTE to V: Login with FB
  browser = scraping.get_selenium_chrome(headless=False)
  browser.get(url=url)
  time.sleep(6)
  next_element = browser.find_element_by_link_text("पुस्तक पढ़ें")
  browser.execute_script("arguments[0].click();", next_element)
  logging.info("Rewinding")
  for _ in tqdm(generator()):
    prev_arrow = browser.find_element_by_css_selector("#prev")
    if "hidden" in prev_arrow.get_attribute("style"):
      break
    try:
      browser.execute_script("arguments[0].click();", prev_arrow)
    except ElementNotInteractableException:
      break 
  return browser

def get_page_content(browser):
  while True:
    try:
      iframe = browser.find_element_by_tag_name("iframe")
      content = iframe.get_attribute("srcdoc")
    except (StaleElementReferenceException, NoSuchElementException):
      continue
    soup = BeautifulSoup(content, features="html.parser")
    content_div = soup.select_one("body>div")
    if content_div is not None:
      return content_div.decode_contents().replace("ॺ", "्य")

def dump_book(url, dest_html_path, final_url_check=None):
  if not dest_html_path.endswith(".html"):
    basename = os.path.basename(url)
    basename = regex.sub("-%28.+", "", basename)
    dest_html_path = os.path.join(dest_html_path, basename + ".html")
  logging.info(f"Dumping {url} to {dest_html_path}")
  browser = get_book_browser(url=url)
  os.makedirs(os.path.dirname(dest_html_path), exist_ok=True)
  logging.info("Flipping pages")
  with codecs.open(dest_html_path, "w") as dest_file:
    part_content_old = ""
    url_old = ""
    for _ in tqdm(generator()):
      part_content = get_page_content(browser=browser)
      # time.sleep(2)
      url = browser.current_url
      if final_url_check is not None and final_url_check(url):
        logging.info("Done")
        break
      if part_content != part_content_old:
        dest_file.write(part_content + "\n")
      url_old = url
      part_content_old = part_content
      next_arrow = browser.find_element_by_css_selector("#next")
      if "hidden" in next_arrow.get_attribute("style"):
        break
      try:
        browser.execute_script("arguments[0].click();", next_arrow)
      except ElementNotInteractableException:
        break
