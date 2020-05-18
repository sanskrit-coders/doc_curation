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


def rewind(init_url):
    browser.get(url=init_url)
    first_line_anchor = browser.find_element_by_css_selector(css_selector="td.utf>a")
    previous_page_url = first_line_anchor.get_attribute("href")
    if previous_page_url != init_url:
        rewind(init_url=previous_page_url)
    else:
        return init_url


def dump_text(init_url, out_path):
    def get_text_and_url(init_url):
        browser.get(url=init_url)
        next_url = browser.find_elements_by_css_selector(css_selector="td.utf>a")[-1].get_attribute("href")
        if next_url == init_url:
            logging.info("Finished.")
            return ("", None)
        text = browser.find_elements_by_css_selector(css_selector="td.utf+td.utf")[-2].text
        text = sanscript.transliterate(data=text, _from=sanscript.IAST, _to=sanscript.DEVANAGARI)
        logging.debug(text)
        return (text, next_url)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    next_url = init_url
    with codecs.open(out_path, "w", 'utf-8') as file_out:
        while next_url is not None:
            (text, next_url) = get_text_and_url(init_url=next_url)
            logging.debug(text)
            file_out.write(text + "  \n")

