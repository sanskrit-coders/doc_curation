import logging
import os

from indic_transliteration import sanscript
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
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


def dump_text_from_element(url, outfile_path, text_css_selector, title_css_selector=None, heading_class=None):
    if os.path.exists(outfile_path):
        logging.info("Skipping dumping: %s to %s", url, outfile_path)
        return 
    logging.info("Dumping: %s to %s", url, outfile_path)
    browser.get(url)
    os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
    text_elements = browser.find_elements_by_css_selector(text_css_selector)
    with open(outfile_path, "w") as outfile:
        for text_element in text_elements:
            text = text_element.text + "\n"
            if heading_class is not None and text_element.get_attribute("class") == heading_class:
                outfile.writelines("\n\n## %s\n" % text)
            else:
                outfile.writelines(text.replace("\n", "  \n"))
        
    if title_css_selector is not None:
        try:
            title_element = browser.find_element_by_css_selector(title_css_selector)
            title = title_element.text.strip()
        except NoSuchElementException:
            title = "UNKNOWN_TITLE"
        md_file = md_helper.MdFile(file_path=outfile_path)
        md_file.set_title(title=title, dry_run=False)
        
    logging.info("Done: %s to %s", url, outfile_path)
