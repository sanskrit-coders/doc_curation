import logging
import os

from doc_curation import book_data
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript
from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.remote.remote_connection import LOGGER

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger

urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


dest_dir_suuktas = "/home/vvasuki/vishvAsa/vedAH/content/atharva/shaunakam/rUDha-saMhitA/sarva-prastutiH"
dest_dir_static = dest_dir_suuktas.replace("/content/", "/static/").replace("sarva-prastutiH", "")
dest_dir_suukta_info = os.path.join(dest_dir_static, "info_vh")
dest_dir_Rks = os.path.join(dest_dir_static, "mUlam")



def dump_text(base_dir):
  opts = options.Options()
  opts.headless = False
  browser = webdriver.Chrome(options=opts)
  browser.implicitly_wait(6)
  unit_info_file = os.path.join(os.path.dirname(book_data.__file__), "vedaH/shaunaka/samhitA.json")

  for kaanda_index in book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[]):
    subunit_list = book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[kaanda_index])
    for subunit_index in subunit_list:
      logging.info("kaanDa %d adhyaaya %d", kaanda_index, subunit_index)

      outfile_path = os.path.join(base_dir, "%02d" % (kaanda_index), "%03d.md" % subunit_index)
      if os.path.exists(outfile_path):
        logging.info("Skipping " + outfile_path)
        continue

      url = "http://vedicheritage.gov.in/samhitas/atharvaveda-samhitas/shaunaka-samhita/kanda-%02d-sukta-%03d/" % (
      kaanda_index, subunit_index)
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
      md_file.dump_to_file(metadata={"title": title}, content=text, dry_run=False)

  browser.close()




