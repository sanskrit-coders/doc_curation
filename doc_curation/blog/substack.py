from doc_curation import blog
from curation_utils import scraping
import logging

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")
logging.getLogger('charsetgroupprober').setLevel(logging.WARNING)
logging.getLogger("charsetgroupprober").propagate = False
logging.getLogger('sbcharsetprober').setLevel(logging.WARNING)
logging.getLogger("sbcharsetprober").propagate = False


def free_article_filter(anchor):
  lock_tags = anchor.parent.select(".audience-lock")
  if len(lock_tags) == 0:
    return True
  return False


def scrape_free_articles_from_index_anchors(url, dir_path, dry_run=False):
  browser = scraping.get_selenium_chrome(headless=True)
  article_scraper = lambda url, dir_path, dry_run: blog.scrape_post_markdown(url=url, dir_path=dir_path, dry_run=dry_run, entry_css_list=[".single-post", "div.body.markup"])
  blog.scrape_index_from_anchors(url=url, dir_path=dir_path, entry_css_list=[], anchor_css="a.post-preview-title", article_scraper=article_scraper, anchor_filter=free_article_filter, browser=browser, dry_run=dry_run)
