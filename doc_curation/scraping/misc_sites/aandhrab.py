from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript
from curation_utils import scraping
from urllib.parse import urljoin
from doc_curation import md
from doc_curation.scraping.html_scraper import souper


from doc_curation.md.file import MdFile, file_helper
import logging
import os, regex


def get_article(url):
  soup = scraping.get_soup(url=url)
  title = soup.select_one("font[size='7']").text
  content_tag = soup.select("div.wmsect table td")[-1]
  content = md.get_md_with_pandoc(content_in=str(content_tag), source_format="html")
  content = content.replace("\|\|", "॥").replace("\|", "।")
  content = regex.sub(r"\n(>[^\n]+)>(?=\n)", r"\n\1  ", content).replace(" > ", " ")

  # Fix footnotes
  content = regex.sub(r"\[\\\[(\d+)\\\]\]\(.+?\)", r"[^\1]", content)
  content = regex.sub(r"(\n\[\^\d+\])", r"\1:", content)

  page_header = f"[[{title}\tSource: [AB]({url})]]"
  content = f"{page_header}\n\n{content}"
  logging.info(f"Got {title} from {url}")
  return (content, title, soup)


def dump_article(url, outfile_path, title_prefix, dry_run=False):
  (page_content, page_title, soup) = get_article(url=url)
  file_path = outfile_path
  md_file = MdFile(file_path=file_path)
  md_file.dump_to_file(metadata={"title": f"{title_prefix} {page_title}"}, content=page_content, dry_run=dry_run)
  metadata_helper.set_filename_from_title(md_file=md_file, dry_run=dry_run, source_script=sanscript.TELUGU)
  return soup

def _next_url_getter(soup, url):
  content_tag = soup.select_one("img[src='../../pics/goldright.gif']")
  if content_tag is None:
    return None
  else:
    return urljoin(url, content_tag.parent["href"])

def dump_series(url, dest_path, title=None, dry_run=False):
  souper.dump_series(start_url=url, out_path=dest_path, dumper=dump_article, next_url_getter=_next_url_getter, end_url=None, index_format="%02d")
  soup = scraping.scroll_and_get_soup(url=url, browser=scraping.get_selenium_chrome())
  for index, page_url in enumerate(page_urls):
    
    if title is None:
      title = page_title
    page_content = regex.sub(r"\[\^(\d+)\]", rf"\n[^{index+1}.\1]", page_content)
    page_content = regex.sub(r"\n[^\n]+To be continued[^\n]+\n", "", page_content)
    content = f"{content}\n\n{page_content}"
  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=dry_run)


