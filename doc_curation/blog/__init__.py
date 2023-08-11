import datetime
import logging
import os
import shutil
import time
import urllib
from urllib.parse import urlsplit, urljoin, unquote
from urllib.request import urlopen, Request
import dateutil.parser as parser

import regex
from bs4 import BeautifulSoup

from curation_utils import file_helper
from curation_utils.file_helper import get_storage_name
from doc_curation.utils import text_utils
from doc_curation.md import get_md_with_pandoc, library
from doc_curation.md.file import MdFile
from doc_curation.scraping.html_scraper.souper import get_tags_matching_css
from curation_utils import scraping
from indic_transliteration import sanscript
from indic_transliteration.detect import detect

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")



def get_post_html(url, entry_css_list=None, browser=None):
  '''get the text body of links'''
  logging.info("Processing post at %s", url)
  if browser is None:
    soup = scraping.get_soup(url)
  else:
    soup = scraping.scroll_and_get_soup(url=url, browser=browser)
  non_content_tags = soup.select("#jp-post-flair") + soup.select("svg") + soup.select("style") + soup.select("script")
  for tag in non_content_tags:
    tag.decompose()

  if entry_css_list is None:
    entry_css_list = ["div.entry-content", "div.entrybody", "div.post-entry", "div.post", "div.available-content", "div.entry", "div.main", "div.card-body"]
  entry_divs = get_tags_matching_css(soup=soup, css_selector_list=entry_css_list)

  if not entry_divs:
    return (None, soup)

  post_html = "\n\n".join(div.encode_contents().decode("utf-8") for div in entry_divs)

  return (post_html, soup)


def get_post_metadata(soup):
  title_css_list = [".post-title", ".entry-title", "h1", "h2", ".card-header", "h3", "h4"]
  title_tags = get_tags_matching_css(soup=soup, css_selector_list=title_css_list)
  title = title_tags[0].text.replace('\xa0', ' ')
  time_css_list = ["time", ".entry-date", ".post-date", ".published", "div.card-body>center"]
  time_tags = get_tags_matching_css(soup=soup, css_selector_list=time_css_list)
  date = None

  if len(time_tags) > 0:
    try:
      time_tag = time_tags[0]
      date_string = time_tag.get("datetime", None)
      if date_string is None:
        date_string = time_tag.text
      date = parser.parse(date_string, fuzzy=True)
    except parser.ParserError:
      date_str = regex.search("\d+[-/]\d+[-/]\d+", time_tags[0].text).group()
      date = parser.parse(date_str, dayfirst=True, fuzzy=True)
  else:
    post_tags = get_tags_matching_css(soup=soup, css_selector_list=["article", ".post"])
    if len(post_tags) > 0:
      import datefinder
      matches = list(datefinder.find_dates(post_tags[0].text))
      if len(matches) > 0:
        date = matches[0]

  return date, title


def file_name_from_url(url, max_title_length=None):
  # construct file_name from the posts url
  parsed_url = urlsplit(url=url)
  path_parts = (parsed_url.path).strip().split("/")
  path_parts = [part for part in path_parts if part != ""]
  # remove slashes, replace with dashes when dealing with urls like https://manasataramgini.wordpress.com/2020/06/08/pandemic-days-the-fizz-is-out-of-the-bottle/
  # https://koenraadelst.blogspot.com/2021/06/resume-spring-2021.html
  post_id = unquote(path_parts[-1])
  return "%s.md" % file_helper.get_storage_name(post_id, max_length=max_title_length)


def fix_special_markup(content):
  # V![\_4](https://s0.wp.com/latex.php?latex=_4&bg=ffffff&fg=333333&s=0&c=20201002)
  content = regex.sub(r"!\[\\(_\d)\]\(.+?\)", r"\1", content)
  return content


