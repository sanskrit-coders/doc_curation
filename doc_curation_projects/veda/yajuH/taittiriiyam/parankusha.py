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
  # parankusha.click_link_by_text(browser=browser, element_text="मूलपाठः")
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "पदपाठः"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/padapAThaH/saMhitA", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/mUlam/saMhitA.json"))
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "मन्त्राः", "expand:मन्त्राः"], base_dir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/saMhitA/mUlam/vAkya-kramaH", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/mUlam/saMhitA.json"))
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "क्रमपाठः"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/kramapAThaH/saMhitA", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/mUlam/saMhitA.json"))
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "संहितायाः भट्टभास्करभाष्यम्"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/bhaTTa-bhAskara/saMhitA", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/bhAShya/bhaTTa-bhAskara/saMhitA.json"))
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "भाष्यम्", "expand:भाष्यम्", "सायणभाष्यम्", "संहितायाः सायणभाष्यम्", "expand:संहितायाः सायणभाष्यम्"], base_dir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/saMhitA/sAyaNaH/rA", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/mUlam/saMhitA.json"))
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "संहिता"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/saMhitA", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/mUlam/saMhitA.json"))

  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "यजुर्वेदः", "कृष्णयजुर्वेदः", "भाष्यम्", "भट्टभास्करभाष्यम्",  "ब्राह्मणस्य भट्टभास्करभाष्यम्", "expand:ब्राह्मणस्य भट्टभास्करभाष्यम्"], base_dir="/home/vvasuki/vvasuki-git/saMskAra/content/sangrahaH/taittirIyA/brAhmaNam/bhaTTa-bhAskara-bhAShyam", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/bhAShya/bhaTTa-bhAskara/brAhmaNa.json"))

  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)", "मूलपाठः", "ब्राह्मणम्"], base_dir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/brAhmaNam/mUlam/drAviDam", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/mUlam/brAhmaNa.json"))
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "ब्राह्मणस्य सायणभाष्यम्"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/sAyaNa/brAhmaNam/", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/bhAShya/bhaTTa-bhAskara/brAhmaNa.json"))

  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)", "मूलपाठः", "आरण्यकम्"], base_dir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/AraNyakam/mUlam/drAviDam", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/mUlam/AraNyaka.json"))
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)", "भाष्यम्", "भट्टभास्करभाष्यम्", "आरण्यकस्य भट्टभास्करभाष्यम्", "expand:आरण्यकस्य भट्टभास्करभाष्यम्", "प्रश्नः-1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/AraNyakam/bhaTTa-bhAskara-bhAShyam")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)", "भाष्यम्", "सायणभाष्यम्", "आरण्यकस्य सायणभाष्यम्", "expand:आरण्यकस्य सायणभाष्यम्", "प्रश्नः-1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/AraNyakam/sAyaNa-bhAShyam")
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "आरण्यकस्य सायणभाष्यम्"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/sAyaNa/AraNyakam/", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/bhAShya/bhaTTa-bhAskara/AraNyaka.json"))

  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "काठकम्"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/kAThakam", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/mUlam/kAThaka.json"))
  # parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "कृष्णयजुर्वेदः-तैत्तिरीयशाखा(सारस्वतपाठः)",  "काठकस्य भट्टभास्करभाष्यम्"], base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/bhaTTa-bhAskara/kAThakam/", unit_info_file=os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/bhAShya/bhaTTa-bhAskara/kAThaka.json"))


if __name__ == '__main__':
  browser = parankusha.get_logged_in_browser(headless=False)
  dump(browser=browser)
