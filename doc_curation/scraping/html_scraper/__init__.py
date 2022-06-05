import collections
import logging
from copy import copy

from bs4 import BeautifulSoup

from curation_utils import scraping
from doc_curation.md.content_processor.details_helper import Detail


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




def get_detail_type(tag_classes, detail_map):
  div_class = tag_classes[0]
  for detail_type, detail_classes in detail_map.items():
    if div_class in detail_classes:
      return detail_type
  return None


def soup_to_details(soup, css_selector, get_detail_type):
  details = []
  tags = soup.select(css_selector)
  for tag in tags:
    if tag.text == "":
      continue
    detail_type = get_detail_type(tag_classes=tag["class"])
    if detail_type is None:
      logging.warning(f"Detail type confusion - {str(tag)}")
    if len(details) > 0 and details[-1].type == detail_type:
      details[-1].content = f"{details[-1].content.strip()}  \n{tag.text.strip()}\n"
    else:
      details.append(Detail(type=detail_type, content=tag.text.strip()))
  return details


def content_from_details(details, format_map):
  content = ""
  for detail in details:
    if detail.type == "SKIP":
      continue
    elif detail.type in format_map:
      content += detail.type % detail.content
    else:
      if detail.type is not None and detail.type.startswith("मूल"):
        detail_vishvaasa = copy(detail)
        detail_vishvaasa.type = "विश्वास-प्रस्तुतिः"
        content += "\n" + detail_vishvaasa.to_html() + "\n"
      content += "\n" + detail.to_html() + "\n"
  return content

