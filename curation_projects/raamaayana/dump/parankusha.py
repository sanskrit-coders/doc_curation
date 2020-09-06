import logging
import os

from doc_curation.scraping import parankusha
from doc_curation import text_data


def get_ramayana_text(browser, text_id, base_dir):
    browser.find_element_by_link_text(text_id).click()
    # browser.implicitly_wait(2)
    unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "raamaayana/andhra.json")
    if text_id == "रामायणम्-नव्यपाठः":
        unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "raamaayana/baroda.json")
    else:
        unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "raamaayana/kumbhakonam.json")

    for kaanda_index in text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[]):
        kaanda_element = browser.find_element_by_link_text("Kanda-%d" % kaanda_index)
        # kaanda_element.click()
        # Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen 
        browser.execute_script("arguments[0].click();", kaanda_element)
        sarga_list = text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[kaanda_index])

        for sarga_index in sarga_list:
            logging.info("Kanda %d Sarga %d", kaanda_index, sarga_index)
            outfile_path = os.path.join(base_dir, str(kaanda_index), "%03d" % sarga_index + ".md")
            if os.path.exists(outfile_path):
                logging.info("Skipping " + outfile_path)
                continue
            browser.find_element_by_link_text("Sarga-%d" % sarga_index).click()
            text_spans = browser.find_element_by_id("divResults").find_elements_by_tag_name("span")
            lines = ["\n", "\n"]
            for span in text_spans:
                shloka = span.text
                shloka = shloka.replace("। ", "।  \n")
                shloka = shloka.replace("।।", " ॥ ")
                lines.append(shloka + "  \n")
            os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
            with open(outfile_path, "w") as outfile:
                outfile.writelines(lines)
        # Close the kANDa - else the driver may pick sarga from this kANDa when it is to pick the sarga from the next kANDa?!
        browser.find_element_by_link_text("Kanda-%d" % kaanda_index).click()


if __name__ == '__main__':
    browser = parankusha.get_logged_in_browser(headless=False)
    get_ramayana_text(browser=browser, text_id="वाल्मीकिरामायणम् प्राचीनपाठः", base_dir="/home/vvasuki/sanskrit/raw_etexts/purANa/rAmAyaNam/kumbhakona")
    # get_ramayana_text(text_id="रामायणम्-नव्यपाठः", base_dir="/home/vvasuki/sanskrit/raw_etexts/purANa/rAmAyaNam/baroda")
    # with open("/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padya/purANa/rAmAyaNa/baroda.md", "a") as outfile:
    #     get_ramayana_text(text_id="रामायणम्-नव्यपाठः", outfile=outfile)
    browser.close()
