import itertools
import logging
import os

import regex

from doc_curation import scraping
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome import options

from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

opts = options.Options()
opts.headless = True
browser = webdriver.Chrome(options=opts)
browser.implicitly_wait(6)


def generic_selenium_dumper(title, url, outfile_path, get_collapsible_content=False, dry_run=False):
  if os.path.exists(outfile_path):
    logging.info("skipping: %s - it exists already", outfile_path)
    return
  logging.info(url)
  browser.get(url)
  text = ""
  if not get_collapsible_content:
    try:
      text = browser.find_element_by_css_selector("div.poem").text
    except NoSuchElementException:
      content_element = browser.find_element_by_css_selector(".mw-parser-output")
      para_elements = content_element.find_elements_by_tag_name("p")
      text = "\n\n".join(map(lambda x: x.text, para_elements))
  else:
    text = browser.find_element_by_css_selector(".mw-collapsible-content").text
  os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
  with open(outfile_path, "w") as outfile:
    outfile.writelines(text.replace("\n", "  \n"))
  md_file = MdFile(file_path=outfile_path)
  md_file.set_title(title=title, dry_run=dry_run)
