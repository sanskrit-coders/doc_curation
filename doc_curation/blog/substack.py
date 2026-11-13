import datetime
import logging
import os
import re
import shutil

import requests
from dateutil import parser

from curation_utils import scraping
from curation_utils.file_helper import get_storage_name
from doc_curation import blog
from doc_curation.utils import text_utils
from doc_curation.md import library
from doc_curation.md.file import MdFile

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


def free_article_filter(anchor):
  lock_tags = anchor.parent.select(".audience-lock")
  if len(lock_tags) == 0:
    return True
  return False


def get_publication_root(url):
  from urllib.parse import urlsplit
  parts = urlsplit(url)
  return "%s://%s" % (parts.scheme or "https", parts.netloc)


def get_archive_posts(url, limit=25, max_retries=6):
  """Fetch all posts of a Substack publication via its public archive API.

  Returns a list of post dicts (with at least slug, post_date, audience, canonical_url).
  Much more reliable (and far cheaper) than scraping dates off the rendered pages.
  """
  import time
  root = get_publication_root(url)
  posts = []
  seen_slugs = set()
  cursor = None
  empty_pages = 0
  while True:
    params = {"sort": "new", "limit": limit}
    if cursor is not None:
      params["cursor"] = cursor
    data = None
    for attempt in range(max_retries):
      try:
        response = requests.get("%s/api/v1/archive" % root, params=params, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
          data = response.json()
          break
        logging.warning("Archive API %s returned %s (attempt %d)", root, response.status_code, attempt + 1)
      except requests.RequestException as e:
        logging.warning("Archive API %s failed: %s (attempt %d)", root, e, attempt + 1)
      time.sleep(2 * (attempt + 1))
    if data is None:
      raise RuntimeError("Could not fetch archive API for %s (cursor=%s)" % (root, cursor))
    page_posts = data.get("posts", [])
    new_posts = [post for post in page_posts if post.get("slug") not in seen_slugs]
    for post in new_posts:
      seen_slugs.add(post.get("slug"))
    posts.extend(new_posts)
    next_cursor = data.get("nextCursor")
    # The API sometimes returns an empty page (rate limiting) along with a cursor; retry rather than stopping early.
    if len(page_posts) == 0 and next_cursor is not None:
      empty_pages += 1
      if empty_pages >= max_retries:
        logging.warning("Archive API %s kept returning empty pages, stopping at %d posts", root, len(posts))
        break
      time.sleep(2 * empty_pages)
      continue
    empty_pages = 0
    if next_cursor is None or next_cursor == cursor:
      break
    cursor = next_cursor
  return posts


def get_post_dates(url):
  """Map of post slug -> post_date (datetime) for a Substack publication."""
  dates = {}
  for slug, post in get_posts_by_slug(url=url).items():
    post_date = post.get("post_date")
    if post_date is None:
      continue
    try:
      dates[slug] = parser.parse(post_date)
    except (ValueError, OverflowError):
      continue
  return dates


def get_slug_from_url(url):
  from urllib.parse import urlsplit
  path_parts = [part for part in urlsplit(url).path.split("/") if part != ""]
  # Some saved URLs point at the comments page of a post.
  while len(path_parts) > 0 and path_parts[-1] in ("comments", "comment"):
    path_parts = path_parts[:-1]
  if not path_parts:
    return None
  return path_parts[-1]


def get_posts_by_slug(url):
  """Map of post slug -> post dict from the Substack archive API."""
  posts = {}
  for post in get_archive_posts(url=url):
    slug = post.get("slug")
    if slug is not None:
      posts[slug] = post
  return posts


def strip_date_prefix(file_name):
  """Strip any leading YYYY-MM-DD_ or (for bogus dates like 1-01-01) Y-M-D_ prefix."""
  while True:
    date_prefix_match = re.match(r"^\d{1,4}-\d\d-\d\d_(.*)$", file_name)
    if date_prefix_match is None:
      return file_name
    file_name = date_prefix_match.group(1)


def _target_path(dir_path, post_date, file_name):
  file_name = strip_date_prefix(file_name)
  # Use the same path computation as the scraper, so that re-scrapes do not create duplicates.
  return blog.get_file_path(date_obj=post_date, dir_path=dir_path, file_name=file_name)


def _normalize_title(title):
  return re.sub(r"[^a-z0-9 ]+", "", (title or "").lower()).strip()


def resolve_slug(slug, posts, title=None):
  """Resolve a (possibly truncated/stale) upstream slug to a slug known to the archive API."""
  if slug is None:
    return None
  if slug in posts:
    return slug
  prefix_matches = [s for s in posts if s.startswith(slug) or slug.startswith(s)]
  if len(prefix_matches) == 1:
    return prefix_matches[0]
  import difflib
  if title is not None:
    normalized_title = _normalize_title(title)
    by_title = {}
    for (candidate_slug, post) in posts.items():
      by_title.setdefault(_normalize_title(post.get("title")), []).append(candidate_slug)
    matches = difflib.get_close_matches(normalized_title, list(by_title.keys()), n=2, cutoff=0.85)
    if len(matches) > 0 and len(by_title[matches[0]]) == 1:
      if len(matches) == 1 or matches[1] != matches[0]:
        return by_title[matches[0]][0]
  return None


def fix_archive(url, dir_path, dry_run=False, quarantine_dir=None):
  """Clean up an existing Substack archive using the archive API.

  - Groups files by post and quarantines (or deletes) duplicates of the same post.
  - Moves each surviving file to <YYYY>/<MM>/<YYYY-MM-DD>_<name>.md and fixes its frontmatter date.

  The archive API is authoritative: the earlier page-scraping fallbacks sometimes latched on to
  dates mentioned inside article text, which produced bogus dates and hence duplicate files.
  """
  urls = url if isinstance(url, (list, tuple)) else [url]
  posts = {}
  for publication_url in urls:
    publication_posts = get_posts_by_slug(url=publication_url)
    if len(publication_posts) == 0:
      raise RuntimeError("No posts found via archive API for %s" % publication_url)
    logging.info("Fetched %d posts from %s", len(publication_posts), publication_url)
    posts.update(publication_posts)

  if not os.path.isdir(dir_path):
    logging.warning("No archive directory at %s; skipping", dir_path)
    return {"ok": 0, "moved": 0, "duplicates": 0, "unmatched": 0, "undated": 0, "conflicts": 0}

  files_by_key = {}
  basename_slugs = {}
  for md_file in library.get_md_files_from_path(dir_path=dir_path):
    (metadata, _) = md_file.read()
    upstream_url = metadata.get("upstream_url")
    slug = get_slug_from_url(upstream_url) if upstream_url is not None else None
    title = metadata.get("full_title") or metadata.get("title")
    resolved_slug = resolve_slug(slug=slug, posts=posts, title=title)
    if resolved_slug is None:
      # Group unresolved files by slug+title, so that files for different posts sharing a bogus slug are not merged.
      files_by_key.setdefault((None, slug, _normalize_title(title)), []).append((md_file.file_path, metadata))
    else:
      files_by_key.setdefault((resolved_slug, None, None), []).append((md_file.file_path, metadata))
    basename = re.sub(r"^\d\d\d\d-\d\d-\d\d_", "", os.path.basename(md_file.file_path))
    basename_slugs.setdefault(basename, set()).add(resolved_slug or slug)
  # Titles which recur across different posts are bogus (usually the publication name got scraped instead of the post title).
  generic_basenames = {basename for (basename, slugs) in basename_slugs.items() if len(slugs) > 1}

  stats = {"ok": 0, "moved": 0, "duplicates": 0, "unmatched": 0, "undated": 0, "conflicts": 0}
  for (resolved_slug, _, _), entries in sorted(files_by_key.items(), key=lambda x: str(x[0])):
    post_date = parser.parse(posts[resolved_slug]["post_date"]) if resolved_slug is not None else None
    api_date_bogus = post_date is not None and not blog.is_valid_article_date(post_date)
    if api_date_bogus:
      logging.warning("Ignoring implausible API date %s for %s", post_date.date(), resolved_slug)
      post_date = None
    date_str = datetime.datetime.strftime(post_date, "%Y-%m-%d") if post_date is not None else None

    def rank(entry):
      # Prefer the most complete file; the date is corrected anyway.
      (file_path, metadata) = entry
      if post_date is None:
        return (os.path.getsize(file_path),)
      metadata_ok = str(metadata.get("date")) == date_str
      return (os.path.getsize(file_path), metadata_ok)

    entries.sort(key=rank, reverse=True)
    if len(entries) > 1:
      logging.info("Keeping %s among %d files for %s", entries[0][0], len(entries), resolved_slug)
    (keeper_path, keeper_metadata) = entries[0]
    if post_date is None:
      logging.warning("No API post for %s (upstream_url %s) in %s", keeper_path, keeper_metadata.get("upstream_url"), dir_path)
      stats["unmatched"] += 1

    # Quarantine duplicates first, so that the keeper can be moved to the freed-up target path.
    for (dup_path, dup_metadata) in entries[1:]:
      logging.info("Duplicate of %s : %s (was %s)", resolved_slug, dup_path, dup_metadata.get("date"))
      stats["duplicates"] += 1
      if dry_run:
        continue
      if quarantine_dir is None:
        os.remove(dup_path)
      else:
        dest = os.path.join(quarantine_dir, os.path.basename(os.path.abspath(dir_path)), os.path.relpath(dup_path, dir_path))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(dup_path, dest)

    if post_date is None:
      # Without an API date, at least move files with an obviously bogus date (e.g. one mentioned in the text) to undated/.
      metadata_date = keeper_metadata.get("date")
      # Only a full YYYY-MM-DD date is trustworthy here; parser.parse("1-01-01") silently yields 2001-01-01.
      metadata_date_obj = None
      if metadata_date is not None and re.match(r"^\d{4}-\d\d-\d\d", str(metadata_date)):
        try:
          metadata_date_obj = parser.parse(str(metadata_date))
        except (ValueError, OverflowError):
          metadata_date_obj = None
      already_undated = os.path.dirname(os.path.abspath(keeper_path)) == os.path.join(os.path.abspath(dir_path), "undated")
      if not already_undated and (api_date_bogus or metadata_date_obj is None or not blog.is_valid_article_date(metadata_date_obj)):
        undated_path = os.path.join(dir_path, "undated", strip_date_prefix(os.path.basename(keeper_path)))
        logging.info("Moving %s to %s (implausible date %s)", keeper_path, undated_path, metadata_date)
        stats["undated"] += 1
        if not dry_run:
          os.makedirs(os.path.dirname(undated_path), exist_ok=True)
          shutil.move(keeper_path, undated_path)
          md_file = MdFile(file_path=undated_path, frontmatter_type=MdFile.TOML)
          (metadata, content) = md_file.read()
          metadata.pop("date", None)
          md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run, silent=True)
      continue
    file_name = os.path.basename(keeper_path)
    target_path = _target_path(dir_path, post_date, file_name)
    if strip_date_prefix(file_name) in generic_basenames:
      api_title = posts[resolved_slug].get("title")
      if api_title:
        api_file_name = "%s.md" % get_storage_name(text=api_title, max_length=50)
        api_target_path = _target_path(dir_path, post_date, api_file_name)
        if api_target_path != target_path:
          logging.info("Retitling %s as %s", keeper_path, api_title)
          file_name = api_file_name
          target_path = api_target_path
          if not dry_run:
            md_file = MdFile(file_path=keeper_path, frontmatter_type=MdFile.TOML)
            md_file.set_frontmatter_field_value(field_name="title", value=text_utils.title_from_text(text=api_title, num_words=5))
            md_file.set_frontmatter_field_value(field_name="full_title", value=text_utils.title_from_text(text=api_title, num_words=50, target_title_length=200))
    if target_path == keeper_path and str(keeper_metadata.get("date")) == date_str:
      stats["ok"] += 1
      continue
    if not dry_run and os.path.exists(target_path) and os.path.abspath(target_path) != os.path.abspath(keeper_path):
      logging.error("Target already exists, cannot move %s to %s", keeper_path, target_path)
      stats["conflicts"] += 1
      continue
    logging.info("Moving %s -> %s (was %s)", keeper_path, target_path, keeper_metadata.get("date"))
    stats["moved"] += 1
    if not dry_run:
      os.makedirs(os.path.dirname(target_path), exist_ok=True)
      shutil.move(keeper_path, target_path)
      MdFile(file_path=target_path, frontmatter_type=MdFile.TOML).set_frontmatter_field_value(field_name="date", value=date_str)

  if not dry_run:
    for (root, dirs, files) in os.walk(dir_path, topdown=False):
      if root == dir_path:
        continue
      if len(os.listdir(root)) == 0:
        os.rmdir(root)

  logging.info("Archive fix stats for %s : %s", dir_path, stats)
  return stats


