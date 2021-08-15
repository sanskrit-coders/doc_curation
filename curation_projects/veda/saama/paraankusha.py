import logging
import os
import sys
import traceback

from selenium.common.exceptions import NoSuchElementException

from doc_curation import text_data, md_helper
from doc_curation.scraping import parankusha


def get_taittiriiya(browser):
    # parankusha.click_link_by_text(browser=browser, element_text="मूलपाठः")
    # get_text(browser=browser, text_id="पदपाठः", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/padapAThaH/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/saMhitA.json"))
    # get_text(browser=browser, text_id="क्रमपाठः", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/kramapAThaH/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/saMhitA.json"))
    # get_text(browser=browser, text_id="संहितायाः भट्टभास्करभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/bhaTTa-bhAskara/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/saMhitA.json"))
    # get_text(browser=browser, text_id="संहितायाः सायणभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/sAyaNa/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/saMhitA.json"))
    # get_text(browser=browser, text_id="संहिता", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/saMhitA.json"))

    parankusha.get_structured_text(browser=browser, start_nodes=["विद्यास्थानानि", "वेदाः", "यजुर्वेदः", "कृष्णयजुर्वेदः", "भाष्यम्", "भट्टभास्करभाष्यम्",  "ब्राह्मणस्य भट्टभास्करभाष्यम्", "expand:ब्राह्मणस्य भट्टभास्करभाष्यम्"], base_dir="/home/vvasuki/vvasuki-git/saMskAra/content/sangrahaH/taittirIyA/brAhmaNam/bhaTTa-bhAskara-bhAShyam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "vedaH/taittirIya/bhAShya/bhaTTa-bhAskara/brAhmaNa.json"))

    # get_text(browser=browser, text_id="ब्राह्मणम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/brAhmaNam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/brAhmaNa.json"))
    # get_text(browser=browser, text_id="ब्राह्मणस्य सायणभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/sAyaNa/brAhmaNam/", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/brAhmaNa.json"))

    # get_text(browser=browser, text_id="आरण्यकम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/AraNyakam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/AraNyaka.json"))
    # get_text(browser=browser, text_id="आरण्यकस्य भट्टभास्करभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/bhaTTa-bhAskara/AraNyakam/", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/AraNyaka.json"))
    # get_text(browser=browser, text_id="आरण्यकस्य सायणभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/sAyaNa/AraNyakam/", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/AraNyaka.json"))

    # get_text(browser=browser, text_id="काठकम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/kAThakam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/kAThaka.json"))
    # get_text(browser=browser, text_id="काठकस्य भट्टभास्करभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/bhaTTa-bhAskara/kAThakam/", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/kAThaka.json"))
    

# def get_rv():
#     # get_text(browser=browser, text_id="क्रमपाठः", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/kramapAThaH/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/shakala/saMhitA.json"))
#     # get_text(browser=browser, text_id="पदपाठः", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/padapAThaH/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/shakala/saMhitA.json"))
#     # get_text(browser=browser, text_id="ब्राह्मणम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/brAhmaNam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/shakala/brAhmaNam.json"))
#     # get_text(browser=browser, text_id="आरण्यकम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/AraNyakam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/shakala/AraNyakam.json"))
# 
# 
# def get_kauthuma():
#     parankusha.click_link_by_text(browser=browser, element_text="ऋग्वेदः")
#     parankusha.click_link_by_text(browser=browser, element_text="यजुर्वेदः")
#     # get_text(browser=browser, text_id="संहिता", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/kauthuma/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/kauthuma/saMhitA.json"))
#     # get_text(browser=browser, text_id="छन्दःपदम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/kauthuma/ChandaHpadam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/kauthuma/ChandaHpadam.json"))
#     get_text(browser=browser, text_id="स्तोभपदम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/kauthuma/stobhapadam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/kauthuma/stobhapadam.json"))
#     # get_text(browser=browser, text_id="रहस्यगानम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/kauthuma/rahasyagAnam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/kauthuma/rahasyagAnam.json"))



if __name__ == '__main__':
    browser = parankusha.get_logged_in_browser(headless=False)
    get_taittiriiya(browser=browser)
    # get_rv()
    # get_kauthuma()
    # browser.implicitly_wait(13)
    browser.close()
