import datetime
import hashlib
import json
import logging
import os
import time
from collections import namedtuple
from urllib.parse import urljoin

from dateutil import parser
import regex
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.remote_connection import LOGGER

from curation_utils import scraping, file_helper
from doc_curation.ebook import pandoc_helper
from doc_curation.md.file import MdFile

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


# GROUPS_HEADLESS=1 runs both browsers headless (for parallel shard workers).
HEADLESS = os.environ.get("GROUPS_HEADLESS", "") == "1"
base_browser = scraping.get_selenium_chrome(headless=HEADLESS)
thread_browser = scraping.get_selenium_firefox(headless=HEADLESS)

Message = namedtuple(typename="Message", field_names=["author", "date", "content"])



def get_date(soup):
  span_tags = soup.select('span')
  date_tags = list(filter(lambda x: regex.match(r"^[A-Z][a-z][a-z] \d+, \d\d\d\d,.+", x.text.strip()) , span_tags))
  if len(date_tags) == 0:
    date_tags = list(filter(lambda x: regex.match(r"^\d+:\d+", x.text.strip()) , span_tags))
  if len(date_tags) == 0:
    return None
  date_str = regex.sub("\(.+?\)", "", date_tags[0].text.strip())
  dt = parser.parse(date_str, fuzzy=True)
  return dt


def get_thread_messages_selenium(url, browser=thread_browser):
  # Expanding threads forces us to click and trigger javascript loading. Hence we then use selenium, rather than soup.
  browser.get(url=url)
  try:
    expand_link = browser.find_element(value="", by=By.LINK_TEXT)
    expand_link.click()
  except NoSuchElementException:
    pass
  subject = browser.find_element(value="h1", by=By.CSS_SELECTOR).text
  section_tags = browser.find_elements(by=By.CSS_SELECTOR, value="section")
  thread_dir = None
  messages = []
  for index, section in enumerate(section_tags):
    section_html = section.get_attribute('innerHTML')
    soup = BeautifulSoup(section_html, features="html.parser")
    dt = get_date(soup=soup)

    author_tag = soup.select_one("h3")
    author = "UNKNOWN_AUTHOR"
    if author_tag is None:
      # Section within a message. As in https://groups.google.com/g/bvparishat/c/eHLaHN4heY4
      if not messages:
        # Leading author-less section (e.g. a system notice); keep it as its own message.
        date_str = dt.strftime('%Y-%m-%d, %H:%M:%S') if dt is not None else "UNKNOWN_DATE"
        content = f"[[{author}\t{date_str} [Source]({url})]]\n\n{soup.text}"
        messages.append(Message(author=author, content=content, date=dt))
      else:
        messages[-1] = messages[-1]._replace(content=f"{messages[-1].content}\n\n{soup.text}")
      continue
    else:
      author = author_tag.text
    message_tag = soup.select_one("div[role='region']")
    message_html = None
    try:
      message_html = str(message_tag)
      content = pandoc_helper.get_md_with_pandoc(content_in=message_html, source_format="html")
    except RecursionError:
      #   https://bugs.launchpad.net/beautifulsoup/+bug/1967610
      logging.warning(f"Infinite recursion : {url}")
      content = message_tag.text
    date_str = "UNKNOWN_DATE"
    if dt is not None:
      date_str = dt.strftime('%Y-%m-%d, %H:%M:%S')
    else:
      logging.warning(f"None date for message {index}: {url} ")
    content = f"[[{author}\t{date_str} [Source]({url})]]\n\n{content}"
    message = Message(author=author, content=content, date=dt)
    messages.append(message)
  if messages:
    thread_header = messages[0].content.split('\n')[0]
    logging.info(f"Thread {thread_header}")
  else:
    logging.warning(f"No messages found in {url}")
  return (messages, subject)


