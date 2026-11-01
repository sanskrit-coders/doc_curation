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
from doc_curation.md.library import metadata_helper
from doc_curation.scraping.html_scraper import souper


LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger

urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

browser = None


def get_browser():
  global browser
  if browser is None:
    browser = scraping.get_selenium_chrome(headless=False)
  return browser

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
  browser = get_browser()
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
    prev_title = title
    md_out += f"\n\n{md}"
    url = next_url_getter(soup, url)
    page_count = page_count + 1

  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={}, content=md_out, dry_run=False)
  metadata_helper.set_title_from_filename(md_file=md_file, dry_run=False)


ADVAITA_SHAARADAA_BASE_URL = "https://advaitasharada.sringeri.net"


def _html_to_text(html, line_separator="\n"):
  html = regex.sub(r"<br\s*/?>", line_separator, html)
  text = BeautifulSoup(html, "html.parser").get_text()
  text = text.replace("\u00ad", "").replace("\u00a0", " ")
  text = regex.sub(r"[ \t]+\n", "\n", text)
  text = regex.sub(r"\n{3,}", "\n\n", text)
  return text.strip()


def _first_sentence(text, max_length=100):
  text = text.split("\n")[0].strip()
  match = regex.match(r"^.*?[।॥]", text)
  if match:
    text = match.group(0).strip()
  if len(text) > max_length:
    text = text[:max_length].rstrip() + "..."
  return text


def _tika_summary_and_body(html, lemma=None):
  soup = BeautifulSoup(html, "html.parser")
  summary = None
  pratika_head = soup.find("span", class_="pratika-head")
  if pratika_head is not None:
    summary = pratika_head.get_text(strip=True)
    pratika_head.decompose()
  if not summary:
    pratika = soup.find("span", class_="pratika")
    if pratika is not None:
      summary = pratika.get_text(strip=True)
  body = _html_to_text(str(soup), line_separator="\n\n")
  if not summary:
    if lemma and len(lemma) <= 100 and "\n" not in lemma:
      summary = lemma
    else:
      summary = _first_sentence(body)
  return summary.strip(), body


def _get_json(url):
  result = scraping.get_url_backoffed(url=url)
  if result.status_code >= 400:
    logging.warning("Failed to get %s", url)
    return None
  return result.json()


def get_split_chunk_details(soup, url, work, tika):
  panes = soup.find("div", class_="panes")
  if panes is None:
    return (None, None)
  chunk = panes["data-chunk"]
  next_chunk = panes.get("data-next")

  (read_soup, result) = scraping.get_soup(url=f"{ADVAITA_SHAARADAA_BASE_URL}/read/{work}/{chunk}/")
  vyakhya = _get_json(f"{ADVAITA_SHAARADAA_BASE_URL}/vyakhya/{work}/{chunk}.{tika}.json")
  if read_soup is None or vyakhya is None:
    return (None, None)

  blocks = []
  chapter = None
  chapter_heading_done = False
  pending_verse_html = None
  current = None

  def flush():
    nonlocal current
    if current is None:
      return
    moolam_parts = []
    if current["verse_html"] is not None:
      moolam_parts.append(_html_to_text(current["verse_html"]))
    moolam_parts.extend(_html_to_text(html) for html in current["base_htmls"])
    moolam = "\n".join(part for part in moolam_parts if part)
    base_id = current["base_id"]
    block = f"Source: [TW]({url}?u={base_id})  \n<details open><summary>मूलम्</summary>\n\n{moolam}\n\n</details>"
    for item in vyakhya.get(base_id, []):
      summary, body = _tika_summary_and_body(item.get("html", ""), item.get("lemma"))
      block += f"\n\n<details><summary>टीका - {summary}</summary>\n\n{body}\n\n</details>"
    blocks.append(block)
    current = None

  def ensure_chapter_heading():
    nonlocal chapter_heading_done
    if chapter is not None and not chapter_heading_done:
      blocks.append(f"## {chapter}")
      chapter_heading_done = True

  for tag in read_soup.select("p.chapter-head, p.unit, div.unit"):
    classes = tag.get("class", [])
    unit_id = tag.get("id")
    if "chapter-head" in classes:
      flush()
      chapter = tag.get_text(strip=True)
      chapter_heading_done = False
      pending_verse_html = None
    elif "kind-heading" in classes:
      flush()
      title = _html_to_text(tag.decode_contents())
      heading = f"{chapter} {title}" if chapter else title
      blocks.append(f"## {heading}")
      chapter_heading_done = True
      pending_verse_html = None
      if unit_id in vyakhya:
        current = {"base_id": unit_id, "verse_html": None, "base_htmls": []}
    elif "verse" in classes:
      flush()
      verse_element = tag.select_one(".verse-text")
      verse_html = (verse_element or tag).decode_contents()
      if unit_id in vyakhya:
        current = {"base_id": unit_id, "verse_html": None, "base_htmls": [verse_html]}
      else:
        pending_verse_html = verse_html
    elif unit_id in vyakhya:
      flush()
      ensure_chapter_heading()
      current = {"base_id": unit_id, "verse_html": pending_verse_html, "base_htmls": [tag.decode_contents()]}
      pending_verse_html = None
    elif regex.match(r"^.+_E\d+$", unit_id or ""):
      if current is not None:
        current["base_htmls"].append(tag.decode_contents())
      else:
        ensure_chapter_heading()
        blocks.append(_html_to_text(tag.decode_contents()))
    elif regex.match(r"^.+_P\d+$", unit_id or ""):
      if current is None:
        ensure_chapter_heading()
        current = {"base_id": unit_id, "verse_html": None, "base_htmls": [tag.decode_contents()]}
      else:
        current["base_htmls"].append(tag.decode_contents())
    elif regex.match(r"^.+_(B|I)\d+$", unit_id or ""):
      flush()
      ensure_chapter_heading()
      current = {"base_id": unit_id, "verse_html": pending_verse_html, "base_htmls": [tag.decode_contents()]}
      pending_verse_html = None
    elif current is not None:
      current["base_htmls"].append(tag.decode_contents())
    else:
      ensure_chapter_heading()
      blocks.append(_html_to_text(tag.decode_contents()))
  flush()

  return ("\n\n".join(block for block in blocks if block), next_chunk)


def dump_split_series(work, tika, dest_path, overwrite=False, start_chunk="1"):
  if os.path.exists(dest_path) and not overwrite:
    logging.warning("Skipping %s", dest_path)
    return
  logging.info("Dumping %s/%s to %s", work, tika, dest_path)

  md_out = ""
  chunk = str(start_chunk)
  while chunk is not None:
    url = f"{ADVAITA_SHAARADAA_BASE_URL}/split/{work}/{chunk}/{tika}/"
    logging.info("Getting chunk %s of %s", chunk, work)
    (soup, result) = scraping.get_soup(url=url)
    if soup is None:
      logging.warning("Failed at %s", url)
      break
    (md, next_chunk) = get_split_chunk_details(soup=soup, url=url, work=work, tika=tika)
    if md is None:
      break
    md_out = f"{md_out}\n\n{md}"
    chunk = next_chunk if next_chunk else None

  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={}, content=f"\n\n{md_out.strip()}", dry_run=False)
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
