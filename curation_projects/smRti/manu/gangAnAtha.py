import itertools
import logging
import os
from urllib.request import urlopen

import regex
from bs4 import BeautifulSoup

from doc_curation.md import get_md_with_pandoc
from doc_curation.md.file import MdFile


def get_md_file(soup, dest_dir):
  title_text = soup.select_one("h1").text.strip()
  verse_id = regex.search("[.-](\d+?)(?= |$)", title_text).group(1)
  verse_id = "%03d" % int(verse_id)
  similar_files = [x for x in os.listdir(dest_dir) if x.startswith(verse_id)]
  md_file = MdFile(file_path=os.path.join(dest_dir, similar_files[0]))
  return md_file


def dump_translations(soup, md_file):
  tags = soup.select('blockquote p')
  translations = [x.text for x in tags[3:]]
  content = "\n\n".join(translations)
  md_file.replace_content(new_content=content, dry_run=False)


def dump_notes(soup, h2_prefix, md_file):
  h2_tags = soup.select('#scontent h2')
  matching_tags = [x for x in h2_tags if x.text.strip().startswith(h2_prefix)]
  if len(matching_tags) == 0:
    logging.warning("No %s content found for %s", h2_prefix, md_file.file_path)
    return 
  next_tag = matching_tags[0].next_sibling
  p_tags = []
  while next_tag is not None and (isinstance(next_tag, str) or next_tag.name == "p"):
    p_tags.append(str(next_tag))
    next_tag = next_tag.next_sibling
  content_html = "\n".join(p_tags)
  content = get_md_with_pandoc(content_in=content_html, source_format="html")
  md_file.replace_content(new_content=content, dry_run=False)


def dump_chapter(index_url, dest_dir):
  page_html = urlopen(index_url)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  tags = soup.select("a")
  tags = [x for x in tags if "Verse" in x.text]
  for tag in tags:
    url="https://www.wisdomlib.org/%s" % tag["href"]
    logging.info("URL: %s", url)
    page_html = urlopen(url)
    tag_soup = BeautifulSoup(page_html.read(), 'lxml')
    md_file = get_md_file(soup=tag_soup, dest_dir=dest_dir)
    # dump_translations(soup=tag_soup, md_file=md_file)
    md_file.file_path = md_file.file_path.replace("mUlAnuvAdaH", "bhAShyAnuvAdaH")
    dump_notes(soup=tag_soup, md_file=md_file, h2_prefix="Medh")
    md_file.file_path = md_file.file_path.replace("bhAShyAnuvAdaH", "TippanyaH")
    dump_notes(soup=tag_soup, md_file=md_file, h2_prefix="Explanatory")
    md_file.file_path = md_file.file_path.replace("TippanyaH", "tulya-vAkyAni")
    dump_notes(soup=tag_soup, md_file=md_file, h2_prefix="Comparative")


if __name__ == '__main__':
  dump_chapter(index_url="https://www.wisdomlib.org/hinduism/book/manusmriti-with-the-commentary-of-medhatithi/d/doc202173.html", dest_dir="/home/vvasuki/vishvAsa/kalpAntaram/static/smRtiH/manuH/gangAnatha-mUlAnuvAdaH/12")