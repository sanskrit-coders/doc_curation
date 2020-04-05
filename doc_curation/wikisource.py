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
browser.implicitly_wait(6)


def get_item_url(id, url_base, url_id_padding):
    import urllib.parse
    dashaka_id = "%s_%s" % (url_base, sanscript.transliterate(url_id_padding % id, sanscript.SLP1, sanscript.DEVANAGARI))
    logging.info(dashaka_id)
    item_url = "https://sa.wikisource.org/wiki/" + urllib.parse.quote(dashaka_id)
    return item_url


def dump_item(title, item_url, outfile_path):
    if os.path.exists(outfile_path):
        logging.info("skipping: %s - it exists already", outfile_path)
        return
    logging.info(item_url)
    browser.get(item_url)
    text = ""
    try:
        text = browser.find_element_by_css_selector("div.poem").text
    except NoSuchElementException:
        content_element = browser.find_element_by_css_selector(".mw-parser-output")
        para_elements = content_element.find_elements_by_tag_name("p")
        text = "\n\n".join(map(lambda x : x.text, para_elements))
    os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
    with open(outfile_path, "w") as outfile:
        outfile.writelines(text.replace("\n", "  \n"))
    md_file = md_helper.MdFile(file_path=outfile_path)
    md_file.set_title(title=title, dry_run=False)


def dump_text(url_base, num_parts, dir_path, url_id_padding="%d"):
    for id in range(1, num_parts+1):
        outfile_path = os.path.join(dir_path, "%03d.md" % id)
        title = sanscript.transliterate("%03d" % id, sanscript.SLP1, sanscript.DEVANAGARI)
        item_url = get_item_url(id=id, url_id_padding=url_id_padding, url_base=url_base)
        dump_item(title=title, outfile_path=outfile_path, item_url=item_url)
