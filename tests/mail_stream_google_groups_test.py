import os
from unittest import mock

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

from curation_utils import scraping

# google_groups launches selenium browsers at import time; stub the factories first.
with mock.patch.object(scraping, "get_selenium_chrome", return_value=None), mock.patch.object(
    scraping, "get_selenium_firefox", return_value=None):
  from doc_curation.mail_stream import google_groups


def _write_message(dest_dir, date_path, thread_dir, file_name, thread_id=None):
  file_path = os.path.join(dest_dir, date_path, thread_dir, file_name)
  os.makedirs(os.path.dirname(file_path), exist_ok=True)
  if thread_id is None:
    content = "[[author\t2022-01-01, 10:00:00]]\n\nbody without a source link\n"
  else:
    content = (
        "[[author\t2022-01-01, 10:00:00 "
        f"[Source](https://groups.google.com/g/testgroup/c/{thread_id})]]\n\nbody\n")
  with open(file_path, "w") as handle:
    handle.write(content)
  return file_path


def _seed_archive(dest_dir, *thread_ids):
  for index, thread_id in enumerate(thread_ids):
    _write_message(dest_dir, "2022/01", f"0{index + 1}", "thread/000_a.md", thread_id)
  return dest_dir


def test_get_archived_message_counts(tmp_path):
  dest_dir = str(tmp_path)
  _write_message(dest_dir, "2022/01/01", "thread", "000_a.md", "AAA")
  _write_message(dest_dir, "2022/01/01", "thread", "001_b.md", "AAA")
  _write_message(dest_dir, "2022/01/02", "thread", "000_a.md", "BBB?pli=1")
  _write_message(dest_dir, "2022/01/03", "thread", "000_a.md", None)
  assert google_groups.get_archived_message_counts(dest_dir) == {"AAA": 2, "BBB": 1}


def test_get_archived_message_counts_missing_dir(tmp_path):
  assert google_groups.get_archived_message_counts(os.path.join(str(tmp_path), "no-such-dir")) == {}


def test_parse_listed_message_count():
  from bs4 import BeautifulSoup
  assert google_groups.parse_listed_message_count(BeautifulSoup(
    '<div><a href="/g/x/c/AAA">t</a><span aria-label="it has 112 messages">112</span></div>',
    features="lxml")) == 112
  assert google_groups.parse_listed_message_count(BeautifulSoup(
    '<div><a href="/g/x/c/AAA">t</a><span aria-label="it has 1 message">1</span></div>',
    features="lxml")) == 1
  assert google_groups.parse_listed_message_count(BeautifulSoup(
    '<div><a href="/g/x/c/AAA">t</a></div>', features="lxml")) is None


def test_redumps_grown_thread(tmp_path):
  dest_dir = _seed_archive(str(tmp_path), "AAA")
  browser = _FakeBrowser(pages=[[("/g/x/c/AAA", 5)]])
  dumper = mock.Mock()
  with mock.patch.object(google_groups, "get_thread_messages_selenium", return_value=([], "Subject")) as fetch:
    failed = google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                                           dumper=dumper, browser=browser, page_timeout=0)
  assert fetch.call_count == 1
  assert dumper.call_count == 1
  assert failed == []


def _write_dated_message(dest_dir, file_name, thread_id, date_str):
  file_path = os.path.join(dest_dir, file_name)
  os.makedirs(os.path.dirname(file_path), exist_ok=True)
  with open(file_path, "w") as handle:
    handle.write(
      "[[author\t%s, 10:00:00 [Source](https://groups.google.com/g/testgroup/c/%s)]]\n\nbody\n"
      % (date_str, thread_id))


