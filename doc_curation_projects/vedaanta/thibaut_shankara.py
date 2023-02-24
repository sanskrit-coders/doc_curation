import os
import shutil

import regex
from bs4 import BeautifulSoup

import doc_curation
from doc_curation.md import library
from doc_curation.md.content_processor import section_helper, include_helper, details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.scraping import sacred_texts
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.wisdom_lib import para_translation
from indic_transliteration import sanscript

base_dir = os.path.join("/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/brahma-sUtrANi/thibaut/")

current_adhyaaya = 1
current_paada = 1
current_part = 0
current_subpart = 1

ordinal_to_number = {
  "first": 1,
  "second": 2,
  "third": 3,
  "fourth": 4
}

def dest_path_maker(url, base_dir):
  global current_adhyaaya, current_paada, current_part, current_subpart
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')

  headings = soup.select("h1, h2")
  if len(headings) > 0:
    texts = [sacred_texts.get_text(x).lower().strip() for x in headings]
    texts = [text for text in texts if "adhyāya" in text or "pāda" in text]
    text = " ".join(texts)
    id = text.split(" ")[0].lower()
    if "adhyāya" in text:
      current_adhyaaya = ordinal_to_number[id]
      current_paada = 1
    elif "pāda" in text:
      current_paada = ordinal_to_number[id]

  sacred_texts.remove_superfluous_tags(soup=soup)
  text = "".join([x.text for x in soup.select("p")]).strip()
  if text is None:
    return None
  match = regex.match("(\d+)\.", text)
  if match is None:
    if current_part == 0:
      index = "_index"
    else:
      index = f"{current_part:02}/{current_subpart:02}"
      current_subpart = current_subpart + 1
      start_file_old = os.path.join(base_dir, f"{current_adhyaaya}/{current_paada}/{current_part:02}.md")
      start_file_new = os.path.join(base_dir, f"{current_adhyaaya}/{current_paada}/{current_part:02}/_index.md")
      if os.path.exists(start_file_old):
        os.makedirs(os.path.dirname(start_file_new), exist_ok=True)
        shutil.move(start_file_old, start_file_new)
  else:
    current_part = int(match.group(1))
    current_subpart = 1
    index = f"{current_part:02}"
  return (os.path.join(base_dir, f"{current_adhyaaya}/{current_paada}/{index}.md"), soup)


def special_pages():
  doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbe48/sbe48002.htm", outfile_path=os.path.join(base_dir, "0/", "intro.md"))


if __name__ == '__main__':
  special_pages()
  sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbe34/sbe34007.htm", base_dir=base_dir, dest_path_maker=dest_path_maker)
  
