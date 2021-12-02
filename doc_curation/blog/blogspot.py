import logging

from bs4 import BeautifulSoup

from doc_curation.blog import get_post_html, scrape_post_markdown, get_post_metadata

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")



def scrape_index(url, dir_path, dry_run=False):
  ( post_html, soup) = get_post_html(url=url)
  date, title = get_post_metadata(soup)
  soup = BeautifulSoup(markup=post_html)
  post_anchors = soup.select(".BlogArchive ul li a")
  raise NotImplementedError
  for anchor in post_anchors:
    scrape_post_markdown(url=anchor["href"], dir_path=dir_path, dry_run=dry_run)
