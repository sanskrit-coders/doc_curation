import json
import logging
import os
import time
import traceback

from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

import doc_curation
from doc_curation import book_data
from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement
from doc_curation.scraping.html_scraper import selenium
from doc_curation.scraping.html_scraper.selenium import click_link_by_text
from indic_transliteration import sanscript
from selenium.common.exceptions import NoSuchElementException

from curation_utils import scraping, file_helper
from selenium.webdriver.support.ui import WebDriverWait

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

# doc_curation.init_configuration()
configuration_parankusha = doc_curation.configuration['parankusha']


def get_logged_in_browser(headless=True):
  """Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen """
  browser = scraping.get_selenium_chrome(headless=headless)
  browser.get("http://parankusan.cloudapp.net/Integrated/Texts.aspx")
  username = browser.find_element(By.ID, "txtUserName")
  username.send_keys(configuration_parankusha["user"])
  browser.find_element(By.ID, "btnNext").click()
  time.sleep(3)
  browser.find_element(By.ID, "txtPassword").send_keys(configuration_parankusha["pass"])
  browser.find_element(By.ID, "btnLogin").click()
  browser.get("http://parankusan.cloudapp.net/Integrated/Texts.aspx")
  # TODO: deal with the inferior transliteration due to the below - esp in mixed devanAgarI/ tamiL context.
  # dropdown = browser.find_element(By.NAME, 'ddlOutputTranslitLang')
  # Select(dropdown).select_by_visible_text("Devanagari")
  # time.sleep(3)
  return browser


def expand_tree_by_text(browser, element_text, timeout=5):
  try:
    WebDriverWait(browser, timeout).until(lambda browser: browser.find_elements(By.LINK_TEXT, element_text))
    subunit_element = browser.find_element(By.LINK_TEXT, element_text)
    expansion_element = subunit_element.find_element(By.XPATH, "./..")
    expansion_element = subunit_element.find_element(By.XPATH, "./../preceding-sibling::td")
    expansion_element = subunit_element.find_element(By.XPATH, "./../preceding-sibling::td/descendant::a")
    logging.info("Expanding: %s" % element_text)
    # subunit_element.click()
    # Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen 
    browser.execute_script("arguments[0].click();", expansion_element)
    return True
  except NoSuchElementException:
    logging.warning("Could not find %s", element_text)
    return False


def deduce_text_name(browser, ordinal=None):
  logging.debug(f"Sequence {ordinal}")
  # Gets the link highlighted by red color in the left panel.
  WebDriverWait(browser,5).until(lambda browser: browser.find_elements(By.CSS_SELECTOR, "td>a.tv_0.tv_3"))

  elements = browser.find_elements(By.CSS_SELECTOR, "td>a.tv_0.tv_3")
  # element = browser.find_elements(By.CSS_SELECTOR, "#gvResults tr[valign=\"top\"] td")[-1]

  text_name = elements[-1].text.strip()
  if ordinal is None:
    return text_name
  else:
    return "%02d %s" % (ordinal, text_name)


def get_output_path(text_name, outdir):
  text_name_transliterated = sanscript.transliterate(data=text_name, _from=sanscript.DEVANAGARI,
                                                     _to=sanscript.OPTITRANS)
  return os.path.join(outdir, file_helper.clean_file_path(text_name_transliterated) + ".md")



def dump_to_file(browser, out_file_path, has_comment=False, text_name=None, start_nodes=None, source_script=sanscript.DEVANAGARI):
  if start_nodes is not None:
    browse_nodes(browser=browser, start_nodes=start_nodes)
  if text_name is None:
    text_name = sanscript.transliterate(data=os.path.basename(out_file_path.replace(".md", "")), _from=sanscript.OPTITRANS,
                            _to=sanscript.DEVANAGARI)
  rows = browser.find_elements(By.CSS_SELECTOR, "#gvResults tr[valign=\"top\"]")
  text = ""
  for row in rows:
    tds = row.find_elements(By.CSS_SELECTOR, "td")
    for td in tds:
      spans = td.find_elements(By.CSS_SELECTOR, "span")
      if len(spans) > 0:
        text_segments = [span.text.strip().replace("\\n", "\n").replace("\n", "  \n") for span in spans]
        main_text = "\n\n".join(text_segments)
        if has_comment:
          commentary_main = False
          if not commentary_main:
            text += f"\n\n<details open><summary>मूलम्</summary>\n\n{main_text}\n</details>\n\n"
            comment_tds = td.find_elements(By.XPATH, './/following-sibling::*')
            for comment_td in comment_tds:
              comment_text = comment_td.text.strip()
              if comment_text != "":
                text += f"\n\n<details><summary>टीका</summary>\n\n{comment_text}\n</details>\n\n"
          else:
            comment_tds = td.find_elements(By.XPATH, './/following-sibling::*')
            for comment_td in comment_tds:
              text += f"\n\n<details open><summary>मूलम्</summary>\n\n{comment_td.text.strip()}\n</details>\n\n"
            text += f"\n\n<details><summary>टीका</summary>\n\n{main_text}\n</details>\n\n"
        else:
          text += f"{main_text}\n\n"
  if source_script != sanscript.DEVANAGARI:
    text = content_processor.transliterate(text=text, source_script=source_script)
  md_file = MdFile(file_path=out_file_path)
  md_file.dump_to_file(metadata={"title": text_name}, content=text, dry_run=False)


