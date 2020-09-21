import logging
import os
import urllib

from bs4 import BeautifulSoup

from curation_utils import scraping
from doc_curation import md_helper

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def get_html(url):
  soup = scraping.get_soup(url)
  body_element = soup.select("body")
  if len(body_element) == 0:
    logging.warning("Could not get text form %s with soup", url)
    filehandle = urllib.request.urlopen(url)
    content = filehandle.read().decode("utf8")
    filehandle.close()
  else:
    content = body_element[0].decode_contents()
  return content


def tag_replacer(soup, css_selector, tag_name):
  for element in soup.select(css_selector):
    element.name = tag_name


def tag_remover(soup, css_selector):
  for element in soup.select(css_selector):
    element.decompose()


def content_from_element(soup, text_css_selector, url):
  content_element = soup.select(text_css_selector)
  if len(content_element) == 0:
    logging.warning("Could not get text form %s with soup", url)
    with urllib.request.urlopen(url) as filehandle:
      content = filehandle.read().decode("utf8")
  else:
    content = content_element[0].decode_contents()
  return content



def dump_text_from_element(url, outfile_path, text_css_selector, title_css_selector=None, title_prefix=None,
                           fallback_title_maker=None, html_fixer=None, dry_run=False):
  logging.info("Dumping: %s to %s", url, outfile_path)
  html = get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')

  def get_metadata():
    metadata = {}
    if title_css_selector is not None:
      title_elements = soup.select(title_css_selector)
      if len(title_elements) > 0:
        metadata["title"] = title_elements[0].text
    if "title" not in metadata:
      if fallback_title_maker is not None:
        metadata["title"] = fallback_title_maker()
      else:
        metadata["title"] = "UNKNOWN_TITLE"
      metadata["title"] = (title_prefix + metadata["title"]).strip()

    return metadata

  metadata = get_metadata()

  if html_fixer is not None:
    html_fixer(soup)

  if os.path.exists(outfile_path):
    logging.info("Skipping dumping: %s to %s", url, outfile_path)
    return soup

  content = content_from_element(soup=soup, text_css_selector=text_css_selector, url=url)

  md_file = md_helper.MdFile(file_path=outfile_path)
  md_file.import_content_with_pandoc(content=content, source_format="html", dry_run=dry_run, metadata=metadata)

  logging.info("Done: %s to %s", url, outfile_path)
  return BeautifulSoup(html, 'html.parser')


def next_url_from_soup_css(soup, css, base_url):
  next_links = soup.select(css)
  if len(next_links) > 0:
    return base_url + next_links[0]["href"]
  return None


def dump_series(start_url, out_path, dumper, next_url_getter, dry_run=False):
  index = 1
  next_url = start_url
  while next_url:
    soup = dumper(url=next_url, outfile_path=os.path.join(out_path, "%02d.md" % index), title_prefix="%02d" % index, dry_run=dry_run)
    next_url = next_url_getter(soup)
    index = index + 1
    # break # For testing
  logging.info("Reached end of series")
