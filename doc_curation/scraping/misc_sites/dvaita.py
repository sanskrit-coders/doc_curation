import bs4
from bs4 import NavigableString
from indic_transliteration import sanscript
from collections import OrderedDict

from curation_utils import scraping
from urllib.parse import urljoin
from doc_curation import md
from doc_curation.ebook import pandoc_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import space_helper
from curation_utils.file_helper import get_storage_name
from doc_curation.utils import text_utils, sanskrit_helper

from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement
import logging
import os, regex
import aksharamukha


SCROLL_PAUSE = 6


def fix_text(text, source_script):
  text = regex.sub(r"</?div.*?>", "", text)
  text = regex.sub(r"\n\[Load More.+\n", "", text)
  text = text.replace(r"\|", "।")
  text = regex.sub("।।+", "॥", text)
  text = regex.sub("ळ", "ल", text)
  text = regex.sub(":", "ः", text)
  text = regex.sub("s", "ऽ", text)
  text = regex.sub("ॆ", "े", text)
  text = regex.sub("ॊ", "ो", text)
  text = regex.sub("व्द्य", "द्व्य", text)
  text = sanskrit_helper.fix_bad_anunaasikas(text)
  text = sanskrit_helper.fix_bad_visargas(text)
  text = sanskrit_helper.fix_bad_vyanjanaantas(text)

  text = regex.sub(r"(?<=^|\n)\*\*\((.+?)\)\*\*(?=$|\n)", r"## \1", text)
  text = space_helper.fix_markup(text)
  text = regex.sub("\n\n\n+", "\n\n", text)
  return text


def get_text(url, browser, source_script=sanscript.DEVANAGARI):
  logging.info("Getting text from " + url)
  soup = scraping.scroll_and_get_soup(url=url, browser=browser, scroll_pause=SCROLL_PAUSE, scroll_btn_css=None)
  title = None
  title_tag = soup.select_one("li.mm-active>a.active")
  if title_tag is not None:
    title = fix_text(text=title_tag.text.strip(), source_script=source_script)
  else:
    logging.fatal("Can't grok title.")
  content_tag = soup.select_one("div.main-content")
  content = pandoc_helper.get_md_with_pandoc(content_in=str(content_tag), source_format="html").strip()
  content = fix_text(text=content, source_script=source_script)
  logging.info(f"Got {title} from {url}")
  return (title, content)


def dump_text(url, dest_path, browser, index_str, source_script=sanscript.DEVANAGARI, overwrite=False, dry_run=False):
  if os.path.exists(dest_path) and not overwrite:
    logging.info(f"Skipping {dest_path}")
    return
  (title, content) = get_text(url=url, browser=browser, source_script=source_script)
  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={"title": f"{index_str} {title}", "upstream_url": url}, content=content, dry_run=dry_run)


def process_ul_tree(ul_tag, path="", overwrite=False, dry_run=False):
  file_map = {}
  items = [l for l in ul_tag.children if l.name == "li" and l.text.strip().lower() != "temp" ]
  # logging.debug(items)
  for index, item in enumerate(items):
    anchor = item.select_one("a")
    title = anchor.text.strip()
    sub_path = f"{index + 1:02d}_{title}"
    sub_path = get_storage_name(text=sub_path, max_length=40)
    item_path = os.path.join(path, sub_path)
    if anchor["href"].startswith("http"):
      file_map[item_path + ".md"] = anchor["href"]
    for child in item.children:
      if child.name == "ul":
        sub_file_map = process_ul_tree(child, item_path)
        file_map.update(sub_file_map)
  return file_map




def dump_series(url, dest_path, start_file=None, end_index=None, source_script=sanscript.DEVANAGARI, overwrite=True, dry_run=False):
  browser = scraping.get_selenium_chrome(headless=False)
  # First, prepare file_map. No need to scroll long just to get the urls.
  soup = scraping.scroll_and_get_soup(url=url, browser=browser, scroll_pause=2, scroll_btn_css=None)
  logging.info(f"Dumping series starting {url}")
  parts_tag = soup.select_one("ul.sub-menu.mm-show")
  file_map = process_ul_tree(parts_tag, overwrite=overwrite, dry_run=dry_run)
  logging.info(f"{len(file_map)} files will be written.")

  file_map = {regex.sub("^[^/]+?/", "", item_path) : url for item_path, url in file_map.items()}
  # drop all items until item_path = start_file
  if start_file is not None:
    try:
      keys = list(file_map.keys())
      start_idx = keys.index(start_file)
      file_map = {k: file_map[k] for k in keys[start_idx:]}
    except ValueError:
      logging.warning(f"start_file '{start_file}' not found in file_map. Proceeding without dropping.")

  # Now get each page.
  for item_path, url in file_map.items():
    item_path = os.path.join(dest_path, item_path)
    index_str = sanscript.transliterate(os.path.basename(item_path).split("_")[0], _to=sanscript.DEVANAGARI, _from=sanscript.IAST)
    dump_text(url=url, index_str=index_str, browser=browser, dest_path=item_path, source_script=source_script, overwrite=overwrite)
  arrangement.fix_index_files(dir_path=os.path.dirname(item_path), overwrite=False, dry_run=False)
