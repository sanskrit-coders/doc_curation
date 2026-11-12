import datetime
import json
import logging
import os
import shutil
import time
from urllib.parse import urlsplit, urljoin, unquote
import re
from dateutil import parser
import doc_curation.md.library

import regex
from bs4 import BeautifulSoup

from curation_utils import file_helper
from curation_utils.file_helper import get_storage_name
from doc_curation.ebook import pandoc_helper
from doc_curation.md import library
from doc_curation.scraping.html_scraper import souper
from doc_curation.utils import text_utils
from doc_curation.md.file import MdFile
from doc_curation.scraping.html_scraper.souper import get_tags_matching_first_css
from curation_utils import scraping

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

# Set the logging level for your specific loggers
logging.getLogger("dateutil").setLevel(logging.WARNING)


def remove_non_content_tags(soup):
  non_content_tags = soup.select("#jp-post-flair") + soup.select("svg") + soup.select("style") + soup.select("script")
  for tag in non_content_tags:
    tag.decompose()


def get_post_html(url, entry_css_list=None, browser=None):
  '''get the text body of links'''
  logging.info("Processing post at %s", url)
  if browser is None:
    (soup, _) = scraping.get_soup(url)
  else:
    soup = scraping.scroll_and_get_soup(url=url, browser=browser)
  if soup is None:
    logging.error(f"Can't get soup for {url}")
    return None, None

  if entry_css_list is None:
    entry_css_list = ["div.entry-content", "div.entrybody", "div.post-entry", "div.post", "div.available-content", "div.entry", "div.main", "div.card-body"]
  entry_divs = get_tags_matching_first_css(soup=soup, css_selector_list=entry_css_list)

  if not entry_divs:
    return (None, soup)

  post_html = "\n\n".join(div.encode_contents().decode("utf-8") for div in entry_divs)

  return (post_html, soup)



def is_valid_article_date(date_obj):
  if date_obj is None:
    return False
  current_year = datetime.datetime.now().year
  return 1995 <= date_obj.year <= current_year + 1


def extract_date_with_regex(text):
  # Pattern 1: Month Day, Year (e.g., "May 24, 2026", "Feb 07, 2026", "October 5, 2025")
  # Matches month name (or abbreviation), day (1-2 digits), and year (4 digits)
  pattern_month_day_year = r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-zA-Z]*\.?\s+\d{1,2},?\s+\d{4}\b'

  # Pattern 2: Day Month Year (e.g., "24 May 2026", "07 February 2026")
  pattern_day_month_year = r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-zA-Z]*\.?\s+\d{4}\b'

  # Pattern 3: Standard ISO/YMD Date (e.g., "2026-05-24", "2026/02/07")
  pattern_iso = r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b'

  # Combine patterns
  combined_pattern = f'({pattern_month_day_year})|({pattern_day_month_year})|({pattern_iso})'

  match = re.search(combined_pattern, text, re.IGNORECASE)
  if match:
    matched_str = match.group(0)
    try:
      # Parse only the extracted substring with fuzzy=False to prevent noise pollution
      d = parser.parse(matched_str, fuzzy=False)
      if is_valid_article_date(d):
        return d
    except Exception:
      pass
  return None