def test_parse_listed_activity_date():
  import datetime
  from bs4 import BeautifulSoup
  parse = google_groups.parse_listed_activity_date
  now = datetime.datetime(2026, 11, 14, 12, 0, 0)

  def row(html):
    return BeautifulSoup(html, features="lxml")

  assert parse(row("<div><span>Nov 13</span></div>"), now=now) == datetime.date(2026, 11, 13)
  assert parse(row("<div><span>Dec 20</span></div>"), now=datetime.datetime(2026, 1, 5)) == datetime.date(2025, 12, 20)
  assert parse(row("<div><span>11/14/25</span></div>"), now=now) == datetime.date(2025, 11, 14)
  assert parse(row("<div><span>10/16/21</span></div>"), now=now) == datetime.date(2021, 10, 16)
  assert parse(row("<div><span>Oct 17, 2021</span></div>"), now=now) == datetime.date(2021, 10, 17)
  # Snippet traps: author+count look like "Junaid 7"; "3/4/40" is year 2040.
  assert parse(row("<div><span>Junaid</span><span>7</span></div>"), now=now) is None
  assert parse(row("<div><span>3/4/40</span></div>"), now=now) is None
  assert parse(row("<div><a>t</a></div>"), now=now) is None
  # The activity date is the last date-like token, after any snippet dates.
  assert parse(row("<div><span>met on Nov 1</span><span>Nov 13</span></div>"), now=now) == datetime.date(2026, 11, 13)


def test_find_oldest_gap():
  import datetime
  D = datetime.date
  find_oldest_gap = google_groups.find_oldest_gap
  assert find_oldest_gap([D(2020, 9, 12), D(2020, 9, 1), D(2026, 11, 13)]) == (D(2020, 9, 12), D(2026, 11, 13))
  assert find_oldest_gap([D(2026, 11, 13), D(2026, 11, 10), D(2026, 11, 1)]) is None
  assert find_oldest_gap([]) is None


def test_cutoff_for_run():
  import datetime
  D = datetime.date
  today = D(2026, 11, 14)
  cutoff_for_run = google_groups.cutoff_for_run
  gap_dates = [D(2020, 9, 12), D(2020, 9, 1), D(2026, 11, 13)]
  dense_dates = [D(2026, 11, 13), D(2026, 11, 10), D(2026, 11, 1)]
  # Catch-up with no marker: oldest gap anchors the bound.
  assert cutoff_for_run(gap_dates, None, today=today) == D(2020, 9, 5)
  # Fresh or young-only archive: full walk.
  assert cutoff_for_run([D(2026, 11, 13), D(2026, 11, 10)], None, today=today) is None
  assert cutoff_for_run([], None, today=today) is None
  # Steady state: last clean completion anchors the bound.
  assert cutoff_for_run(dense_dates, {"completed_on": D(2026, 11, 7), "cutoff_used": D(2026, 10, 30)}, today=today) == D(2026, 10, 31)
  # Gaps already verified by a bounded run are ignored...
  idle_dates = [D(2024, 6, 1), D(2024, 8, 1), D(2026, 11, 13)]
  assert cutoff_for_run(idle_dates, {"completed_on": D(2026, 11, 13), "cutoff_used": D(2026, 10, 26)}, today=today) == D(2026, 11, 6)
  # ...but gaps ending past the verified point are still honored (takes min).
  assert cutoff_for_run(idle_dates, {"completed_on": D(2026, 11, 13), "cutoff_used": D(2024, 1, 1)}, today=today) == D(2024, 5, 25)
  # A full-walk marker yields to the marker bound, never the gap.
  assert cutoff_for_run(gap_dates, {"completed_on": D(2026, 11, 13), "cutoff_used": None}, today=today) == D(2026, 11, 6)
  # Stale tail (dense archive ending years ago): newest minus overlap.
  old_dense = [D(2022, 4, 1), D(2022, 3, 28), D(2022, 3, 20)]
  assert cutoff_for_run(old_dense, None, today=today) == D(2022, 3, 25)
  # Tail and marker combine by min.
  assert cutoff_for_run(old_dense, {"completed_on": D(2026, 11, 13), "cutoff_used": None}, today=today) == D(2022, 3, 25)


def test_completion_marker_roundtrip(tmp_path):
  import datetime
  dest_dir = str(tmp_path)
  assert google_groups.load_completion_marker(dest_dir) is None
  google_groups.save_completion_marker(dest_dir, datetime.date(2026, 11, 6))
  assert google_groups.load_completion_marker(dest_dir) == {
    "completed_on": datetime.date.today(), "cutoff_used": datetime.date(2026, 11, 6)}
  with open(os.path.join(dest_dir, google_groups.MARKER_FILE_NAME), "w") as handle:
    handle.write("garbage")
  assert google_groups.load_completion_marker(dest_dir) is None