def dump_messages_to_files(messages, subject, dest_dir, url, dry_run=False):
  if not messages:
    logging.warning(f"No messages to dump for {url}")
    return
  dated_messages = [message for message in messages if message.date is not None]
  thread_subdir = "%s__%s" % (file_helper.get_storage_name(subject), os.path.basename(url)[:2])
  if dated_messages:
    first = dated_messages[0]
    thread_dir = os.path.join(dest_dir, str(first.date.year), "%02d" % first.date.month, "%02d" % first.date.day, thread_subdir)
  else:
    thread_dir = os.path.join(dest_dir, "undated", thread_subdir)
  for index, message in enumerate(messages):
    title = "%03d %s" % (index, message.author)
    md_file = MdFile(file_path=os.path.join(thread_dir, file_helper.get_storage_name(title) + ".md"))
    md_file.dump_to_file(content=message.content, metadata={"title": title}, dry_run=dry_run)


def dump_messages_by_subject(messages, subject, dest_dir, url, dry_run=False):
  md_file = MdFile(file_path=os.path.join(dest_dir, file_helper.get_storage_name(subject) + ".md"))
  content = ""
  for index, message in enumerate(messages):
    title = "%03d %s" % (index, message.author)
    content = f"{content}\n\n## {title}\n{message.content}"
  md_file.dump_to_file(content=message.content, metadata={"title": subject}, dry_run=dry_run)


def get_thread_id_from_url(url):
  return regex.sub(r"[?#].*$", "", url.rstrip("/")).rsplit("/", 1)[-1]


def scan_archive(dest_dir):
  """(thread_id -> archived message count, list of archived message dates)."""
  counts = {}
  dates = []
  if not os.path.isdir(dest_dir):
    return (counts, dates)
  for root, _, files in os.walk(dest_dir):
    for file_name in files:
      if not file_name.endswith(".md"):
        continue
      try:
        with open(os.path.join(root, file_name)) as handle:
          content = handle.read()
      except OSError:
        continue
      # Only the first link: the header line. Quoted bodies may link elsewhere.
      source_match = regex.search(r"\[Source\]\((https://groups\.google\.com[^)]+)\)", content)
      if source_match is not None:
        thread_id = get_thread_id_from_url(source_match.group(1))
        counts[thread_id] = counts.get(thread_id, 0) + 1
      date_match = regex.search(r"\[\[[^\]]*?(\d{4}-\d{2}-\d{2}), \d{2}:\d{2}:\d{2}", content)
      if date_match is not None:
        try:
          dates.append(datetime.datetime.strptime(date_match.group(1), "%Y-%m-%d").date())
        except ValueError:
          pass
  return (counts, dates)


def get_archived_message_counts(dest_dir):
  """Map of archived thread id -> number of archived message files.

  The group listing is ordered by recent activity, not chronology, so resuming
  from a positional start thread would skip unarchived threads listed ahead of
  it. Skipping by archive membership instead is correct under any listing order.
  """
  return scan_archive(dest_dir)[0]


MARKER_FILE_NAME = ".groups_scrape_state.json"


def find_oldest_gap(dates, gap_days=14):
  """Oldest (start, end) span without archived messages; None if dates are dense."""
  unique_dates = sorted(set(dates))
  for (start, end) in zip(unique_dates, unique_dates[1:]):
    if (end - start).days > gap_days:
      return (start, end)
  return None


def load_completion_marker(dest_dir):
  """Last clean-completion record {"completed_on", "cutoff_used"} (dates), or None."""
  path = os.path.join(dest_dir, MARKER_FILE_NAME)
  try:
    with open(path) as handle:
      data = json.load(handle)
    completed_on = datetime.datetime.strptime(data["completed_on"], "%Y-%m-%d").date()
    cutoff_used = data.get("cutoff_used")
    if cutoff_used is not None:
      cutoff_used = datetime.datetime.strptime(cutoff_used, "%Y-%m-%d").date()
    return {"completed_on": completed_on, "cutoff_used": cutoff_used}
  except (OSError, ValueError, KeyError):
    return None


def save_completion_marker(dest_dir, cutoff_used):
  """Record a clean completion (full listing verified) for the next run's bound."""
  if not os.path.isdir(dest_dir):
    return
  data = {
    "completed_on": datetime.date.today().isoformat(),
    "cutoff_used": cutoff_used.isoformat() if cutoff_used is not None else None,
  }
  tmp_path = os.path.join(dest_dir, MARKER_FILE_NAME + ".tmp")
  with open(tmp_path, "w") as handle:
    handle.write(json.dumps(data))
  os.replace(tmp_path, os.path.join(dest_dir, MARKER_FILE_NAME))