def browse_nodes(browser, start_nodes, timeout=10):
  # We don't "expand all" to avoid confusion among nodes with identical names.
  for node in start_nodes:
    if node.startswith("expand:"):
      click_link_by_text(browser=browser, element_text=node.replace("expand:", ""), ordinal=0, timeout=timeout)
      expand_tree_by_text(browser=browser, element_text=node.replace("expand:", ""), timeout=timeout)
    else:
      click_link_by_text(browser=browser, element_text=node, ordinal=0, timeout=timeout)


def get_texts(browser, outdir, start_nodes, ordinal_start=1, has_comment=False, source_script=sanscript.DEVANAGARI):
  def _dump_text(browser, outdir, ordinal=None, has_comment=False, start_nodes=None):
    text_name = deduce_text_name(browser, ordinal)
    out_file_path = get_output_path(text_name=text_name, outdir=outdir)
    dump_to_file(browser=browser, has_comment=has_comment, out_file_path=out_file_path, text_name=text_name, start_nodes=start_nodes, source_script=source_script)

  browse_nodes(browser=browser, start_nodes=start_nodes)

  os.makedirs(name=outdir, exist_ok=True)
  ordinal = ordinal_start
  _dump_text(browser=browser, outdir=outdir, ordinal=ordinal, has_comment=has_comment)
  while click_link_by_text(browser=browser, element_text="Next"):
    if ordinal is not None:
      ordinal = ordinal + 1
    _dump_text(browser=browser, outdir=outdir, ordinal=ordinal, has_comment=has_comment)
  arrangement.fix_index_files(dir_path=outdir, overwrite=False, dry_run=False)


def get_structured_text(browser, start_nodes, base_dir, unit_info_file, has_comment=False, source_script=sanscript.DEVANAGARI):
  def open_path(subunit_path, unit_data):
    logging.debug(list(zip(subunit_path, unit_data["unitNameListInSite"])))
    for (subunit, unitNameInSite) in zip(subunit_path, unit_data["unitNameListInSite"]):
      element_text = "%s%d" % (unitNameInSite, subunit)
      click_link_by_text(browser=browser, element_text=element_text)

  def close_path(subunit_path, unit_data):
    logging.info(list(zip(reversed(subunit_path), reversed(unit_data["unitNameListInSite"]))))
    for (subunit, unitNameInSite) in list(zip(reversed(subunit_path), reversed(unit_data["unitNameListInSite"]))):
      element_text = "%s%d" % (unitNameInSite, subunit)
      logging.info(element_text)
      click_link_by_text(browser=browser, element_text=element_text)

  browse_nodes(browser=browser, start_nodes=start_nodes)
  os.makedirs(name=base_dir, exist_ok=True)
  unit_data = book_data.get_subunit_data(unit_info_file, [])

  for subunit_path in book_data.get_subunit_path_list(file_path=unit_info_file, unit_path_list=[]):
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
      os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
      text_name = deduce_text_name(browser)
      dump_to_file(browser=browser, has_comment=has_comment, out_file_path=outfile_path, text_name=text_name, start_nodes=None, source_script=source_script)
    # Close the kANDa - else the driver may pick sarga from this kANDa when it is to pick the sarga from the next kANDa?!
    close_path(subunit_path=subunit_path, unit_data=unit_data)
  library.fix_index_files(dir_path=base_dir)
