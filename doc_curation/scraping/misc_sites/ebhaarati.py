from selenium.common import WebDriverException

import indic_transliteration
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript, detect
from curation_utils import scraping
from urllib.parse import urljoin
from doc_curation import md
from doc_curation.md import library
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.html_scraper import selenium

from doc_curation.md.file import MdFile, file_helper
from doc_curation.md.content_processor import ocr_helper, footnote_helper
import logging
import os, regex

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


BASE_URL = "https://www.ebharatisampat.in/"
DEST_DIR = "/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/ebhAratI-sampat"


def remove_dummy_lines(text):
  text = regex.sub(r"\n.*?include/loader\.gif.*?\n", "\n", text)
  text = regex.sub(r"\n\*\*End Of Book\*\*\n*", "\n", text)
  return text


def fix_footnotes(content):
  content = regex.sub(r"\]\(http://॑ *", "](", content)
  old_content = content
  content = regex.sub(r"\!\[\]\(([^\)]+?)\)", r'<MISSING_FIG href="\1"/>', content)
  content = regex.sub(rf"({footnote_helper.REF_PATTERN})\(", r'\1 (', content)
  content = footnote_helper.inline_comments_to_footnotes(content=content, pattern=r"(?<=\])\(((?!https?:\/\/|mailto:)[^\n\)]+?)\)")
  if content != old_content:
    content = footnote_helper.define_footnotes_near_use(content=content)
    content = regex.sub(r"\[([^\]]+)\](?=\[\^)", r"\1", content)
  return content


def get_article(url, browser=None, scroll_pause=2):
  try:
    soup = scraping.scroll_and_get_soup(url=url, browser=browser, scroll_pause=scroll_pause, element_css="#content")
    title_element = soup.select_one("li.title")
    if title_element is None:
      # Pages like https://www.ebharatisampat.in/login.php 
      content = "ERROR - COULD NOT GET TEXT!"
      title = "Unknown"
    else:
      title = title_element.text
      content_tag = soup.select("div.page-content")
      content = md.get_md_with_pandoc(content_in=str(content_tag), source_format="html-native_divs-native_spans")
  except WebDriverException as e:
    logging.error(e)
    raise 
  content = ocr_helper.misc_sanskrit_typos(content)
  content = remove_dummy_lines(content)
  content = regex.sub(r"\n +", r"\n", content)
  # content = regex.sub(r"ब्राहृ", r"ब्रह्म", content)
  content = regex.sub(r"\n(>[^\n]+)>(?=\n)", r"\n\1  ", content).replace(" > ", " ")
  content = fix_footnotes(content=content)
  
  page_header = f"[[{title}\tSource: [EB]({url})]]"
  content = f"{page_header}\n\n{content}"
  logging.info(f"Got {title} from {url}")
  return (content, title, soup)


def dump_article(url, outfile_path, browser=None, title_prefix="", metadata=None, dry_run=False):
  logging.info(f"Dumping {outfile_path} from {url}")
  (page_content, page_title, soup) = get_article(url=url, browser=browser, scroll_pause=2)
  if outfile_path.endswith(".md"):
    file_path = outfile_path
  else:
    file_path = os.path.join(outfile_path, file_helper.get_storage_name(text=page_title, source_script=sanscript.DEVANAGARI) + ".md")
  md_file = MdFile(file_path=file_path)
  if metadata is None:
    metadata = {}
  metadata["title"] = f"{title_prefix} {page_title}".strip()
  md_file.dump_to_file(metadata=metadata, content=page_content, dry_run=dry_run)
  arrangement.fix_index_files(os.path.dirname(os.path.dirname(file_path)))
  return soup


def get_metadata(url):
  soup = scraping.get_soup(url=url)
  metadata = {}
  for detail_tag in soup.select(".product__info__main h5"):
    detail_parts = regex.split(r"\s*:\s*", detail_tag.text)
    key = detail_parts[0].lower().strip()
    value = ":".join(detail_parts[1:]).strip()
    if detect.detect(text=value) == sanscript.DEVANAGARI:
      value = ocr_helper.misc_sanskrit_typos(value)
    metadata[key] = value
  button = soup.select_one(".wn__single__product a#btn")
  metadata["source_url"] = urljoin(BASE_URL, button["href"])
  return metadata

def dump_all(list_url="https://www.ebharatisampat.in/unicodetype.php?cat=All&sub_cat=All&author=All&publisher=All&contributor=All&language=All&sort=DESC", dest_dir=DEST_DIR, scroll_pause=2, use_url_cache=False):
  browser = scraping.get_selenium_chrome()
  urls = get_urls(browser, dest_dir, list_url, scroll_pause, use_url_cache)

  out_paths = []
  for url in urls:
    metadata = get_metadata(url=url)
    out_path = dest_dir
    if "DOMAIN" in metadata and metadata["DOMAIN"] != "":
      out_path = os.path.join(out_path, file_helper.get_storage_name(text=metadata["DOMAIN"]))
    if "SUB-DOMAIN" in metadata and metadata["SUB-DOMAIN"] != "":
      out_path = os.path.join(out_path, file_helper.get_storage_name(text=metadata["SUB-DOMAIN"]))
    if "AUTHOR" in metadata and metadata["AUTHOR"] != "":
      out_path = os.path.join(out_path, file_helper.get_storage_name(text=metadata["AUTHOR"]))
    out_path = os.path.join(out_path, file_helper.get_storage_name(text=metadata["TITLE"]) + ".md")
    if metadata["title"] in ["श्रीस्कान्दमहापुराणम्", "मानसोल्लासः द्वितीयभागः"]:
      logging.warning(f"Skipping {out_path}")
      continue
    if os.path.exists(out_path):
      logging.info(f"Skipping {url} with \n{metadata}")
    else:
      dump_article(url=metadata["url"], outfile_path=out_path, metadata=metadata, browser=browser)
    out_paths.append(out_path)
  # dest_files_md = MdFile(file_path=os.path.join(dest_dir, "dest_files.md"))
  # dest_files_md.dump_to_file(metadata={"title": "Dest files"}, content="\n".join(out_paths), dry_run=False)
  library.dump_matching_files(dir_path=dest_dir, file_name_filter=lambda x: not x.endswith("_index.md"))
  pass


def get_urls(browser, dest_dir, list_url, scroll_pause, use_url_cache):
  return selenium.get_urls(browser=browser, dest_dir=dest_dir, list_url=list_url, scroll_pause=scroll_pause, use_url_cache=use_url_cache, scroll_btn_css="#load_more", url_css="div.product__thumb a.first__img")



if __name__ == '__main__':
  metadata = get_metadata("https://www.ebharatisampat.in/readunicode.php?id=ODcyMjgwNzM1OTg0OTYz")
  logging.info(metadata)