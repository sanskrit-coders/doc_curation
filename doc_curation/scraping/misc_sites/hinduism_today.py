import logging
import os
import re
import time
from datetime import datetime

import regex
import requests
from bs4 import BeautifulSoup

from curation_utils import file_helper
from doc_curation.ebook import pandoc_helper
from doc_curation.md.file import MdFile

# Configurable settings
BASE_URL = "https://www.hinduismtoday.com/category/magazine/"
DELAY = 1.5  # Polite delay (seconds) between individual article requests to prevent rate-limiting

# User-Agent to bypass basic browser detection
HEADERS = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
session = requests.Session()
session.headers.update(HEADERS)

# Regex to find dates like "January 1, 2026" or "November 23, 1995"
MONTHS = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
DATE_PATTERN = re.compile(rf"{MONTHS}\s+(\d{{1,2}}),\s+(\d{{4}})", re.IGNORECASE)

try:
  import html2text
except ImportError:
  html2text = None
  logging.info("WARNING: 'html2text' is not installed. Articles will be saved as raw HTML.")


def get_page_url(page_num):
  """Generates the URL for category pagination."""
  if page_num == 1:
    return BASE_URL
  return f"{BASE_URL}page/{page_num}/"


def parse_date(text):
  """Extracts and parses date from raw text to a datetime object."""
  match = DATE_PATTERN.search(text)
  if match:
    month_str, day_str, year_str = match.groups()
    try:
      return datetime.strptime(f"{month_str} {day_str} {year_str}", "%B %d %Y")
    except ValueError:
      pass
  return None


def extract_date_from_url(url):
  """Fallback method: Deduces the issue year/month from the article's URL pattern."""
  match = re.search(
    r'/(january|february|march|april|may|june|july|august|september|october|november|december)[^/]*?(\d{4})/', url,
    re.I)
  if match:
    month_name, year_str = match.groups()
    month_map = {
      'january': '01_01', 'february': '02_01', 'march': '03_01', 'april': '04_01',
      'may': '05_01', 'june': '06_01', 'july': '07_01', 'august': '08_01',
      'september': '09_01', 'october': '10_01', 'november': '11_01', 'december': '12_01'
    }
    month_day = month_map.get(month_name.lower(), '01_01')
    return f"{year_str}_{month_day}"
  return None


def slugify(title):
  """Converts a title into a clean slug."""
  # If title has a colon, we focus on the subtitle portion
  if ":" in title:
    title = title.split(":")[-1]

  s = title.lower()
  s = s.replace("’s", "").replace("'s", "")  # strip possessives
  s = re.sub(r"[^\w\s-]", "", s)  # remove special characters
  s = re.sub(r"[-\s]+", "-", s)  # spaces/hyphens to single hyphen

  # Custom adjustment for user's specific example "vijayanagara-grand-arc" to "vijayanagara-arc"
  s = s.replace("grand-", "")

  slug = s.strip("-")
  return slug


def clean_content(soup_elem):
  """Removes script, styles, share elements, and tracking details from the content."""
  if not soup_elem:
    return ""

  import copy
  elem = copy.copy(soup_elem)

  for tag in elem(['script', 'style', 'iframe', 'noscript']):
    tag.decompose()

  # Decompose common share blocks, comment fields, and navigation elements
  for tag in elem.find_all(
      class_=re.compile(r'(share|social|nav-links|comments|reply|author-bio|post-navigation|footer|header|sidebar)',
                        re.I)):
    tag.decompose()

  # Remove text-based metadata clutter
  for tag in elem.find_all(string=re.compile(r'(Post Views:|Share this article:|Leave a Comment|Cancel Reply)', re.I)):
    parent = tag.parent
    if parent:
      parent.decompose()

  return elem


def convert_to_markdown(html_elem):
  """Converts a BeautifulSoup element into Markdown format."""
  text = pandoc_helper.get_md_with_pandoc(content_in=str(html_elem))
  if text is None and html2text:
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = False
    converter.body_width = 0  # Prevents unnecessary wrapping of text lines
    return converter.handle(str(html_elem))
  elif text is None:
    text = html_elem.get_text("\n\n").strip()
  text = regex.sub(r"^\*\*(.+?)\*\*$", r"## \1", text, flags=regex.MULTILINE)
  text = regex.sub(r"\n\n\n+", r"\n\n", text)
  return text


def parse_category_page(html):
  """Finds all articles and dates on a category list page."""
  soup = BeautifulSoup(html, 'html.parser')
  articles_found = []

  # Target typical WordPress post container blocks
  posts = soup.find_all(['article', 'div'], class_=lambda c: c and ('post' in c or 'hentry' in c or 'article' in c))

  urls_seen = []
  if not posts:
    # Fallback to headings directly if standard container class matches fail
    for h in soup.find_all(['h2', 'h3']):
      link = h.find('a')
      if link and link.get('href') and '/category/' not in link.get('href'):
        parent_text = h.parent.get_text() if h.parent else ""
        date_str = ""
        date_match = DATE_PATTERN.search(parent_text)
        if date_match:
          date_str = date_match.group(0)
        if link.get('href') not in urls_seen:
          articles_found.append({
            'title': h.get_text().strip(),
            'url': link.get('href'),
            'date_str': date_str
          })
        urls_seen.append(link.get('href'))
    return articles_found

  for post in posts:
    title_link = post.select_one('.entry-title a, .post-title a, h2 a, h3 a')
    if not title_link:
      title_link = post.find('a', href=True)

    if not title_link or not title_link.get('href'):
      continue

    url = title_link.get('href')
    title = title_link.get_text().strip()

    # Prevent self-referential pagination or category loops
    if '/category/' in url or url == BASE_URL:
      continue

    # Try retrieving publish date
    date_str = ""
    time_tag = post.find('time')
    if time_tag:
      date_str = time_tag.get_text().strip()

    if not date_str:
      date_elem = post.select_one('.entry-date, .published, .post-date, .date, .entry-meta')
      if date_elem:
        date_str = date_elem.get_text().strip()

    if not date_str:
      # Fallback to plain regex search across container text
      match = DATE_PATTERN.search(post.get_text())
      if match:
        date_str = match.group(0)

    if url not in urls_seen:
      articles_found.append({
        'title': title,
        'url': url,
        'date_str': date_str
      })
    urls_seen.append(url)

  return articles_found


