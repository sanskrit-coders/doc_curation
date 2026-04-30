import codecs
import logging
import os

import pypandoc
import regex
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.remote_connection import LOGGER
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.support.wait import WebDriverWait

from curation_utils import scraping
from doc_curation.md.file import MdFile
from doc_curation.md import library
from doc_curation.md.library import arrangement, metadata_helper
from doc_curation.scraping.html_scraper import souper


LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger

urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

browser = scraping.get_selenium_chrome(headless=False)

urls = []
# To construct urls like https://advaitasharada.sringeri.net/display/bhashya/Aitareya
shankara_bhaashyas = ["Isha", "Kena_pada", "Kena_vakya", "Kathaka", "Prashna", "Mundaka", "Mandukya", "Taitiriya",
                      "Aitareya", "Chandogya", "Brha", "Gita", "BS"]

# To construct urls like https://advaitasharada.sringeri.net/display/moola/Prashna
muulas = shankara_bhaashyas
muulas.extend(["jbl", "jbl", "svt", "kst"])

# To construct urls like https://advaitasharada.sringeri.net/display/bhashyaVyakhya/BS?vyakhya=VN
aanandagiri_bhaashyavyaakhya_texts = ["Isha", "Kena_pada", "Kena_vakya", "Kathaka", "Prashna", "Mundaka", "Mandukya",
                                      "Taitiriya", "Aitareya", "Chandogya", "Brha", "Gita"]

bhaashyavyaakhyas = {
  "BS": ["VN", "RP", "PP", "BM", "NY"],
  "panchapadika": ["VK"],
  "Taitiriya": ["TV", "TVN"]
}

for text in aanandagiri_bhaashyavyaakhya_texts:
  current_vyaakhyas = bhaashyavyaakhyas.get(text, [])
  current_vyaakhyas.append("AA")
  bhaashyavyaakhyas[text] = current_vyaakhyas

# To construct urls like https://advaitasharada.sringeri.net/display/prakarana/shatashloki
prakarana_texts = ["vivekachudamani", "shrutisarasamuddharanam", "shatashloki", "sarvavedantasiddhantasarasangraha",
                   "hastamalakiya-bhashya", "hastamalakiyam", "vedantaparibhasha", "vedantasara", "advaitasiddhi",
                   "shastra-siddanthalesha-sangraha"]


def get_text(url):
  browser.get(url=url)
  chapter_links = browser.find_elements(By.CSS_SELECTOR, "ul#sidebar > li:not(.special) > a")
  for chapter_link in chapter_links:
    target = chapter_link.get_attribute("href").replace(url, "")
    if "#" in target:
      target = regex.sub(r".+(?=#)", "", target)
    if chapter_link.text.strip() == "" or target == "#":
      continue
    logging.debug("Clicking %s, waiting for %s", chapter_link.text, target)
    chapter_link.click()
    element = WebDriverWait(browser, 20).until(
      presence_of_element_located((By.CSS_SELECTOR, target))
    )

  title_divs = browser.find_elements(By.CSS_SELECTOR, "div.col-md-7")
  chapter_divs = browser.find_elements(By.CSS_SELECTOR, "div.chapter")
  text_md = ""
  if len(title_divs + chapter_divs) == 0:
    return None
  for chapter_div in title_divs + chapter_divs:
    chapter_html = chapter_div.get_attribute('innerHTML')
    # Convert <div ... type="vishaya" data-name="...">text</div> to <h3>...</h3><p>text</p>
    chapter_html = regex.sub(
      r'<div(?=[^>]*\btype="vishaya")(?=[^>]*\bdata-name="([^"]+)")[^>]*>(.*?)</div>',
      r'<h3>\1</h3><p>\2</p>',
      chapter_html,
      flags=regex.DOTALL,
    )
    chapter_html = regex.sub("<(a|span)[^>]+>|</(a|span)>", "", chapter_html)
    chapter_html = regex.sub("<div[^>]+>", "<p>", chapter_html)
    chapter_html = regex.sub("</div[^>]+>", "</p>", chapter_html)
    chapter_md = pypandoc.convert_text(source=chapter_html, to="gfm", format='html',
                                       extra_args=['--markdown-headings=atx'])
    text_md = "%s\n\n%s" % (text_md, chapter_md)
  text_md = text_md.replace(" ", "")
  return text_md


