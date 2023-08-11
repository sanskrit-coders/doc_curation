import glob
import itertools
import logging
import os
import shutil
from datetime import datetime

import dateutil.parser as parser
from dateutil.relativedelta import relativedelta

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
  scrape_index_from_anchors(url=url, dir_path=dir_path, anchor_css_list=["ul li a"], dry_run=dry_run)


def month_str_from_url(url):
  match = regex.match(".+/(2\d\d\d/\d\d)/", url)
  if match is None:
    return None
  return match.group(1)


def get_month_urls(url, reverse=True, init_year_month_str=None):
  ( post_html, soup) = blog.get_post_html(url=url)
  month_anchors = soup.select(".widget_archive a")
  if len(month_anchors) == 0:
    archives_elements = soup.select_one("[name='archive-dropdown']")
    if archives_elements is not None and len(archives_elements) != 0:
      urls = sorted([option["value"] for option in archives_elements.select("option") if option["value"] != ""], reverse=reverse)
      pass
      # TODO : Fix this.
    else:
      archives_elements = soup.find_all(text="Archives")
      month_anchors = archives_elements[0].parent.parent.select("a")
      urls = sorted([anchor["href"] for anchor in month_anchors], reverse=reverse)
  else:
    urls = sorted([anchor["href"] for anchor in month_anchors], reverse=reverse)
  if init_year_month_str is not None:
    if not reverse:
      urls = itertools.dropwhile(lambda x: init_year_month_str > month_str_from_url(x), urls)
    else:
      urls = itertools.takewhile(lambda x: init_year_month_str <= month_str_from_url(x), urls)
  urls = list(urls)
  return urls


def scrape_monthly_indexes(url, dir_path, reverse=True, init_year_month_str=None, final_year_month_str=None, delay=None, dry_run=False):
  """
  
  :param url: 
  :param dir_path: 
  :param reverse: 
  :param init_year_month_str: Example 2021/12
  :param dry_run: 
  :return: 
  """
  if final_year_month_str is not None:
    month_urls = []
    init_date = parser.parse(f"{init_year_month_str}/01", fuzzy=True)
    if final_year_month_str == "current":
      final_date = datetime.now()
    else:
      final_date = parser.parse(f"{final_year_month_str}/01", fuzzy=True)
    date = init_date
    while date <= final_date:
      month_urls.append(f"{url}/{date.year}/{date.month}")
      date = date + relativedelta(months=+1)
  else:
    month_urls = get_month_urls(url, init_year_month_str=init_year_month_str, reverse=reverse)
  for month_url in month_urls:
    scrape_index_from_anchors(url=month_url, dir_path=dir_path, anchor_css_list=None, dry_run=dry_run, delay=delay)
