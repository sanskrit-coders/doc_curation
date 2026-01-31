import copy
import json
import logging
import os
import time
import traceback

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select

import doc_curation
from doc_curation import book_data
from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from doc_curation.md.content_processor import details_helper
from doc_curation.md.library import arrangement
from doc_curation.scraping.html_scraper import selenium
from doc_curation.scraping.html_scraper.selenium import click_link_by_text
from indic_transliteration import sanscript
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException

from curation_utils import scraping, file_helper
from selenium.webdriver.support.ui import WebDriverWait

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

# doc_curation.init_configuration()
configuration_parankusha = doc_curation.configuration['parankusha']


def get_logged_in_browser(headless=True):
  """Sometimes headless browser fails with selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted . Then, non-headless browser works fine! Or can try https://stackoverflow.com/questions/48665001/can-not-click-on-a-element-elementclickinterceptedexception-in-splinter-selen """
  browser = scraping.get_selenium_firefox(headless=headless)
  scraping.get_selenium_url("http://parankusan.cloudapp.net/Integrated/Texts.aspx", browser=browser)
  username = browser.find_element(By.ID, "txtUserName")
  username.send_keys(configuration_parankusha["user"])
  browser.find_element(By.ID, "btnNext").click()
  time.sleep(3)
  browser.find_element(By.ID, "txtPassword").send_keys(configuration_parankusha["pass"])
  browser.find_element(By.ID, "btnLogin").click()
  scraping.get_selenium_url("http://parankusan.cloudapp.net/Integrated/Texts.aspx", browser=browser)
  # TODO: deal with the inferior transliteration due to the below - esp in mixed devanAgarI/ tamiL context.
  # dropdown = browser.find_element(By.NAME, 'ddlOutputTranslitLang')
  # Select(dropdown).select_by_visible_text("Devanagari")
  # time.sleep(3)
  return browser


def expand_tree_by_text(browser, element_text, timeout=5, mode="expand", take_after=0):
  element_text = element_text.strip()
  def _get_subunit_element():
    subunit_elements = browser.find_elements(By.LINK_TEXT, element_text)
    subunit_elements = subunit_elements[take_after:]
    if len(subunit_elements) == 0:
      raise NoSuchElementException(f"Link not found - {element_text}")
    subunit_element = subunit_elements[0]
    return subunit_element
  
  try:
    subunit_element = _get_subunit_element()
    try:
      img_element = subunit_element.find_element(By.XPATH, "./../preceding-sibling::td/descendant::img")
    except NoSuchElementException as e:
      img_element = None

    if img_element is not None and "Collaps" in img_element.get_attribute("alt"):
      return True

    click_link_by_text(browser=browser, element_text=element_text, ordinal=take_after, timeout=timeout, post_wait=1)
    # WebDriverWait(browser, timeout).until(lambda browser: browser.find_elements(By.LINK_TEXT, element_text))
    
    # After clicking, StaleElementReferenceException is possible. So, reget the elements.
    subunit_element = _get_subunit_element()
    try:
      img_element = subunit_element.find_element(By.XPATH, "./../preceding-sibling::td/descendant::img")
    except NoSuchElementException as e:
      img_element = None


    if mode != "expand" and "Expand" in img_element.get_attribute("alt"):
      return True

    if mode == "expand" and "Collaps" in img_element.get_attribute("alt"):
      return True
    logging.info("Expanding: %s" % element_text)
    # subunit_element.click()

    expansion_element = subunit_element.find_element(By.XPATH, "./../preceding-sibling::td/descendant::a")

    selenium.click_element(browser=browser, element=expansion_element, post_wait=timeout)
    return True
  except NoSuchElementException as e:
    logging.warning(f"Could not find {element_text}, {e.msg}")
    return False


def deduce_text_name(browser, ordinal=None):
  # Gets the link highlighted by red color in the left panel.
  WebDriverWait(browser,5).until(lambda browser: browser.find_elements(By.CSS_SELECTOR, "td>a.tv_0.tv_3"))

  elements = browser.find_elements(By.CSS_SELECTOR, "td>a.tv_0.tv_3")
  # element = browser.find_elements(By.CSS_SELECTOR, "#gvResults tr[valign=\"top\"] td")[-1]

  text_name = elements[-1].text.strip()
  if ordinal is None:
    return text_name
  else:
    return "%02d %s" % (ordinal, text_name)


