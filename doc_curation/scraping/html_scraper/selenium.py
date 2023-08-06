import logging
import os
from functools import lru_cache
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome import options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.remote_connection import LOGGER
import time
from bs4 import BeautifulSoup

from doc_curation.md.file import MdFile

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger

urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


@lru_cache
def get_browser():
  opts = options.Options()
  opts.headless = False
  browser = webdriver.Chrome(options=opts)
  browser.implicitly_wait(2)
  return browser

def get_soup(x):
  browser = get_browser()
  if hasattr(x, "page_source"):
    return BeautifulSoup(browser.page_source, features="html.parser")
  else:
    elementHTML = x.get_attribute('outerHTML')
    return BeautifulSoup(elementHTML,'html.parser')

def get_text(browser, text_css_selector):
  text_elements = browser.find_elements(by=By.CSS_SELECTOR, value=text_css_selector)
  texts = [text_element.text for text_element in text_elements]
  return "\n\n".join(texts)

def dump_text_from_element(url, outfile_path, text_css_selector, title_css_selector=None, heading_class=None, skip_existing=True):
  if os.path.exists(outfile_path) and skip_existing:
    logging.info("Skipping dumping: %s to %s", url, outfile_path)
    return
  logging.info("Dumping: %s to %s", url, outfile_path)
  browser = get_browser()
  browser.get(url)
  os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
  with open(outfile_path, "w") as outfile:
    text_elements = browser.find_elements(by=By.CSS_SELECTOR, value=text_css_selector)
    for text_element in text_elements:
      text = text_element.text + "\n"
      if heading_class is not None and text_element.get_attribute("class") == heading_class:
        outfile.writelines("\n\n## %s\n" % text)
      else:
        outfile.writelines(text.replace("\n", "  \n"))

  if title_css_selector is not None:
    title = get_title(title_css_selector)
    md_file = MdFile(file_path=outfile_path)
    md_file.set_title(title=title, dry_run=False)

  logging.info("Done: %s to %s", url, outfile_path)


def get_title(title_css_selector):
  if title_css_selector is None:
    return "UNKNOWN_TITLE"
  try:
    browser = get_browser()
    title_element = browser.find_element(value=title_css_selector, by=By.CSS_SELECTOR)
    title = title_element.text.strip()
  except NoSuchElementException:
    title = "UNKNOWN_TITLE"
  return title


def dump_pages(url, out_path, next_button_css, content_css, page_id_css_selector=None, wait_between_requests=2, skip_existing=True):
  if os.path.exists(out_path) and skip_existing:
    return 
  logging.info("Dumping: %s to %s", url, out_path)
  browser = get_browser()
  browser.get(url)
  page_number = 1
  prev_page_id = "DUMMY"
  os.makedirs(name=os.path.dirname(out_path), exist_ok=True)
  with open(out_path, "w") as outfile:
    while True:
      if page_id_css_selector is not None:
        element = browser.find_element(value=page_id_css_selector, by=By.CSS_SELECTOR)
        if element.tag_name.lower() == "input":
          page_id = element.get_attribute('value')
        else:
          page_id = element.text.strip()
        if prev_page_id == page_id:
          break
      else:
        page_id = "%03d" % page_number
      logging.info("page_id: %s", page_id)
      text = get_text(browser=browser, text_css_selector=content_css)
      outfile.write(f"[[{page_id}]]\n\n{text}\n\n")
      next_button = browser.find_element(value=next_button_css, by=By.CSS_SELECTOR)
      if next_button is None or next_button.get_attribute("disabled") == "true":
        break
      else:
        click_element(browser=browser, element=next_button)
        time.sleep(wait_between_requests)
        page_number = page_number + 1
        prev_page_id = page_id


def click_element(browser, element):
  # element.click()
  # Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen 
  browser.execute_script("arguments[0].click();", element)

def click_link_by_text(browser, element_text):
  try:
    subunit_elements = browser.find_elements(By.LINK_TEXT, element_text)
    if len(subunit_elements) == 0:
      logging.warning("Could not find %s", element_text)
      return False
    logging.info("Clicking: %s" % element_text)
    click_element(browser=browser, element=subunit_elements[-1])
    return True
  except NoSuchElementException:
    logging.warning("Could not find %s", element_text)
    return False
