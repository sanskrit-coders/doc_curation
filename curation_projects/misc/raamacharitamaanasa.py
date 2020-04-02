import logging
import os

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome import options
from selenium.webdriver.remote.remote_connection import LOGGER

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

opts = options.Options()
opts.headless = False
browser = webdriver.Chrome(options=opts)
browser.implicitly_wait(6)


def dump_page(outfile_path):
    logging.info(browser.current_url)
    text_element = browser.find_element_by_css_selector("div.mangal_text")
    os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
    with open(outfile_path, "a") as outfile:
        outfile.writelines(text_element.text)
    try:
        next_link_element = browser.find_element_by_css_selector('[src="../image/next.gif"]')
        next_link_element.click()
        dump_page(outfile_path=outfile_path)
    except NoSuchElementException:
        logging.info("Reached end of series.")


def get_kaanda(init_page, outfile_path):
    browser.get(init_page)
    dump_page(outfile_path=outfile_path)
    

if __name__ == '__main__':
    # get_kaanda("http://www.pareekjagran.com/ramayan/balkand-1.asp", outfile_path="/home/vvasuki/sanskrit/raw_etexts/purANa/rAmacharitamAnasa/01_bAlakANDa.md")
    get_kaanda("http://www.pareekjagran.com/ramayan/ayodhyakand-1.asp", outfile_path="/home/vvasuki/sanskrit/raw_etexts/purANa/rAmacharitamAnasa/02_ayodhyAkANDa.md")
    get_kaanda("http://www.pareekjagran.com/ramayan/aranykand-1.asp", outfile_path="/home/vvasuki/sanskrit/raw_etexts/purANa/rAmacharitamAnasa/03_araNyakANDa.md")
    get_kaanda("http://www.pareekjagran.com/ramayan/kishkindhakand-1.asp", outfile_path="/home/vvasuki/sanskrit/raw_etexts/purANa/rAmacharitamAnasa/04_kiShkindhAkANDa.md")
    get_kaanda("http://www.pareekjagran.com/ramayan/sundarkand-1.asp", outfile_path="/home/vvasuki/sanskrit/raw_etexts/purANa/rAmacharitamAnasa/05_sundarakANDa.md")
    get_kaanda("http://www.pareekjagran.com/ramayan/lankakand-1.asp", outfile_path="/home/vvasuki/sanskrit/raw_etexts/purANa/rAmacharitamAnasa/06_lankAkANDa.md")
    get_kaanda("http://www.pareekjagran.com/ramayan/uttarkand-1.asp", outfile_path="/home/vvasuki/sanskrit/raw_etexts/purANa/rAmacharitamAnasa/07_uttarakANDa.md")