def scrape_post_markdown(url, dir_path, max_title_length=50, dry_run=False, entry_css_list=None):
  logging.debug(f"Scraping {url}")
  (title, post_html, date_obj) = (None, None, None)
  
  if regex.search("/(\d\d\d\d)/(\d\d)/", url):
    file_name = file_name_from_url(url=url, max_title_length=max_title_length)
    result = regex.search("(\d\d\d\d)/(\d\d)/(\d\d)", url)
    if result is None:
      result = regex.search("(\d\d\d\d)/(\d\d)/", url)
      date_obj = parser.parse(result.group().replace("/", "-") + "01", fuzzy=True)
      # This provisional date_obj may be revised after the post is read.
    else:
      date_obj = parser.parse(result.group().replace("/", "-"), fuzzy=True)
    post_parsed = False
  else:
    ( post_html, soup) = get_post_html(url=url, entry_css_list=entry_css_list)
    date_obj, title = get_post_metadata(soup)
    file_name = "%s.md" % get_storage_name(text=title, max_length=max_title_length)

  file_path = get_file_path(date_obj, dir_path, file_name)

  if os.path.exists(file_path):
    logging.warning("Skipping %s : exists", file_name)
    return post_html is not None
  
  # post_html could've been computed in order to determine target file name.
  if post_html is None:
    ( post_html, soup) = get_post_html(url=url, entry_css_list=entry_css_list)
    date_obj_alt, title = get_post_metadata(soup)
    if date_obj_alt is not None:
      date_obj = date_obj_alt
      file_path = get_file_path(date_obj, dir_path, file_name)

  # Date may have been determined after get_post_html() . So, rechecking.
  if os.path.exists(file_path):
    logging.warning("Skipping %s : exists", file_name)
    return post_html is not None

  short_title = text_utils.title_from_text(text=title, num_words=5)
  full_title = text_utils.title_from_text(text=title, num_words=50, target_title_length=200)
  logging.info("Dumping %s to %s with title %s.", url, file_path, short_title)

  metadata = {"title": short_title, "full_title": full_title, "upstream_url": url}
  if date_obj is not None:
    metadata["date"] = datetime.datetime.strftime(date_obj, "%Y-%m-%d")
  md_file = MdFile(file_path=file_path, frontmatter_type=MdFile.TOML)
  content = get_md_with_pandoc(content_in=post_html, source_format="html")
  content = fix_special_markup(content=content)
  content = "Source: [here](%s).\n\n%s\n\n%s" % (url, title, content)
  md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)
  return post_html is not None


def get_file_path(date_obj, dir_path, file_name):
  if date_obj is None:
    file_path = file_helper.clean_file_path(file_path=os.path.join(dir_path, "undated", file_name))
  else:
    file_path = file_helper.clean_file_path(
      file_path=os.path.join(dir_path, datetime.datetime.strftime(date_obj, "%Y/%m/%Y-%m-%d_") + file_name))
  return file_path


def scrape_index_from_anchors(url, dir_path, article_scraper=scrape_post_markdown, browser=None, entry_css_list=None, anchor_css_list=["a[href]"], anchor_filter=lambda x: True, urlpattern=None, delay=None, dry_run=False):
  # standardize lengths of preexisting files to avoid duplication.
  from doc_curation.md.library import metadata_helper
  library.apply_function(fn=metadata_helper.truncate_file_name, max_length=50 + len("2020-02-10_"), dry_run=dry_run, dir_path=dir_path)
  ( post_html, soup) = get_post_html(url=url, entry_css_list=entry_css_list, browser=browser)
  if anchor_css_list is not None:
    if post_html is not None:
      soup = BeautifulSoup(post_html, 'lxml')
    post_anchors = get_tags_matching_css(soup=soup, css_selector_list=anchor_css_list)
  else:
    anchor_css = [".entry-title a", "h1.title a", "h3 a",]
    post_anchors = get_tags_matching_css(soup=soup, css_selector_list=anchor_css)

  post_anchors = [x for x in post_anchors if "href" in x.attrs]
  if urlpattern is not None:
    post_anchors = [anchor for anchor in post_anchors if regex.match(urlpattern, anchor["href"])]
  processed_urls = []
  for anchor in post_anchors:
    post_url = urljoin(url, anchor["href"])
    if post_url in processed_urls:
      continue
    else:
      processed_urls.append(post_url)
    if not anchor_filter(anchor):
      logging.info('Skipping %s', anchor["href"])
      continue
    if post_url != url:
      post_parsed = article_scraper(url=post_url, dir_path=dir_path, dry_run=dry_run)
      if post_parsed and delay is not None:
        logging.info(f'Waiting for {delay} secs.')
        time.sleep(delay)
        logging.info(f'Waited for {delay} secs.')

  prev_page_anchor = soup.select_one(".nav-previous a")
  if prev_page_anchor is not None:
    if delay is not None:
      logging.info(f'Waiting for {delay} secs.')
      time.sleep(delay)
      logging.info(f'Waited for {delay} secs.')
    scrape_index_from_anchors(url=prev_page_anchor["href"], dir_path=dir_path, article_scraper=article_scraper, browser=browser, anchor_css=anchor_css, anchor_filter=anchor_filter, urlpattern=urlpattern, dry_run=dry_run, delay=delay)


def organize_by_date(dir_path, dry_run=False):
  md_files = library.get_md_files_from_path(dir_path=dir_path)
  for md_file in md_files:
    (metadata, content) = md_file.read()
    if 'date' in metadata:
      sub_path = "/".join(metadata['date'].split("-")[:-1])
      new_path = os.path.join(dir_path, sub_path, metadata['date'] + "_" + os.path.basename(md_file.file_path))
      if new_path == md_file.file_path:
        continue
      logging.info(f"Moving {md_file.file_path} to {new_path}")
      if not dry_run:
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.move(md_file.file_path, new_path)