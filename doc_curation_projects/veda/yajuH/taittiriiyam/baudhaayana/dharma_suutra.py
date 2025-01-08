import functools
import os
import regex
from bs4 import BeautifulSoup

import doc_curation.md.library.arrangement
from curation_utils import dir_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.md.content_processor import details_helper
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping import sacred_texts
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.sacred_texts import para_translation
from indic_transliteration import sanscript
import functools
import logging

base_dir = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/baudhAyanaH/dharma-sUtram/sarva-prastutiH"



def buhler_adder(details_tag, metadata):
  detail = details_helper.Detail.from_soup_tag(detail_tag=details_tag)
  id = sanscript.transliterate(regex.search("[०-९]+", detail.title)[0], _from=sanscript.DEVANAGARI, _to=sanscript.IAST)
  file_path = metadata["_file_path"].replace("content", "static").replace("sarva-prastutiH", "buhler").replace(".md", f"/{id}.md")
  if os.path.exists(file_path):
    md_file = MdFile(file_path=file_path)
    [_, content] = md_file.read()
    content = content.strip()
    os.remove(file_path)
    details_helper.detail_content_replacer_soup(details_tag, content)
  else:
    # content = "MISSING"
    pass


def buhler_dest_path_maker(url, base_dir, *args, **kwargs):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  title = souper.title_from_element(soup, title_css_selector="h3")
  title = title.replace(" I,", "1,").replace(" II,", "2,").replace(" III,", "3,").replace(" IV,", "4,")
  match = regex.match('PRASNA *(\d+), ADHYÂYA *(\d+), KANDIKÂ *(\d+). Footnotes', title)
  subpath = f"{int(match.group(1)):02d}/{int(match.group(2)):02d}/{int(match.group(3)):02d}"
  return os.path.join(base_dir, subpath + ".md")


def buhler_dump():
  sacred_texts.dump_serially(start_url="https://sacred-texts.com/hin/sbe14/sbe1434.htm", base_dir=base_dir.replace("content", "static").replace("sarva-prastutiH", "buhler"), dest_path_maker=buhler_dest_path_maker)


if __name__ == '__main__':
  pass
  # library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=details_helper.insert_duplicate_adjascent, new_title="Buhler\\1")
  buhler_dump()
  # library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=details_helper.transform_detail_tags_with_soup, transformer=buhler_adder, title_pattern="Buhler(.*)")

