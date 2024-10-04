import logging

import regex

from curation_utils import file_helper
import os

import requests
from bs4 import BeautifulSoup

from curation_utils import scraping
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.scraping.html_scraper import souper
from indic_transliteration import sanscript


def get_all_texts():
  # URL of the page to scrape
  url = "https://www.dsbcproject.org/canon-text/browse-by-list/77"
  
  # Send a GET request to the URL
  soup = scraping.get_soup(url)
  # Find the table containing the texts
  table = soup.find('table')
  
  # Initialize a list to hold the scraped data
  texts = []
  
  # Iterate over each row in the table (skipping the header)
  for row in table.find_all('tr')[1:]:
    # Extract title and category from each row
    columns = row.find_all('td')
    if len(columns) >= 2:  # Ensure there are enough columns
      title = columns[0].get_text(strip=True)
      category = columns[1].get_text(strip=True).split("»")
      category = [x for x in category if x.lower() != "देवनागरी"]
      link = columns[0].find('a')['href'] if columns[0].find('a') else None  # Extract URL if available
      texts.append({'title': title, 'category': category, "url": link})
  
  # logging.info the scraped texts
  for text in texts:
    logging.info(f"Title: {text['title']}, Category: {text['category']}, URL: {text['url']}")
  return texts




def dump_text_to_file(url, dir_path, title):
  soup = scraping.get_soup(url)

  def _get_meta_info(soup):
    # Find the table on the page
    table = soup.find('div', class_='title-tag')

    metadata = {}
    metadata['dbcs_url'] = url
    # Iterate over each row in the table (skipping the header)
    for row in table.find_all('li'):
      # Extract title and category from each row
      columns = list(row.children)
      if len(columns) == 2:  # Ensure there are exactly two columns
        key = columns[0].get_text(strip=True)
        value = columns[1].get_text(strip=True)
        if key not in ['Parallel Romanized version', 'Text Version']:
          metadata[key] = value
    souper.element_remover(soup=soup, css_selector="div.title-tag")
    return metadata
  
  # Create a filename based on the title or a unique identifier
  safe_title = file_helper.get_storage_name(title)
  file_name = f"{safe_title}.md"
  file_path = os.path.join(dir_path, file_name)
  logging.info("Dumping to file %s", file_path)
  metadata = _get_meta_info(soup)
  metadata['title'] = title
  
  paras = [x.text for x in soup.find_all(class_='relin-paragraph-target')]
  if len(paras) > 0:
    content = "\n\n".join(paras)
  else:
    # metadata_element = soup.select_one("div.news-section div.row")
    # content = souper.get_text_after_element(metadata_element)
    content = soup.select_one("div.news-section").get_text(strip=False)
    content = regex.split("Technical Details", content)[1]
  content = regex.sub("(?<=\n|^)\s+", "", content)
  # content = sanscript.transliterate(content, _from=sanscript.IAST, _to=sanscript.DEVANAGARI)
  MdFile(file_path=file_path).dump_to_file(metadata=metadata, content=content, dry_run=False)


def dump_text_bunch(text, base_path):
  # Send a GET request to the URL
  soup = scraping.get_soup(text["url"])
  # Find the table containing the texts
  table = soup.find('table')
  if not table:
    logging.info("No table found on the page.")
    return

  rows = table.find_all('tr')[1:]
  dir_path = os.path.join(base_path, *[file_helper.get_storage_name(x) for x in text["category"]], file_helper.get_storage_name(text["title"]))
  if len(rows) == 1:
    dir_path = os.path.dirname(dir_path)

  # Iterate over each row in the table (skipping the header)
  for index, row in enumerate(rows):
    columns = row.find_all('td')
    if len(columns) >= 2:  # Ensure there are enough columns
      title = columns[1].get_text(strip=True)
      if len(rows) > 1:
        if regex.match(r"\d", title):
          if regex.match(r"\d\D", title):
            title = "0" + title
        else:
          title = f"{(index + 1):02d} {title}"
      link = columns[1].find('a')['href'] if columns[1].find('a') else None

      if link:
        # If link is relative, make it absolute
        if not link.startswith('http'):
          link = requests.compat.urljoin(text["url"], link)

        dump_text_to_file(url=link, dir_path=dir_path, title=title)


def dump_all_texts(base_path):
  texts = get_all_texts()
  for text in texts:
    dump_text_bunch(text=text, base_path=base_path)
  library.fix_index_files(os.path.dirname(base_path), overwrite=False)
  

if __name__ == '__main__':
  dump_all_texts(base_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/bauddhaH/")