"""
Dumps emails from mailman archive to markdown files organized by year/month/subject. ( Example output: https://github.com/hindu-comm/mail_stream_indology) Example invocation at curation_projects/mail_stream_dumper.py in this repo.
"""

from joblib import Parallel, delayed
from tqdm import tqdm
import email
import logging
import os
import textwrap
from urllib.request import urlopen
from urllib.parse import urljoin
import time
import datetime

from bs4 import BeautifulSoup

from curation_utils import file_helper
from curation_utils.file_helper import get_storage_name
from doc_curation.mail_stream import delete_last_month
from doc_curation.md.file import MdFile

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")





months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def scrape_message(url, message_index, dest_dir, list_id, dry_run=False):
  logging.info("Processing message %s", url)
  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')

  subject = soup.find("h1").text.replace(list_id, "")
  author = soup.find("b").text
  date_string = soup.find("i").text
  message_time = time.mktime(email.utils.parsedate(date_string))
  date_string_cleaned = datetime.datetime.fromtimestamp(message_time).strftime('%Y-%m-%d')
  
  post_content = "ERROR: NO CONTENT FOUND!!"
  pre_tag = soup.find("pre")
  if pre_tag:
    post_content = pre_tag.text.replace("<i>", "").replace("</i>", "")
    post_content = textwrap.dedent(post_content)
  post_md = "[Archive link](%s)\n\n%s" % (url, post_content)

  subject_dir = os.path.join(dest_dir, get_storage_name(text=subject))
  md_file = MdFile(file_path=os.path.join(subject_dir, "_index.md"))
  if not os.path.exists(md_file.file_path):
    md_file.dump_to_file(metadata={"title": subject[:30]}, content="", dry_run=dry_run)


  file_name = "%02d__%s.md" % (message_index, get_storage_name(author))
  title = "%02d %s"  % (message_index, author)
  dest_path = os.path.join(subject_dir, file_name)
  md_file = MdFile(file_path=dest_path)
  metadata = {"title": title, "date": date_string_cleaned, "upstream_url": url}
  md_file.dump_to_file(metadata=metadata, content=post_md,
                                     dry_run=dry_run)


def scrape_messages_for_month(url, dest_dir_base, list_id, dry_run=False):
  logging.info("Processing %s", url)
  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  [month_str, year] = soup.find("h1").text.split()[:2]
  month_index = months.index(month_str) + 1

  dest_dir = os.path.join(dest_dir_base, year, "%02d" % month_index)
  dir_files = [x[0] for x in os.walk(dest_dir)]
  if len(dir_files) > 0:
    logging.info("Skipping %s", dest_dir)
    return


  tags = soup.select("ul:nth-of-type(2) a[href]")
  for message_index, anchor in enumerate(tags):
    post_url = urljoin(url, anchor["href"])
    scrape_message(url=post_url, message_index=message_index, dest_dir=dest_dir, list_id=list_id, dry_run=dry_run)


def scrape_months(url, dest_dir_base, list_id, jobs=None, dry_run=False):
  # delete_last_month(dest_dir_base)

  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  tags = soup.select("a[href]")
  month_anchors = [tag for tag in tags if "Thread" in tag.text]

  # Number of parallel jobs, default to use all processors
  job_count = -1 if jobs is None else jobs
  backend = 'sequential' if job_count == 1 else 'multiprocessing'

  r = Parallel(n_jobs=job_count, backend=backend)(
    delayed(scrape_messages_for_month)(urljoin(url, anchor["href"]), dest_dir_base, list_id, dry_run)
    for anchor in tqdm(month_anchors))
    