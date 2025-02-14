import json
import logging
import os

from selenium.webdriver.common.by import By

from curation_utils import scraping
from doc_curation import configuration

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_config.json'), 'r') as handle:
    configuration = json.load(handle)

site_configuration = configuration['vedanidhi']


def get_logged_in_browser(headless=True):
    """Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen """
    browser = scraping.get_selenium_chrome(headless=headless)
    browser.get("https://vaakya.vedanidhi.in/login/")
    username = browser.find_element(By.ID, "username")
    username.send_keys(site_configuration["user"])
    browser.find_element(By.ID, "password").send_keys(site_configuration["pass"])
    browser.find_element(By.ID, "submit_button").click()
    browser.get("https://vaakya.vedanidhi.in/browse/?lang=En")
    return browser