def test_marker_saved_on_clean_completion(tmp_path):
  import datetime
  dest_dir = _seed_archive(str(tmp_path), "AAA", "BBB")
  browser = _two_page_browser()
  google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                               browser=browser, page_timeout=0)
  assert google_groups.load_completion_marker(dest_dir)["completed_on"] == datetime.date.today()


def test_scan_archive_collects_counts_and_dates(tmp_path):
  dest_dir = str(tmp_path)
  _write_dated_message(dest_dir, "2022/01/01/t/000_a.md", "AAA", "2022-01-01")
  _write_dated_message(dest_dir, "2022/01/01/t/001_b.md", "AAA", "2022-06-01")
  _write_dated_message(dest_dir, "2022/01/02/t/000_a.md", "BBB", "2021-05-05")
  (counts, dates) = google_groups.scan_archive(dest_dir)
  assert counts == {"AAA": 2, "BBB": 1}
  assert sorted(dates)[-1].isoformat() == "2022-06-01"


def test_stops_at_thread_older_than_cutoff(tmp_path):
  dest_dir = str(tmp_path)
  _write_dated_message(dest_dir, "2026/01/01/t/000_a.md", "ZZZ", "2026-01-01")
  _write_dated_message(dest_dir, "2025/01/01/t/000_a.md", "YYY", "2025-01-01")
  # Cutoff = 2025-01-01 - 7d = 2024-12-25. AAA (2026) is dumped; BBB (2020) stops the walk.
  browser = _FakeBrowser(pages=[[("/g/x/c/AAA", 5, "Nov 13, 2026")], [("/g/x/c/BBB", 2, "Jan 5, 2020")]])
  dumper = mock.Mock()
  with mock.patch.object(google_groups, "get_thread_messages_selenium", return_value=([], "Subject")) as fetch:
    failed = google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                                           dumper=dumper, browser=browser, page_timeout=0)
  assert [call.kwargs["url"] for call in dumper.call_args_list] == ["https://groups.google.com/g/x/c/AAA"]
  assert fetch.call_count == 1
  assert failed == []
  assert browser.reads == 3
  assert browser.max_page == 1


class _FakeSection:
  def __init__(self, inner_html):
    self._inner_html = inner_html

  def get_attribute(self, name):
    assert name == "innerHTML"
    return self._inner_html


class _FakeThreadBrowser:
  def __init__(self, subject, sections):
    self._subject = subject
    self._sections = sections

  def get(self, url):
    pass

  def find_element(self, value=None, by=None):
    if value == "h1":
      return mock.Mock(text=self._subject)
    raise NoSuchElementException("no expand link")

  def find_elements(self, by=None, value=None):
    return [_FakeSection(html) for html in self._sections]


def test_thread_leading_authorless_section_does_not_crash():
  browser = _FakeThreadBrowser("Subject", [
    "<div><span>Nov 13, 2026, 10:00 AM</span><div role='region'><p>system notice</p></div></div>",
    "<div><h3>Author A</h3><span>Nov 13, 2026, 11:00 AM</span><div role='region'><p>hello</p></div></div>",
  ])
  (messages, subject) = google_groups.get_thread_messages_selenium(url="https://x/t", browser=browser)
  assert subject == "Subject"
  assert len(messages) == 2
  assert messages[0].author == "UNKNOWN_AUTHOR"
  assert "system notice" in messages[0].content
  assert messages[1].author == "Author A"


def test_thread_without_sections_returns_empty():
  browser = _FakeThreadBrowser("Subject", [])
  (messages, subject) = google_groups.get_thread_messages_selenium(url="https://x/t", browser=browser)
  assert (messages, subject) == ([], "Subject")


