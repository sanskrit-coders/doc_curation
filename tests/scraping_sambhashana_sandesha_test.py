import logging
import os
from unittest import mock

from bs4 import BeautifulSoup

from doc_curation.scraping.misc_sites import sambhashana_sandesha


def _soup(html):
  return BeautifulSoup(html, "html.parser")


def test_dump_month_warns_when_no_articles(tmp_path, caplog):
  login_page = _soup("<html><body>login wall</body></html>")
  with mock.patch.object(sambhashana_sandesha.scraping, "get_soup", return_value=(login_page, None)):
    with caplog.at_level(logging.WARNING):
      sambhashana_sandesha.dump_month("https://sambhashanasandesha.in/openSearchable.php?id=x", str(tmp_path))
  assert [f for f in os.listdir(str(tmp_path)) if f.endswith(".md")] == []
  assert "No article content" in caplog.text


def test_dump_month_writes_article_files(tmp_path):
  html = ("<html><body><div id='showData'>"
          "<div><h1>परीक्षा लेखः</h1><p>विषयः अस्ति।</p></div>"
          "<div><h1>द्वितीयः</h1><p>अन्यः।</p></div>"
          "</div></body></html>")
  with mock.patch.object(sambhashana_sandesha.scraping, "get_soup", return_value=(_soup(html), None)):
    sambhashana_sandesha.dump_month("https://x/month", str(tmp_path))
  files = sorted(f for f in os.listdir(str(tmp_path)) if f.endswith(".md"))
  assert len(files) == 2
  assert files[0].startswith("01_") and files[1].startswith("02_")


def test_dump_year_maps_newest_link_to_latest_month(tmp_path):
  html = "<html><body><a href='m12.php'>Unicode</a><a href='m11.php'>Unicode</a></body></html>"
  with mock.patch.object(sambhashana_sandesha.scraping, "get_soup", return_value=(_soup(html), None)), \
      mock.patch.object(sambhashana_sandesha, "dump_month") as dump_month:
    sambhashana_sandesha.dump_year(2023, str(tmp_path))
  assert dump_month.call_count == 2
  assert dump_month.call_args_list[0].args[1].endswith(os.path.join("2023", "02"))
  assert dump_month.call_args_list[1].args[1].endswith(os.path.join("2023", "01"))