def scrape_free_articles_from_index_anchors(url, dir_path, dry_run=False):
  """Scrape all free posts of one or more Substack publications into dir_path.

  Dates and titles are taken from the publication's archive API (rather than scraped off the post
  pages, where the page's own heading/date heuristics can pick up dates mentioned in the text).
  """
  global browser
  if browser is None:
    browser = scraping.get_selenium_chrome(headless=True)
  urls = url if isinstance(url, (list, tuple)) else [url]
  posts = {}
  for publication_url in urls:
    posts.update(get_posts_by_slug(url=publication_url))

  def article_scraper(url, dir_path, dry_run):
    post = posts.get(get_slug_from_url(url), {})
    post_date = post.get("post_date")
    undated = False
    if post_date is not None:
      post_date = parser.parse(post_date)
      if not blog.is_valid_article_date(post_date):
        post_date, undated = None, True
    return blog.scrape_post_markdown(
      url=url, dir_path=dir_path, dry_run=dry_run, entry_css_list=[".single-post", "div.body.markup"], browser=browser,
      date_override=post_date, title_override=post.get("title"), undated=undated)

  for publication_url in urls:
    blog.scrape_index_from_anchors(url=publication_url, dir_path=dir_path, entry_css_list=[], anchor_css_list=['a[data-testid="post-preview-title"]', ".portable-archive-list a"], article_scraper=article_scraper, urlpattern=".*/p/[^/]+/?$", anchor_filter=free_article_filter, browser=browser, dry_run=dry_run)
