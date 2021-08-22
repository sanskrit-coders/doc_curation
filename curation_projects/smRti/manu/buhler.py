import logging
import os
from urllib.request import urlopen

import regex
from bs4 import BeautifulSoup

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


if __name__ == '__main__':
  for x in range(1, 13):
    dump_chapter(chapter_id=x, dest_dir="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/buhler")