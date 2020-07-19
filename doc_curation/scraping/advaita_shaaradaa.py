import codecs
import logging
import os

import pypandoc
import regex
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.remote_connection import LOGGER
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.support.wait import WebDriverWait

from curation_utils import scraping

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


browser = scraping.get_selenium_browser(headless=False)


urls = []
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
    chapter_links = browser.find_elements_by_css_selector(css_selector="ul#sidebar > li:not(.special) > a")
    for chapter_link in chapter_links:
        target = chapter_link.get_attribute("href").replace(url, "").replace("/", "")
        if chapter_link.text.strip() == "" or target == "#":
            continue
        logging.debug("Clicking %s, waiting for %s", chapter_link.text, target)
        chapter_link.click()
        element = WebDriverWait(browser, 20).until(
            presence_of_element_located((By.CSS_SELECTOR, target))
        )
    
    title_divs = browser.find_elements_by_css_selector("div.col-md-7")
    chapter_divs = browser.find_elements_by_css_selector("div.chapter")
    text_md = ""
    if len(title_divs + chapter_divs) == 0:
        return None
    for chapter_div in title_divs + chapter_divs:
        chapter_html = chapter_div.get_attribute('innerHTML')
        chapter_html = regex.sub("<(a|span)[^>]+>|</(a|span)>", "", chapter_html)
        chapter_html = regex.sub("<div[^>]+>", "<p>", chapter_html)
        chapter_html = regex.sub("</div[^>]+>", "</p>", chapter_html)
        chapter_md = pypandoc.convert_text(source=chapter_html, to="gfm", format='html', extra_args=['--atx-headers'])
        text_md = "%s\n\n%s" % (text_md, chapter_md)
    return text_md


def dump_text(url, dest_path):
    if os.path.exists(dest_path):
        logging.warning("Skipping %s", dest_path)
        return
    logging.info("Dumping %s to %s", url, dest_path)
    md = get_text(url)
    if md is None:
        logging.warning("No content. Skipping %s.", url)
        return 
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with codecs.open(dest_path, "w", 'utf-8') as file_out:
        file_out.write(md)


def dump_texts(dest_dir):
    for item in muulas:
        url = "https://advaitasharada.sringeri.net/display/moola/%s" % item
        dump_text(url=url, dest_path=os.path.join(dest_dir, "mUla", item + ".md"))
    for item in shankara_bhaashyas:
        url = "https://advaitasharada.sringeri.net/display/bhashya/%s" % item
        dump_text(url=url, dest_path=os.path.join(dest_dir, "bhAShya", item + ".md"))
    for item in prakarana_texts:
        url = "https://advaitasharada.sringeri.net/display/prakarana/%s" % item
        dump_text(url=url, dest_path=os.path.join(dest_dir, "prakaraNa", item + ".md"))
    for text in bhaashyavyaakhyas:
        for vyaakhyaa in bhaashyavyaakhyas[text]:
            url = "https://advaitasharada.sringeri.net/display/bhashyaVyakhya/%s?vyakhya=%s" % (text, vyaakhyaa)
            dump_text(url=url, dest_path=os.path.join(dest_dir, "bhaShya_vyAkhyA", text, vyaakhyaa + ".md"))