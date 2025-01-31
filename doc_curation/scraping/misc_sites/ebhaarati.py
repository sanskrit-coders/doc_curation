from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript
from curation_utils import scraping
from urllib.parse import urljoin
from doc_curation import md
from doc_curation.md import library
from doc_curation.scraping.html_scraper import souper


from doc_curation.md.file import MdFile, file_helper
from doc_curation.md.content_processor import ocr_helper
import logging
import os, regex

BASE_URL = "https://www.ebharatisampat.in/"


def get_article(url, scroll_pause=2):
  soup = scraping.scroll_and_get_soup(url=url, browser=None, scroll_pause=scroll_pause, element_css="#content")
  title = soup.select_one("li.title").text
  content_tag = soup.select("div.page-content")
  content = md.get_md_with_pandoc(content_in=str(content_tag), source_format="html")
  content = ocr_helper.misc_sanskrit_typos(content)
  content = regex.sub(r"\n +", r"\n", content)
  # content = regex.sub(r"ब्राहृ", r"ब्रह्म", content)
  content = regex.sub(r"\n(>[^\n]+)>(?=\n)", r"\n\1  ", content).replace(" > ", " ")
  
  
  page_header = f"[[{title}\tSource: [EB]({url})]]"
  content = f"{page_header}\n\n{content}"
  logging.info(f"Got {title} from {url}")
  return (content, title, soup)


def dump_article(url, outfile_path, title_prefix="", metadata=None, dry_run=False):
  (page_content, page_title, soup) = get_article(url=url, scroll_pause=2)
  if outfile_path.endswith(".md"):
    file_path = outfile_path
  else:
    file_path = os.path.join(outfile_path, file_helper.get_storage_name(text=page_title, source_script=sanscript.DEVANAGARI) + ".md")
  md_file = MdFile(file_path=file_path)
  if metadata is None:
    metadata = {}
  metadata["title"] = f"{title_prefix} {page_title}".strip()
  md_file.dump_to_file(metadata=metadata, content=page_content, dry_run=dry_run)
  library.fix_index_files(os.path.dirname(os.path.dirname(file_path)))
  return soup


def get_metadata(url):
  soup = scraping.get_soup(url=url)
  metadata = {}
  for detail_tag in soup.select(".product__info__main h5"):
    detail_parts = regex.split("\s*:\s*", detail_tag.text)
    metadata[detail_parts[0]] = ":".join(detail_parts[1:]).strip()
  button = soup.select_one(".wn__single__product a#btn")
  metadata["url"] = urljoin(BASE_URL, button["href"])
  return metadata

def dump_all(list_url="https://www.ebharatisampat.in/unicodetype.php?cat=All&sub_cat=All&author=All&publisher=All&contributor=All&language=All&sort=DESC", dest_dir="/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/ebhAratI-sampat", scroll_pause=2, use_url_cache=False):
  url_md_file = MdFile(file_path=os.path.join(dest_dir, "urls.md"))
  if not use_url_cache:
    soup = scraping.scroll_and_get_soup(url=list_url, browser=None, scroll_pause=scroll_pause, scroll_btn_css="#load_more")
    urls = [urljoin(BASE_URL, x["href"]) for x in soup.select("div.product__thumb a.first__img")]
    url_md_file.dump_to_file(metadata={"title": "URLs"}, content="\n".join(urls), dry_run=False)
  else:
    [_, urls] = url_md_file.read()
    urls = urls.split("\n")
  for url in urls:
    metadata = get_metadata(url=url)
    out_path = dest_dir
    if "DOMAIN" in metadata and metadata["DOMAIN"] != "":
      out_path = os.path.join(out_path, file_helper.get_storage_name(text=metadata["DOMAIN"]))
    if "SUB-DOMAIN" in metadata and metadata["SUB-DOMAIN"] != "":
      out_path = os.path.join(out_path, file_helper.get_storage_name(text=metadata["SUB-DOMAIN"]))
    if "AUTHOR" in metadata and metadata["AUTHOR"] != "":
      out_path = os.path.join(out_path, file_helper.get_storage_name(text=metadata["AUTHOR"]))
    if os.path.exists(out_path):
      logging.info(f"Skipping {url} with \n{metadata}")
    else:
      dump_article(url=metadata["url"], outfile_path=out_path, metadata=metadata)
  pass
  

if __name__ == '__main__':
  metadata = get_metadata("https://www.ebharatisampat.in/readunicode.php?id=ODcyMjgwNzM1OTg0OTYz")
  logging.info(metadata)