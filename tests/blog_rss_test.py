import os

from doc_curation.blog import rss
from doc_curation.md.file import MdFile


def _write_archived(dest_dir, rel_path, upstream_url):
  file_path = os.path.join(dest_dir, rel_path)
  os.makedirs(os.path.dirname(file_path), exist_ok=True)
  MdFile(file_path=file_path).dump_to_file(
    metadata={"title": "t", "upstream_url": upstream_url}, content="body", dry_run=False)


def test_normalize_url_strips_query_and_fragment():
  assert rss.normalize_url("https://a.medium.com/slug-hash?source=rss-1") == "https://a.medium.com/slug-hash"
  assert rss.normalize_url("https://a.medium.com/slug-hash?source=user_profile#frag") == "https://a.medium.com/slug-hash"
  assert rss.normalize_url("https://a.medium.com/slug-hash/") == "https://a.medium.com/slug-hash"


def test_get_archived_urls_matches_feed_links_to_archived_posts(tmp_path):
  dest_dir = str(tmp_path)
  # Archived by the older selenium scraper, with its own query string.
  _write_archived(dest_dir, "2026/08/2026-08-11_Old_title.md",
                  "https://satyan-sharma.medium.com/some-slug-dc4f847a6fde?source=user_profile_page---0---5ac5a06ffac---")
  _write_archived(dest_dir, "2026/06/2026-06-04_Other.md", "https://satyan-sharma.medium.com/other-ad3845b90de2")
  archived = rss.get_archived_urls(dest_dir)
  # Same posts as seen in the RSS feed, with the feed's query string, must match.
  assert rss.normalize_url("https://satyan-sharma.medium.com/some-slug-dc4f847a6fde?source=rss-5ac5a06ffac------2") in archived
  assert "https://satyan-sharma.medium.com/other-ad3845b90de2" in archived
  assert "https://satyan-sharma.medium.com/brand-new-084ebffddbec" not in archived


def test_get_archived_urls_missing_dir(tmp_path):
  assert rss.get_archived_urls(os.path.join(str(tmp_path), "no-such-dir")) == set()
