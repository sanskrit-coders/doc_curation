import glob
import itertools
import logging
import os
import shutil

from doc_curation import blog
from doc_curation.blog import scrape_index_from_anchors
from doc_curation.md import library
import regex

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


def month_str_from_url(url):
  match = regex.match(".+/(2\d\d\d/\d\d)/", url)
  if match is None:
    return None
  return match.group(1)


def get_month_urls(url, reverse=True, init_year_month_str=None):
  ( post_html, soup) = blog.get_post_html(url=url)
  month_anchors = soup.select(".widget_archive a")
  if len(month_anchors) == 0:
    archives_elements = soup.find_all(text="Archives")
    if len(archives_elements) != 0:
      month_anchors = archives_elements[0].parent.parent.select("a")
      urls = sorted([anchor["href"] for anchor in month_anchors], reverse=reverse)
    else:
      archives_element = soup.select_one("[name='archive-dropdown']")
      urls = sorted([option["value"] for option in archives_element.select("option") if option["value"] != ""], reverse=reverse)
      # TODO : Fix this.
  else:
    urls = sorted([anchor["href"] for anchor in month_anchors], reverse=reverse)
  if init_year_month_str is not None:
    if not reverse:
      urls = itertools.dropwhile(lambda x: init_year_month_str > month_str_from_url(x), urls)
    else:
      urls = itertools.takewhile(lambda x: init_year_month_str <= month_str_from_url(x), urls)
  return urls


def scrape_monthly_indexes(url, dir_path, reverse=True, init_year_month_str=None, dry_run=False):
  """
  
  :param url: 
  :param dir_path: 
  :param reverse: 
  :param init_year_month_str: Example 2021/12
  :param dry_run: 
  :return: 
  """
  month_urls = get_month_urls(url, init_year_month_str=init_year_month_str, reverse=reverse)
  for month_url in month_urls:
    scrape_index_from_anchors(url=month_url, dir_path=dir_path, anchor_css=None, dry_run=dry_run)