def get_output_path(text_name, outdir, source_script=sanscript.DEVANAGARI):
  if source_script is None:
    text_name_transliterated = text_name
  else:
    text_name_transliterated = content_processor.transliterate(text=text_name, source_script=source_script, dest_script=sanscript.OPTITRANS)
  return os.path.join(outdir, file_helper.clean_file_path(text_name_transliterated) + ".md")



def dump_to_file(browser, out_file_path, comment_mode=None, text_name=None, start_nodes=None, source_script=sanscript.DEVANAGARI, overwrite=False, timeout=10, debrowse=True):

  if os.path.exists(out_file_path) and not overwrite:
      logging.info("Skipping " + out_file_path)
  else:
    text = browse_get_text(browser, comment_mode, source_script, start_nodes, timeout=timeout)
    if text_name is None and source_script is not None:
      text_name = sanscript.transliterate(data=os.path.basename(out_file_path.replace(".md", "")), _from=sanscript.OPTITRANS,_to=sanscript.DEVANAGARI)
    elif source_script is not None and source_script != sanscript.DEVANAGARI:
      text_name = content_processor.transliterate(text=text_name, source_script=source_script)
    md_file = MdFile(file_path=out_file_path)
    md_file.dump_to_file(metadata={"title": text_name}, content=text, dry_run=False)
    if debrowse:
      debrowse_nodes(browser=browser, start_nodes=start_nodes)


def browse_get_text(browser, comment_mode, source_script, start_nodes, timeout=10):
  def get_rows():
    return WebDriverWait(browser, timeout).until(
      EC.presence_of_all_elements_located((By.CSS_SELECTOR, '#gvResults tr[valign="top"]'))
    )

  if start_nodes is not None:
    browse_nodes(browser=browser, start_nodes=start_nodes)

  text = ""
  max_retries = 3
  rows = get_rows()

  for i in range(len(rows)):
    retry_count = 0
    while retry_count < max_retries:
      try:
        # refetch the row element to avoid stale reference
        rows = get_rows()
        row = rows[i]
        tds = row.find_elements(By.CSS_SELECTOR, "td")

        for td in tds:
          spans = td.find_elements(By.CSS_SELECTOR, "span")
          if len(spans) > 0:
            text_segments = [span.text.strip().replace("\\n", "\n").replace("\n", "  \n") for span in spans]
            main_text = "\n\n".join(text_segments)
            comment_tds = td.find_elements(By.XPATH, './following-sibling::*')
            if len(comment_tds) == 0:
              comment_mode = None
            id_tds = td.find_elements(By.XPATH, './preceding-sibling::*[1]')
            comment_id = ""
            if len(id_tds) > 0:
              id_td = id_tds[0]
              comment_id = " - " + id_td.text.strip()
            if comment_mode == "last":
              detail = details_helper.Detail(title=f"मूलम्{comment_id}", content=main_text)
              text += f"\n\n{detail.to_md_html(attributes_str='open')}\n\n"
              for comment_td in comment_tds:
                comment_text = comment_td.text.strip()
                if comment_text != "":
                  detail = details_helper.Detail(title=f"टीका{comment_id}", content=comment_text)
                  text += f"\n\n{detail.to_md_html()}\n\n"
            elif comment_mode == "first":
              for comment_td in comment_tds:
                comment_text = comment_td.text.strip()
                if comment_text != "":
                  detail = details_helper.Detail(title=f"मूलम्{comment_id}", content=comment_text)
                  text += f"\n\n{detail.to_md_html(attributes_str='open')}\n\n"
              detail = details_helper.Detail(title=f"टीका{comment_id}", content=main_text)
              text += f"\n\n{detail.to_md_html()}\n\n"
            else:
              detail = details_helper.Detail(title=f"मूलम्{comment_id}", content=main_text)
              text += f"\n\n{detail.to_md_html(attributes_str='open')}\n\n"

        break  # success, exit retry loop
      except StaleElementReferenceException:
        retry_count += 1
        time.sleep(0.5)  # short wait before retry

    else:
      # max retries exceeded
      print(f"Warning: Skipped row {i} due to stale element exceptions after {max_retries} retries.")

  if source_script is not None and source_script != sanscript.DEVANAGARI:
    text = content_processor.transliterate(text=text, source_script=source_script)

  return text


