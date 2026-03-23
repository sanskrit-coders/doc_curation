import logging
import os.path

import regex
from urllib.parse import urljoin

from curation_utils import scraping
from doc_curation.ebook.pandoc_helper import get_md_with_pandoc
from doc_curation.md.library import arrangement
from doc_curation.md import content_processor
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

# Base settings
BASE_URL = "https://divyaprabandham.koyil.org/"


def extract_main_content(url, source_script=sanscript.TAMIL):
  """Try to find the main article content"""
  # Most common location in WordPress-style sites
  soup = scraping.get_soup(url)
  if not soup:
    logging.info("Cannot continue - failed to load main page.")
    exit(1)
  main_div = soup.select_one("div.inside-article .entry-content")
  if not main_div:
    logging.warning(f"Could not locate main content area in {url}.")
    return "", "", soup

  title_div = soup.select_one("div.inside-article .entry-title")
  title = title_div.text
  if source_script is not None:
    title = content_processor.transliterate(text=title, source_script=source_script)

  html = str(main_div)
  md = get_md_with_pandoc(content_in=html, source_format="html")
  if source_script is not None:
    md = content_processor.transliterate(text=md, source_script=source_script)
    md = regex.sub(r"\nअडिये.् [^\n]+\n+[^\n]+https://.+", "", md.strip(), flags=regex.DOTALL)
  else:
    md = regex.sub(r"\n[^\n]+Dh?as\S+\n+archived[^\n]+https://.+", "", md.strip(), flags=regex.DOTALL|regex.IGNORECASE)
  # md = regex.sub("वलैत्तळम् – <https://.+", "", md.strip(), flags=regex.DOTALL)
  return (md, title, soup)



def dump_text(index_url, dest_path, source_script=sanscript.TAMIL):
  logging.info(f"Scraping index from {index_url}")
  
  base_url = scraping.get_base_url(index_url)
  (md, title, soup) = extract_main_content(index_url, source_script=source_script)
  md = f"Source: [TW]({index_url})\n\n{md}"
  lang_code = os.path.basename(dest_path).split(".")[0]
  if lang_code in ["hi", "kn", "te", "en", "ta"]:
    title = lang_code
  
  main_div = soup.find("article") or \
            soup.find("div", class_=regex.compile(r"post-content|entry-content|content"))

  # 2. Collect introductory text (before the list of pasurams)
  intro_parts = []
  seen_links = False
  links = main_div.find_all("a", href=True)
  for link in links:
    link_url = link["href"]
    if link_url.endswith("/") and base_url in link_url:
      link_url = urljoin(index_url, link_url)
      (link_md, link_title, link_soup) = extract_main_content(url=link_url, source_script=source_script)
      md += f"\n\n# {link_title}\n{link_md}"
  
  md = md.replace("\n#", "\n##")
  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={"title": title}, content=md, dry_run=False)
  arrangement.fix_index_files(os.path.dirname(os.path.dirname(dest_path)))
  logging.info("Done.")