def test_dump_messages_handles_datetimeless_first_message(tmp_path):
  import datetime
  Message = google_groups.Message
  messages = [
    Message(author="UNKNOWN_AUTHOR", date=None, content="[[UNKNOWN_AUTHOR\tUNKNOWN_DATE]]\n\nnotice"),
    Message(author="A", date=datetime.datetime(2026, 11, 13, 10, 0, 0), content="[[A\t2026-11-13]]\n\nhello"),
  ]
  google_groups.dump_messages_to_files(messages=messages, subject="Some Subject", dest_dir=str(tmp_path),
                                       url="https://groups.google.com/g/x/c/THREADID", dry_run=False)
  files = []
  for root, _, names in os.walk(str(tmp_path)):
    files.extend(os.path.join(root, n) for n in names if n.endswith(".md"))
  assert len(files) == 2
  assert all("/2026/11/13/" in f for f in files)


def test_dump_messages_all_dateless_goes_undated(tmp_path):
  Message = google_groups.Message
  messages = [Message(author="UNKNOWN_AUTHOR", date=None, content="[[UNKNOWN_AUTHOR\tUNKNOWN_DATE]]\n\nnotice")]
  google_groups.dump_messages_to_files(messages=messages, subject="Some Subject", dest_dir=str(tmp_path),
                                       url="https://groups.google.com/g/x/c/THREADID", dry_run=False)
  files = []
  for root, _, names in os.walk(str(tmp_path)):
    files.extend(os.path.join(root, n) for n in names if n.endswith(".md"))
  assert len(files) == 1
  assert "/undated/" in files[0]


def test_dump_messages_empty_list_does_not_crash(tmp_path):
  google_groups.dump_messages_to_files(messages=[], subject="S", dest_dir=str(tmp_path),
                                       url="https://groups.google.com/g/x/c/ZZZ", dry_run=False)
  assert [f for f in os.listdir(str(tmp_path)) if f.endswith(".md")] == []


def test_dumper_exception_does_not_abort_run(tmp_path):
  browser = _FakeBrowser(pages=[["/g/x/c/AAA"]])
  dumper = mock.Mock(side_effect=RuntimeError("disk on fire"))
  with mock.patch.object(google_groups, "get_thread_messages_selenium", return_value=([], "Subject")):
    failed = google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=str(tmp_path),
                                                     dumper=dumper, browser=browser, page_timeout=0)
  assert dumper.call_count == 1
  assert failed == ["https://groups.google.com/g/x/c/AAA"]
  assert google_groups.load_completion_marker(str(tmp_path)) is None


def test_backfill_start_skips_until_match_and_ignores_cutoff(tmp_path):
  dest_dir = str(tmp_path)
  _write_dated_message(dest_dir, "2026/01/01/t/000_a.md", "ZZZ", "2026-01-01")
  _write_dated_message(dest_dir, "2025/01/01/t/000_a.md", "YYY", "2025-01-01")
  # Cutoff would be 2024-12-25, but start_url disables it: BBB (Jan 2020) is
  # skipped positionally, not stopped at, and AAA is dumped.
  browser = _FakeBrowser(pages=[[("/g/x/c/BBB", 2, "Jan 5, 2020")], [("/g/x/c/AAA", 5, "Nov 13, 2026")]])
  dumper = mock.Mock()
  with mock.patch.object(google_groups, "get_thread_messages_selenium", return_value=([], "Subject")) as fetch:
    failed = google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                                                     dumper=dumper, browser=browser, page_timeout=0,
                                                     start_url="AAA")
  assert [call.kwargs["url"] for call in dumper.call_args_list] == ["https://groups.google.com/g/x/c/AAA"]
  assert fetch.call_count == 1
  assert failed == []
  assert browser.reads == 4
  assert browser.max_page == 1


def test_shard_partitions_threads_deterministically(tmp_path):
  import hashlib
  # Pinned: sharding must stay hashlib-based (stable across processes), never hash().
  assert int(hashlib.md5(b"https://groups.google.com/g/x/c/DDD").hexdigest(), 16) % 2 == 1
  assert int(hashlib.md5(b"https://groups.google.com/g/x/c/EEE").hexdigest(), 16) % 2 == 0
  dumped = {}
  for index in (0, 1):
    browser = _FakeBrowser(pages=[["/g/x/c/DDD", "/g/x/c/EEE"]])
    dumper = mock.Mock()
    with mock.patch.object(google_groups, "get_thread_messages_selenium", return_value=([], "Subject")):
      failed = google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=str(tmp_path),
                                                       dumper=dumper, browser=browser, page_timeout=0,
                                                       shard=(index, 2))
    assert failed == []
    dumped[index] = sorted(call.kwargs["url"] for call in dumper.call_args_list)
  assert dumped[0] == ["https://groups.google.com/g/x/c/EEE"]
  assert dumped[1] == ["https://groups.google.com/g/x/c/DDD"]


