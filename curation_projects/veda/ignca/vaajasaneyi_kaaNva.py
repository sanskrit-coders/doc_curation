import logging
import os

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome import options
from selenium.webdriver.remote.remote_connection import LOGGER

from doc_curation import text_data
from doc_curation.md_helper import MdFile
from indic_transliteration import sanscript

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


def dump_text(base_dir):
    unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "vedaH/vAjasaneyi/samhitA.json")

    for kaanda_index in text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[]):
        logging.info("adhyAya %d", kaanda_index)

        outfile_path = os.path.join(base_dir, "%02d.md" % (kaanda_index))
        if os.path.exists(outfile_path):
            logging.info("Skipping " + outfile_path)
            continue

        url = "http://vedicheritage.gov.in/samhitas/yajurveda/shukla-yajurveda/vajasaneyi-kanva-samhita-chapter-%02d/" % (kaanda_index)
        logging.info("url %s to %s", url, outfile_path)
        browser.get(url=url)
        try:
            text = browser.find_element_by_id("videotext").text
            text = text.replace("\n", "  \n")
            title = "%02d" % kaanda_index
            title = sanscript.transliterate(title, sanscript.HK, sanscript.DEVANAGARI)
            md_file = MdFile(file_path=outfile_path)
            md_file.dump_to_file(metadata={"title": title}, md=text, dry_run=False)
        except NoSuchElementException:
            logging.warning("Page missing! %s ", url)


if __name__ == '__main__':
    dump_text(base_dir="/home/vvasuki/sanskrit/raw_etexts/vedaH/yajur/vAjasaneyi/kANvam/saMhitA/")
    browser.close()
    pass
