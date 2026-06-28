"""
Wikisource scraping.
"""
from urllib.parse import urljoin

from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.utils import sanskrit_helper


def next_url_getter(soup, url, next_url_text):
  next_page_links = [l for l in soup.select("#mw-pages>a") if next_url_text in l.text]
  if len(next_page_links) > 0:
    url = urljoin(url, next_page_links[0]["href"])
  else:
    url = None
  return url


def sanskrit_fixes(dir_path):
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, *args, **kwargs: sanskrit_helper.fix_anunaasikaadi(x, level=0), dry_run=False, silent_iteration=False)
  library.apply_function(fn=metadata_helper.set_title_from_content, dir_path=dir_path, title_extractor=lambda x: metadata_helper.iti_naama_title_extractor(x, conclusion_pattern="इति.+\n?.+ध्याय"))
