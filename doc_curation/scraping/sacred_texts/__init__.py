import logging
import os

import regex
from bs4 import NavigableString, BeautifulSoup

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.scraping.html_scraper import souper


def footnote_extractor(footnote_div):
  footnote_elements = footnote_div.findChildren('p',recursive=False)
  content_out = ""
  for tag in footnote_elements:
    anchors = tag.findChildren('a',recursive=False)
    if len(anchors) < 2:
      continue
    footnote_id = anchors[0].get('name').strip()
    for anchor in anchors:
      anchor.decompose()
    definition = get_text(tag).strip()
    content_out += "\n\n[^%s]: %s" % (footnote_id, definition)
  content_out = content_out.replace("", " - ")
  return content_out


def decode_italicized_text(text):
  replacements = {"n": "ṇ", "t": "ṭ", "d": "ḍ", "m": "ṁ", "h": "ḥ", "ri": "r̥", "k": "c", "g": "j", "s": "ś"} # sh not intalicized is ṣ
  for x, y in replacements.items():
    text = text.replace(x, y)
    text = text.replace(x.capitalize(), y.capitalize())
  return text


def get_text(tag):
  content_out = ""
  if isinstance(tag, NavigableString):
    content_out += tag
  elif tag.name == "i":
    content_out += decode_italicized_text(tag.text)
  elif tag.name == "br":
    content_out += "  \n"
  else:
    for child in tag.children:
      if child.name == "p":
        content_out += "\n\n"
      content_out += get_text(tag=child)
  return content_out


def get_content_divs(soup):
  partitions = soup.select("div.fake_partition_div")
  main_content_tag = None
  footnote_content_tag = None
  for partition in partitions:
    footnote_tags = [x for x in partition.select("*") if x.text.startswith("Footnote")]
    if len(footnote_tags) > 0:
      footnote_content_tag = partition
      break
    else:
      main_content_tag = partition
  return (main_content_tag, footnote_content_tag)


def get_main_content(main_content_tag):
  content_out = ""
  for child in main_content_tag.children:
    content_out += get_text(tag=child)
    content_out += "\n\n"
  return content_out


def get_content(soup, main_content_extractor=get_main_content):
  # Pandoc cannot handle html footnotes well by itself. Hence, not using it.
  souper.insert_divs_between_tags(soup, "hr")
  footnote_markers = soup.select("a[href]>font[size='1']")
  for marker in footnote_markers:
    footnote_id = marker.parent.get("href").replace("#", "")
    footnote_md = f"[^{footnote_id}]"
    marker.parent.replace_with(footnote_md)

  souper.tag_remover(soup=soup, css_selector="font[size='-1']")
  souper.tag_remover(soup=soup, css_selector="font[size='-2']")
  souper.tag_remover(soup=soup, css_selector="font[color='GREEN']")

  (main_div, footnote_div) = get_content_divs(soup=soup)
  content_out = main_content_extractor(main_div)

  content_out += footnote_extractor(footnote_div)
  content_out = content_processor.define_footnotes_near_use(content=content_out)
  replacements = {"â": "ā", "î": "ī", "û": "ū", "": "\\`", "": " - ", " ": " "}
  for x, y in replacements.items():
    content_out = content_out.replace(x, y)
    content_out = content_out.replace(x.capitalize(), y.capitalize())
  content_out = regex.sub("\n\n+", "\n\n", content_out)
  return content_out


def dump(url, outfile_path, main_content_extractor=get_main_content, dry_run=False, overwrite=False):
  if callable(outfile_path):
    outfile_path = outfile_path(url)
  if not overwrite and os.path.exists(outfile_path):
    logging.info("skipping: %s - it exists already", outfile_path)
    return
  logging.info("Dumping: %s to %s", url, outfile_path)
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  content = get_content(soup=soup, main_content_extractor=main_content_extractor)
  title = souper.title_from_element(soup, title_css_selector="h4")
  md_file = MdFile(file_path=outfile_path)
  md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=dry_run)
  return soup


def dump_serially(start_url, base_dir, dest_path_maker, dry_run=False):
  next_url_getter = lambda soup, base_url: souper.anchor_url_from_soup_css(soup=soup, css="center a", base_url=base_url, pattern="Next:")

  next_url = start_url
  while next_url:
    from doc_curation.scraping.sacred_texts import para_translation
    soup = dump(url=next_url, outfile_path=lambda x: dest_path_maker(x, base_dir=base_dir), dry_run=dry_run, main_content_extractor=para_translation.get_main_content)
    if soup is None:
      html = souper.get_html(url=next_url)
      soup = BeautifulSoup(html, 'html.parser')
    next_url = next_url_getter(soup, base_url=next_url)
    # break # For testing
  logging.info("Reached end of series")


def dump_meta_article(url, outfile_path):
  dump(url=url, outfile_path=outfile_path, overwrite=True)
  library.fix_index_files(os.path.dirname(outfile_path), transliteration_target=None)
  metadata_helper.set_title_from_filename(md_file=MdFile(file_path=outfile_path), dry_run=False, transliteration_target=None)