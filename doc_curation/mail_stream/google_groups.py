import codecs
import logging
import os
from datetime import datetime

import regex
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.remote_connection import LOGGER

from curation_utils import scraping, file_helper

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


browser = scraping.get_selenium_chrome(headless=False)


def scrape_thread(url, dest_dir, dry_run=False):
  browser.get(url=url)
  try:
    expand_link = browser.find_element_by_link_text("")
    expand_link.click()
  except NoSuchElementException:
    pass
  subject = browser.find_element_by_css_selector("h1").text
  section_tags = browser.find_elements_by_css_selector("section")
  span_tags = section_tags[0].find_elements_by_css_selector("span")
  date_tag = list(filter(lambda x: regex.match("^[A-Z][a-z][a-z] \d\d, \d\d\d\d,.+", x.text.strip()) , span_tags))[0]
  thread_date = datetime.strptime(date_tag.text, '%b %d, %Y, %I:%M:%S %p')
  thread_dir = os.path.join(dest_dir, str(thread_date.year), "%02d" % thread_date.month, "%02d" % thread_date.day, "%s__%s" % (file_helper.get_storage_name(subject), os.path.basename(url)[:2]))
  for section in enumerate(section_tags):
    section_html = section.get_attribute('innerHTML')


if __name__ == '__main__':
    scrape_thread("https://groups.google.com/g/bvparishat/c/q3U6WByFG3Y")