import os

from   selenium import webdriver
from   selenium.common.exceptions import TimeoutException

import json

from doc_curation.text_data import raamaayana

browser = webdriver.Chrome()

configuration = {}
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_config.json'), 'r') as handle:
    configuration = json.load(handle)

configuration_parankusha = configuration['parankusha']
browser.get("http://parankusan.cloudapp.net/Integrated/Texts.aspx")

def login():
    username = browser.find_element_by_id("txtUserName")
    username.send_keys(configuration_parankusha["user"])
    browser.find_element_by_id("btnNext").click()
    browser.find_element_by_id("txtPassword").send_keys(configuration_parankusha["pass"])
    browser.find_element_by_id("btnLogin").click()
    browser.get("http://parankusan.cloudapp.net/Integrated/Texts.aspx")

def get_sarga_text():
    pass

def get_kumbhakona_ramayana_text():
    browser.find_element_by_link_text("वाल्मीकिरामायणम् प्राचीनपाठः").click()
    # browser.implicitly_wait(2)
    for kaanda_index in raamaayana.kaanda_indices[0:1]:
        browser.find_element_by_link_text("Kanda-%d" % kaanda_index).click()
        for sarga_index in raamaayana.get_sarga_list_kumbhakonam(kaanda_index=kaanda_index)[0:1]:
            browser.find_element_by_link_text("Sarga-%d" % sarga_index).click()
            text_spans = browser.find_element_by_id("divResults").find_elements_by_tag_name("span")
            for span in text_spans:
                print(span.text)


if __name__ == '__main__':
    login()
    get_kumbhakona_ramayana_text()
    # browser.close()s