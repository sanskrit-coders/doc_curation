import logging
import os
from urllib.parse import urlsplit
from urllib.request import urlopen

import regex
from bs4 import BeautifulSoup

from curation_utils import file_helper
from doc_curation.md.file import MdFile


for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")



def get_post_html(url):
  '''get the text body of links'''
  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  non_content_tags = soup.select("#jp-post-flair")
  for tag in non_content_tags:
    tag.decompose()

  # find the text content of the post
  entry_divs = soup.find_all('div', {'class': 'entry-content'})
  # some use entrybody instead
  if not entry_divs:
    entry_divs = soup.find_all('div', {'class': 'entrybody'})
  # some use post-entry
  if not entry_divs:
    entry_divs = soup.find_all('div', {'class': 'post-entry'})
  # some use post-entry
  if not entry_divs:
    entry_divs = soup.find_all('div', {'class': 'entry'})
    # some use main
  if not entry_divs:
    entry_divs = soup.find_all('div', {'class': 'main'})
  if not entry_divs:
    return (None, None, None)
  post_html = entry_divs[0].encode_contents()
  
  title_tag = soup.find(attrs={'class': 'entry-title'})
  if title_tag is None:
    title_tag = soup.find("h1")
  title = title_tag.string.replace('\\xa0', ' ').replace("xa0", " ")

  time_tag = soup.find(attrs={'class': ['entry-date', 'published']})
  date = None
  if time_tag is not None:
    date_parts = time_tag.text.strip().split("/")
    date_parts.reverse()
    date = "-".join(date_parts)
  return (title, post_html, date)


def scrape_post_markdown(url, dir_path, dry_run):
  # construct file_name from the posts url
  parsed_url = urlsplit(url=url)
  file_name = (parsed_url.path).strip()
  if file_name.endswith(".html"):
    # https://koenraadelst.blogspot.com/2021/06/resume-spring-2021.html
    file_name = regex.sub("/(....)/(..)/(.+).html", r"\1/\2/\1-\2_\3.md", file_name)
    date = regex.sub("/(....)/(..)/.+", r"\1-\2-01", file_name)
  else:
    # remove slashes, replace with dashes when dealing with urls like https://manasataramgini.wordpress.com/2020/06/08/pandemic-days-the-fizz-is-out-of-the-bottle/
    file_name = regex.sub("/(....)/(..)/(..)/(.+)/", r"\1/\2/\1-\2-\3_\4.md", file_name)
    date = regex.sub(".+(\d\d\d\d)-(\d\d)-(\d\d).+", r"\1-\2-\3", file_name)
    # For 'https://padmavajra.net/2021/07/19/one-of-the-few-versions-of-the-7-line-prayer-to-the-vajrayana-master-padmasambhava-i-saw-in-an-ia-language/' type urls

  file_path = file_helper.clean_file_path(file_path=os.path.join(dir_path, file_name))

  if os.path.exists(file_path):
    logging.warning("Skipping %s : exists", file_name)
    return
  (title, post_html, date_from_post) = get_post_html(url=url)
  if date_from_post:
    date = date_from_post
  logging.info("Dumping %s to %s with title %s.", url, file_path, title)

  md_file = MdFile(file_path=file_path, frontmatter_type=MdFile.TOML)
  md_file.import_content_with_pandoc(metadata={"title": title, "date": date}, content=post_html, source_format="html",
                                     dry_run=dry_run)