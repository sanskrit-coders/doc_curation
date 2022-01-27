import logging
import os

import regex
from bs4 import BeautifulSoup, NavigableString, Tag
from doc_curation.md.file import MdFile

from doc_curation.scraping.html_scraper import souper


def get_content(soup):
  # Pandoc cannot handle html footnotes well by itself. Hence, not using it.
  para_elements = soup.select("#scontent > p")
  content_out = ""
  for para in para_elements:
    para_title = regex.search("(^\d\S*)\. ", para.text)
    if para_title is not None:
      para_title = para_title.group(1)
      if para_title.isnumeric():
        para_title = "%02d" % int(para_title)
      else:
        logging.warning("Non numeric para element: %s" % para_title)
      content_out += "## %s\n" % (para_title)
    for child in para.children:
      if isinstance(child, NavigableString):
        content_out += child
      elif isinstance(child, Tag) and child.name == "sup":
        footnote_text = child.text.replace("[", "[^")
        content_out += " %s " % footnote_text
    content_out += "\n\n"

  footnote_elements = soup.select("section.footnotes div.f")
  for tag in footnote_elements:
    footnote_id = tag.find('p', {'class': 'nr'}).text.replace("[", "[^")
    definition = tag.findChild("div").text.strip()  
    content_out += "\n\n%s %s" % (footnote_id, definition)
  return content_out


def dump(url, outfile_path, dry_run=False):
  if callable(outfile_path):
    outfile_path = outfile_path(url)
  if os.path.exists(outfile_path):
    logging.info("skipping: %s - it exists already", outfile_path)
    return
  logging.info("Dumping: %s to %s", url, outfile_path)
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  content = get_content(soup=soup)
  title = souper.title_from_element(soup, title_css_selector="h1")
  md_file = MdFile(file_path=outfile_path)
  md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=dry_run)
  return soup



def dump_serially(start_url, base_dir, dest_path_maker, dry_run=False):
  next_url_getter = lambda soup: souper.next_url_from_soup_css(soup=soup, css="div.order-3 a", base_url="https://www.wisdomlib.org/")

  next_url = start_url
  while next_url:
    soup = dump(url=next_url, outfile_path=lambda x: dest_path_maker(x, base_dir=base_dir), dry_run=dry_run)
    if soup is None:
      html = souper.get_html(url=next_url)
      soup = BeautifulSoup(html, 'html.parser')
    next_url = next_url_getter(soup)
    # break # For testing
  logging.info("Reached end of series")