def get_post_metadata(soup):
  # 1. Extract the title
  title_css_list = [".post-title", ".entry-title", "h1", "h2", ".card-header", "h3", "h4"]
  title_tags = get_tags_matching_first_css(soup=soup, css_selector_list=title_css_list)

  title = None
  if len(title_tags) > 0:
    title = title_tags[0].get_text(separator="\n", strip=True).replace('\xa0', ' ')

  date = None

  # 2. Primary Attempt: Extract from JSON-LD structured metadata (Highly reliable for Substack)
  json_ld_tags = soup.find_all("script", type="application/ld+json")
  for tag in json_ld_tags:
    txt = tag.string or tag.get_text()
    if txt:
      try:
        data = json.loads(txt)
        candidates = []
        if isinstance(data, dict):
          candidates.append(data)
          if "@graph" in data and isinstance(data["@graph"], list):
            candidates.extend(data["@graph"])
        elif isinstance(data, list):
          candidates.extend(data)
        
        for item in candidates:
          if isinstance(item, dict):
            for field in ["datePublished", "dateCreated", "dateModified"]:
              date_string = item.get(field)
              if date_string:
                try:
                  candidate_date = parser.parse(date_string, fuzzy=True)
                  if is_valid_article_date(candidate_date):
                    date = candidate_date
                    break
                except Exception:
                  pass
            if date is not None:
              break
        if date is not None:
          break
      except Exception:
        pass

  # 2b. Substack embedded script post_date (e.g. "post_date":"2023-03-05T15:29:11.601Z")
  if date is None:
    for s in soup.find_all("script"):
      stext = s.string or s.get_text()
      if stext and "post_date" in stext:
        m = re.search(r'"post_date"\s*:\s*"([^"]+)"', stext)
        if m:
          try:
            candidate_date = parser.parse(m.group(1), fuzzy=True)
            if is_valid_article_date(candidate_date):
              date = candidate_date
              break
          except Exception:
            pass

  # 3. Secondary Attempt: Extract from standard HTML head meta-tags
  if date is None:
    meta_selectors = [
      "meta[property='article:published_time']",
      "meta[name='publication_date']",
      "meta[name='publish-date']",
      "meta[property='og:pubdate']",
      "meta[property='article:modified_time']",
      "meta[property='og:updated_time']",
    ]
    for selector in meta_selectors:
      meta_tags = soup.select(selector)
      for meta_tag in meta_tags:
        if meta_tag and meta_tag.get("content"):
          try:
            candidate_date = parser.parse(meta_tag["content"], fuzzy=True)
            if is_valid_article_date(candidate_date):
              date = candidate_date
              break
          except Exception:
            pass
      if date is not None:
        break

  # 4. Tertiary Fallback: Time element CSS selectors
  if date is None:
    time_tags = soup.find_all("time")
    if not time_tags:
      time_css_list = [".entry-date", ".post-date", ".published", "div.card-body>center"]
      time_tags = get_tags_matching_first_css(soup=soup, css_selector_list=time_css_list)
    for time_tag in time_tags:
      date_string = time_tag.get("datetime", None)
      if date_string is None:
        date_string = time_tag.get_text(separator="\n", strip=True)
      if date_string:
        try:
          candidate_date = parser.parse(date_string, fuzzy=True)
          if is_valid_article_date(candidate_date):
            date = candidate_date
            break
        except Exception:
          pass

  # 5. Final Fallback: Regex on raw article text (with strict year validation)
  if date is None:
    post_tags = get_tags_matching_first_css(soup=soup, css_selector_list=["article", ".post"])
    if len(post_tags) > 0:
      candidate_date = extract_date_with_regex(post_tags[0].get_text(separator="\n"))
      if is_valid_article_date(candidate_date):
        date = candidate_date
      else:
        import datefinder
        matches = list(datefinder.find_dates(post_tags[0].get_text(separator="\n")))
        for m in matches:
          if is_valid_article_date(m):
            date = m
            break

  if date is not None and not is_valid_article_date(date):
    date = None

  return date, title


def file_name_from_url(url, max_title_length=None):
  # construct file_name from the posts url
  parsed_url = urlsplit(url=url)
  path_parts = (parsed_url.path).strip().split("/")
  path_parts = [part for part in path_parts if part != ""]
  if not path_parts:
    # Root or empty path (e.g. https://site.com/): fall back to host.
    path_parts = [parsed_url.netloc]
  # remove slashes, replace with dashes when dealing with urls like https://manasataramgini.wordpress.com/2020/06/08/pandemic-days-the-fizz-is-out-of-the-bottle/
  # https://koenraadelst.blogspot.com/2021/06/resume-spring-2021.html
  post_id = unquote(path_parts[-1])
  return "%s.md" % file_helper.get_storage_name(post_id, max_length=max_title_length)


def fix_special_markup(content):
  # V![\_4](https://s0.wp.com/latex.php?latex=_4&bg=ffffff&fg=333333&s=0&c=20201002)
  content = regex.sub(r"!\[\\(_\d)\]\(.+?\)", r"\1", content)
  
  
  ## Medium.com stuff
  content = regex.sub(r"!\[\]\(data:image/svg\+xml;.+", r"", content)
  content = regex.sub(r"\[\]\(https://medium\.com/m/signin.+", r"", content)
  content = regex.sub(r".+resize:fill.+", r"", content)
  content = re.sub(r"##\s*Get\s+.*?stories.*?Remember\s+me\s+for\s+faster\s+sign\s+in", "", content, flags=re.DOTALL | re.IGNORECASE)
  content = re.sub(r"\n+.*?source=post_page---(?:author|read_next)_recirc[\s\S]*$", "\n", content, flags=re.DOTALL | re.IGNORECASE)
  return content