def browse_nodes(browser, start_nodes, timeout=10):
  # We don't "expand all" to avoid confusion among nodes with identical names.
  nodes_done = []
  for node in start_nodes:
    take_after = len([x for x in nodes_done if x == node])
    if node.startswith("expand:"):
      expand_tree_by_text(browser=browser, element_text=node.replace("expand:", ""), timeout=timeout, take_after=take_after)
    else:
      click_link_by_text(browser=browser, element_text=node, ordinal=take_after, timeout=timeout, post_wait=1)
    nodes_done.append(node)


def debrowse_nodes(browser, start_nodes, timeout=3):
  # We don't "expand all" to avoid confusion among nodes with identical names.
  for node in reversed(start_nodes):
    if node.startswith("expand:"):
      expand_tree_by_text(browser=browser, element_text=node.replace("expand:", ""), timeout=timeout, mode="collapse")


def get_texts(browser, outdir, start_nodes, ordinal_start=1, comment_mode=None, source_script=sanscript.DEVANAGARI, timeout=10):
  def _dump_text(browser, outdir, ordinal=None, comment_mode=comment_mode, start_nodes=None):
    text_name = deduce_text_name(browser, ordinal)
    try:
      out_file_path = get_output_path(text_name=text_name, outdir=outdir, source_script=source_script)
    except TimeoutException:
      logging.warning("Returning to the previous page - next button likely failed.")
      browser.back()
      debrowse_nodes(browser=browser, start_nodes=start_nodes)
      return
    dump_to_file(browser=browser, comment_mode=comment_mode, out_file_path=out_file_path, text_name=text_name, start_nodes=start_nodes, source_script=source_script, timeout=timeout, debrowse=False)

  browse_nodes(browser=browser, start_nodes=start_nodes)

  os.makedirs(name=outdir, exist_ok=True)
  ordinal = ordinal_start
  _dump_text(browser=browser, outdir=outdir, ordinal=ordinal, comment_mode=comment_mode)
  while click_link_by_text(browser=browser, element_text="Next", post_wait=3):
    if ordinal is not None:
      ordinal = ordinal + 1
    _dump_text(browser=browser, outdir=outdir, ordinal=ordinal, comment_mode=comment_mode)
  arrangement.fix_index_files(dir_path=outdir, overwrite=False, dry_run=False)
  debrowse_nodes(browser=browser, start_nodes=start_nodes)


def get_structured_text(browser, start_nodes, base_dir, unit_info_file, comment_mode=None, source_script=sanscript.DEVANAGARI, detail_title=None, prev_detail_title=None):
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
    outfile_path_base = os.path.join(base_dir, "/".join(map(lambda x: f"{x:02d}", subunit_path)))
    file_with_prefix = file_helper.find_file_with_prefix(path_prefix=outfile_path_base)
    if file_with_prefix is not None:
      out_file_path = file_with_prefix
    else:
      out_file_path = outfile_path_base + ".md"
  
    os.makedirs(name=os.path.dirname(out_file_path), exist_ok=True)
    if detail_title is not None:
      text = browse_get_text(browser=browser, comment_mode=comment_mode, source_script=source_script, start_nodes=None)
      md_file = MdFile(file_path=out_file_path)
      detail = details_helper.Detail(title=detail_title, content=text)
      md_file.transform(content_transformer=lambda c, *args, **kwargs: details_helper.insert_adjascent_element(content=c, metadata=m, title=prev_detail_title, new_element=detail))
    else:
      text_name = deduce_text_name(browser)
      dump_to_file(browser=browser, comment_mode=comment_mode, out_file_path=out_file_path, text_name=text_name, start_nodes=None, source_script=source_script)
    # Close the kANDa - else the driver may pick sarga from this kANDa when it is to pick the sarga from the next kANDa?!
    close_path(subunit_path=subunit_path, unit_data=unit_data)
  arrangement.fix_index_files(dir_path=base_dir)
