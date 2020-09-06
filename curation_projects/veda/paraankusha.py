import logging
import os
import sys
import traceback

from selenium.common.exceptions import NoSuchElementException

from doc_curation import text_data
from doc_curation.scraping import parankusha


def open_path(subunit_path, unit_data):
    logging.debug(list(zip(subunit_path, unit_data["unitNameListInSite"])))
    for (subunit, unitNameInSite) in zip(subunit_path, unit_data["unitNameListInSite"]):
        element_text = "%s%d" % (unitNameInSite, subunit)
        parankusha.click_link_by_text(browser=browser, element_text=element_text)


def close_path(subunit_path, unit_data):
    logging.info(list(zip(reversed(subunit_path), reversed(unit_data["unitNameListInSite"]))))
    for (subunit, unitNameInSite) in list(zip(reversed(subunit_path), reversed(unit_data["unitNameListInSite"]))):
        element_text = "%s%d" % (unitNameInSite, subunit)
        logging.info(element_text)
        parankusha.click_link_by_text(browser=browser, element_text=element_text)


def get_text(browser, text_id, base_dir, unit_info_file):
    parankusha.click_link_by_text(browser=browser, element_text=text_id)
    unit_data = text_data.get_subunit_data(unit_info_file, [])
    
    for subunit_path in text_data.get_subunit_path_list(json_file=unit_info_file, unit_path_list=[]):
        try:
            open_path(subunit_path=subunit_path, unit_data=unit_data)
        except NoSuchElementException as e:
            close_path(subunit_path=subunit_path, unit_data=unit_data)
            exit()
            logging.warning("Skipping as Could not find element " + str(traceback.format_exc()))
            continue
        outfile_path = os.path.join(base_dir, "/".join(map(str, subunit_path)) + ".md")
        if os.path.exists(outfile_path):
            logging.info("Skipping " + outfile_path)
        else:
            text_spans = browser.find_element_by_id("divResults").find_elements_by_tag_name("span")
            lines = ["\n", "\n"]
            for span in text_spans:
                lines.append(span.text + "  \n")
            os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
            with open(outfile_path, "w") as outfile:
                outfile.writelines(lines)
        # Close the kANDa - else the driver may pick sarga from this kANDa when it is to pick the sarga from the next kANDa?!
        close_path(subunit_path=subunit_path, unit_data=unit_data)


def get_taittiriiya():
    parankusha.click_link_by_text(browser=browser, element_text="ऋग्वेदः")
    parankusha.click_link_by_text(browser=browser, element_text="शुक्लयजुर्वेदः")
    parankusha.click_link_by_text(browser=browser, element_text="मूलपाठः")
    # get_text(browser=browser, text_id="पदपाठः", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/padapAThaH/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/saMhitA.json"))
    get_text(browser=browser, text_id="क्रमपाठः", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/kramapAThaH/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/saMhitA.json"))
    # get_text(browser=browser, text_id="संहितायाः भट्टभास्करभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/bhaTTa-bhAskara/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/saMhitA.json"))
    # get_text(browser=browser, text_id="संहितायाः सायणभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/sAyaNa/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/saMhitA.json"))
    # get_text(browser=browser, text_id="संहिता", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/saMhitA.json"))

    # get_text(browser=browser, text_id="ब्राह्मणम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/brAhmaNam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/brAhmaNa.json"))
    # get_text(browser=browser, text_id="ब्राह्मणस्य भट्टभास्करभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/bhaTTa-bhAskara/brAhmaNam/", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/brAhmaNa.json"))
    # get_text(browser=browser, text_id="ब्राह्मणस्य सायणभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/sAyaNa/brAhmaNam/", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/brAhmaNa.json"))

    # get_text(browser=browser, text_id="आरण्यकम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/AraNyakam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/AraNyaka.json"))
    # get_text(browser=browser, text_id="आरण्यकस्य भट्टभास्करभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/bhaTTa-bhAskara/AraNyakam/", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/AraNyaka.json"))
    # get_text(browser=browser, text_id="आरण्यकस्य सायणभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/sAyaNa/AraNyakam/", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/AraNyaka.json"))

    # get_text(browser=browser, text_id="काठकम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/kAThakam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/kAThaka.json"))
    # get_text(browser=browser, text_id="काठकस्य भट्टभास्करभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/bhaTTa-bhAskara/kAThakam/", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/kAThaka.json"))
    

def get_rv():
    # get_text(browser=browser, text_id="क्रमपाठः", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/kramapAThaH/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/shakala/saMhitA.json"))
    # get_text(browser=browser, text_id="पदपाठः", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/padapAThaH/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/shakala/saMhitA.json"))
    # get_text(browser=browser, text_id="ब्राह्मणम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/brAhmaNam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/shakala/brAhmaNam.json"))
    get_text(browser=browser, text_id="आरण्यकम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/shakala/AraNyakam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/shakala/AraNyakam.json"))


def get_kauthuma():
    parankusha.click_link_by_text(browser=browser, element_text="ऋग्वेदः")
    parankusha.click_link_by_text(browser=browser, element_text="यजुर्वेदः")
    # get_text(browser=browser, text_id="संहिता", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/kauthuma/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/kauthuma/saMhitA.json"))
    # get_text(browser=browser, text_id="छन्दःपदम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/kauthuma/ChandaHpadam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/kauthuma/ChandaHpadam.json"))
    get_text(browser=browser, text_id="स्तोभपदम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/kauthuma/stobhapadam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/kauthuma/stobhapadam.json"))
    # get_text(browser=browser, text_id="रहस्यगानम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/kauthuma/rahasyagAnam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/kauthuma/rahasyagAnam.json"))



if __name__ == '__main__':
    browser = parankusha.get_logged_in_browser(headless=False)
    # get_taittiriiya()
    # get_rv()
    get_kauthuma()
    # browser.implicitly_wait(13)
    browser.close()
