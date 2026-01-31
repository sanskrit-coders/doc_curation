from curation_utils.file_helper import get_storage_name
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import details_helper
from doc_curation.md.library import metadata_helper, arrangement
from doc_curation.utils import sanskrit_helper
from indic_transliteration import sanscript
from curation_utils import scraping
from urllib.parse import urljoin
from doc_curation import md
from doc_curation.scraping.html_scraper import souper


from doc_curation.md.file import MdFile, file_helper
import logging
import os, regex, doc_curation



config_aws = doc_curation.configuration['aws']


def dump_kIrtana(url, dest_path, overwrite=False):
  # The below fails
  # soup = scraping.get_soup(url=url, config_aws=(config_aws["id"], config_aws["key"]))
  soup = scraping.get_soup(url=url)
  def _get_text(css):
    node = soup.select_one(css)
    if node is None:
      return ""
    text = node.get_text(separator="  \n", strip=True)
    text = content_processor.transliterate(text, source_script=sanscript.TELUGU)
    return sanskrit_helper.fix_lazy_anusvaara(text, script=sanscript.DEVANAGARI).replace(":", " -")

  if url.startswith("/"):
    id = os.path.basename(url).replace(".html", "")
    url = f"https://www.andhrabharati.com/kIrtanalu/annamayya/kirtana.php?id={id}&dispScript=uc:de"

  meta = _get_text("div.vol_reku")
  composer = _get_text("div.vaggeyakara")
  raaga = regex.sub("रागमु ?- ?", "", _get_text("div.raga")).strip()
  title_raw = _get_text("title")
  if len(title_raw.split(" - ")) < 2:
    raise ConnectionError("Rate limited")
  title = title_raw.split(" - ")[2].strip()
  text = _get_text("div.content table")
  meta_detail = details_helper.Detail(title="अधिगीतम्", content=f"{composer}  \n{raaga}  \n{meta}").to_md_html()
  content_detail = details_helper.Detail(title="मूलम्", content=text.replace("\n", "  \n")).to_md_html(attributes_str="open")
  content = "\n\n".join([meta_detail, content_detail])
  md_path = os.path.join(dest_path, get_storage_name(composer), get_storage_name(raaga), get_storage_name(title) + ".md")
  if os.path.exists(md_path) and not overwrite:
    logging.info(f"Skipping {md_path}")
    return 
  dest_md = MdFile(md_path)

  # Use stable string keys in metadata.
  dest_md.dump_to_file(
    metadata={"title": title, "composer": composer, "raaga": raaga, "upstream_url": url},
    content=content,
    dry_run=False
  )

  # `fix_index_files` expects a directory path, not a file path.
  arrangement.fix_index_files(dir_path=dest_path, dry_run=False)


def dump_from_html_files(src_path, dest_path):
  for filename in os.listdir(src_path):
    if filename.endswith(".html"):
      file_path = os.path.join(src_path, filename)
      dump_kIrtana(file_path, dest_path, overwrite=False)


def get_article(url):
  soup = scraping.get_soup(url=url)
  title = soup.select_one("font[size='7']").text
  content_tag = soup.select("div.wmsect table td")[-1]
  content = pandoc_helper.get_md_with_pandoc(content_in=str(content_tag), source_format="html")
  content = content.replace(r"\|\|", "॥").replace(r"\|", "।")
  content = regex.sub(r"\n(>[^\n]+)>(?=\n)", r"\n\1  ", content).replace(" > ", " ")

  # Fix footnotes
  content = regex.sub(r"\[\\\[(\d+)\\\]\]\(.+?\)", r"[^\1]", content)
  content = regex.sub(r"(\n\[\^\d+\])", r"\1:", content)

  page_header = f"[[{title}\tSource: [AB]({url})]]"
  content = f"{page_header}\n\n{content}"
  logging.info(f"Got {title} from {url}")
  return (content, title, soup)


def dump_article(url, outfile_path, title_prefix, dry_run=False):
  (page_content, page_title, soup) = get_article(url=url)
  file_path = outfile_path
  md_file = MdFile(file_path=file_path)
  md_file.dump_to_file(metadata={"title": f"{title_prefix} {page_title}"}, content=page_content, dry_run=dry_run)
  metadata_helper.set_filename_from_title(md_file=md_file, dry_run=dry_run, source_script=sanscript.TELUGU)
  return soup

def _next_url_getter(soup, url):
  content_tag = soup.select_one("img[src='../../pics/goldright.gif']")
  if content_tag is None:
    return None
  else:
    return urljoin(url, content_tag.parent["href"])

def dump_series(url, dest_path, a_css, title=None, dry_run=False):
  
  souper.dump_series(start_url=url, out_path=dest_path, dumper=dump_article, next_url_getter=_next_url_getter, end_url=None, index_format="%02d")
  soup = scraping.scroll_and_get_soup(url=url, browser=scraping.get_selenium_chrome())
  anchor_tags = soup.select(a_css)
  anchor_tags.reverse()
  page_urls = [urljoin("https://www.prekshaa.in/", a["href"]) for a in anchor_tags]
  for index, page_url in enumerate(page_urls):
    (page_content, page_title) = get_article(url=page_url)
    
    if title is None:
      title = page_title
    page_content = regex.sub(r"\[\^(\d+)\]", rf"\n[^{index+1}.\1]", page_content)
    page_content = regex.sub(r"\n[^\n]+To be continued[^\n]+\n", "", page_content)
    content = f"{content}\n\n{page_content}"
  md_file = MdFile(file_path=dest_path)
  md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=dry_run)


