import datetime
import os
from collections import namedtuple
from unittest import mock

import pytest
from selenium.common.exceptions import WebDriverException

from curation_utils import scraping

# google_groups launches selenium browsers at import time; stub the factories first.
with mock.patch.object(scraping, "get_selenium_chrome", return_value=None), mock.patch.object(
    scraping, "get_selenium_firefox", return_value=None):
  from doc_curation.mail_stream import google_groups

from doc_curation_projects import mail_stream_dumper

_Msg = namedtuple("_Msg", ["author", "date", "content"])


def _messages():
  return [
    _Msg("a", datetime.datetime(2012, 9, 29, 21, 22, 24), "FIRST-MESSAGE"),
    _Msg("b", datetime.datetime(2012, 9, 30, 10, 0, 0), "SECOND-MESSAGE"),
  ]


def test_dump_sadaasvaada_writes_all_messages(tmp_path):
  dest_dir = str(tmp_path)
  mail_stream_dumper.dump_sadaasvaada(
    messages=_messages(), subject="Sadāsvāda - test edition", dest_dir=dest_dir,
    url="https://groups.google.com/g/sadaswada/c/xyz", dry_run=False)
  files = [f for f in os.listdir(dest_dir) if f.endswith(".md")]
  assert len(files) == 1
  with open(os.path.join(dest_dir, files[0])) as handle:
    content = handle.read()
  assert "FIRST-MESSAGE" in content
  assert "SECOND-MESSAGE" in content


def test_dump_sadaasvaada_dry_run_writes_nothing(tmp_path):
  dest_dir = str(tmp_path)
  mail_stream_dumper.dump_sadaasvaada(
    messages=_messages(), subject="Sadāsvāda - test edition", dest_dir=dest_dir,
    url="https://groups.google.com/g/sadaswada/c/xyz", dry_run=True)
  assert [f for f in os.listdir(dest_dir) if f.endswith(".md")] == []


def test_scrape_with_recovery_retries_after_browser_crash():
  chrome2, firefox2 = mock.Mock(), mock.Mock()
  with mock.patch.object(google_groups, "scrape_threads_backwards", side_effect=[WebDriverException("dead"), []]) as scrape, \
      mock.patch.object(google_groups, "base_browser", mock.Mock()) as old_chrome, \
      mock.patch.object(google_groups, "thread_browser", mock.Mock()) as old_firefox, \
      mock.patch.object(scraping, "get_selenium_chrome", return_value=chrome2), \
      mock.patch.object(scraping, "get_selenium_firefox", return_value=firefox2):
    result = mail_stream_dumper.scrape_with_recovery(url="https://groups.google.com/g/x", dest_dir="/tmp/nope",
                                                     start_url="XYZ-backfill", shard=(2, 5), recovery_delay=0)
  assert result == []
  assert scrape.call_count == 2
  assert scrape.call_args_list[1].kwargs["browser"] is chrome2
  assert scrape.call_args_list[1].kwargs["start_url"] == "XYZ-backfill"
  assert scrape.call_args_list[1].kwargs["shard"] == (2, 5)
  old_chrome.quit.assert_called_once()
  old_firefox.quit.assert_called_once()


def test_scrape_with_recovery_raises_after_max_attempts():
  with mock.patch.object(google_groups, "scrape_threads_backwards", side_effect=WebDriverException("always dead")) as scrape, \
      mock.patch.object(google_groups, "base_browser", mock.Mock()), \
      mock.patch.object(google_groups, "thread_browser", mock.Mock()), \
      mock.patch.object(scraping, "get_selenium_chrome", return_value=mock.Mock()), \
      mock.patch.object(scraping, "get_selenium_firefox", return_value=mock.Mock()), \
      mock.patch.object(mail_stream_dumper.time, "sleep") as sleep:
    with pytest.raises(WebDriverException):
      mail_stream_dumper.scrape_with_recovery(url="https://groups.google.com/g/x", dest_dir="/tmp/nope", max_attempts=2,
                                              recovery_delay=45)
  assert scrape.call_count == 2
  sleep.assert_called_once_with(45)