def test_backfill_start_match_detected_regardless_of_shard(tmp_path):
  # AAA hashes to shard 0 mod 2; shard 1 must still detect the match (else it
  # would falsely report backfill-start-never-found) while not dumping it.
  browser = _FakeBrowser(pages=[[("/g/x/c/AAA", 5, "Nov 13, 2026")]])
  dumper = mock.Mock()
  with mock.patch.object(google_groups, "get_thread_messages_selenium") as fetch:
    failed = google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=str(tmp_path),
                                                     dumper=dumper, browser=browser, page_timeout=0,
                                                     start_url="AAA", shard=(1, 2))
  assert fetch.call_count == 0
  assert dumper.call_count == 0
  assert failed == []


def test_backfill_start_never_matching_fails_loudly(tmp_path):
  dest_dir = str(tmp_path)
  browser = _two_page_browser()
  dumper = mock.Mock()
  with mock.patch.object(google_groups, "get_thread_messages_selenium") as fetch:
    failed = google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                                                     dumper=dumper, browser=browser, page_timeout=0,
                                                     start_url="ZZZ-no-such-thread")
  assert fetch.call_count == 0
  assert dumper.call_count == 0
  assert failed == ["backfill-start:ZZZ-no-such-thread"]
  assert google_groups.load_completion_marker(dest_dir) is None


def test_warns_when_dumped_count_mismatches_listing(tmp_path, caplog):
  import logging
  dest_dir = str(tmp_path)  # Empty archive: everything is fetched.
  browser = _FakeBrowser(pages=[[("/g/x/c/AAA", 5)]])
  dumper = mock.Mock()
  with mock.patch.object(google_groups, "get_thread_messages_selenium",
                         return_value=([mock.Mock(), mock.Mock(), mock.Mock()], "Subject")):
    with caplog.at_level(logging.WARNING):
      failed = google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                                             dumper=dumper, browser=browser, page_timeout=0)
  assert dumper.call_count == 1
  assert failed == []
  assert "but listing shows 5" in caplog.text


def test_skips_ungrown_thread(tmp_path):
  dest_dir = str(tmp_path)
  _write_message(dest_dir, "2022/01/01", "thread", "000_a.md", "AAA")
  _write_message(dest_dir, "2022/01/01", "thread", "001_b.md", "AAA")
  browser = _FakeBrowser(pages=[[("/g/x/c/AAA", 2)]])
  dumper = mock.Mock()
  with mock.patch.object(google_groups, "get_thread_messages_selenium") as fetch:
    failed = google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                                           dumper=dumper, browser=browser, page_timeout=0)
  assert fetch.call_count == 0
  assert dumper.call_count == 0
  assert failed == []


class _FakeTag:
  def __init__(self, inner_html):
    self._inner_html = inner_html

  def get_attribute(self, name):
    assert name == "innerHTML"
    return self._inner_html


class _FakeButton:
  def __init__(self, aria_disabled=None):
    self._aria_disabled = aria_disabled

  def get_attribute(self, name):
    if name == "aria-disabled":
      return self._aria_disabled
    return None


class _FlakyTag:
  def get_attribute(self, name):
    raise StaleElementReferenceException("stale row")