def dump_text(url, dest_path, overwrite=False):
  if os.path.exists(dest_path) and not overwrite:
    logging.warning("Skipping %s", dest_path)
    return
  logging.info("Dumping %s to %s", url, dest_path)
  md = get_text(url)
  if md is None:
    logging.warning("No content. Skipping %s.", url)
    return
  os.makedirs(os.path.dirname(dest_path), exist_ok=True)
  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={}, content=md, dry_run=False)
  metadata_helper.set_title_from_filename(md_file=md_file, dry_run=False)



def get_2pane_page_details(soup):
  """
  Converts the provided HTML content to a structured Markdown format.
  """
  markdown_output = []

  # --- Extract Heading ---
  header_div = soup.find('div', class_='splitWindow-address')
  title = None
  if header_div:
    spans = header_div.find_all('span')
    heading_parts = [span.get_text(strip=True) for span in spans]
    if heading_parts:
      title = ' '.join(heading_parts)

  # --- Extract Moolam (Original Text) ---
  bhashya_holder = soup.find('div', class_='bhashyaHolder')
  if bhashya_holder:
    moolam_text = bhashya_holder.get_text('\n', strip=True)
    markdown_output.append("<details open><summary>मूलम्</summary>\n")
    markdown_output.append(f"{moolam_text}\n")
    markdown_output.append("</details>\n")

  # --- Extract Tika (Commentaries) ---
  vyakhya_descriptors = soup.find_all('div', class_='VyakhyaDescriptor')
  for descriptor in vyakhya_descriptors:
    prateeka = descriptor.find('p', class_='prateeka')
    if prateeka:
      summary_text = prateeka.get_text(strip=True)

      # Get all the text within the VyakhyaDescriptor
      tika_paragraphs = descriptor.find_all('p')
      tika_content = "\n\n".join(p.get_text(strip=True).replace('\xa0', ' ') for p in tika_paragraphs)

      markdown_output.append(f"<details><summary>टीका - {summary_text}</summary>\n")
      markdown_output.append(f"{tika_content}\n")
      markdown_output.append("</details>\n")

  return ("\n".join(markdown_output), title)


def dump_2pane_series(url, dest_path, overwrite=False):
  logging.info("Dumping %s to %s", url, dest_path)

  next_url_getter = lambda soup, url: souper.anchor_url_from_soup_css(soup=soup, css="span.next a", base_url=url)

  md_out = ""
  current_url = url
  get_page = True
  page_count = 0
  prev_title = None
  while url is not None:
    logging.info(f"Getting item {page_count} {url}")
    (soup, result) = scraping.get_soup(url=url)
    if soup is None:
      logging.warning(f"Failed at {url}")
      break
    (md, title) = get_2pane_page_details(soup)
    md = f"Source: [TW]({url})  \n{md}"
    if title is not None and title != prev_title:
      md = f"## {title}\n{md}"
    md_out += f"\n\n{md}"
    url = next_url_getter(soup, url)
    page_count = page_count + 1

  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={}, content=md_out, dry_run=False)
  metadata_helper.set_title_from_filename(md_file=md_file, dry_run=False)


def dump_texts(dest_dir):
  for item in muulas:
    url = "https://advaitasharada.sringeri.net/display/moola/%s" % item
    dump_text(url=url, dest_path=os.path.join(dest_dir, "mUla", item + ".md"))
  for item in shankara_bhaashyas:
    url = "https://advaitasharada.sringeri.net/display/bhashya/%s" % item
    dump_text(url=url, dest_path=os.path.join(dest_dir, "bhAShya", item + ".md"))
  for item in prakarana_texts:
    url = "https://advaitasharada.sringeri.net/display/prakarana/%s" % item
    dump_text(url=url, dest_path=os.path.join(dest_dir, "prakaraNa", item + ".md"))
  for text in bhaashyavyaakhyas:
    for vyaakhyaa in bhaashyavyaakhyas[text]:
      url = "https://advaitasharada.sringeri.net/display/bhashyaVyakhya/%s?vyakhya=%s" % (text, vyaakhyaa)
      dump_text(url=url, dest_path=os.path.join(dest_dir, "bhaShya_vyAkhyA", text, vyaakhyaa + ".md"))