def cutoff_for_run(dates, marker, gap_days=14, overlap_days=7, stale_days=30, today=None):
  """Stop boundary for this run; None = walk the full listing.

  Combines the oldest archive gap (catch-up signal), a stale tail (archive
  newest weeks behind today), and the last clean completion (steady-state
  signal), taking the oldest bound, so every failure mode degrades to walking
  more, never to skipping unarchived threads. Gaps already verified by a
  previous bounded run are ignored.
  """
  if today is None:
    today = datetime.date.today()
  candidates = []
  verified_through = datetime.date.min
  if marker is not None:
    if marker["cutoff_used"] is None:
      verified_through = datetime.date.max
    else:
      verified_through = marker["cutoff_used"]
    candidates.append(marker["completed_on"] - datetime.timedelta(days=overlap_days))
  gap = find_oldest_gap(dates, gap_days=gap_days)
  if gap is not None and gap[1] > verified_through:
    candidates.append(gap[0] - datetime.timedelta(days=overlap_days))
  if dates:
    newest = max(dates)
    if (today - newest).days > stale_days:
      candidates.append(newest - datetime.timedelta(days=overlap_days))
  if not candidates:
    return None
  return min(candidates)


_MONTHS_PATTERN = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_DATE_TOKEN_PATTERN = r"\b%s\.?\s+\d{1,2}(?:,?\s+\d{4})?\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b" % _MONTHS_PATTERN


def _parse_date_token(token, today):
  for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%m/%d/%y"):
    try:
      return datetime.datetime.strptime(token, fmt).date()
    except ValueError:
      pass
  for fmt in ("%b %d", "%B %d"):
    try:
      parsed = datetime.datetime.strptime(token, fmt).date().replace(year=today.year)
      if parsed > today:
        parsed = parsed.replace(year=today.year - 1)
      return parsed
    except ValueError:
      pass
  return None


def parse_listed_activity_date(row_soup, now=None):
  """Last-activity date shown in a listing row, or None if unparseable.

  The activity date is the last date-like token in the row (snippet prose may
  contain dates too); implausible readings (before 2000, after today) are
  rejected, so traps like author "Junaid 7" or "3/4/40" never match.
  """
  if now is None:
    now = datetime.datetime.now()
  today = now.date()
  best = None
  for match in regex.finditer(_DATE_TOKEN_PATTERN, row_soup.get_text(separator="\n")):
    parsed = _parse_date_token(match.group(0), today)
    if parsed is not None and datetime.date(2000, 1, 1) <= parsed <= today:
      best = parsed
  return best


def parse_listed_message_count(row_soup):
  """Message count shown in a listing row, or None if unparseable."""
  for tag in row_soup.select("[aria-label]"):
    match = regex.search(r"(\d+)\s+messages?", tag.get("aria-label", ""), flags=regex.IGNORECASE)
    if match is not None:
      return int(match.group(1))
  for line in row_soup.get_text(separator="\n").split("\n"):
    if line.strip().isdigit():
      return int(line.strip())
  return None


def fetch_thread_with_retry(thread_url, max_attempts=3):
  """Fetch one thread, relaunching the thread browser if the driver goes bad.

  Raises the last error after max_attempts failures.
  """
  global thread_browser
  last_error = None
  for attempt in range(1, max_attempts + 1):
    try:
      return get_thread_messages_selenium(url=thread_url, browser=thread_browser)
    except WebDriverException as e:
      last_error = e
      logging.warning("Thread fetch failed (attempt %d/%d): %s", attempt, max_attempts, thread_url)
      time.sleep(5)
      try:
        thread_browser.quit()
      except Exception:
        pass
      thread_browser = scraping.get_selenium_firefox(headless=HEADLESS)
  raise last_error


_PAGE_POLL_SECONDS = 0.5


