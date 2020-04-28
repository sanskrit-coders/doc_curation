import logging
import os

from indic_transliteration import sanscript
from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.remote.remote_connection import LOGGER

from doc_curation import md_helper

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

opts = options.Options()
opts.headless = True
browser = webdriver.Chrome(options=opts)
browser.implicitly_wait(2)


def dump_text_from_element(url, outfile_path, text_css_selector, title_css_selector=None):
    logging.info("Dumping: %s to %s", url, outfile_path)
    browser.get(url)
    text = browser.find_element_by_css_selector(text_css_selector).text
    os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
    with open(outfile_path, "w") as outfile:
        outfile.writelines(text.replace("\n", "  \n"))
        
    if title_css_selector is not None:
        title = browser.find_element_by_css_selector(title_css_selector).text
        md_file = md_helper.MdFile(file_path=outfile_path)
        md_file.set_title(title=title, dry_run=False)
        
    logging.info("Done: %s to %s", url, outfile_path)
