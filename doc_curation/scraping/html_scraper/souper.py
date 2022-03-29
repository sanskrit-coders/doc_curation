import codecs
import logging
import os
import urllib
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin

import regex
from bs4 import BeautifulSoup, Tag, Comment
from doc_curation import md

from curation_utils import file_helper, scraping
from curation_utils import scraping
from doc_curation.md import content_processor
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


def tag_appender(soup, css_selector, tag_name):
  for element in soup.select(css_selector):
    element.insert_after(soup.new_tag(tag_name))


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


def strip_comments(soup):
  comments = soup.find_all(string=lambda text: isinstance(text, Comment))
  for comment in comments:
    comment.extract()


def find_matching_tags(tags, filter):
  return [tag for tag in tags if filter(tag)]


def find_matching_tag(tags, filter):
  tags = find_matching_tags(tags=tags, filter=filter)
  if len(tags) > 0:
    return tags[0]
  return None


def empty_tag(tag):
  for a in list(tag.children):
    if isinstance(a, Tag):
      a.decompose()
    else:
      a.extract()


def dump_text_from_element(url, outfile_path, text_css_selector, title_maker, title_prefix="", html_fixer=None, footnote_definier=None, md_fixer=None, overwrite=False, dry_run=False):
  if callable(outfile_path):
    outfile_path = outfile_path(url)
  if os.path.exists(outfile_path) and not overwrite:
    logging.info("skipping: %s - it exists already", outfile_path)
    # We definitely want to return the original html even if the file exists - we may need to navigate to the next element.
    return scraping.get_soup(url)
  logging.info("Dumping: %s to %s", url, outfile_path)
  html = get_html(url=url)
  unaltered_soup = BeautifulSoup(html, 'html.parser')
  soup = BeautifulSoup(html, 'html.parser')

  if html_fixer is not None:
    html_fixer(soup)

  metadata = {"title": title_maker(soup, title_prefix)}

  content = get_content_from_element(soup=soup, text_css_selector=text_css_selector, url=url)

  md_file = MdFile(file_path=outfile_path)
  content = md.get_md_with_pandoc(content_in=content, source_format="html")


  if md_fixer is not None:
    # md_fixer may fix footnote markers as well. So it should be called earlier.
    content = md_fixer(content)

  if footnote_definier is not None:
    footnote_md = footnote_definier(unaltered_soup)
    content = "%s\n\n%s" % (content, footnote_md)
    content = content_processor.define_footnotes_near_use(content=content)

  md_file.dump_to_file(content=content, metadata=metadata, dry_run=dry_run)

  logging.info("Done: %s to %s", url, outfile_path)
  return unaltered_soup


def anchor_url_from_soup_css(soup, css, base_url, pattern=None):
  links = soup.select(css)
  if pattern is not None:
    links = [link for link in links if regex.match(pattern, link.text)]
  if len(links) > 0:
    return urljoin(base_url, links[0]["href"])
  return None



def dump_series(start_url, out_path, dumper, next_url_getter, end_url=None, index_format="%02d", dry_run=False):
  index = 1
  next_url = start_url
  while next_url:
    soup = dumper(url=next_url, outfile_path=os.path.join(out_path, index_format % index + ".md"), title_prefix= index_format % index, dry_run=dry_run)
    assert soup is not None, "Dumper returning None soup"
    if next_url == end_url:
      break
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


def insert_divs_between_tags(soup, css):
  border_elements = soup.select(css)
  for index, border in enumerate(border_elements):
    if index == len(border_elements) - 1:
      next_border = None
    else:
      next_border = border_elements[index + 1]
    mid_nodes = []
    next_node = border.nextSibling
    while next_node and next_node != next_border:
      mid_nodes.append(next_node)
      next_node = next_node.nextSibling
    container_div = soup.new_tag("div", attrs={"class": "fake_partition_div"})
    border.insert_after(container_div)
    for mid_node in mid_nodes:
      mid_node.extract()
      container_div.append(mid_node)


def get_md_paragraphs_with_pandoc(tags, para_joiner="\n\n"):
  from doc_curation.md import get_md_with_pandoc
  return para_joiner.join([get_md_with_pandoc(content_in=str(x), source_format="html") for x in tags])


def gather_urls(soup, css, base_url=None, link_filter=None):
  links = soup.select(css)
  if link_filter is not None:
    links = [l for l in links if link_filter(l)]
  urls = [l["href"] for l in links]
  if base_url is not None:
    urls = [urljoin(base_url, url) for url in urls]
  return urls


def get_indexed_urls(start_url, next_url_getter, url_gatherer, url_file_path=None, overwrite=False):
  if os.path.exists(url_file_path) and not overwrite:
    logging.info("Using cached urls.")
    with codecs.open(url_file_path, "r") as f:
      return [x.strip() for x in f.readlines()]
  urls = []
  url = start_url
  while url is not None:
    soup = scraping.get_soup(url)
    urls.extend(url_gatherer(soup, url))
    url = next_url_getter(soup, url)
  if url_file_path is not None:
    os.makedirs(os.path.dirname(url_file_path), exist_ok=True)
    with codecs.open(url_file_path, "w") as f:
      f.write("\n".join(urls))
  return urls