def _get_page_thread_urls(browser):
  """Thread urls currently listed, or None if the page is mid-render."""
  try:
    tags = browser.find_elements(by=By.CSS_SELECTOR, value='[role="row"]')
  except StaleElementReferenceException:
    return None
  urls = []
  for tag in tags:
    try:
      inner_html = tag.get_attribute('innerHTML')
    except StaleElementReferenceException:
      return None
    try:
      soup = BeautifulSoup(inner_html, features="lxml")
    except Exception:
      continue
    anchor = soup.select_one("a")
    if anchor and anchor.get("href"):
      urls.append(urljoin("https://groups.google.com/", anchor["href"]))
  return urls


def _wait_for_rows(browser, timeout):
  """Row tags of the current listing, waiting for the initial render."""
  deadline = time.monotonic() + timeout
  tags = []
  while not tags:
    try:
      tags = browser.find_elements(by=By.CSS_SELECTOR, value='[role="row"]')
    except StaleElementReferenceException:
      tags = []
    if tags or time.monotonic() >= deadline:
      return tags
    time.sleep(_PAGE_POLL_SECONDS)
  return tags


def _wait_for_page_change(browser, prev_urls, timeout):
  """True once the listing differs from prev_urls; False on timeout (last page)."""
  deadline = time.monotonic() + timeout
  while True:
    current_urls = _get_page_thread_urls(browser)
    if current_urls is not None and current_urls != prev_urls:
      return True
    if time.monotonic() >= deadline:
      return False
    time.sleep(_PAGE_POLL_SECONDS)


def is_next_page_disabled(next_button):
  """Whether a 'Next page' button is disabled.

  Only an explicit truthy value counts: some markup renders aria-disabled="false"
  on enabled buttons, which a plain `is not None` check misreads as disabled.
  """
  for attr in ("aria-disabled", "disabled"):
    value = next_button.get_attribute(attr)
    if value is not None and str(value).strip().lower() not in ("", "false", "0"):
      return True
  return False


