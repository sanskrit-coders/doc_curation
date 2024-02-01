from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript
from curation_utils import scraping
from urllib.parse import urljoin
from doc_curation import md
from doc_curation.md import library
from doc_curation.scraping.html_scraper import souper


from doc_curation.md.file import MdFile, file_helper
from doc_curation.md.content_processor import ocr_helper
import logging
import os, regex


def get_article(url):
  soup = scraping.scroll_and_get_soup(url=url, browser=None, scroll_pause=2)
  title = soup.select_one("li.title").text
  content_tag = soup.select("div.page-content")
  content = md.get_md_with_pandoc(content_in=str(content_tag), source_format="html")
  content = ocr_helper.misc_sanskrit_typos(content)
  content = regex.sub(r"\n +", r"\n", content)
  content = regex.sub(r"ब्राहृ", r"ब्रह्म", content)
  content = regex.sub(r"\n(>[^\n]+)>(?=\n)", r"\n\1  ", content).replace(" > ", " ")
  
  
  page_header = f"[[{title}\tSource: [EB]({url})]]"
  content = f"{page_header}\n\n{content}"
  logging.info(f"Got {title} from {url}")
  return (content, title, soup)


def dump_article(url, outfile_path, title_prefix="", dry_run=False):
  (page_content, page_title, soup) = get_article(url=url)
  if outfile_path.endswith(".md"):
    file_path = outfile_path
  else:
    file_path = os.path.join(outfile_path, file_helper.get_storage_name(text=page_title, source_script=sanscript.DEVANAGARI) + ".md")
  md_file = MdFile(file_path=file_path)
  md_file.dump_to_file(metadata={"title": f"{title_prefix} {page_title}".strip()}, content=page_content, dry_run=dry_run)
  library.fix_index_files(os.path.dirname(os.path.dirname(file_path)))
  return soup