def parse_article_page(html):
  """Extracts the main body content from a single article page."""
  soup = BeautifulSoup(html, 'html.parser')

  title_elem = soup.find('h1')
  title = title_elem.get_text().strip() if title_elem else "Untitled"

  content_html = None
  content_selectors = ['.entry-content', '.post-content', 'article', '.content', 'main']

  for selector in content_selectors:
    elem = soup.select_one(selector)
    if elem and len(elem.get_text().strip()) > 100:
      content_html = elem
      break

  if not content_html:
    content_html = soup.find('body')

  return title, content_html, soup


def dump_article(article, dest_dir):
  title = article['title']
  article_url = article['url']
  date_str = article['date_str']

  # Match date
  dt = parse_date(date_str) if date_str else None
  if dt:
    formatted_date = dt.strftime("%Y_%m_%d")
  else:
    formatted_date = extract_date_from_url(article_url)
    if not formatted_date:
      formatted_date = "0000_00_00"  # fallback if date is entirely missing
  date_parts = formatted_date.split("_")

  slug = slugify(title)
  if slug is None:
    logging.warning(f"Something wrong with {article_url}. Skipping.")
    return None
  filename = f"{slug}.md"
  filepath = os.path.join(dest_dir, date_parts[0], date_parts[1], filename)
  filepath = file_helper.get_storage_path(file_path=filepath, source_script=None)

  # Resume check: Check if file already exists before sending a request
  if os.path.exists(filepath):
    logging.info(f"  [SKIPPED] Already scraped: {article_url} {filename}")
    return "SKIPPED"

  logging.info(f"  [SCRAPING] {title}...")
  time.sleep(DELAY)  # Respectful crawlers avoid rapid requests

  try:
    art_response = session.get(article_url, timeout=15)
    art_response.raise_for_status()

    full_title, content_html, soup = parse_article_page(art_response.text)
    cleaned_content = clean_content(content_html)
    markdown_body = convert_to_markdown(cleaned_content)

    # Prepend basic front-matter metadata
    metadata = {"title": title.replace('\"', '\\\"'), "article_date": date_str if date_str else 'UNKNOWN', "upstream_url": article_url}
    MdFile(file_path=filepath).dump_to_file(metadata=metadata, content=markdown_body, dry_run=False)

    logging.info(f"    [SAVED] {filename}")
    return filepath

  except Exception as e:
    logging.info(f"    [ERROR] Failed to extract {article_url}: {e}")
    return None
  



def dump_all(dest_dir="/home/vvasuki/gitland/hindu-comm/mags/hindusim_today"):
  os.makedirs(dest_dir, exist_ok=True)
  session = requests.Session()
  session.headers.update(HEADERS)

  page_num = 1
  scraped_count = 0
  skipped_count = 0
  error_count = 0

  logging.info("Beginning crawl of Hinduism Today...")
  logging.info(f"Output files will be saved in: {dest_dir}")

  while True:
    logging.info(f"\n--- Processing Category Page {page_num} ---")
    url = get_page_url(page_num)

    try:
      response = session.get(url, timeout=15)
      if response.status_code == 404:
        logging.info("Pagination finished (404 Page Not Found). Execution complete.")
        break
      response.raise_for_status()
    except Exception as e:
      logging.info(f"Error fetching page {page_num}: {e}. Retrying once in 5 seconds...")
      time.sleep(5)
      try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
      except Exception as retry_err:
        logging.info(f"Failed to fetch page {page_num} on retry: {retry_err}. Skipping page.")
        page_num += 1
        continue

    articles = parse_category_page(response.text)
    if not articles:
      logging.info("No more articles detected on this listing page. Ending.")
      break

    logging.info(f"Found {len(articles)} articles to inspect on index page {page_num}.")

    for article in articles:
      result = dump_article(article=article, dest_dir=dest_dir)
      if result == "SKIPPED":
        skipped_count += 1
      elif result == None:
        error_count += 1
      else:
        scraped_count += 1
    page_num += 1

  logging.info("\n--- Scrape Session Summary ---")
  logging.info(f"Total pages processed: {page_num - 1}")
  logging.info(f"Articles saved: {scraped_count}")
  logging.info(f"Articles skipped (already cached): {skipped_count}")
  logging.info(f"Extraction errors: {error_count}")


if __name__ == "__main__":
  try:
    dump_all()
  except KeyboardInterrupt:
    logging.info("\nSession paused by user. Progress saved.")
