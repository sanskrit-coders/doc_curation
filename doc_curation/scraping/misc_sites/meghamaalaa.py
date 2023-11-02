from indic_transliteration import sanscript

from curation_utils import scraping
from urllib.parse import urljoin
from doc_curation import md
from doc_curation.md import library, content_processor
from curation_utils.file_helper import get_storage_name
from doc_curation.utils import text_utils

from doc_curation.md.file import MdFile
import logging
import os, regex
import aksharamukha

def get_text(url, source_script=sanscript.DEVANAGARI):
  soup = scraping.get_soup(url=url)
  title = soup.select_one("h1.entry-title").text
  content_tag = soup.select_one("#chapter-content")
  content = md.get_md_with_pandoc(content_in=str(content_tag), source_format="html")
  content = content.replace("\|", "।")
  content = regex.sub("।।+", "॥", content)
  if source_script == sanscript.DEVANAGARI:
    content = regex.sub("ळ", "ल", content)
    content = regex.sub(":", "ः", content)
    content = regex.sub("s", "ऽ", content)
  elif source_script.startswith(sanscript.TAMIL):
    content = regex.sub(r"\*\*([²³⁴₂₃₄])\*\*", "$1", content)
    content = regex.sub(r"\*\* \*\*", " ", content)
    content = regex.sub("श्रिय:", "श्रियः", content)
    content = regex.sub(":", "-", content)
    content = regex.sub("&nbsp;", "", content)
    content = regex.sub("[sS]", "ऽ", content)
    content = content_processor.transliterate(text=content, source_script=source_script)
  content = regex.sub("\n.+?Audio Archive.+?\n", "", content)
  logging.info(f"Got {title} from {url}")
  return (title, content)


def dump_text(url, dest_path, source_script=sanscript.DEVANAGARI, overwrite=False, dry_run=False):
  if os.path.exists(dest_path) and not overwrite:
    logging.info(f"Skipping {dest_path}")
    return 
  (title, content) = get_text(url=url, source_script=source_script)
  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=dry_run)

def dump_series(url, dest_path, start_index=None, filename_from_title=None, source_script=sanscript.DEVANAGARI, overwrite=False):
  soup = scraping.get_soup(url=url)
  logging.info(f"Dumping series starting {url}")
  parts_tag = soup.select_one("#chapter-content").find_previous_sibling('div')
  links = list(parts_tag.select("a"))
  for index, link in enumerate(links):
    if filename_from_title is not None:
      file_name = f"{get_storage_name(text=filename_from_title(link.text), max_length=20, source_script=source_script)}.md"
    else:
      file_name = ".md"
    if not start_index is None:
      file_name = f"{start_index - index :02d}_{file_name}"
    else:
      file_name = f"{index + 1:02d}_{file_name}"
    file_name = file_name.replace("_.", ".")
    dest_subpath = os.path.join(dest_path, file_name)
    dump_text(url=link["href"], dest_path=dest_subpath, source_script=source_script, overwrite=overwrite)
  library.fix_index_files(dir_path=os.path.dirname(dest_path), overwrite=False, dry_run=False)
  