def scrape_post_markdown(url, dir_path, max_title_length=50, dry_run=False, entry_css_list=None, browser=None):
  logging.debug(f"Scraping {url}")
  (title, post_html, date_obj) = (None, None, None)
  
  if regex.search(r"/(\d\d\d\d)/(\d\d)/", url):
    file_name = file_name_from_url(url=url, max_title_length=max_title_length)
    result = regex.search(r"(\d\d\d\d)/(\d\d)/(\d\d)", url)
    if result is None:
      result = regex.search(r"(\d\d\d\d)/(\d\d)/", url)
      date_obj = parser.parse(result.group().replace("/", "-") + "01", fuzzy=True)
      # This provisional date_obj may be revised after the post is read.
    else:
      date_obj = parser.parse(result.group().replace("/", "-"), fuzzy=True)
    post_parsed = False
  else:
    ( post_html, soup) = get_post_html(url=url, entry_css_list=entry_css_list, browser=browser)
    if soup is None:
      logging.error(f"Could not get title from {url}")
      return False
    date_obj, title = get_post_metadata(soup)
    if title is None:
      logging.warning(f"Could not get title from {url}")
      return False
    file_name = "%s.md" % get_storage_name(text=title, max_length=max_title_length)

  file_path = get_file_path(date_obj, dir_path, file_name)

  if os.path.exists(file_path):
    logging.warning("Skipping %s : exists", file_name)
    return post_html is not None
  
  # post_html could've been computed in order to determine target file name.
  if post_html is None:
    ( post_html, soup) = get_post_html(url=url, entry_css_list=entry_css_list, browser=browser)
    if post_html is None or soup is None:
      logging.warning(f"Could not get post html : {url}")
      return False
    date_obj_alt, title = get_post_metadata(soup)
    if date_obj_alt is not None:
      date_obj = date_obj_alt
      file_path = get_file_path(date_obj, dir_path, file_name)

  if title is None:
    logging.warning(f"Could not get title from {url}")
    return False

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
  content = pandoc_helper.get_md_with_pandoc(content_in=post_html, source_format="html")
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
  if soup is None:
    logging.error(f"Could not fetch index page, aborting: {url}")
    return
  if anchor_css_list is not None:
    if post_html is not None:
      soup = BeautifulSoup(post_html, 'lxml')
    post_anchors = souper.get_tags_matching_css(soup=soup, css_selector_list=anchor_css_list)
  else:
    anchor_css = [".entry-title a", "h1.title a", "h2 a", "h3 a"]
    post_anchors = souper.get_tags_matching_css(soup=soup, css_selector_list=anchor_css)

  post_anchors = [x for x in post_anchors if "href" in x.attrs]
  if urlpattern is not None:
    post_anchors = [anchor for anchor in post_anchors if regex.match(urlpattern, anchor["href"])]
  post_anchors = [anchor for anchor in post_anchors if "share=" not in anchor["href"]]

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
  if prev_page_anchor is not None and "href" in prev_page_anchor.attrs:
    if delay is not None:
      logging.info(f'Waiting for {delay} secs.')
      time.sleep(delay)
      logging.info(f'Waited for {delay} secs.')
    scrape_index_from_anchors(url=urljoin(url, prev_page_anchor["href"]), dir_path=dir_path, article_scraper=article_scraper, browser=browser, entry_css_list=entry_css_list, anchor_css_list=anchor_css_list, anchor_filter=anchor_filter, urlpattern=urlpattern, dry_run=dry_run, delay=delay)


def organize_by_date(dir_path, dry_run=False):
  md_files = doc_curation.md.library.get_md_files_from_path(dir_path=dir_path)
  for md_file in md_files:
    (metadata, content) = md_file.read()
    if 'date' in metadata:
      # TOML/YAML loaders may hand us date/datetime objects, not strings.
      date_str = str(metadata['date'])
      sub_path = "/".join(date_str.split("-")[:-1])
      new_path = os.path.join(dir_path, sub_path, date_str + "_" + os.path.basename(md_file.file_path))
      if new_path == md_file.file_path:
        continue
      logging.info(f"Moving {md_file.file_path} to {new_path}")
      if not dry_run:
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.move(md_file.file_path, new_path)


if __name__ == '__main__':
  browser = scraping.get_selenium_chrome(headless=True)
  soup = scraping.scroll_and_get_soup(url="https://www.razibkhan.com/p/korean-identity-a-story-of-genetic", browser=browser)
  get_post_metadata(soup=soup)