def scrape_threads_backwards(url, dest_dir, dumper=dump_messages_to_files, browser=base_browser, dry_run=False, page_timeout=20, start_url=None, shard=None):
  """Walk a group listing newest-first, dumping unarchived and grown threads.

  start_url is a thread-id suffix to skip until (for backfills into ancient
  history); it disables the cutoff stop so the walk runs to the listing end.

  shard is an (index, total) pair splitting the dump set by stable URL hash
  across parallel workers; sharded runs never write completion markers.
  """
  (archived_counts, archive_dates) = scan_archive(dest_dir)
  logging.info(f"Skipping {len(archived_counts)} archived threads.")
  if start_url is not None:
    cutoff = None
    logging.info(f"Backfilling from thread {start_url}; no cutoff.")
  else:
    cutoff = cutoff_for_run(archive_dates, load_completion_marker(dest_dir))
    if cutoff is not None:
      logging.info(f"Stopping at threads older than {cutoff}.")
    else:
      logging.info("No cutoff; walking the full listing.")
  browser.get(url=url)
  thread_count = 0
  page_count = 0
  seen_thread_urls = set()
  stalled_pages = 0
  failed_urls = []
  stop_reached = False
  stalled_out = False
  requested_start = start_url
  start_matched = start_url is None
  shard_index = shard_total = None
  if shard is not None:
    (shard_index, shard_total) = shard
    if not (0 <= shard_index < shard_total):
      raise ValueError(f"Invalid shard {shard} (want 0 <= index < total).")
  while(True):
    logging.info(f"Processing page -{page_count}. {thread_count} threads done. URL {url}")
    thread_tags = _wait_for_rows(browser, timeout=page_timeout)
    page_count = page_count + 1
    page_urls = []
    stale_retries = 0
    row_index = 0
    while row_index < len(thread_tags):
      thread_tag = thread_tags[row_index]
      try:
        soup = BeautifulSoup(thread_tag.get_attribute('innerHTML'), features="lxml")
      except StaleElementReferenceException:
        # The listing re-rendered mid-page; the old row handles are dead. Re-read
        # the page and restart it, restoring the resume point so pre-resume rows
        # stay skipped. Re-dumps overwrite identical files and are harmless.
        if stale_retries >= 10:
          logging.error("Thread rows keep going stale; skipping page %d.", page_count)
          break
        stale_retries += 1
        logging.warning("Stale thread row, re-reading page (retry %d).", stale_retries)
        time.sleep(2)
        thread_tags = browser.find_elements(by=By.CSS_SELECTOR, value='[role="row"]')
        row_index = 0
        page_urls = []
        continue
      except Exception as e:
        logging.error(f"Skipping unreadable thread row: {e}")
        row_index += 1
        continue
      row_index += 1
      thread_count = thread_count + 1
      anchor = soup.select_one("a")
      if not anchor:
        continue
      thread_url = urljoin("https://groups.google.com/", anchor["href"])
      if cutoff is not None:
        activity_date = parse_listed_activity_date(soup)
        if activity_date is not None and activity_date < cutoff:
          logging.info(f"Reached threads older than {cutoff}; stopping.")
          stop_reached = True
          break
      page_urls.append(thread_url)
      if thread_url in seen_thread_urls:
        # Re-read of an already processed page (e.g. stuck last page): no refetch.
        continue
      if start_url is not None:
        if not thread_url.endswith(start_url):
          logging.info("Skipping thread")
          continue
        else:
          logging.info(f"Reached backfill start {start_url}.")
          start_url = None
          start_matched = True
      if shard is not None:
        # Stable md5 (never salted hash()): disjoint across workers even as the
        # listing shifts underneath concurrent walks.
        if int(hashlib.md5(thread_url.encode("utf-8")).hexdigest(), 16) % shard_total != shard_index:
          logging.debug("Skipping thread on another shard")
          continue
      archived_count = archived_counts.get(get_thread_id_from_url(thread_url))
      listed_count = parse_listed_message_count(soup)
      if archived_count is not None:
        if listed_count is None or listed_count <= archived_count:
          logging.info("Skipping archived thread")
          continue
        logging.info(f"Thread grew ({archived_count} -> {listed_count}), re-dumping {thread_url}")
      try:
        (messages, subject) = fetch_thread_with_retry(thread_url=thread_url)
        if listed_count is not None and len(messages) != listed_count:
          logging.warning("Thread %s: dumped %d messages but listing shows %d",
                          thread_url, len(messages), listed_count)
        dumper(messages=messages, subject=subject, dest_dir=dest_dir, url=thread_url, dry_run=dry_run)
      except Exception as e:
        logging.error("Giving up on %s: %s", thread_url, e)
        failed_urls.append(thread_url)
        continue
    if stop_reached:
      break
    new_urls = [thread_url for thread_url in page_urls if thread_url not in seen_thread_urls]
    seen_thread_urls.update(page_urls)
    if not new_urls:
      # The Next click was a no-op (or the page failed to load): same threads again.
      stalled_pages += 1
      if stalled_pages >= 2:
        logging.warning("No new threads for %d consecutive pages; assuming last page.", stalled_pages)
        stalled_out = True
        break
    else:
      stalled_pages = 0
    try:
      next_url_tag = browser.find_element(value='[aria-label="Next page"]', by=By.CSS_SELECTOR)
      if is_next_page_disabled(next_url_tag):
        logging.info("Next page is disabled; assuming last page.")
        break
      # next_url_tag.click()
      logging.info(f"Moving to page {page_count}.")
      browser.execute_script("arguments[0].click();", next_url_tag)
    except NoSuchElementException:
      logging.info("No next-page button; assuming last page.")
      break
    except StaleElementReferenceException:
      # Re-rendered between find and click; the re-read page yields no new urls
      # and counts toward the stall limit, so a persistent churn still terminates.
      logging.warning("Stale next-page button, re-reading page.")
      continue
    # The listing reloads asynchronously (~seconds); without this wait every
    # "next page" re-reads the current one.
    if not _wait_for_page_change(browser, page_urls, timeout=page_timeout):
      logging.info("Next page did not load; assuming last page.")
      break


  if requested_start is not None and not start_matched:
    logging.error(f"Backfill start thread {requested_start} never found; refusing to mark complete.")
    failed_urls.append(f"backfill-start:{requested_start}")
  logging.info(f"Scraped {thread_count} threads.")
  if failed_urls:
    logging.error("Failed threads (%d): %s", len(failed_urls), failed_urls)
  elif not dry_run and not stalled_out and shard is None:
    save_completion_marker(dest_dir, cutoff)
  return failed_urls