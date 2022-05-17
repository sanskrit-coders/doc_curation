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
    archives_elements = soup.find_all(text="Archives")
    if len(archives_elements) != 0:
      month_anchors = archives_elements[0].parent.parent.select("a")
      urls = sorted([anchor["href"] for anchor in month_anchors])
    else:
      archives_element = soup.select_one("[name='archive-dropdown']")
      urls = sorted([option["value"] for option in archives_element.select("option") if option["value"] != ""])
      # TODO : Fix this.
  if init_year_month_str is not None:
    urls = itertools.dropwhile(lambda x: init_year_month_str not in x, urls)
  return urls


def scrape_monthly_indexes(url, dir_path, init_year_month_str=None, dry_run=False):
  month_urls = get_month_urls(url, init_year_month_str=init_year_month_str)
  for month_url in month_urls:
    scrape_index_from_anchors(url=month_url, dir_path=dir_path, anchor_css=None, dry_run=dry_run)
