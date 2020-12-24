import logging
import os

from selenium import webdriver
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
    unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "vedaH/shaunaka/samhitA.json")

    for kaanda_index in text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[]):
        subunit_list = text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[kaanda_index])
        for subunit_index in subunit_list:
            logging.info("kaanDa %d adhyaaya %d", kaanda_index, subunit_index)

            outfile_path = os.path.join(base_dir, "%02d" % (kaanda_index), "%03d.md" % subunit_index)
            if os.path.exists(outfile_path):
                logging.info("Skipping " + outfile_path)
                continue

            url = "http://vedicheritage.gov.in/samhitas/atharvaveda-samhitas/shaunaka-samhita/kanda-%02d-sukta-%03d/" % (kaanda_index, subunit_index)
            logging.info("url %s to %s", url, outfile_path)
            browser.get(url=url)
            text = browser.find_element_by_id("videotext").text
            text = text.replace("\n", "  \n")
            title_tags = browser.find_elements_by_css_selector("#videotext  strong")
            title = "%03d" % subunit_index
            if len(title_tags) > 0:
                title = "%03d %s" % (subunit_index, title_tags[0].text)
            title = sanscript.transliterate(title, sanscript.HK, sanscript.DEVANAGARI)
            md_file = MdFile(file_path=outfile_path)
            md_file.dump_to_file(metadata={"title": title}, md=text, dry_run=False)


if __name__ == '__main__':
    dump_text(base_dir="/home/vvasuki/sanskrit/raw_etexts/vedaH/atharva/shaunaka/saMhitA_VH")
    browser.close()
    pass
