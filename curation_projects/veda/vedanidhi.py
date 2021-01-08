import logging
import time

import regex
from selenium.webdriver.support.select import Select

from doc_curation import md_helper
from doc_curation.scraping import vedanidhi, html
from doc_curation.scraping.html import selenium
from indic_transliteration import sanscript


def select_part(browser, veda, shaakhaa, text, division=None, chapter=None, para=None, cluster=None):
  time.sleep(2)
  Select(browser.find_element_by_css_selector("select#vedam")).select_by_visible_text(veda)
  time.sleep(2)
  Select(browser.find_element_by_css_selector("select#shakha")).select_by_visible_text(shaakhaa)
  time.sleep(2)
  Select(browser.find_element_by_css_selector("select#text")).select_by_visible_text(text)
  if division is not None:
    time.sleep(2)
    Select(browser.find_element_by_css_selector("select#division")).select_by_visible_text(division)
  if chapter is not None:
    time.sleep(2)
    Select(browser.find_element_by_css_selector("select#chapter")).select_by_visible_text(chapter)
  if para is not None:
    time.sleep(2)
    Select(browser.find_element_by_css_selector("select#para")).select_by_visible_text(para)
  if cluster is not None:
    Select(browser.find_element_by_css_selector("select#cluster")).select_by_visible_text(cluster)

  browser.find_element_by_css_selector("#browse-data1").click()


def get_page_text(browser):
  rows = browser.find_elements_by_css_selector("table#example tbody tr")
  text_segments = [row.text.strip().replace("\n", "  \n") for row in rows]
  text = "\n\n".join(text_segments)
  text = replace_private_space_characters(text=text)
  return text


def replace_private_space_characters(text):
  text = text.replace("", "꣡").replace("", "꣡꣯").replace("", "꣢").replace("", "꣢꣯").replace("", "꣣").replace("", "꣣꣯").replace("", "꣤").replace("", "꣤꣯").replace("", "꣥").replace("", "꣥꣯").replace("", "꣯")
  # क़ 	ख़ 	ग़ 	ज़ 	ड़ 	ढ़ 	फ़ 	य़
  text = text.replace("ख़", "ऽ᳒२᳒").replace("ग़", "᳐").replace("ढ़", "꣭").replace("ड़", "꣰").replace("ज़", "꣰꣯").replace("य़", "꣪")
  text = text.replace("", "ः").replace("", "ᳲ").replace("", "ऽ").replace("", "ऽऽ").replace("", "ꣳ")
  # अग्नि.मीळे पुरोहितँ- यज्ञस्य देव.मृत्विजम्। होतारं रत्नधातमम्।।  
  # वाय उक्थेभि र्जरन्ते- त्वा.मच्छा जरितारः। सुतसोमाˆ अहर्विदः।
  # वृषा यूथेव वंसग- कृष्टी.रिय.र्त्योजसा। ईशानो अप्रति¤ष्कुतः।।   तुञ्जेतुञ्जे य उत्तरे- स्तोमाˆ इन्द्रस्य हो
  text = text.replace("", "॒").replace("", "᳚").replace("", "॑").replace("", "").replace("", "").replace("", "").replace("", "").replace("¤", "")
  if "ऽ" in text:
    # Convert digits
    text = sanscript.transliterate(text, _from=sanscript.HK, _to=sanscript.DEVANAGARI)
    text = regex.sub("([॒᳚॑꣡꣯꣢꣣꣤꣥᳒᳐])([ःᳲꣳ])", r"\2\1", text)
  return text

def dump_text(browser, title, out_file_path):
  previous_page_text = None
  text = ""
  while True:
    page_text = get_page_text(browser=browser)
    if previous_page_text == page_text:
      break
    logging.debug(page_text)
    text = text + page_text
    time.sleep(2)
    selenium.click_link_by_text(browser=browser, element_text="Next")
    previous_page_text = page_text

  md_file = md_helper.MdFile(file_path=out_file_path)
  md_file.dump_to_file(metadata={"title": title}, md=text, dry_run=False)


if __name__ == '__main__':
  browser = vedanidhi.get_logged_in_browser(headless=False)
  select_part(browser=browser, veda="Samaveda", shaakhaa="कौथुमशाखा", text="प्रकृति, आरण्यकगानम्")
  dump_text(browser=browser, title="प्रकृति, आरण्यकगानम्", out_file_path="/home/vvasuki/sanskrit/raw_etexts/vedaH/sAma/kauthumam/prakRti-araNya-gAnAni.md")