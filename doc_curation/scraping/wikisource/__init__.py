"""
Wikisource scraping.
"""
from urllib.parse import urljoin


def next_url_getter(soup, url, next_url_text):
  next_page_links = [l for l in soup.select("#mw-pages>a") if next_url_text in l.text]
  if len(next_page_links) > 0:
    url = urljoin(url, next_page_links[0]["href"])
  else:
    url = None
  return url


