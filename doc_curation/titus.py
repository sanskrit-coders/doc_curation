import logging

from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.remote.remote_connection import LOGGER
from selenium.webdriver.support.select import Select

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

options = options.Options()
options.headless = True
browser = webdriver.Chrome(options=options)


def navigate_to_part(base_page_url, level_3_id, level_4_id=None, level_3_frame="etaindex"):
    browser.get(base_page_url)

    browser.switch_to.frame("vadd")
    browser.switch_to.frame(level_3_frame)
    Select(browser.find_element_by_name("TT3")).select_by_visible_text(str(level_3_id))
    browser.switch_to.default_content()

    if level_4_id != None:
        browser.switch_to.frame("vadd")
        browser.switch_to.frame("etaindexb")
        Select(browser.find_element_by_name("TT4")).select_by_visible_text(str(level_4_id))
        browser.switch_to.default_content()

    browser.switch_to.frame("vadd")
    browser.switch_to.frame("etaindexb")
    browser.find_element_by_name("TTForm").submit()
    browser.switch_to.default_content()

def get_text(elements_xpath="//span[@id='iovpla16' or @id='iovmla16']"):
    browser.switch_to.default_content()
    browser.switch_to.frame("etatext")
    text_elements = browser.find_elements_by_xpath(elements_xpath)
    assert len(text_elements) > 0
    # logging.info(text_elements)
    sentences = [element.text for element in text_elements]
    # logging.info(sentences)
    return sentences
