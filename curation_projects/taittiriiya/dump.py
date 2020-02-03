import logging
import os

from doc_curation import parankusha, text_data


def get_text(browser, text_id, base_dir, unit_info_file):
    browser.find_element_by_link_text(text_id).click()
    unit_data = text_data.get_subunit_data(unit_info_file, [])
    
    for subunit_path in text_data.get_subunit_path_list(json_file=unit_info_file, unit_path_list=[]):
        for (subunit, unitNameInSite) in zip(subunit_path, unit_data["unitNameListInSite"]):
            element_text = "%s%d" % (unitNameInSite, subunit)
            logging.info("Clicking: %s" % (element_text))
            subunit_element = browser.find_element_by_link_text(element_text)
            # subunit_element.click()
            # Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen 
            browser.execute_script("arguments[0].click();", subunit_element)
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
        subunit_element = browser.find_element_by_link_text(element_text)
        logging.info("Clicking: %s" % element_text)
        browser.execute_script("arguments[0].click();", subunit_element)


if __name__ == '__main__':
    browser = parankusha.get_logged_in_browser(headless=False)
    # browser.implicitly_wait(13)
    get_text(browser=browser, text_id="संहितायाः भट्टभास्करभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/bhaTTa-bhAskara/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/saMhitA.json"))
    # get_text(browser=browser, text_id="संहितायाः सायणभाष्यम्", base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/taittirIya/sAyaNa/saMhitA", unit_info_file=os.path.join(os.path.dirname(text_data.__file__), "veda/taittirIya/bhAShya/bhaTTa-bhAskara/saMhitA.json"))
    browser.close()