class _FakeBrowser:
  """Two-page group listing; Next clicks stick on the last page."""

  def __init__(self, pages, aria_disabled_flags=None, max_reads=20, script=None, cycle=False):
    self._pages = pages
    self._aria_disabled_flags = aria_disabled_flags or [None] * len(pages)
    self._max_reads = max_reads
    # Optional scripted reads consumed before live pages; None = stale-raising row.
    self._script = list(script or [])
    self._cycle = cycle
    self.page_index = 0
    self.reads = 0
    self.max_page = 0

  def get(self, url):
    pass

  def _tag_for(self, entry):
    if entry is None:
      return _FlakyTag()
    if isinstance(entry, tuple):
      (href, count) = entry[:2]
      date_span = f"<span>{entry[2]}</span>" if len(entry) > 2 else ""
      return _FakeTag(
        f'<div><a href="{href}">t</a>'
        f'<span aria-label="it has {count} messages">{count}</span>{date_span}</div>')
    return _FakeTag(f'<div><a href="{entry}">t</a></div>')

  def find_elements(self, by=None, value=None):
    self.reads += 1
    assert self.reads <= self._max_reads, "pagination did not terminate"
    self.max_page = max(self.max_page, self.page_index)
    if self._script:
      entries = self._script.pop(0)
    else:
      entries = self._pages[self.page_index]
    return [self._tag_for(entry) for entry in entries]

  def find_element(self, value=None, by=None):
    return _FakeButton(aria_disabled=self._aria_disabled_flags[self.page_index])

  def execute_script(self, script, button):
    if self._cycle:
      self.page_index = (self.page_index + 1) % len(self._pages)
    elif self.page_index < len(self._pages) - 1:
      self.page_index += 1
    # Else stuck on the last page: the click is a no-op.


def _two_page_browser(**kwargs):
  return _FakeBrowser(pages=[["/g/x/c/AAA"], ["/g/x/c/BBB"]], **kwargs)


def test_pagination_stops_on_repeated_last_page(tmp_path):
  dest_dir = _seed_archive(str(tmp_path), "AAA", "BBB")
  # Broken-markup case from the TODO: aria-disabled never appears and the click
  # on the last page is a no-op, so the post-click wait times out.
  # All listed threads are seeded as archived, so no thread page is ever fetched.
  browser = _two_page_browser()
  with mock.patch.object(google_groups, "get_thread_messages_selenium") as fetch:
    failed = google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                                           browser=browser, page_timeout=0)
  assert fetch.call_count == 0
  assert failed == []
  assert browser.max_page == 1
  assert browser.reads == 4


def test_pagination_advances_through_pages(tmp_path):
  dest_dir = _seed_archive(str(tmp_path), "AAA", "BBB", "CCC")
  browser = _FakeBrowser(pages=[["/g/x/c/AAA"], ["/g/x/c/BBB"], ["/g/x/c/CCC"]],
                         aria_disabled_flags=[None, None, "true"])
  google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                               browser=browser, page_timeout=0)
  assert browser.max_page == 2
  assert browser.reads == 5


def test_page_change_wait_polls_until_listing_updates(tmp_path):
  dest_dir = _seed_archive(str(tmp_path), "AAA", "BBB")
  browser = _FakeBrowser(pages=[["/g/x/c/BBB"]], script=[["/g/x/c/AAA"], ["/g/x/c/AAA"]])
  google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                               browser=browser, page_timeout=1)
  # A single-check wait would stop after 2 reads; polling reaches the updated
  # listing (4+ reads) and the tail timeout adds more. Upper bound is max_reads.
  assert browser.reads >= 6


def test_cycling_pages_stop_via_stall_limit(tmp_path):
  dest_dir = _seed_archive(str(tmp_path), "AAA", "BBB")
  browser = _FakeBrowser(pages=[["/g/x/c/AAA"], ["/g/x/c/BBB"]], cycle=True)
  google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                               browser=browser, page_timeout=0)
  assert browser.reads == 7
  assert google_groups.load_completion_marker(dest_dir) is None


def test_pagination_stops_when_next_disabled(tmp_path):
  dest_dir = _seed_archive(str(tmp_path), "AAA", "BBB")
  browser = _two_page_browser(aria_disabled_flags=[None, "true"])
  google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                               browser=browser, page_timeout=0)
  assert browser.max_page == 1
  assert browser.reads == 3


def test_pagination_stops_when_next_button_missing(tmp_path):
  dest_dir = _seed_archive(str(tmp_path), "AAA", "BBB")
  browser = _two_page_browser()
  browser.find_element = mock.Mock(side_effect=NoSuchElementException("no next button"))
  google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                               browser=browser, page_timeout=0)
  assert browser.reads == 1


