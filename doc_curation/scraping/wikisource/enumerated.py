import logging
import os
import time

from selenium.webdriver.remote.remote_connection import LOGGER

from doc_curation import book_data
from doc_curation.scraping.wikisource.item_dumpers import generic_selenium_dumper
from doc_curation.scraping.wikisource.url_helper import get_url_suffix, generic_url_maker
from indic_transliteration import sanscript

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger

urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def dump_text(url_base, num_parts, dir_path, url_id_padding="%d", dumper=generic_selenium_dumper,
              transliterate_id=True):
  for id in range(1, num_parts + 1):
    outfile_path = os.path.join(dir_path, "%03d.md" % id)
    title = sanscript.transliterate("%03d" % id, sanscript.SLP1, sanscript.DEVANAGARI)
    url = "https://sa.wikisource.org/wiki/%s" % (
      get_url_suffix(id=id, url_id_padding=url_id_padding, id_base=url_base, transliterate_id=transliterate_id))
    dumper(title=title, outfile_path=outfile_path, url=url)


def dump_deep_text(dir_path, unit_info_file, dumper=generic_selenium_dumper, url_maker=generic_url_maker,
                   start_path=None, end_path=None, wait_between_requests=False, dry_run=False):
  unit_data = book_data.get_subunit_data(unit_info_file, [])
  for subunit_path in book_data.get_subunit_path_list(file_path=unit_info_file, unit_path_list=[]):
    relative_path = "/".join(["%02d" % x for x in subunit_path[:-1]] + ["%03d.md" % subunit_path[-1]])
    if start_path is not None and relative_path < start_path:
      # logging.info("Skipping %s", relative_path)
      continue
    if end_path is not None and relative_path > end_path:
      logging.info("Skipping %s", relative_path)
      return 

    outfile_path = os.path.join(dir_path, relative_path)
    title = sanscript.transliterate("%03d" % subunit_path[-1], sanscript.SLP1, sanscript.DEVANAGARI)
    url = url_maker(subunit_path=subunit_path, unit_data=unit_data)
    logging.info("Getting %s to %s with title %s", url, outfile_path, title)
    if not dry_run:
      dumper(title=title, outfile_path=outfile_path, url=url, dry_run=dry_run)
      if wait_between_requests:
        time.sleep(wait_between_requests)