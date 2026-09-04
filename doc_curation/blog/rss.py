import datetime

import dateutil.parser as parser
from doc_curation import blog
from curation_utils import scraping
import logging
import os
import re
from pathlib import Path
import feedparser
import requests
import trafilatura

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



def get_rss_url(profile_url: str) -> str:
  """Derive the RSS feed URL from a Medium profile or publication URL."""
  base_url = profile_url.rstrip("/")
  if "medium.com/@" in base_url:
    parts = base_url.split("/")
    username = next((p for p in parts if p.startswith("@")), None)
    if username:
      return f"https://medium.com/feed/{username}"
  elif ".medium.com" in base_url:
    return f"{base_url}/feed"
  return f"{base_url}/feed"

def scrape_medium_blog(profile_url: str, dist_dir: str = "dist_dir"):
  # 1. Create distribution directory if it doesn't exist
  output_path = Path(dist_dir)
  output_path.mkdir(parents=True, exist_ok=True)

  # 2. Parse RSS feed to get list of articles and embedded content
  rss_url = get_rss_url(profile_url)
  print(f"-> Fetching RSS feed from: {rss_url}")

  feed = feedparser.parse(rss_url)
  if not feed.entries:
    print("-> No articles found or unable to access the RSS feed.")
    return

  print(f"-> Found {len(feed.entries)} articles. Processing content...\n")

  for entry in feed.entries:
    title = entry.get("title", "Untitled")
    link = entry.get("link", "")
    date_string = entry.get("published", "Unknown Date")
    date_obj = parser.parse(date_string, fuzzy=True)
    date = datetime.datetime.strftime(date_obj, "%Y-%m-%d")

    if not link:
      continue

    print(f"Processing: {title}")

    try:
      # Medium RSS feeds embed the full article HTML in entry.content
      html_content = ""
      if hasattr(entry, "content") and entry.content:
        html_content = entry.content[0].value
      elif hasattr(entry, "summary"):
        html_content = entry.summary

      if not html_content:
        print(f"   [Warning] No content found in RSS for {link}")
        continue

      # Convert the RSS HTML snippet to Markdown via Trafilatura
      markdown_content = trafilatura.extract(
        html_content,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_images=True
      )
      if not markdown_content:
        logging.warning(f"   [Warning] Could not extract markdown content for {link}")
        continue

      markdown_content = (
        f"{title}  \n{date}  \nSource: [here]({link})\n\n{markdown_content}"
      )

      file_name = blog.file_name_from_url(url=link, max_title_length=50)
      file_path = blog.get_file_path(date_obj=date_obj, dir_path=output_path, file_name=file_name)
      md_file = MdFile(file_path)
      metadata = {"title": title, "date": date, "upstream_url": link}
      md_file.dump_to_file(metadata=metadata, content=markdown_content)
    except Exception as e:
      print(f"   [Error] An exception occurred: {e}")


if __name__ == "__main__":
  # Target profile/publication URL and destination directory
  MEDIUM_PROFILE_URL = "https://satyan-sharma.medium.com/"
  DESTINATION_DIRECTORY = "dist_dir"

  scrape_medium_blog(MEDIUM_PROFILE_URL, DESTINATION_DIRECTORY)