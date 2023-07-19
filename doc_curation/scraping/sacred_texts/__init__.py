import logging
import os

from indic_transliteration import sanscript

import doc_curation.md.content_processor.footnote_helper
import regex
from bs4 import NavigableString, BeautifulSoup

import doc_curation.md.library.arrangement
from curation_utils import scraping
from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper, arrangement
from doc_curation.scraping.html_scraper import souper


def get_footnote_def_text(footnote_div):
  definitions = get_footnote_definitions(footnote_div)

  content_out = ""
  for footnote_id, definition in definitions.items():
    content_out += "\n\n[^%s]: %s" % (footnote_id, definition)
  content_out = content_out.replace("", " - ")
  return content_out


def get_footnote_definitions(footnote_div):
  footnote_elements = footnote_div.findChildren('p', recursive=False)
  definitions = {}
  prev_footnote = None
  for tag in footnote_elements:
    anchors = tag.findChildren('a', recursive=False)
    if len(anchors) < 2:
      continue
    footnote_id = anchors[0].get('name')
    anchors[0].decompose()
    definition = get_text(tag).strip()
    if footnote_id is None:
      definitions[prev_footnote] += definition
    else:
      footnote_id = footnote_id.strip()
    definitions[footnote_id] = definition
    prev_footnote = footnote_id
  return definitions


def decode_italicized_text(text):
  replacements = {"n": "ṇ", "t": "ṭ", "d": "ḍ", "m": "ṁ", "kh": "ch", "h": "ḥ", "ri": "r̥", "k": "c", "g": "j", "s": "ś"} # sh not intalicized is ṣ
  for x, y in replacements.items():
    text = text.replace(x, y)
    text = text.replace(x.capitalize(), y.capitalize())
  return text


def get_text(tag):
  content_out = ""
  if isinstance(tag, NavigableString):
    content_out += tag
  elif tag.name == "i":
    text = tag.text
    if len(text) <= 2:
      content_out += decode_italicized_text(text)
    else:
      content_out += f"_{text}_"
  elif tag.name == "br":
    content_out += "  \n"
  else:
    for child in tag.children:
      if child.name == "p":
        content_out += "\n\n"
      content_out += get_text(tag=child)
  replacements = {"â": "ā", "î": "ī", "û": "ū", "": "\\`", "": " - ", " ": " "}
  for x, y in replacements.items():
    content_out = content_out.replace(x, y)
    content_out = content_out.replace(x.capitalize(), y.capitalize())
  return content_out


def get_content_divs(soup):
  partitions = soup.select("div.fake_partition_div")
  main_content_tag = None
  footnote_content_tag = None
  for index, partition in enumerate(partitions):
    footnote_tags = [x for x in partition.select("*") if x.text.startswith("Footnote")]
    if len(footnote_tags) > 0:
      footnote_content_tag = partition
      main_content_tag = partitions[index-1]
      break
  if main_content_tag is None:
    if len(partitions) > 1:
      # Last partition likely to be a link to next page, as in https://www.sacred-texts.com/hin/sbr/sbe43/sbe4321.htm
      main_content_tag = partitions[-2]
    else:
      main_content_tag = partitions[-1]
  return (main_content_tag, footnote_content_tag)


def get_main_content(main_content_tag):
  content_out = ""
  for child in main_content_tag.children:
    content_out += get_text(tag=child)
    content_out += "\n\n"
  return content_out


def remove_superfluous_tags(soup):
  souper.element_remover(soup=soup, css_selector="font[size='-1']")
  souper.element_remover(soup=soup, css_selector="font[size='-2']")
  souper.element_remover(soup=soup, css_selector="font[color='GREEN']")


def get_content(soup, main_content_extractor=get_main_content):
  # Pandoc cannot handle html footnotes well by itself. Hence, not using it.
  souper.insert_divs_between_tags(soup, "hr")
  footnote_markers = soup.select("a[href]>font[size='1']")
  for marker in footnote_markers:
    footnote_id = marker.parent.get("href").replace("#", "")
    footnote_md = f"[^{footnote_id}]"
    marker.parent.replace_with(footnote_md)

  (main_div, footnote_div) = get_content_divs(soup=soup)
  content_out = main_content_extractor(main_div)
  if footnote_div is not None:
    content_out += get_footnote_def_text(footnote_div)
  content_out = doc_curation.md.content_processor.footnote_helper.define_footnotes_near_use(content=content_out)
  content_out = regex.sub("\n\n+", "\n\n", content_out)
  return content_out


def dump(url, outfile_path, main_content_extractor=get_main_content, dry_run=False, overwrite=False):
  soup = None
  if callable(outfile_path):
    outfile_path = outfile_path(url)
    if isinstance(outfile_path, tuple):
      outfile_path, soup = outfile_path
    if outfile_path is None:
      logging.info(f"Likely reached special page: {url}")
      return None
  if not overwrite and os.path.exists(outfile_path):
    logging.info("skipping: %s - it exists already", outfile_path)
    return None
  logging.info("Dumping: %s to %s", url, outfile_path)
  if soup is None:
    soup = scraping.get_soup(url, features='html.parser')
  full_title = title_from_element(soup, title_css_selector="h3,h4")
  title = metadata_helper.title_from_text(text=full_title, num_words=3, target_title_length=30, script=sanscript.IAST)
  content = get_content(soup=soup, main_content_extractor=main_content_extractor)
  metadata = {"title": title}
  if full_title != title:
    metadata["full_title"] = full_title
    content = f"{full_title}\n\n{content}"
  md_file = MdFile(file_path=outfile_path)
  md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)
  metadata_helper.prepend_file_index_to_title(md_file=md_file, dry_run=dry_run)
  return soup


def title_from_element(soup, title_css_selector=None, title_prefix=""):
  title_elements = soup.select(title_css_selector)
  titles = [get_text(title_element) for title_element in title_elements]
  titles = [x for x in titles if x.strip() not in ["Footnotes"]]
  if len(titles) > 0:
    title = titles[0]
    # title = " ".join(titles)
  else:
    title = ""
  title = ("%s %s" % (title_prefix, title)).strip()
  title = title.replace(" Footnotes", "")
  return title


def dump_serially(start_url, base_dir, dest_path_maker,max_items=9999, dry_run=False):
  next_url_getter = lambda soup, base_url: souper.anchor_url_from_soup_css(soup=soup, css="center a", base_url=base_url, pattern="Next:")

  next_url = start_url
  num_items = 0
  while next_url and num_items < max_items:
    from doc_curation.scraping.sacred_texts import para_translation
    num_items = num_items + 1
    soup = dump(url=next_url, outfile_path=lambda x: dest_path_maker(x, base_dir=base_dir), dry_run=dry_run, main_content_extractor=para_translation.get_main_content)
    if soup is None:
      html = souper.get_html(url=next_url)
      soup = BeautifulSoup(html, 'html.parser')
    next_url = next_url_getter(soup, base_url=next_url)
    # break # For testing
  logging.info("Reached end of series")


def dump_meta_article(url, outfile_path):
  dump(url=url, outfile_path=outfile_path, overwrite=True)
  arrangement.fix_index_files(os.path.dirname(outfile_path), transliteration_target=None)
  metadata_helper.set_title_from_filename(md_file=MdFile(file_path=outfile_path), dry_run=False, transliteration_target=None)


def get_cross_page_footnote(url, footnote_id):
  soup = scraping.get_soup(url, "html.parser")
  souper.insert_divs_between_tags(soup, "hr")
  (main_div, footnote_div) = get_content_divs(soup=soup)
  definitions = get_footnote_definitions(footnote_div)
  return definitions.get(footnote_id, None)
