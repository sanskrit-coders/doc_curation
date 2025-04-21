from doc_curation.md.library import metadata_helper
import logging
import os
import sys
import traceback

from selenium.common.exceptions import NoSuchElementException

from doc_curation import book_data
from doc_curation.scraping.misc_sites import parankusha

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

from doc_curation.scraping.misc_sites import parankusha

def dump(browser):
  pass
  parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "शुक्लयजुर्वेदः-काण्वशाखा", "भाष्यम्",  "शुक्लयजुर्वेदः (माध्यन्दिनशाखा) - महीधरभाष्यम्", "expand:शुक्लयजुर्वेदः (माध्यन्दिनशाखा) - महीधरभाष्यम्"], base_dir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/vAjasaneyam/mAdhyandinam/saMhitA/sarvASh_TIkAH", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/vAjasaneyi/mAdhyandina/samhitA.json"), prev_detail_title="पदपाठः - दयानन्दादि", detail_title="महीधरः")


if __name__ == '__main__':
  browser = parankusha.get_logged_in_browser(headless=False)
  dump(browser=browser)
