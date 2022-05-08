import logging
import os
from itertools import dropwhile, takewhile

import regex
from bs4 import BeautifulSoup

from doc_curation_projects.veda import Rk
from curation_utils import scraping
from doc_curation import md
from doc_curation.md.file import MdFile
from doc_curation.scraping import wisdom_lib
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.html_scraper.souper import get_content_from_element, get_html
from doc_curation.scraping.wisdom_lib import serial


WILSON_DIR = os.path.join(Rk.SAMHITA_DIR_STATIC, "wilson")
HELLWIG_DIR = os.path.join(Rk.SAMHITA_DIR_STATIC, "hellwig_grammar")


def dumper (url, dry_run, *args, **kwargs):
  Rk_id_to_name_map = Rk.get_Rk_id_to_name_map_from_muulam()

  html = get_html(url=url)
  unaltered_soup = BeautifulSoup(html, 'html.parser')
  soup = BeautifulSoup(html, 'html.parser')

  title = souper.title_from_element(soup=soup, title_css_selector="h1", title_prefix="")
  metadata = {"title": title}
  if not title.startswith("Rig Veda"):
    return unaltered_soup
  Rk_id_parts = [int(x) for x in title.replace("Rig Veda ", "").split(".")]
  Rk_id = "%02d/%03d/%02d" % (Rk_id_parts[0], Rk_id_parts[1], Rk_id_parts[2])
  subpath = "%02d/%03d/%s.md" % (Rk_id_parts[0], Rk_id_parts[1], Rk_id_to_name_map[Rk_id])

  souper.tag_replacer(soup=soup, css_selector="#scontent a", tag_name="b")
  souper.tag_appender(soup=soup, css_selector="#scontent .border-bottom", tag_name="hr")
  souper.tag_replacer(soup=soup, css_selector="#scontent .border-bottom .row", tag_name="ul")
  souper.tag_replacer(soup=soup, css_selector="#scontent .border-bottom .col-12", tag_name="li")
  content = get_content_from_element(soup=soup, text_css_selector="#scontent", url=url)
  content = md.get_md_with_pandoc(content_in=content, source_format="html")
  content_lines = content.split("\n")

  content_lines_wilson = list(dropwhile(lambda x: not x.strip().startswith("## English"), content_lines))
  content_lines_wilson = list(takewhile(lambda x: x.strip() != "### Details:", content_lines_wilson))
  content_wilson = "\n".join(content_lines_wilson).replace("### ", "## ")

  md_file = MdFile(file_path=os.path.join(WILSON_DIR, subpath))
  md_file.dump_to_file(content=content_wilson, metadata=metadata, dry_run=dry_run)

  content_lines_hellwig = list(dropwhile(lambda x: "English analysis of grammar" not in x, content_lines))
  content_lines_hellwig = [x for x in content_lines_hellwig if x.strip() != ""]
  content_hellwig = "\n".join(content_lines_hellwig[1:])
  content_hellwig = regex.sub("\n- [\n ]+", "\n- ", content_hellwig)

  md_file = MdFile(file_path=os.path.join(HELLWIG_DIR, subpath))
  md_file.dump_to_file(content=content_hellwig, metadata=metadata, dry_run=dry_run)

  return unaltered_soup


def dump():
  serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/rig-veda-english-translation/d/doc828866.html", out_path=WILSON_DIR, dumper=dumper)


if __name__ == '__main__':
  dump()