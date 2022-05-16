import json
import logging
import os
import traceback

from doc_curation import book_data
from doc_curation.md.file import MdFile
from doc_curation.scraping.html_scraper.selenium import click_link_by_text
from indic_transliteration import sanscript
from selenium.common.exceptions import NoSuchElementException

from curation_utils import scraping, file_helper

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

configuration = {}
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_config.json'), 'r') as handle:
  configuration = json.load(handle)

configuration_parankusha = configuration['parankusha']


def get_logged_in_browser(headless=True):
  """Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen """
  browser = scraping.get_selenium_chrome(headless=headless)
  browser.get("http://parankusan.cloudapp.net/Integrated/Texts.aspx")
  username = browser.find_element_by_id("txtUserName")
  username.send_keys(configuration_parankusha["user"])
  browser.find_element_by_id("btnNext").click()
  browser.find_element_by_id("txtPassword").send_keys(configuration_parankusha["pass"])
  browser.find_element_by_id("btnLogin").click()
  browser.get("http://parankusan.cloudapp.net/Integrated/Texts.aspx")
  return browser


def expand_tree_by_text(browser, element_text):
  try:
    subunit_element = browser.find_element_by_link_text(element_text)
    expansion_element = subunit_element.find_element_by_xpath(xpath="./..")
    expansion_element = subunit_element.find_element_by_xpath(xpath="./../preceding-sibling::td")
    expansion_element = subunit_element.find_element_by_xpath(xpath="./../preceding-sibling::td/descendant::a")
    logging.info("Expanding: %s" % element_text)
    # subunit_element.click()
    # Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen 
    browser.execute_script("arguments[0].click();", expansion_element)
    return True
  except NoSuchElementException:
    logging.warning("Could not find %s", element_text)
    return False


def deduce_text_name(browser, sequence):
  element = browser.find_elements_by_css_selector("td>a.tv_0.tv_3")[-1]
  # element = browser.find_elements_by_css_selector("#gvResults tr[valign=\"top\"] td")[-1]
  return "%02d %s" % (sequence, element.text.strip())


def get_output_path(text_name, outdir):
  text_name_transliterated = sanscript.transliterate(data=text_name, _from=sanscript.DEVANAGARI,
                                                     _to=sanscript.OPTITRANS)
  return os.path.join(outdir, file_helper.clean_file_path(text_name_transliterated) + ".md")


def dump_text(browser, outdir, sequence):
  text_name = deduce_text_name(browser, sequence)
  out_file_path = get_output_path(text_name=text_name, outdir=outdir)
  text_spans = browser.find_elements_by_css_selector("#gvResults tr[valign=\"top\"] td span")
  text_segments = [span.text.strip().replace("\n", "  \n") for span in text_spans]
  text = "\n\n".join(text_segments)
  md_file = MdFile(file_path=out_file_path)
  md_file.dump_to_file(metadata={"title": text_name}, content=text, dry_run=False)


def browse_nodes(browser, start_nodes):
  for node in start_nodes:
    if node.startswith("expand:"):
      expand_tree_by_text(browser=browser, element_text=node.replace("expand:", ""))
    else:
      click_link_by_text(browser=browser, element_text=node)


def get_texts(browser, outdir, start_nodes):
  browse_nodes(browser=browser, start_nodes=start_nodes)
  os.makedirs(name=outdir, exist_ok=True)
  sequence = 1
  dump_text(browser=browser, outdir=outdir, sequence=sequence)
  while click_link_by_text(browser=browser, element_text="Next"):
    sequence = sequence + 1
    dump_text(browser=browser, outdir=outdir, sequence=sequence)


def get_structured_text(browser, start_nodes, base_dir, unit_info_file):
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
      text_spans = browser.find_element_by_id("divResults").find_elements_by_tag_name("span")
      lines = ["\n", "\n"]
      for span in text_spans:
        lines.append(span.text + "  \n")
      os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
      with open(outfile_path, "w") as outfile:
        outfile.writelines(lines)
    # Close the kANDa - else the driver may pick sarga from this kANDa when it is to pick the sarga from the next kANDa?!
    close_path(subunit_path=subunit_path, unit_data=unit_data)
  MdFile.fix_index_files(dir_path=base_dir)
