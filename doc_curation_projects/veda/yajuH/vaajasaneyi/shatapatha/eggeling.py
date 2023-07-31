import logging
import os
import shutil

import regex
from bs4 import BeautifulSoup

import doc_curation
from doc_curation.md import library
from doc_curation.md.content_processor import section_helper, include_helper, details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper, arrangement
from doc_curation.scraping import sacred_texts
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.wisdom_lib import para_translation
from doc_curation_projects.veda.yajuH.vaajasaneyi import shatapatha
from indic_transliteration import sanscript

# base_dir = os.path.join(shatapatha.CONTENT_BASE, "eggeling/")
base_dir = os.path.join(shatapatha.CONTENT_BASE, "sarva-prastutiH")


def dest_path_maker(url, base_dir, *args, **kwargs):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')

  # Special cases to handle data errors:
  url_to_path = {"https://www.sacred-texts.com/hin/sbr/sbe41/sbe4139.htm":
    "06/04/3.md", "https://www.sacred-texts.com/hin/sbr/sbe44/sbe44072.htm": "12/09/2.md"}
  if url in url_to_path:
    return (os.path.join(base_dir, url_to_path[url]), soup)
  

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

  # doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe12/sbe1264.htm", outfile_path=os.path.join(base_dir, "meta/", "errata/v1.md"))
  # doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe26/sbe2680.htm", outfile_path=os.path.join(base_dir, "meta/", "errata/v2.md"))
  # doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe41/sbe4167.htm", outfile_path=os.path.join(base_dir, "meta/", "errata/v3.md"))
  # doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe43/sbe4376.htm", outfile_path=os.path.join(base_dir, "meta/", "errata/v4.md"))
  # doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbr/sbe44/sbe44126.htm", outfile_path=os.path.join(base_dir, "meta/", "errata/v5.md"))

def missing_pages():
  # sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe41/sbe4139.htm", max_items=1, base_dir=base_dir, dest_path_maker=dest_path_maker)
  # sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe43/sbe4321.htm", max_items=1, base_dir=base_dir, dest_path_maker=dest_path_maker)
  sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe43/sbe4347.htm", max_items=1, base_dir=base_dir, dest_path_maker=dest_path_maker)


def fix_corss_page_footnotes(dry_run=False):
  md_files = arrangement.get_md_files_from_path(dir_path=base_dir)
  for md_file in md_files:
    (metadata, old_content) = md_file.read()
    content = old_content
    if "sbe" not in content:
      continue
    # For example, sbe1204.htmegg_96 refers to https://www.sacred-texts.com/hin/sbr/sbe12/sbe1204.htm#fn_96
    matches = regex.finditer("sbe(\d\d)(\d\d.htm)egg_(\d+)", content)
    for match in matches:
      url = f"https://www.sacred-texts.com/hin/sbr/sbe{match.group(1)}/sbe{match.group(1)}{match.group(2)}"
      definition = sacred_texts.get_cross_page_footnote(url=url, footnote_id=f"fn_{match.group(3)}")
      #  if definition is None:
      logging.info(f"{url} not found!")
      continue
      content += f"\n\n[^egg_{match.group(3)}]: {definition}"
    if old_content.strip() == content.strip():
      continue
    content = regex.sub("sbe\d\d\d\d.htm(egg_\d+)", r"\1", content)
    from doc_curation.md.content_processor import footnote_helper
    content = footnote_helper.define_footnotes_near_use(content=content)
    md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)


if __name__ == '__main__':
  pass
  fix_corss_page_footnotes()
  # missing_pages()
  # special_pages()
  # sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe12/sbe1203.htm", base_dir=base_dir, dest_path_maker=dest_path_maker)
  # sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe26/sbe2603.htm", base_dir=base_dir, dest_path_maker=dest_path_maker)
  # sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe41/sbe4103.htm", base_dir=base_dir, dest_path_maker=dest_path_maker)
  # sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe43/sbe4303.htm", base_dir=base_dir, dest_path_maker=dest_path_maker)
  # sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbr/sbe44/sbe44003.htm", base_dir=base_dir, dest_path_maker=dest_path_maker)
  # para_translation.split(base_dir=base_dir)