import codecs
import json
import logging
import os

from indic_transliteration import sanscript
from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.remote.remote_connection import LOGGER

from doc_curation import scraping

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


browser = scraping.get_browser(headless=False)


def dump_text(url, out_path, overwrite=True):
    if overwrite == False and os.path.exists(out_path):
        logging.info("Not overwriting %s to %s", url, out_path)
        return
    logging.info("Dumping %s to %s", url, out_path)
    browser.get(url)
    text_elements = browser.find_elements_by_css_selector("div.sam")
    if len(text_elements) == 0:
        text_elements = [browser.find_elements_by_css_selector("table")[1]]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with codecs.open(out_path, "w", 'utf-8') as file_out:
        for text_element in text_elements:
            text = text_element.text.replace("\n", "  \n") + "\n"
            file_out.write(text)


def dump_book(init_url, out_path, overwrite=True):
    logging.info("Dumping %s to %s", init_url, out_path)
    browser.get(init_url)
    book_part_links = browser.find_elements_by_css_selector(css_selector="div.adLinks a")
    if len(book_part_links) == 0:
        book_part_links = browser.find_elements_by_css_selector(css_selector="div.suktaLinks a")
    part_urls = [part.get_attribute("href") for part in book_part_links]
    for url in part_urls:
        file_name = url.split("/")[-1].split(".")[0] + ".md"
        dump_text(url=url, out_path=os.path.join(out_path, file_name), overwrite=overwrite)