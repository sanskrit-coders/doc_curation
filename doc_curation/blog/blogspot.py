"""Scraper for Blogger/Blogspot sites (e.g. https://koenraadelst.blogspot.com/).

Post discovery is feed-first: the site's RSS feed (``/feeds/posts/default``)
carries every post's URL, title and publication date, paginated via
``start-index``. Each post page is then dumped with the shared
:func:`doc_curation.blog.scrape_post_markdown` pipeline (pandoc HTML->MD),
passing the feed's date/title as overrides.

Why overrides: the generic page-metadata heuristics misread Blogspot dates
(the ``abbr.published`` tag's visible text is just a time like "1:00 PM",
which parses as *today*), so the feed's ``pubDate`` is authoritative.

If the feed is disabled or unreachable, falls back to following the
"Older Posts" (``a.blog-pager-older-link``) pagination chain from the
homepage, extracting Blogspot dates off each post page
(``abbr.published[title]``, then ``.date-header``).
"""

import logging
import time
import xml.etree.ElementTree as ET

import regex
from dateutil import parser

from curation_utils import scraping
from doc_curation import blog

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

# Blogspot post pages look like /2025/04/slug.html (also /2025/04/slug.html?...).
POST_URL_PATTERN = r".*/\d{4}/\d{2}/[^/]+\.html"

# Blogspot truncates feed pages by payload size, so a max-results=500 request
# typically returns far fewer items; pagination via start-index is required.
FEED_PAGE_SIZE = 500


def get_feed_posts(site_url):
  """List ``{"url", "title", "date"}`` dicts for every post in the site's feed."""
  base_url = site_url.rstrip("/")
  posts = []
  seen_urls = set()
  start_index = 1
  total_results = None
  while True:
    feed_url = (
      f"{base_url}/feeds/posts/default?alt=rss"
      f"&max-results={FEED_PAGE_SIZE}&start-index={start_index}"
    )
    logging.info("Fetching feed page: %s", feed_url)
    response = scraping.get_url_backoffed(url=feed_url)
    if response is None or not (200 <= response.status_code < 300):
      status = getattr(response, "status_code", None)
      logging.error("Feed request failed with status %s: %s", status, feed_url)
      break
    try:
      root = ET.fromstring(response.text)
    except ET.ParseError as e:
      logging.error("Could not parse feed XML from %s: %s", feed_url, e)
      break
    channel = root.find("channel")
    if channel is None:
      logging.error("No channel element in feed: %s", feed_url)
      break
    if total_results is None:
      total_el = channel.find(
        "{http://a9.com/-/spec/opensearchrss/1.0/}totalResults")
      if total_el is not None and total_el.text:
        try:
          total_results = int(total_el.text)
        except ValueError:
          pass
    items = channel.findall("item")
    if not items:
      break
    new_count = 0
    for item in items:
      link = (item.findtext("link") or "").strip()
      if not link or link in seen_urls:
        continue
      if not regex.match(POST_URL_PATTERN, link):
        continue
      seen_urls.add(link)
      title = (item.findtext("title") or "").strip() or None
      date_obj = None
      pub_date = (item.findtext("pubDate") or "").strip()
      if pub_date:
        try:
          date_obj = parser.parse(pub_date)
        except (ValueError, OverflowError):
          date_obj = None
      if date_obj is not None and not blog.is_valid_article_date(date_obj):
        logging.warning("Ignoring implausible feed date %s for %s", date_obj, link)
        date_obj = None
      posts.append({"url": link, "title": title, "date": date_obj})
      new_count += 1
    logging.info("Feed progress: %d/%s posts", len(posts), total_results or "?")
    start_index += len(items)
    if new_count == 0:
      break
    if total_results is not None and len(posts) >= total_results:
      break
  # Deduplicate while preserving feed order (newest first).
  return list({post["url"]: post for post in posts}.values())


