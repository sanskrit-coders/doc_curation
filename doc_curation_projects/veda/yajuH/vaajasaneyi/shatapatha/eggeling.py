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
from doc_curation_projects.veda.yajuH.vaajasaneyi import shatapatha
from indic_transliteration import sanscript

base_dir = os.path.join(shatapatha.CONTENT_BASE, "eggeling/")


def dest_path_maker(url, base_dir, *args, **kwargs):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  path_suffix = soup.select_one(".margnote")
  if path_suffix is None:
    return None
  path_suffix = path_suffix.text.replace(";", ":")
  ordinals = [int(x) for x in path_suffix.split(":") if x != ""]
  assert len(ordinals) >= 3
  return (os.path.join(base_dir, f"{ordinals[0]:02}/{ordinals[1]:02}/{ordinals[2]}.md"), soup)


def special_pages():
  # doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe12/sbe1202.htm", outfile_path=os.path.join(base_dir, "meta/", "intros/_index.md"))
  # doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe26/sbe2602.htm", outfile_path=os.path.join(base_dir, "meta/", "intros/v2.md"))
  # doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe41/sbe4102.htm", outfile_path=os.path.join(base_dir, "meta/", "indices/v3.md"))
  # doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe43/sbe4302.htm", outfile_path=os.path.join(base_dir, "meta/", "indices/v4.md"))
  # doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe44/sbe44002.htm", outfile_path=os.path.join(base_dir, "meta/", "indices/v5.md"))

  doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe26/sbe2679.htm", outfile_path=os.path.join(base_dir, "meta/", "indices/v2.md"))
  doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe44/sbe44125.htm", outfile_path=os.path.join(base_dir, "meta/", "indices/v5.md"))

  doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe12/sbe1264.htm", outfile_path=os.path.join(base_dir, "meta/", "errata/v1.md"))
  doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe26/sbe2680.htm", outfile_path=os.path.join(base_dir, "meta/", "errata/v2.md"))
  doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe41/sbe4167.htm", outfile_path=os.path.join(base_dir, "meta/", "errata/v3.md"))
  doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe43/sbe4376.htm", outfile_path=os.path.join(base_dir, "meta/", "errata/v4.md"))
  doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe44/sbe44126.htm", outfile_path=os.path.join(base_dir, "meta/", "errata/v5.md"))


if __name__ == '__main__':
  # special_pages()
  # sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe12/sbe1203.htm", base_dir=base_dir, dest_path_maker=dest_path_maker)
  # sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe26/sbe2603.htm", base_dir=base_dir, dest_path_maker=dest_path_maker)
  sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe41/sbe4103.htm", base_dir=base_dir, dest_path_maker=dest_path_maker)
  sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe43/sbe4303.htm", base_dir=base_dir, dest_path_maker=dest_path_maker)
  sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe44/sbe44003.htm", base_dir=base_dir, dest_path_maker=dest_path_maker)
  # para_translation.split(base_dir=base_dir)