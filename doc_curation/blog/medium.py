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

browser = None



def article_scraper(url, dir_path, dry_run): 
  return blog.scrape_post_markdown(url=url, dir_path=dir_path, dry_run=dry_run, entry_css_list=["article", "div.body.markup"], browser=browser)

def scrape_medium_blog(url, dir_path, dry_run=False):
  global browser
  if browser is None:
    browser = scraping.get_selenium_chrome(headless=False)

  blog.scrape_index_from_anchors(url=url, dir_path=dir_path, entry_css_list=[], anchor_css_list=["a:has(h2)"], article_scraper=article_scraper, browser=browser, dry_run=dry_run)
