import glob
import itertools
import logging
import os
import shutil

from doc_curation import blog
from doc_curation.blog import scrape_index_from_anchors
from doc_curation.md import library

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def scrape_index(url, dir_path, dry_run=False):
  """
  
  Way to create an index easily - https://wordpress.com/support/archives-shortcode/ .
  
  :param url: 
  :param dir_path: 
  :param dry_run: 
  :return: 
  """
  scrape_index_from_anchors(url=url, dir_path=dir_path, anchor_css="ul li a", dry_run=dry_run)


def get_month_urls(url, init_year_month_str=None):
  ( post_html, soup) = blog.get_post_html(url=url)
  month_anchors = soup.select(".widget_archive a")
  if len(month_anchors) == 0:
    month_anchors = soup.find_all(text="Archives")[0].parent.parent.select("a")
  urls = sorted([anchor["href"] for anchor in month_anchors])
  if init_year_month_str is not None:
    urls = itertools.dropwhile(lambda x: init_year_month_str not in x, urls)
  return urls


def scrape_monthly_indexes(url, dir_path, init_year_month_str=None, dry_run=False):
  month_urls = get_month_urls(url, init_year_month_str=init_year_month_str)
  for month_url in month_urls:
    scrape_index_from_anchors(url=month_url, dir_path=dir_path, anchor_css=None, dry_run=dry_run)


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
  library.fix_index_files(dir_path=dir_path, dry_run=dry_run)
