import logging
import os
import urllib
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from curation_utils import file_helper
from curation_utils import scraping
from doc_curation.md.file import MdFile

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


def get_tags_matching_css(soup, css_selector_list):
  for css in css_selector_list:
    tags = soup.select(css)
    if len(tags) > 0:
      return tags
  return []


def tag_replacer(soup, css_selector, tag_name):
  for element in soup.select(css_selector):
    element.name = tag_name


def tag_remover(soup, css_selector):
  for element in soup.select(css_selector):
    element.decompose()


def get_content_from_element(url, text_css_selector, soup=None):
  html = get_html(url=url)
  if soup is None:
    soup = BeautifulSoup(html, 'html.parser')
  content_element = soup.select(text_css_selector)
  if len(content_element) == 0:
    logging.warning("Could not get text from %s for css selector: %s with soup", url, text_css_selector)
    try:
      with urllib.request.urlopen(url) as filehandle:
        content = filehandle.read().decode("utf8")
    except HTTPError:
      logging.warning("404 on %s", url)
      content = None
  else:
    content = content_element[0].decode_contents()
  return content


def title_from_element(soup, title_css_selector=None, title_prefix=""):
  if title_css_selector is not None:
    title_elements = soup.select(title_css_selector)
    if len(title_elements) > 0:
      title = " ".join(title_element.text for title_element in title_elements)
    else:
      title = "UNKNOWN_TITLE"
    title = ("%s %s" % (title_prefix, title)).strip()
  return title


def find_matching_tags(tags, filter):
  return [tag for tag in tags if filter(tag)]


def find_matching_tag(tags, filter):
  tags = find_matching_tags(tags=tags, filter=filter)
  if len(tags) > 0:
    return tags[0]
  return None


def dump_text_from_element(url, outfile_path, text_css_selector, title_maker, title_prefix="", html_fixer=None, md_fixer=None, dry_run=False):
  if os.path.exists(outfile_path):
    logging.info("skipping: %s - it exists already", outfile_path)
    return
  logging.info("Dumping: %s to %s", url, outfile_path)
  html = get_html(url=url)
  unaltered_soup = BeautifulSoup(html, 'html.parser')
  soup = BeautifulSoup(html, 'html.parser')

  if html_fixer is not None:
    html_fixer(soup)

  metadata = {"title": title_maker(soup, title_prefix)}

  # We definitely want to return the original html even if the file exists - we may need to navigate to the next element.
  if os.path.exists(outfile_path):
    logging.info("Skipping dumping: %s to %s", url, outfile_path)
    return unaltered_soup

  content = get_content_from_element(soup=soup, text_css_selector=text_css_selector, url=url)

  md_file = MdFile(file_path=outfile_path)
  md_file.import_content_with_pandoc(content=content, source_format="html", dry_run=dry_run, metadata=metadata)
  if md_fixer is not None:
    [_, md] = md_file.read()
    md = md_fixer(md)
    md_file.replace_content_metadata(new_content=md, dry_run=dry_run)
  

  logging.info("Done: %s to %s", url, outfile_path)
  return unaltered_soup


def next_url_from_soup_css(soup, css, base_url):
  next_links = soup.select(css)
  if len(next_links) > 0:
    return urljoin(base_url, next_links[0]["href"])
  return None


def dump_series(start_url, out_path, dumper, next_url_getter, index_format="%02d", dry_run=False):
  index = 1
  next_url = start_url
  while next_url:
    soup = dumper(url=next_url, outfile_path=os.path.join(out_path, index_format % index + ".md"), title_prefix= index_format % index, dry_run=dry_run)
    next_url = next_url_getter(soup)
    index = index + 1
    # break # For testing
  logging.info("Reached end of series")



def markdownify_local_htmls(src_dir, dest_dir, dumper, dry_run=False):
  file_paths = sorted(Path(src_dir).glob("**/*.htm*"))
  for index, src_path in enumerate(file_paths):
    dest_path = str(src_path).replace(".html", ".md").replace(".htm", ".md").replace(src_dir, dest_dir)
    dest_path = file_helper.clean_file_path(dest_path)
    _ = dumper(url="file://" + str(src_path), outfile_path=dest_path, title_prefix="%02d" % index, dry_run=dry_run)


def get_md_paragraph(tags):
  return "  \n".join([x.strip() for x in tags if isinstance(x, str) and x.strip() != ""])

def get_md_paragraphs_with_pandoc(tags, para_joiner="\n\n"):
  from doc_curation.md import get_md_with_pandoc
  return para_joiner.join([get_md_with_pandoc(content_in=str(x), source_format="html") for x in tags])

