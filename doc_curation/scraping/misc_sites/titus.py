import logging, regex

from selenium.webdriver.common.by import By

from doc_curation.scraping.html_scraper import selenium as selenium_scraper
from selenium.webdriver.support.select import Select
from urllib3.connectionpool import log as urllibLogger

urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")



def navigate_to_part(base_page_url, level_3_id, level_4_id=None, level_3_frame="etaindex"):
  browser = selenium_scraper.get_browser()
  browser.get(base_page_url)

  browser.switch_to.frame("vadd")
  browser.switch_to.frame(level_3_frame)
  Select(browser.find_element(By.NAME, "TT3")).select_by_visible_text(str(level_3_id))
  browser.switch_to.default_content()

  if level_4_id != None:
    browser.switch_to.frame("vadd")
    browser.switch_to.frame("etaindexb")
    Select(browser.find_element(By.NAME, "TT4")).select_by_visible_text(str(level_4_id))
    browser.switch_to.default_content()

  browser.switch_to.frame("vadd")
  browser.switch_to.frame("etaindexb")
  browser.find_element(By.NAME, "TTForm").submit()
  browser.switch_to.default_content()


def get_text(text_css="span#iovpla16, span#iovmla16", part_css="span#h5, span#h6"):
  browser = selenium_scraper.get_browser()
  browser.switch_to.default_content()
  browser.switch_to.frame("etatext")
  soup = selenium_scraper.get_soup(browser=browser)

  text_elements = soup.select(f"{text_css}, {part_css}")
  assert len(text_elements) > 0
  # logging.info(text_elements)
  lines = []
  for element in text_elements:
    if element.attrs["id"] == "h4":
      text = regex.sub(".+: ", "# ", element.text)
    elif element.attrs["id"] == "h5":
      text = regex.sub(".+: ", "## ", element.text)
    elif element.attrs["id"] == "h6":
      text = regex.sub(".+: ", "### ", element.text)
    else:
      text = element.text + "॥"
    lines.append(text.strip())
  # logging.info(sentences)
  return lines
