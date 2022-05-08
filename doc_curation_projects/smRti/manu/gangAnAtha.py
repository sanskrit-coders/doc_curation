import itertools
import logging
import os
import shutil
from urllib.request import urlopen

import regex
from bs4 import BeautifulSoup

from doc_curation_projects.smRti.manu import medhaatithi
from doc_curation.md import get_md_with_pandoc
from doc_curation.md.file import MdFile


def get_canonical_verse_id(soup, chapter_id):
  title_text = soup.select_one("h1").text.strip()
  if "5.122" in title_text and "(a)" in title_text:
    return "123"
  if "7.86b" in title_text:
    return "087-1"
  verse_id = regex.search("[.-](\d+?)(?= |$)", title_text).group(1)
  verse_num = int(verse_id)
  verse_maps = {
  }
  verse_map = verse_maps.get(chapter_id, {})
  verse_num = verse_map.get(verse_num, verse_num)
  # gangAnatha jhA seems to follow the canonical numbering (confirmed on ch 3 and 8). No correction needed.
  if chapter_id == "05":
    if verse_num >= 61 and verse_num < 122:
      verse_num += 1
    elif chapter_id == "05" and verse_num >= 122:
      verse_num += 2
  verse_id = "%03d" % verse_num
  return verse_id


def get_md_file(soup, dest_dir, chapter_id):
  verse_id = get_canonical_verse_id(soup=soup, chapter_id=chapter_id)
  if chapter_id == "01":
    chapter_id += "_praveshaH"
  dest_dir = os.path.join(dest_dir, chapter_id)
  reference_dir = "/home/vvasuki/vishvAsa/kalpAntaram/static/smRtiH/manuH/vishvAsa_prastutiH/%s" % chapter_id
  similar_files = [x for x in os.listdir(reference_dir) if x.startswith(verse_id + "_")]
  md_file = MdFile(file_path=os.path.join(dest_dir, similar_files[0]))
  if not os.path.exists(md_file.file_path):
    os.makedirs(os.path.dirname(md_file.file_path), exist_ok=True)
    shutil.copy(os.path.join(reference_dir, similar_files[0]), md_file.file_path)
  return md_file


def dump_translations(soup, md_file):
  tags = soup.select('blockquote p')
  translations = [x.text for x in tags[3:]]
  content = "\n\n".join(translations)
  md_file.replace_content_metadata(new_content=content, dry_run=False)


def dump_notes(soup, h2_prefix, md_file):
  h2_tags = soup.select('#scontent h2')
  matching_tags = [x for x in h2_tags if x.text.strip().startswith(h2_prefix)]
  if len(matching_tags) == 0:
    logging.warning("No %s content found for %s", h2_prefix, md_file.file_path)
    if os.path.exists(md_file.file_path):
      os.remove(md_file.file_path)
    return 
  next_tag = matching_tags[0].next_sibling
  p_tags = []
  while next_tag is not None and (isinstance(next_tag, str) or next_tag.name != "h2"):
    p_tags.append(str(next_tag))
    next_tag = next_tag.next_sibling
    print(".", end ="")
  print("\n", end ="")
  content_html = "\n".join(p_tags)
  content = get_md_with_pandoc(content_in=content_html, source_format="html")
  md_file.replace_content_metadata(new_content=content, dry_run=False)


def dump_chapter(dest_dir, chapter_id):
  index_urls = get_chapter_urls()
  index_url = index_urls[int(chapter_id)-1]
  page_html = urlopen(index_url)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  tags = soup.select("a")
  tags = [x for x in tags if "Verse" in x.text]
  # tags = list(itertools.dropwhile(lambda x: not "121" in x.text, tags))
  for tag in tags:
    url="https://www.wisdomlib.org/%s" % tag["href"]
    logging.info("%s URL: %s", tag.text, url)
    page_html = urlopen(url)
    tag_soup = BeautifulSoup(page_html.read(), 'lxml')
    md_file = get_md_file(soup=tag_soup, dest_dir=os.path.join(dest_dir, 'gangAnatha-mUlAnuvAdaH'), chapter_id=chapter_id)
    dump_translations(soup=tag_soup, md_file=md_file)
    md_file = get_md_file(soup=tag_soup, dest_dir=os.path.join(dest_dir, 'gangAnatha-bhAShyAnuvAdaH'), chapter_id=chapter_id)
    dump_notes(soup=tag_soup, md_file=md_file, h2_prefix="Medh")
    md_file = get_md_file(soup=tag_soup, dest_dir=os.path.join(dest_dir, 'gangAnatha-TippanyaH'), chapter_id=chapter_id)
    dump_notes(soup=tag_soup, md_file=md_file, h2_prefix="Explanatory")
    md_file.file_path = md_file.file_path.replace("TippanyaH", "tulya-vAkyAni")
    md_file = get_md_file(soup=tag_soup, dest_dir=os.path.join(dest_dir, 'gangAnatha-tulya-vAkyAni'), chapter_id=chapter_id)
    dump_notes(soup=tag_soup, md_file=md_file, h2_prefix="Comparative")


def get_chapter_urls():
  page_html = urlopen("https://www.wisdomlib.org/hinduism/book/manusmriti-with-the-commentary-of-medhatithi")
  soup = BeautifulSoup(page_html.read(), 'lxml')
  tags = soup.select("a")
  tags = [x for x in tags if "Discourse" in x.text]
  urls = ["https://www.wisdomlib.org/" + tag["href"] for tag in tags]
  return urls


if __name__ == '__main__':
  for i in range(7, 8):
    dump_chapter(dest_dir="/home/vvasuki/vishvAsa/kalpAntaram/static/smRtiH/manuH/", chapter_id="%02d" % i)