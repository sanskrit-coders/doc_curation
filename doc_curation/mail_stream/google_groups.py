import codecs
import logging
import os
from collections import namedtuple
from datetime import datetime
from urllib.parse import urljoin

from dateutil import parser
import regex
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.remote_connection import LOGGER

from curation_utils import scraping, file_helper
from doc_curation import md
from doc_curation.md.file import MdFile
from doc_curation.scraping.html_scraper import souper

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


base_browser = scraping.get_selenium_chrome(headless=False)
thread_browser = scraping.get_selenium_firefox(headless=False)

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
    expand_link = browser.find_element_by_link_text("")
    expand_link.click()
  except NoSuchElementException:
    pass
  subject = browser.find_element_by_css_selector("h1").text
  section_tags = browser.find_elements_by_css_selector("section")
  thread_dir = None
  messages = []
  for index, section in enumerate(section_tags):
    section_html = section.get_attribute('innerHTML')
    soup = BeautifulSoup(section_html, features="html.parser")
    dt = get_date(soup=soup)

    author_tag = soup.select_one("h3")
    author = "UNKNOWN_AUTHOR"
    if author_tag is None:
      # logging.warning("Could not get author")
      # Section within a message. As in https://groups.google.com/g/bvparishat/c/eHLaHN4heY4
      messages[-1] = messages[-1]._replace(content=f"{messages[-1].content}\n\n{content}")
      continue
    else:
      author = author_tag.text
    message_tag = soup.select_one("div[role='region']")
    message_html = None
    try:
      message_html = str(message_tag)
      content = md.get_md_with_pandoc(content_in=message_html, source_format="html")
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
  thread_header = messages[0].content.split('\n')[0]
  logging.info(f"Thread {thread_header}")
  return (messages, subject)


def dump_messages_to_files(messages, subject, dest_dir, url, dry_run=False):
  for index, message in enumerate(messages):
    if index == 0:
      thread_dir = os.path.join(dest_dir, str(message.date.year), "%02d" % message.date.month, "%02d" % message.date.day, "%s__%s" % (file_helper.get_storage_name(subject), os.path.basename(url)[:2]))
  
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


def scrape_threads(url, dest_dir, start_url=None, dumper=dump_messages_to_files, browser=base_browser, dry_run=False):
  browser.get(url=url)
  thread_count = 0
  page_count = 0
  while(True):
    logging.info(f"Processing page -{page_count}. {thread_count} threads done.")
    thread_tags = browser.find_elements_by_css_selector('[role="row"]')
    page_count = page_count + 1
    for thread_tag in thread_tags:
      soup = BeautifulSoup(thread_tag.get_attribute('innerHTML'), features="lxml")
      thread_count = thread_count + 1
      anchor = soup.select_one("a")
      if not anchor:
        continue
      thread_url = urljoin("https://groups.google.com/", anchor["href"])
      if start_url is not None:
        if not thread_url.endswith(start_url):
          logging.info("Skipping thread")
          continue
        else:
          start_url = None
      (messages, subject) = get_thread_messages_selenium(url=thread_url)
      dumper(messages=messages, subject=subject, dest_dir=dest_dir, url=thread_url, dry_run=dry_run)
    next_url_tag = browser.find_element_by_css_selector('[aria-label="Next page"]')
    if next_url_tag.get_attribute("aria-disabled") is not None:
      # TODO: The above is not working properly.
      break
    else:
      # next_url_tag.click()
      logging.info(f"Moving to page {page_count}.")
      browser.execute_script("arguments[0].click();", next_url_tag)


  logging.info(f"Scraped {thread_count} threads.")