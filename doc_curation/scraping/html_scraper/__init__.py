import collections
import logging

from bs4 import BeautifulSoup

from curation_utils import scraping


def get_class_counts(html, css_selector):
  if html.startswith('/') or html.startswith('http', 'html.parser'):
    soup = scraping.get_soup(html)
  else:
    soup = BeautifulSoup(html, 'html.parser')
  tags = soup.select(css_selector)
  class_count = {}
  for tag in tags:
    if "class" in tag.attrs:
      classes = tag.attrs["class"]
      for c in classes:
        class_count[c] = class_count.get(c, 0) + 1
  logging.info(f"Total classes: {len(class_count)}. Total tags: {len(tags)}")
  for cls in sorted(class_count, key=class_count.get, reverse=True):
    logging.info(f"{cls} - {class_count[cls]}")
  return class_count

