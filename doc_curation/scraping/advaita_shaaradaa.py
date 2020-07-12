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


# To construct urls like https://advaitasharada.sringeri.net/display/bhashya/Aitareya
shankara_bhaashyas = ["Isha", "Kena_pada", "Kena_vakya", "Kathaka", "Prashna", "Mundaka", "Mandukya", "Taitiriya", "Aitareya",  "Chandogya", "Brha", "Gita", "BS"]

# To construct urls like https://advaitasharada.sringeri.net/display/moola/Prashna
muulas = shankara_bhaashyas
muulas.extend(["jbl", "jbl", "svt", "kst"])

# To construct urls like https://advaitasharada.sringeri.net/display/bhashyaVyakhya/BS?vyakhya=VN
aanandagiri_bhaashyavyaakhya_texts = ["Isha", "Kena_pada", "Kena_vakya", "Kathaka", "Prashna", "Mundaka", "Mandukya", "Taitiriya", "Aitareya",  "Chandogya", "Brha", "Gita"]

bhaashyavyaakhyas = {
    "BS": ["VN", "RP", "PP", "BM", "NY"],
    "panchapadika": ["VK"], 
    "Taitiriya": ["TV", "TVN"]
}

for text in aanandagiri_bhaashyavyaakhya_texts:
    current_vyaakhyas = bhaashyavyaakhyas.get(text, [])
    current_vyaakhyas.append("AA")
    bhaashyavyaakhyas[text] = current_vyaakhyas

# To construct urls like https://advaitasharada.sringeri.net/display/prakarana/shatashloki
prakarana_texts = ["vivekachudamani", "shrutisarasamuddharanam", "shatashloki", "sarvavedantasiddhantasarasangraha", "hastamalakiya-bhashya", "hastamalakiyam", "vedantaparibhasha", "vedantasara", "advaitasiddhi", "shastra-siddanthalesha-sangraha"]

def get_text(url):
    browser.get(url=url)
    chapter_links = browser.find_element_by_css_selector(css_selector=".sidebar li:not(.special) a")
    for chapter_link in chapter_links:
        chapter_link.click()
    
    title_div = browser.find_element_by_css_selector("div.col-md-7")
    chapter_divs = browser.find_elements_by_css_selector("div.chapter")
    