import logging
import os

from doc_curation import parankusha
from doc_curation.text_data import raamaayana

browser = parankusha.browser

def get_ramayana_text(text_id, base_dir):
    browser.find_element_by_link_text(text_id).click()
    # browser.implicitly_wait(2)
    for kaanda_index in [2, 6, 7]:
        browser.find_element_by_link_text("Kanda-%d" % kaanda_index).click()
        if text_id == "रामायणम्-नव्यपाठः":
            sarga_list = raamaayana.get_sarga_list_baroda(kaanda_index=kaanda_index)
        else:
            sarga_list = raamaayana.get_sarga_list_kumbhakonam(kaanda_index=kaanda_index)

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


if __name__ == '__main__':
    parankusha.login()
    get_ramayana_text(text_id="वाल्मीकिरामायणम् प्राचीनपाठः", base_dir="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padya/purANa/rAmAyaNa/kumbhakona")
    # with open("/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padya/purANa/rAmAyaNa/baroda.md", "a") as outfile:
    #     get_ramayana_text(text_id="रामायणम्-नव्यपाठः", outfile=outfile)
    browser.close()
