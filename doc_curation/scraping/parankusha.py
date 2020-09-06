import json
import logging
import os

from indic_transliteration import sanscript
from selenium.common.exceptions import NoSuchElementException

from curation_utils import scraping, file_helper
from doc_curation import md_helper

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


configuration = {}
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_config.json'), 'r') as handle:
    configuration = json.load(handle)

configuration_parankusha = configuration['parankusha']


def get_logged_in_browser(headless=True):
    """Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen """
    browser = scraping.get_selenium_browser(headless=headless)
    browser.get("http://parankusan.cloudapp.net/Integrated/Texts.aspx")
    username = browser.find_element_by_id("txtUserName")
    username.send_keys(configuration_parankusha["user"])
    browser.find_element_by_id("btnNext").click()
    browser.find_element_by_id("txtPassword").send_keys(configuration_parankusha["pass"])
    browser.find_element_by_id("btnLogin").click()
    browser.get("http://parankusan.cloudapp.net/Integrated/Texts.aspx")
    return browser


def click_link_by_text(browser, element_text):
    try:
        subunit_element = browser.find_element_by_link_text(element_text)
        logging.info("Clicking: %s" % element_text)
        # subunit_element.click()
        # Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen 
        browser.execute_script("arguments[0].click();", subunit_element)
        return True
    except NoSuchElementException:
        logging.warning("Could not find %s", element_text)
        return False


def expand_tree_by_text(browser, element_text):
    try:
        subunit_element = browser.find_element_by_link_text(element_text)
        expansion_element = subunit_element.find_element_by_xpath(xpath="./..")
        expansion_element = subunit_element.find_element_by_xpath(xpath="./../preceding-sibling::td")
        expansion_element = subunit_element.find_element_by_xpath(xpath="./../preceding-sibling::td/descendant::a")
        logging.info("Expanding: %s" % element_text)
        # subunit_element.click()
        # Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen 
        browser.execute_script("arguments[0].click();", expansion_element)
        return True
    except NoSuchElementException:
        logging.warning("Could not find %s", element_text)
        return False


def deduce_text_name(browser):
    element = browser.find_elements_by_css_selector("#gvResults tr[valign=\"top\"] td")[-1]
    return element.text.strip()


def get_output_path(text_name, outdir):
    text_name_transliterated = sanscript.transliterate(data=text_name, _from=sanscript.DEVANAGARI, _to=sanscript.OPTITRANS)
    return os.path.join(outdir, file_helper.clean_file_path(text_name_transliterated)  + ".md")


def dump_text(browser, outdir):
    text_name = deduce_text_name(browser)
    out_file_path = get_output_path(text_name=text_name, outdir=outdir)
    text_spans = browser.find_elements_by_css_selector("#gvResults tr[valign=\"top\"] td span")
    text_segments = [span.text.strip().replace("\n", "  \n") for span in text_spans]
    text = "\n\n".join(text_segments)
    md_file = md_helper.MdFile(file_path=out_file_path)
    md_file.dump_to_file(metadata={"title": text_name}, md=text, dry_run=False)


def get_texts(browser, outdir, start_nodes):
    for node in start_nodes:
        if node.startswith("expand:"):
            expand_tree_by_text(browser=browser, element_text=node.replace("expand:", ""))
        else:
            click_link_by_text(browser=browser, element_text=node)
    os.makedirs(name=outdir, exist_ok=True)
    dump_text(browser=browser, outdir=outdir)
    while click_link_by_text(browser=browser, element_text="Next"):
        dump_text(browser=browser, outdir=outdir)
