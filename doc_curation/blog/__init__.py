import datetime
import logging
import os
from urllib.parse import urlsplit, urljoin
from urllib.request import urlopen, Request
import dateutil.parser as parser

import regex
from bs4 import BeautifulSoup

from curation_utils import file_helper
from curation_utils.file_helper import get_storage_name
from doc_curation.md import get_md_with_pandoc
from doc_curation.md.file import MdFile
from doc_curation.scraping.html.souper import get_tags_matching_css

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")



def get_post_html(url):
  '''get the text body of links'''
  logging.info("Processing post at %s", url)
  raw_request = Request(url)
  raw_request.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:78.0) Gecko/20100101 Firefox/78.0')
  raw_request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
  page_html = urlopen(raw_request)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  non_content_tags = soup.select("#jp-post-flair")
  for tag in non_content_tags:
    tag.decompose()

  entry_css_list = ["div.entry-content", "div.entrybody", "div.post-entry", "div.entry", "div.main", "div.card-body"]
  entry_divs = get_tags_matching_css(soup=soup, css_selector_list=entry_css_list)

  if not entry_divs:
    return (None, None, None)

  post_html = entry_divs[0].encode_contents()

  title_css_list = [".entry-title", ".card-header", "h1", "h2", "h3", "h4"]
  title_tags = get_tags_matching_css(soup=soup, css_selector_list=title_css_list)
  title = title_tags[0].text.replace('\xa0', ' ')

  time_css_list = [".entry-date", ".published", "div.card-body>center"]
  time_tags = get_tags_matching_css(soup=soup, css_selector_list=time_css_list)
  date = None
  if len(time_tags) > 0:
    try:
      date = parser.parse(time_tags[0].text, fuzzy=True)
    except parser.ParserError:
      date_str = regex.search("\d+[-/]\d+[-/]\d+", time_tags[0].text).group()
      date = parser.parse(date_str, dayfirst=True, fuzzy=True)
  return (title, post_html, date)


def file_name_from_url(url):
  # construct file_name from the posts url
  parsed_url = urlsplit(url=url)
  path_parts = (parsed_url.path).strip().split("/")
  path_parts = [part for part in path_parts if part != ""]
  # remove slashes, replace with dashes when dealing with urls like https://manasataramgini.wordpress.com/2020/06/08/pandemic-days-the-fizz-is-out-of-the-bottle/
  # https://koenraadelst.blogspot.com/2021/06/resume-spring-2021.html
  return "%s.md" % path_parts[-1]


def scrape_post_markdown(url, dir_path, dry_run=False):

  (title, post_html, date_obj) = (None, None, None)
  
  
  if regex.search("/(\d\d\d\d)/(\d\d)/", url):
    file_name = file_name_from_url(url=url)
    result = regex.search("(\d\d\d\d)/(\d\d)/(\d\d)?", url)
    date_obj = parser.parse(result.group().replace("/", "-"), fuzzy=True)
  else:
    (title, post_html, date_obj) = get_post_html(url=url)
    file_name = "%s.md" % get_storage_name(text=title)

  file_path = file_helper.clean_file_path(file_path=os.path.join(dir_path, datetime.datetime.strftime(date_obj, "%Y/%m/%Y-%m-%d_") + file_name))

  if os.path.exists(file_path):
    logging.warning("Skipping %s : exists", file_name)
    return
  
  if post_html is None:
    (title, post_html, date_obj) = get_post_html(url=url)

  logging.info("Dumping %s to %s with title %s.", url, file_path, title)

  metadata = {"title": title, "date": datetime.datetime.strftime(date_obj, "%Y-%m-%d"), "upstream_url": url}
  md_file = MdFile(file_path=file_path, frontmatter_type=MdFile.TOML)
  content = get_md_with_pandoc(content_in=post_html, source_format="html")
  content = "Source: [here](%s).\n\n%s" % (url, content)
  md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)


def scrape_index_from_anchors(url, dir_path, article_scraper=scrape_post_markdown, anchor_css="a[href]", urlpattern=None, dry_run=False):
  (_, post_html, _) = get_post_html(url=url)
  soup = BeautifulSoup(post_html, 'lxml')
  post_anchors = soup.select(anchor_css)
  if urlpattern is not None:
    post_anchors = [anchor for anchor in post_anchors if regex.match(urlpattern, anchor["href"])]
  for anchor in post_anchors:
    post_url = urljoin(url, anchor["href"])
    if post_url != url:
      article_scraper(url=post_url, dir_path=dir_path, dry_run=dry_run)


