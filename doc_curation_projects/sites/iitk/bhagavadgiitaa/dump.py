import logging
import os
from urllib.request import urlopen

import doc_curation.text_utils
from bs4 import BeautifulSoup

from doc_curation_projects.iitk.bhagavadgiitaa import folder_path_from_title
from doc_curation.md.file import MdFile
from doc_curation.scraping.html_scraper import souper
from curation_utils.file_helper import get_storage_name

from doc_curation.md import library
import regex

from doc_curation.book_data import get_subunit_data


def dump_shloka_details(url, base_dir, chapter_title):
  chapter_id = regex.match(".+field_chapter_value=(\d+)", url).group(1)
  chapter_id = int(chapter_id)
  shloka_id = regex.match(".+field_nsutra_value=(\d+)", url).group(1)
  shloka_id = int(shloka_id)
  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  part_divs = soup.select(".views-field")

  content_tag = part_divs[0].select("font[size='3px']")[0]
  shloka = souper.get_md_paragraph(content_tag.contents)
  title = "%02d %s" % (shloka_id, doc_curation.text_utils.title_from_text(text=regex.sub("^\S+\s+उवाच", "", shloka.strip())))
  metadata={"title": title}
  out_path = "%02d_%s/%s.md" % (chapter_id, get_storage_name(text=chapter_title), get_storage_name(text=title))
  dest_path = os.path.join(base_dir, "mUlam", out_path)
  logging.info(url)
  if not os.path.exists(dest_path):
    md_file = MdFile(file_path=dest_path)
    md_file.dump_to_file(metadata=metadata, content=shloka, dry_run=False)


  from doc_curation.md import get_md_with_pandoc
  for part_div in part_divs[1:]:
    title_tags = part_div.select("font[size='4px']")
    if len(title_tags) == 0:
      title_tags = part_div.select("strong")
    if len(title_tags) == 0:
      logging.warning("No title found! %s", str(part_div))
      continue
    commentary_title = title_tags[0].text
    folder_path = folder_path_from_title(title=commentary_title)
    if folder_path is None:
      logging.fatal("Could not find folder_path for: %s", commentary_title)
    dest_path = os.path.join(base_dir, folder_path, out_path)
    if not os.path.exists(dest_path):
      md_file = MdFile(file_path=dest_path)
      content_tags = part_div.select("font[size='3px']")
      if len(content_tags) == 0:
        logging.warning("Could not find content div for: %s", commentary_title)
        content_html = str(part_div)
      else:
        content_html = str(content_tags[0])
      content = get_md_with_pandoc(content_in=content_html, source_format="html")
      md_file.dump_to_file(metadata=metadata, content=content, dry_run=False)



def dump_chapter(chapter_id, base_dir):
  chapter_data = get_subunit_data(file_path="/home/vvasuki/sanskrit-coders/doc_curation/doc_curation/book_data/mahaabhaaratam/bhagavadgItA.toml", unit_path_list=["%02d" % chapter_id])
  for shloka_id in range(1, chapter_data["length"]+1):
    url = "https://www.gitasupersite.iitk.ac.in/srimad?language=dv&field_chapter_value=%d&field_nsutra_value=%d&htrskd=1&httyn=1&htshg=1&scsh=1&hcchi=1&hcrskd=1&scang=1&scram=1&scanand=1&scjaya=1&scmad=1&scval=1&scms=1&scsri=1&scvv=1&scpur=1&scneel=1&scdhan=1&ecsiva=1&etsiva=1&etpurohit=1&etgb=1&setgb=1&etssa=1&etassa=1&etradi=1&etadi=1&choose=1" % (chapter_id, shloka_id)
    dump_shloka_details(url=url, base_dir=base_dir, chapter_title=chapter_data["alt_title"])



if __name__ == '__main__':
  base_dir = "/home/vvasuki/vishvAsa/purANam/static/mahAbhAratam/06-bhIShma-parva/02-bhagavad-gItA-parva"
  for chapter_id in range(1, 19):
    dump_chapter(chapter_id=chapter_id, base_dir=base_dir)