import logging
import os
import sys
import traceback

from selenium.common.exceptions import NoSuchElementException

from doc_curation import parankusha, text_data


def get_text(browser, text_id, base_dir, unit_info_file):
    parankusha.click_link_by_text(browser=browser, element_text=text_id)
    unit_data = text_data.get_subunit_data(unit_info_file, [])
    
    for subunit_path in text_data.get_subunit_path_list(json_file=unit_info_file, unit_path_list=[]):
        try:
            for (subunit, unitNameInSite) in zip(subunit_path, unit_data["unitNameListInSite"]):
                element_text = "%s%d" % (unitNameInSite, subunit)
                parankusha.click_link_by_text(browser=browser, element_text=element_text)
        except NoSuchElementException as e:
            logging.warning("Skipping as Could not find element " + str(traceback.format_exc()))
            continue
        logging.info(list(zip(unit_data["unitNameListInSite"], subunit_path)))
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
        element_text = "%s%d" % (unit_data["unitNameListInSite"][0], subunit_path[0])
        parankusha.click_link_by_text(browser=browser, element_text=element_text)


def get_taittiriiya():
    parankusha.click_link_by_text(browser=browser, element_text="ऋग्वेदः")
    parankusha.click_link_by_text(browser=browser, element_text="शुक्लयजुर्वेदः")
    # get_text(browser=browser, text_id="संहितायाः भट्टभास्करभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/bhaTTa-bhAskara/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/saMhitA.json"))
    # get_text(browser=browser, text_id="संहितायाः सायणभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/sAyaNa/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/saMhitA.json"))
    # get_text(browser=browser, text_id="संहिता", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/saMhitA.json"))
    # get_text(browser=browser, text_id="ब्राह्मणम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/brAhmaNam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/brAhmaNa.json"))
    # get_text(browser=browser, text_id="आरण्यकम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/AraNyakam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/AraNyaka.json"))
    # get_text(browser=browser, text_id="काठकम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/mUlam/kAThakam", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/mUlam/kAThaka.json"))
    

if __name__ == '__main__':
    browser = parankusha.get_logged_in_browser(headless=False)
    get_taittiriiya()
    # browser.implicitly_wait(13)
    browser.close()
