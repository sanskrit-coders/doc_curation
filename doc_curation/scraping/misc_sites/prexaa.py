from curation_utils import scraping
from urllib.parse import urljoin
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from doc_curation import md
import time

from doc_curation.md.file import MdFile
from doc_curation.md.library import combination
import logging
import os, regex


def get_article(url):
  soup = scraping.get_soup(url=url)
  title = soup.select_one("h1").text
  content_tag = soup.select_one("article .field")
  content = md.get_md_with_pandoc(content_in=str(content_tag), source_format="html")
  content = content.replace("\|\|", "॥").replace("\|", "।")
  content = regex.sub(r"\n(>[^\n]+)>(?=\n)", r"\n\1  ", content).replace(" > ", " ")

  # Fix footnotes
  content = regex.sub(r"\[\\\[(\d+)\\\]\]\(.+?\)", r"[^\1]", content)
  content = regex.sub(r"(\n\[\^\d+\])", r"\1:", content)

  page_header = f"[[{title}\tSource: [prekshaa]({url})]]"
  content = f"{page_header}\n\n{content}"
  content = regex.sub("</?div.*?>", "", content)
  logging.info(f"Got {title} from {url}")
  return (content, title)

# Series id may be had from source of dropdown in https://www.prekshaa.in/archive?field_preksha_series_tid=7830
def dump_series(dest_path, url="https://www.prekshaa.in/archive", search_fields=None, title=None, dry_run=False):
  browser = scraping.get_selenium_chrome()
  def _select_search_field(field):
    if field in search_fields:
      Select(browser.find_element(by=By.ID, value=f"edit-field-{field}-article-target-id")).select_by_visible_text(search_fields[field])

  if search_fields is not None:
    logging.info(f"Search fields: {search_fields}")
    browser.get(url=url)
    if "search_text" in search_fields:
      browser.find_element(by=By.ID, value="edit-keys").send_keys(search_fields["search_text"])
    _select_search_field(field="author")
    _select_search_field(field="series")
    _select_search_field(field="language")
    _select_search_field(field="translator")
    browser.find_element(by=By.ID, value="edit-submit-archive-posts").click()
    time.sleep(5)
    soup = scraping.scroll_and_get_soup(url=None, browser=browser)
  else:
    soup = scraping.scroll_and_get_soup(url=url, browser=browser)
  anchor_tags = soup.select("#block-system-main .views-field-title a")
  anchor_tags.reverse()
  page_urls = [urljoin("https://www.prekshaa.in/", a["href"]) for a in anchor_tags]
  content = f"Source: [prekshaa series]({url})"
  logging.info(f"{len(page_urls)} in {url}")
  for index, page_url in enumerate(page_urls):
    if not dest_path.endswith(".md"):
      dest_file_path = os.path.join(dest_path, regex.sub(".+/", "", page_url) + ".md")
      if os.path.exists(dest_file_path):
        continue
    (page_content, page_title) = get_article(url=page_url)
    if title is None:
      title = page_title
    page_content = regex.sub(r"\[\^(\d+)\]", rf"\n[^{index+1}.\1]", page_content)
    page_content = regex.sub(r"\n[^\n]+To be continued[^\n]+\n", "", page_content)
    if dest_path.endswith(".md"):
      content = f"{content}\n\n{page_content}"
    else:
      md_file = MdFile(file_path=dest_file_path)
      md_file.dump_to_file(metadata={"title": page_title}, content=page_content, dry_run=dry_run)
  if dest_path.endswith(".md"):
    md_file = MdFile(file_path=dest_path)
    md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=dry_run)
  else:
    combination.combine_parts(dir_path=dest_path)

