import logging
import os
from urllib.request import urlopen

import regex
from bs4 import BeautifulSoup

from doc_curation.md import library
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile


def dump_chapter(chapter_id, dest_dir):
  title = "%02d" % chapter_id
  url = "https://www.sacred-texts.com/hin/manu/manu%s.htm" % title
  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  tags = soup.select('p')
  content = ""
  for tag in tags:
    text = tag.text
    verse_num_match = regex.match("(\d+)\. ", text)
    if verse_num_match is None:
      logging.warning("No match in %s", text)
      continue
    verse_num = int(verse_num_match.group(1))
    verse_id = "%03d" % verse_num
    comment = text.replace(verse_num_match.group(0), "")
    content += "%s\t%s\n" % (verse_id, comment)
  md_file = MdFile(file_path=os.path.join(dest_dir, title + ".md"))
  md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=False)


def migrate_and_include(chapter_id):
  def title_maker(text_matched, index, file_title):
    shloka_id = text_matched.split("\t")[0]
    if str(chapter_id) == "11" and shloka_id >= "053":
      shloka_id = "%03d" % (int(shloka_id) - 1)
    return shloka_id
  def replacement_maker(text_matched, dest_path):
    return ""
  chapter_id = "%02d" % chapter_id
  if chapter_id == "01":
    chapter_id += "_praveshaH"
  include_helper.migrate_and_replace_texts(text_patterns=["\d+\t.+"], md_file=MdFile("/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/buhler/%s.md" % chapter_id), replacement_maker=replacement_maker, title_maker=title_maker, dry_run=False)
  


if __name__ == '__main__':
  for x in range(11, 12):
    # dump_chapter(chapter_id=x, dest_dir="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/buhler")
    migrate_and_include(chapter_id=x)