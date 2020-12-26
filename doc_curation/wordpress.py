import glob
import logging
import os
import shutil
from urllib.parse import urlsplit
from urllib.request import urlopen

import regex
from bs4 import BeautifulSoup

from curation_utils import file_helper
from doc_curation.md_helper import MdFile

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
    return None
  post_html = entry_divs[0].encode_contents()
  title = soup.find(attrs={'class': 'entry-title'}).string.replace('\\xa0', ' ').replace("xa0", " ")
  return (title, post_html)


def scrape_post_markdown(url, dir_path, dry_run):
  # construct file_name from the posts url
  parsed_url = urlsplit(url=url)
  file_name = (parsed_url.path).strip()
  # remove slashes, replace with dashes when dealing with urls like https://manasataramgini.wordpress.com/2020/06/08/pandemic-days-the-fizz-is-out-of-the-bottle/
  file_name = regex.sub("/(....)/(..)/(..)/(.+)/", r"\1/\2/\1-\2-\3_\4.md", file_name)
  file_path = file_helper.clean_file_path(file_path=os.path.join(dir_path, file_name))

  if os.path.exists(file_path):
    logging.warning("Skipping %s : exists", file_name)
    return
  (title, post_html) = get_post_html(url=url)
  logging.info("Dumping %s to %s with title %s.", url, file_path, title)

  md_file = MdFile(file_path=file_path, frontmatter_type=MdFile.TOML)
  md_file.import_content_with_pandoc(metadata={"title": title}, content=post_html, source_format="html",
                                     dry_run=dry_run)


def scrape_index(url, dir_path, dry_run=False):
  (title, post_html) = get_post_html(url=url)
  soup = BeautifulSoup(markup=post_html)
  post_anchors = soup.select("ul li a")
  for anchor in post_anchors:
    scrape_post_markdown(url=anchor["href"], dir_path=dir_path, dry_run=dry_run)


def fix_paths(dir_path, dry_run=False):
  files = glob.glob(os.path.join(dir_path, '**/2*.md'), recursive=True)
  for file_path in files:
    base_name = os.path.basename(file_path)
    year_str = base_name.split("-")[0]
    month_str = base_name.split("-")[1]
    dest_path = os.path.join(dir_path, year_str, month_str, base_name)
    logging.info("Move %s to %s", file_path, dest_path)
    if not dry_run:
      os.makedirs(name=os.path.dirname(dest_path), exist_ok=True)
      shutil.move(src=file_path, dst=dest_path)
  MdFile.fix_index_files(dir_path=dir_path, dry_run=dry_run)
