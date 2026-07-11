"""
Dumps emails from mailman archive to markdown files organized by year/month/subject. ( Example output: https://github.com/hindu-comm/mail_stream_indology) Example invocation at curation_projects/mail_stream_dumper.py in this repo.
"""
import regex
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

from curation_utils import file_helper, scraping
from curation_utils.file_helper import get_storage_name
from doc_curation.mail_stream import delete_last_month
from doc_curation.md import library
from doc_curation.md.file import MdFile

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")





months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def extract_year_month_numeric(url):
  # Regex to match a 4-digit year followed by a hyphen and a month name
  match = regex.search(r'/?(\d{4})-([a-zA-Z]+)/', url)

  if match:
    year = match.group(1)
    month_name = match.group(2)

    try:
      # Convert the month name to a 2-digit MM format
      month_obj = datetime.datetime.strptime(month_name, "%B")
      month_numeric = month_obj.strftime("%m")
      return f"{year}/{month_numeric}"
    except ValueError:
      # Handle cases where the string isn't a valid full month name
      # (e.g., trying %b if it uses short forms like 'Sep')
      try:
        month_obj = datetime.datetime.strptime(month_name, "%b")
        month_numeric = month_obj.strftime("%m")
        return f"{year}/{month_numeric}"
      except ValueError:
        return None

  return None



def scrape_message(url, message_index, dest_dir, list_id, dry_run=False):
  logging.info("Processing message %s", url)
  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')

  subject = regex.sub(fr"^{list_id} *", "", soup.find("h1").text)
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
  soup, _ = scraping.get_soup(url)
  [month_str, year] = soup.find("h1").text.split()[:2]
  month_index = months.index(month_str) + 1

  dest_dir = os.path.join(dest_dir_base, year, "%02d" % month_index)
  dir_files = library.get_md_files_from_path(dir_path=dest_dir, file_name_filter=lambda x:os.path.basename(x) != "_index.md")  

  tags = soup.select("ul:nth-of-type(2) a[href]")
  

  if len(tags) == len(dir_files):
    logging.info(f"Skipping {dest_dir} with {len(dir_files)} files")
    return

  logging.info(f"Getting in {dest_dir}  {len(tags) - len(dir_files)} files")

  for message_index, anchor in enumerate(tags):
    post_url = urljoin(url, anchor["href"])
    scrape_message(url=post_url, message_index=message_index, dest_dir=dest_dir, list_id=list_id, dry_run=dry_run)


def scrape_months(url, dest_dir_base, list_id, jobs=None, start_month=None, end_month=None, dry_run=False):
  # delete_last_month(dest_dir_base)

  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  tags = soup.select("a[href]")
  month_anchors = [tag for tag in tags if "Thread" in tag.text]
  if start_month is not None:
    month_anchors = [tag for tag in month_anchors if extract_year_month_numeric(tag["href"]) >= start_month]
  if end_month is not None:
    month_anchors = [tag for tag in month_anchors if extract_year_month_numeric(tag["href"]) <= end_month]

  # Number of parallel jobs, default to use all processors
  job_count = -1 if jobs is None else jobs
  backend = 'sequential' if job_count == 1 else 'multiprocessing'

  r = Parallel(n_jobs=job_count, backend=backend)(
    delayed(scrape_messages_for_month)(urljoin(url, anchor["href"]), dest_dir_base, list_id, dry_run)
    for anchor in tqdm(month_anchors))
    