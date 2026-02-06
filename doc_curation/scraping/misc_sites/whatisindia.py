import codecs
import logging
import os
from pathlib import Path

import regex
from bs4 import BeautifulSoup

import doc_curation.md
from curation_utils import file_helper
from doc_curation.ebook import pandoc_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.scraping.html_scraper import souper
from indic_transliteration import sanscript


def get_text(src_file):
  with codecs.open(src_file, "r", 'utf-8') as file_in:
    contents = file_in.read()
    soup = BeautifulSoup(contents, 'lxml')
    content_element = soup.select('td[width="999"]:has(> div)')
    souper.element_remover(soup, "div[align=right] table")
    text = pandoc_helper.get_md_with_pandoc(content_in=str(content_element))
    return text




def markdownify_all(src_dir, dest_dir):
  file_paths = sorted(Path(src_dir).glob("**/*.html"))
  for src_path in file_paths:
    filename = regex.sub(".html?", ".md", os.path.basename(src_path))
    dest_path = os.path.join(
      os.path.dirname(str(src_path).replace(src_dir, dest_dir)),
      filename)
    dest_path = file_helper.clean_file_path(dest_path)
    content = get_text(src_file=src_path)
    md_file = MdFile(file_path=dest_path)
    md_file.dump_to_file(content=content, metadata={}, dry_run=False)
    metadata_helper.set_title_from_filename(md_file=md_file, dry_run=False, dest_script=None)


if __name__ == '__main__':
  markdownify_all(src_dir="/home/vvasuki/gitland/sanskrit/whatisindia_inscriptions_dump/www.whatisindia.com/inscriptions", dest_dir="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/satem/indo-iranian/indo-aryan/india/articles/epigraphy/whatisindia")
