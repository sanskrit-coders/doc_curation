import glob
import logging
import os
import shutil

from bs4 import BeautifulSoup

from doc_curation.blog import get_post_html, scrape_post_markdown
from doc_curation.md import library

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


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
  library.fix_index_files(dir_path=dir_path, dry_run=dry_run)
