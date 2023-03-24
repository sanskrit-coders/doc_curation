import itertools
import logging
import os

import regex
from indic_transliteration import sanscript

from curation_utils.file_helper import get_storage_name
from doc_curation import md
from doc_curation.md.file import MdFile

import doc_curation.md
from curation_utils import scraping, file_helper
from doc_curation.scraping.html_scraper.souper import get_tags_matching_css

BASE_URL = "https://sambhashanasandesha.in"


def get_title(div):
  title_css_list = ["h1", "h2", "h3", "h4", "h5", "h6", "p"]
  paras = get_tags_matching_css(soup=div, css_selector_list=title_css_list)
  title = " ".join([x.text.strip() for x in itertools.takewhile(lambda x: x.name.lower()[0] == "h", paras)])
  if title == "":
    title = " ".join([x.text.strip() for x in itertools.takewhile(lambda x: x.get("style", "") == "text-align:center", paras)])
  if title == "":
    title = " ".join([x.text.strip() for x in itertools.takewhile(lambda x: x.get("style", "") == "strong", paras)])
  if title == "":
    title = " ".join([x.text.strip() for x in paras])
  return file_helper.clear_bad_chars(title)[:30]

def dump_month(url, dest_path_month):
  soup = scraping.get_soup(url=url)
  content_divs = soup.select("#showData>div")
  for index, div in enumerate(content_divs):
    title = f"{(index + 1):02d} " + get_title(div)
    file_name = f"{get_storage_name(text=title, max_length=20, source_script=sanscript.DEVANAGARI)}.md"
    dest_path = os.path.join(dest_path_month, file_name)
    if os.path.exists(dest_path):
      logging.info(f"Skipping {dest_path}")
      continue
    md_file = MdFile(file_path=dest_path)
    content = md.get_md_with_pandoc(content_in=str(div), source_format="html")
    content = content.replace(":", "ः").replace("\n# ", "\n## ")
    md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=False)

def dump_year(year, dest_path):
  url = f"{BASE_URL}/months?year={year}"
  soup = scraping.get_soup(url=url)
  month_urls = [os.path.join(BASE_URL, x["href"]) for x in soup.find_all("a") if x.text.strip() == "Unicode" ]
  num_months = len(month_urls)
  logging.info(f"Months in {year}: {num_months}")
  for index, month_url in enumerate(month_urls):
    dump_month(month_url, os.path.join(dest_path, str(year), "%02d" % (num_months - index)))