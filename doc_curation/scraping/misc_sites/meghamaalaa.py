from indic_transliteration import sanscript
from collections import OrderedDict

from curation_utils import scraping
from urllib.parse import urljoin
from doc_curation import md
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import space_helper
from curation_utils.file_helper import get_storage_name
from doc_curation.utils import text_utils

from doc_curation.md.file import MdFile
import logging
import os, regex
import aksharamukha

def get_text(url, source_script=sanscript.DEVANAGARI):
  soup = scraping.get_soup(url=url)
  title_tag = soup.select_one("h1.elementor-heading-title")
  if title_tag is not None:
    title = title_tag.text
  else:
    logging.fatal("Can't grok title.")
  content_tag = soup.select_one(".elementor-widget-theme-post-content .elementor-widget-container")
  content = md.get_md_with_pandoc(content_in=str(content_tag), source_format="html")
  content = fix_text(content, source_script)
  logging.info(f"Got {title} from {url}")
  return (title, content)


def fix_text(text, source_script):
  text = text.replace("\|", "।")
  text = regex.sub("।।+", "॥", text)
  if source_script == sanscript.DEVANAGARI:
    text = regex.sub("ळ", "ल", text)
    text = regex.sub(":", "ः", text)
    text = regex.sub("s", "ऽ", text)
  elif source_script.startswith(sanscript.TAMIL):
    text = regex.sub(r"\*\*([²³⁴₂₃₄])\*\*", r"\1", text)
    text = regex.sub("श्रिय:", "श्रियः", text)
    # content = regex.sub(":", "-", content) - fails with sanskrit parts of maNipravALa!
    text = regex.sub("&nbsp;", "", text)
    text = regex.sub("[sS]", "ऽ", text)
    text = content_processor.transliterate(text=text, source_script=source_script)
  text = regex.sub(r"\*\*ः", "ः**", text)
  text = regex.sub(r"(\*{1,2})ः\1", "ः", text)
  text = regex.sub(r"(?<=^|\n)\*\*\((.+?)\)\*\*(?=$|\n)", r"## \1", text)
  text = space_helper.fix_markup(text)
  text = regex.sub("\n.+?Audio Archive.+?\n", "", text)
  return text


def dump_text(url, dest_path, source_script=sanscript.DEVANAGARI, overwrite=False, dry_run=False):
  if os.path.exists(dest_path) and not overwrite:
    logging.info(f"Skipping {dest_path}")
    return 
  (title, content) = get_text(url=url, source_script=source_script)
  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=dry_run)

def dump_series(url, dest_path, start_index=None, end_index=None, filename_from_title=None, source_script=sanscript.DEVANAGARI, overwrite=False):
  soup = scraping.get_soup(url=url)
  logging.info(f"Dumping series starting {url}")
  parts_tag = soup.select_one(".related-posts-meghamala")
  links = list(parts_tag.select("a"))
  index_to_link = OrderedDict()
  for index, link in enumerate(links):
    index_to_link[index + 1] = link
  if start_index is not None:
    for index in [x for x in index_to_link.keys()]:
      if index < start_index:
        index_to_link.pop(index)
  if end_index is not None:
    for index in [x for x in index_to_link.keys()]:
      if index > end_index:
        index_to_link.pop(index)
  for index, link in index_to_link.items():
    if filename_from_title is not None:
      file_name = f"{get_storage_name(text=filename_from_title(link.text), max_length=20, source_script=source_script)}.md"
    else:
      file_name = ".md"
    if not regex.match("\d+", file_name):
      file_name = f"{index:02d}b_{file_name}"
    file_name = file_name.replace("_.", ".")
    dest_subpath = os.path.join(dest_path, file_name)
    dump_text(url=link["href"], dest_path=dest_subpath, source_script=source_script, overwrite=overwrite)
  library.fix_index_files(dir_path=os.path.dirname(dest_path), overwrite=False, dry_run=False)
  