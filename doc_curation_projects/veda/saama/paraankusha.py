import logging
import os
import sys
import traceback

from selenium.common.exceptions import NoSuchElementException

from doc_curation import book_data
from doc_curation.scraping.misc_sites import parankusha


  

def get_rv():
  pass
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "क्रमपाठः"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/kramapAThaH/saMhitA", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/veda/shakala/saMhitA.json"))
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "पदपाठः"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/padapAThaH/saMhitA", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/veda/shakala/saMhitA.json"))
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "ब्राह्मणम्"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/brAhmaNam", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/veda/shakala/brAhmaNam.json"))
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "आरण्यकम्"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/AraNyakam", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/veda/shakala/AraNyakam.json"))


def get_kauthuma():
  parankusha.click_link_by_text(browser=browser, element_text="ऋग्वेदः")
  parankusha.click_link_by_text(browser=browser, element_text="यजुर्वेदः")
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "संहिता"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/kauthuma/saMhitA", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/veda/kauthuma/saMhitA.json"))
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "छन्दःपदम्"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/kauthuma/ChandaHpadam", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/veda/kauthuma/ChandaHpadam.json"))
  parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "स्तोभपदम्"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/kauthuma/stobhapadam", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/veda/kauthuma/stobhapadam.json"))
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "रहस्यगानम्"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/kauthuma/rahasyagAnam", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/veda/kauthuma/rahasyagAnam.json"))


def get_misc(browser):
  pass
  for i in [3,5,7,9]:
    parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "expand:विद्यास्थानानि", "वेदाः", f"expand:वैदिक-पादानुक्रम-कोशः-{i}", f"{i}.1"], outdir=f"/home/vvasuki/gitland/sanskrit/raw_etexts/koshaH/indic-dict/kAvya/vaidika-padAnukrama-koshaH/mUla/0{i}")
    # Reset.
    parankusha.browse_nodes(browser=browser, start_nodes=["विद्यास्थानानि"])
  


if __name__ == '__main__':
  browser = parankusha.get_logged_in_browser(headless=False)
  # get_taittiriiya(browser=browser)
  get_misc(browser=browser)
  # get_rv()
  # get_kauthuma()
  # browser.implicitly_wait(13)
  browser.close()
