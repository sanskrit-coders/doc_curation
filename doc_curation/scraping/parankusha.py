import json
import logging
import os

from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.remote.remote_connection import LOGGER

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


configuration = {}
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_config.json'), 'r') as handle:
    configuration = json.load(handle)

configuration_parankusha = configuration['parankusha']

def get_logged_in_browser(headless=True):
    """Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen """
    opts = options.Options()
    opts.headless = headless
    browser = webdriver.Chrome(options=opts)
    
    browser.get("http://parankusan.cloudapp.net/Integrated/Texts.aspx")
    username = browser.find_element_by_id("txtUserName")
    username.send_keys(configuration_parankusha["user"])
    browser.find_element_by_id("btnNext").click()
    browser.find_element_by_id("txtPassword").send_keys(configuration_parankusha["pass"])
    browser.find_element_by_id("btnLogin").click()
    browser.get("http://parankusan.cloudapp.net/Integrated/Texts.aspx")
    return browser

def click_link_by_text(browser, element_text):
    subunit_element = browser.find_element_by_link_text(element_text)
    logging.info("Clicking: %s" % element_text)
    # subunit_element.click()
    # Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen 
    browser.execute_script("arguments[0].click();", subunit_element)
    