def get_post_date(soup):
  """Blogspot-specific post date: ``abbr.published[title]``, else ``.date-header``."""
  published = soup.select_one("abbr.published")
  if published is not None and published.get("title"):
    try:
      date_obj = parser.parse(published["title"])
      if blog.is_valid_article_date(date_obj):
        return date_obj
    except (ValueError, OverflowError):
      pass
  date_header = soup.select_one(".date-header")
  if date_header is not None:
    date_obj = blog.extract_date_with_regex(
      date_header.get_text(separator="\n", strip=True))
    if blog.is_valid_article_date(date_obj):
      return date_obj
  return None


def title_from_url_slug(url):
  """Derive a readable title from a Blogspot post URL slug (untitled posts)."""
  from urllib.parse import urlsplit, unquote
  slug = unquote(urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1])
  slug = regex.sub(r"\.html?$", "", slug)
  return regex.sub(r"[-_]+", " ", slug).strip() or None


def scrape_post(url, dir_path, dry_run=False, date_override=None,
                title_override=None):
  """Dump one Blogspot post page, resolving its date the Blogspot way."""
  if date_override is None or title_override is None:
    (soup, _) = scraping.get_soup(url)
    if soup is None:
      logging.error("Could not fetch post page: %s", url)
      return False
    if date_override is None:
      date_override = get_post_date(soup)
    if title_override is None:
      if soup.select_one("h3.post-title, .post-title") is None:
        # Untitled post: the generic fallback would return the blog name
        # (h1), so derive a title from the URL slug instead.
        title_override = title_from_url_slug(url)
      else:
        (_, title_override) = blog.get_post_metadata(soup)
  # get_soup() results are cached, so the re-fetch inside
  # scrape_post_markdown() below does not hit the network again.
  return blog.scrape_post_markdown(
    url=url, dir_path=dir_path, dry_run=dry_run,
    entry_css_list=["div.post-body", "div.entry-content"],
    date_override=date_override, title_override=title_override)


def scrape_index(url, dir_path, dry_run=False, delay=None, use_feed=True):
  """Dump every post of a Blogspot site into ``dir_path``.

  :param url: Site root (e.g. https://koenraadelst.blogspot.com/) or any
    page on the site; the feed is derived from its host.
  :param delay: Optional seconds to sleep between post fetches.
  :param use_feed: Set False to skip the feed and only follow the
    "Older Posts" HTML pagination chain.
  """
  from urllib.parse import urlsplit
  parts = urlsplit(url)
  site_url = "%s://%s" % (parts.scheme or "https", parts.netloc)
  posts = get_feed_posts(site_url) if use_feed else []
  if posts:
    logging.info("Scraping %d feed-discovered posts from %s", len(posts), site_url)
    for post in posts:
      scraped = scrape_post(
        url=post["url"], dir_path=dir_path, dry_run=dry_run,
        date_override=post["date"], title_override=post["title"])
      if scraped and delay is not None:
        logging.info("Waiting for %s secs.", delay)
        time.sleep(delay)
    return

  # Fallback: follow the "Older Posts" pagination chain from the homepage.
  logging.warning("Feed yielded no posts for %s; falling back to HTML pagination", site_url)
  page_url = site_url
  visited_pages = set()
  while page_url is not None and page_url not in visited_pages:
    visited_pages.add(page_url)
    (soup, _) = scraping.get_soup(page_url)
    if soup is None:
      logging.error("Could not fetch index page, aborting: %s", page_url)
      return
    anchors = [a for a in soup.select("h3.post-title a[href], .post-title a[href]")
               if regex.match(POST_URL_PATTERN, a["href"])]
    logging.info("Found %d post links on %s", len(anchors), page_url)
    seen = set()
    for anchor in anchors:
      post_url = anchor["href"]
      if post_url in seen:
        continue
      seen.add(post_url)
      scraped = scrape_post(url=post_url, dir_path=dir_path, dry_run=dry_run)
      if scraped and delay is not None:
        logging.info("Waiting for %s secs.", delay)
        time.sleep(delay)
    older = soup.select_one("a.blog-pager-older-link[href]")
    page_url = older["href"] if older is not None else None


# Alias: the site root is the index for feed-based discovery.
scrape_site = scrape_index
