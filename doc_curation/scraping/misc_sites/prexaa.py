from curation_utils import scraping
from urllib.parse import urljoin
from doc_curation import md

from doc_curation.md.file import MdFile
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
  logging.info(f"Got {title} from {url}")
  return (content, title)


def dump_series(url, dest_path, title=None, dry_run=False):
  soup = scraping.scroll_and_get_soup(url=url, browser=scraping.get_selenium_chrome())
  anchor_tags = soup.select("#block-system-main .views-field-title a")
  anchor_tags.reverse()
  page_urls = [urljoin("https://www.prekshaa.in/", a["href"]) for a in anchor_tags]
  content = f"Source: [prekshaa series]({url})"
  logging.info(f"{len(page_urls)} in {url}")
  for index, page_url in enumerate(page_urls):
    (page_content, page_title) = get_article(url=page_url)
    if title is None:
      title = page_title
    page_content = regex.sub(r"\[\^(\d+)\]", rf"\n[^{index+1}.\1]", page_content)
    page_content = regex.sub(r"\n[^\n]+To be continued[^\n]+\n", "", page_content)
    content = f"{content}\n\n{page_content}"
  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=dry_run)