def test_is_next_page_disabled():
  assert google_groups.is_next_page_disabled(_FakeButton(aria_disabled="true")) is True
  assert google_groups.is_next_page_disabled(_FakeButton(aria_disabled="false")) is False
  assert google_groups.is_next_page_disabled(_FakeButton(aria_disabled=None)) is False


def test_stale_row_rereads_page_and_terminates(tmp_path):
  dest_dir = _seed_archive(str(tmp_path), "AAA")
  browser = _FakeBrowser(pages=[["/g/x/c/AAA"]], script=[[None]])
  google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                               browser=browser, page_timeout=0)
  # Initial read, one re-read after the stale row, then the wait times out.
  assert browser.reads == 3


def test_stale_row_recovery_still_skips_archived(tmp_path):
  hrefs = ["/g/x/c/XXX", "/g/x/c/AAA", "/g/x/c/BBB"]
  browser = _FakeBrowser(pages=[hrefs], script=[hrefs[:2] + [None]])
  dest_dir = _seed_archive(str(tmp_path), "XXX")
  dumper = mock.Mock()
  with mock.patch.object(google_groups, "get_thread_messages_selenium", return_value=([], "Subject")):
    google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                                 dumper=dumper, browser=browser, page_timeout=0)
  dumped_urls = [call.kwargs["url"] for call in dumper.call_args_list]
  assert dumped_urls, "expected threads to be dumped"
  # XXX is archived: skipped on the first pass and still skipped after recovery.
  assert all(not url.endswith("/XXX") for url in dumped_urls)
  assert any(url.endswith("/AAA") for url in dumped_urls)
  assert any(url.endswith("/BBB") for url in dumped_urls)


def test_stale_next_button_does_not_crash(tmp_path):
  dest_dir = _seed_archive(str(tmp_path), "AAA", "BBB")
  browser = _two_page_browser()
  real_find_element = browser.find_element
  browser.find_element = mock.Mock(side_effect=[
    StaleElementReferenceException("stale button"),
    StaleElementReferenceException("stale button"),
    real_find_element(), real_find_element(), real_find_element()])
  google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                               browser=browser, page_timeout=0)
  assert browser.reads == 3


def test_thread_fetch_retries_with_fresh_browser():
  from selenium.common.exceptions import WebDriverException
  browser = _FakeBrowser(pages=[["/g/x/c/AAA"]])
  dumper = mock.Mock()
  old_browser = mock.Mock()
  fresh_browser = mock.Mock()
  with mock.patch.object(google_groups, "thread_browser", old_browser), \
      mock.patch.object(scraping, "get_selenium_firefox", return_value=fresh_browser), \
      mock.patch.object(google_groups, "get_thread_messages_selenium",
                        side_effect=[WebDriverException("marionette down"), ([], "Subject")]) as fetch, \
      mock.patch.object(google_groups.time, "sleep"):
    google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir="/tmp/nope",
                                 dumper=dumper, browser=browser, page_timeout=0)
  assert fetch.call_count == 2
  assert fetch.call_args_list[0].kwargs["browser"] is old_browser
  assert fetch.call_args_list[1].kwargs["browser"] is fresh_browser
  old_browser.quit.assert_called_once()
  assert dumper.call_count == 1


def test_persistent_thread_failure_does_not_abort_run(tmp_path):
  from selenium.common.exceptions import WebDriverException
  dest_dir = str(tmp_path)
  browser = _FakeBrowser(pages=[["/g/x/c/AAA", "/g/x/c/BBB"]])
  dumper = mock.Mock()
  with mock.patch.object(google_groups, "thread_browser", mock.Mock()), \
      mock.patch.object(scraping, "get_selenium_firefox", return_value=mock.Mock()), \
      mock.patch.object(google_groups, "get_thread_messages_selenium",
                        side_effect=WebDriverException("always down")) as fetch, \
      mock.patch.object(google_groups.time, "sleep"):
    failed = google_groups.scrape_threads_backwards(url="https://groups.google.com/g/x", dest_dir=dest_dir,
                                           dumper=dumper, browser=browser, page_timeout=0)
  assert fetch.call_count == 6
  assert dumper.call_count == 0
  assert browser.reads == 2
  assert len(failed) == 2
  assert google_groups.load_completion_marker(dest_dir) is None
