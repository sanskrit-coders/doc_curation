import codecs
import logging
import os

from selenium.webdriver.remote.remote_connection import LOGGER

from curation_utils import scraping

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


browser = scraping.get_selenium_browser(headless=False)


def dump_text(url, out_path, overwrite=True):
    if overwrite == False and os.path.exists(out_path):
        logging.info("Not overwriting %s to %s", url, out_path)
        return
    logging.info("Dumping %s to %s", url, out_path)
    browser.get(url)
    text_elements = browser.find_elements_by_css_selector("div.sam")
    if len(text_elements) == 0:
        text_elements = [browser.find_elements_by_css_selector("table")[-1]]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with codecs.open(out_path, "w", 'utf-8') as file_out:
        for text_element in text_elements:
            text = text_element.text.replace("\n", "  \n") + "\n"
            file_out.write(text)


def dump_book(init_url, out_path, overwrite=True):
    logging.info("Dumping %s to %s", init_url, out_path)
    browser.get(init_url)
    
    divs = browser.find_elements_by_css_selector(css_selector="div")
    divs = [div for div in divs if 
            (div.get_attribute("class") and "Links" in div.get_attribute("class")) or 
            (div.get_attribute("id") and "left" in div.get_attribute("id"))]
    
    book_part_links = []
    for div in divs:
        book_part_links.extend(div.find_elements_by_css_selector("a"))

    if len(book_part_links) == 0:
        logging.error("Could not get book part links!")
    part_urls = [part.get_attribute("href") for part in book_part_links]
    for url in part_urls:
        file_name = url.split("/")[-1].split(".")[0] + ".md"
        dump_text(url=url, out_path=os.path.join(out_path, file_name), overwrite=overwrite)