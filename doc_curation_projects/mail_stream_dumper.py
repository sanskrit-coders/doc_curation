import regex, os
import logging
import time
from doc_curation import md
from doc_curation.md import library
from doc_curation.md.file import MdFile
from curation_utils import scraping, file_helper


def dump_sadaasvaada(messages, subject, dest_dir, url, dry_run=False):
  subject = regex.sub("Sadāsvāda[ -]*", "", subject)
  title = messages[0].date.strftime('%Y-%m-%d') + "__" + subject
  file_name = os.path.join(dest_dir, file_helper.get_storage_name(title))
  md_file = MdFile(file_path=os.path.join(dest_dir, file_name + ".md"))
  content = ""
  for index, message in enumerate(messages):
    content = f"{content}\n\n{message.content}"
  md_file.dump_to_file(content=content, metadata={"title": title}, dry_run=dry_run)


def scrape_groups():
  from doc_curation.mail_stream import mailman
  mailman.scrape_months(url="https://list.indology.info/pipermail/indology/", list_id="[INDOLOGY] ", dest_dir_base="/home/vvasuki/gitland/hindu-comm/mail_stream/indology/", jobs=2, start_month="2026/11", dry_run=False)
  mailman.scrape_months(url="https://dvaita.info/pipermail/dvaita-list_dvaita.info/", list_id="[DVAITA] ", dest_dir_base="/home/vvasuki/gitland/hindu-comm/mail_stream/dvaita-list/", jobs=2, start_month="2026/11", dry_run=False)
  mailman.scrape_months(url="https://lists.advaita-vedanta.org/archives/advaita-l/", list_id="[Advaita-l] ", dest_dir_base="/home/vvasuki/gitland/hindu-comm/mail_stream/advaita-l/", jobs=2, start_month="2026/11", dry_run=False)
  pass

def scrape_with_recovery(url, dest_dir, dry_run=False, dumper=None, max_attempts=3, start_url=None, shard=None, recovery_delay=120):
  """Scrape one group, relaunching both browsers and retrying if the driver dies.

  Safe to retry: already-archived threads are skipped by archive membership.
  start_url restores the old positional resume for backfills (disables cutoff).
  shard is an (index, total) pair splitting the dump set across parallel workers.
  recovery_delay spaces attempts so transient outages (DNS, driver flake) clear.
  """
  from doc_curation.mail_stream import google_groups
  from curation_utils import scraping
  for attempt in range(1, max_attempts + 1):
    try:
      kwargs = dict(url=url, dest_dir=dest_dir, dry_run=dry_run, browser=google_groups.base_browser)
      if dumper is not None:
        kwargs["dumper"] = dumper
      if start_url is not None:
        kwargs["start_url"] = start_url
      if shard is not None:
        kwargs["shard"] = shard
      return google_groups.scrape_threads_backwards(**kwargs)
    except Exception as e:
      if attempt >= max_attempts:
        raise
      logging.warning("Group scrape failed (attempt %d/%d): %s. Retrying in %ds.", attempt, max_attempts, e, recovery_delay)
      time.sleep(recovery_delay)
      for name in ("base_browser", "thread_browser"):
        try:
          getattr(google_groups, name).quit()
        except Exception:
          pass
      google_groups.base_browser = scraping.get_selenium_chrome(headless=google_groups.HEADLESS, undetected=False)
      google_groups.thread_browser = scraping.get_selenium_firefox(headless=google_groups.HEADLESS)


def dump_google_groups():
  from doc_curation.mail_stream import mailman, google_groups
  # sadaswada is private ("Content unavailable") as of 2026-11; re-enable when accessible.
  # scrape_with_recovery(url="https://groups.google.com/g/sadaswada", dest_dir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/AsvAdaH/sadAsvAdaH", dumper=dump_sadaasvaada, dry_run=False)
  scrape_with_recovery(url="https://groups.google.com/g/hindu-vidya", dest_dir="/home/vvasuki/gitland/hindu-comm/mail_stream/hindu-vidya", dry_run=False)
  scrape_with_recovery(url="https://groups.google.com/g/advaitin", dest_dir="/home/vvasuki/gitland/hindu-comm/mail_stream/advaitin", dry_run=False)
  scrape_with_recovery(url="https://groups.google.com/g/bvparishat", dest_dir="/home/vvasuki/gitland/hindu-comm/mail_stream/bvparishat", dry_run=False)
  scrape_with_recovery(url="https://groups.google.com/g/samskrita", dest_dir="/home/vvasuki/gitland/hindu-comm/mail_stream/samskrita", dry_run=False)
  # google_groups.get_thread_messages_selenium(url="https://groups.google.com/g/bvparishat/c/vkOvpkrL97o")

def word_clouds():
  stop_words = ["https", "groups", "group", "google", "com", "email", "subscribed", "msgid", "wrote", "gmail", "regards", "samskrita", "bvparishat", "http", "googlegroups", "तव", "send", "post", "discussion", "unsubscribe", "namaste", "PM", "AM", "footer", "Professor", "Source"]
  library.dump_word_cloud(src_path="/home/vvasuki/gitland/hindu-comm/mail_stream/samskrita", dest_path="word-clouds/general.png", stop_words=stop_words)
  library.dump_word_cloud(src_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/AsvAdaH/sadAsvAdaH", dest_path="word-clouds/general.png", stop_words=stop_words)
  library.dump_word_cloud(src_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/AsvAdaH/sadAsvAdaH", dest_path="word-clouds/general.png", stop_words=stop_words)
  library.dump_word_cloud(src_path="/home/vvasuki/gitland/hindu-comm/mail_stream/indology", dest_path="word-clouds/general.png", stop_words=stop_words)
  library.dump_word_cloud(src_path="/home/vvasuki/gitland/hindu-comm/mail_stream/advaita-l", dest_path="word-clouds/general.png", stop_words=stop_words)
  library.dump_word_cloud(src_path="/home/vvasuki/gitland/hindu-comm/mail_stream/hindu-vidya", dest_path="word-clouds/general.png", stop_words=stop_words)


if __name__ == '__main__':
  # word_clouds()
  scrape_groups()
  # dump_google_groups()
  pass
