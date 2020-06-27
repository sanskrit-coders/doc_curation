import os

import regex
import logging

from bs4 import BeautifulSoup, Tag
from indic_transliteration import sanscript

from curation_utils import scraping, file_helper
from doc_curation.md_helper import MdFile

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

browser = scraping.get_selenium_browser(headless=True)


def get_title(title_iast_in):
    title_iast = title_iast_in.replace("Part ", "").replace("Volume ", "").replace("volume ", "").replace("Vol. ", "").replace("with ", "").replace("text ", "").replace("version ", "").replace("by ", "").replace("commentary ", "").replace("commentaries ", "").replace("rescension ", "").replace("ṣṃ", "ṣm").strip()
    return title_iast


def get_author(author_iast_in):
    author_iast = author_iast_in.replace("anonymous", "").replace("attributed ", "").replace("to ", "").replace("to: ", "").replace("chapters ", "").replace("thru ", "").strip()
    return author_iast


def get_file_path(out_dir, title_iast, author_iast="", catalog_number=""):
    title_optitrans = sanscript.transliterate(data=title_iast, _from=sanscript.IAST, _to=sanscript.OPTITRANS)
    author_optitrans = sanscript.transliterate(data=author_iast, _from=sanscript.IAST, _to=sanscript.OPTITRANS)
    file_path = "%s_%s_%s.md" % (title_optitrans, author_optitrans, catalog_number.strip())
    file_path = file_helper.clean_file_path(file_path=file_path)
    file_path = os.path.join(out_dir, file_path)
    return file_path


def get_text(url):
    logging.info("Processing %s", url)
    soup = scraping.get_soup(url=url)
    content = soup.select("pre")[0].text
    content = sanscript.transliterate(data=content, _from=sanscript.IAST, _to=sanscript.DEVANAGARI)
    return content


def get_front_matter(html):
    frontmatter = {}
    soup = BeautifulSoup(html, features="lxml")
    item_heads = soup.select("span.listItemName")
    for item_head in item_heads:
        tag = item_head.text.replace(":", "")
        tag = tag.strip()
        values = frontmatter.get(tag, [])
        value_item = item_head.next_sibling
        while value_item.name == "br":
            value_item = value_item.next_sibling
        while isinstance(value_item, Tag) and value_item.has_attr("class") and value_item["class"][0] == "listItem":
            values.extend([value_item.text.strip()])
            value_item = value_item.next_sibling
        if tag in ['Catalog number', 'Uniform title', 'Main title', 'Description', 'Notes', 'Publication country']:
            frontmatter[tag] = values[0]
        else:
            frontmatter[tag] = values
    if 'Notes' in frontmatter:
        frontmatter.pop('Notes')
    if 'E-text' in frontmatter:
        frontmatter.pop('E-text')
    frontmatter["title_iast"] = get_title(frontmatter["Uniform title"])
    if "Author" in frontmatter:
        frontmatter["author_iast"] = get_author(frontmatter["Author"][0])
    frontmatter["title"] = sanscript.transliterate(data=frontmatter["title_iast"], _from=sanscript.IAST, _to=sanscript.DEVANAGARI)
    return frontmatter


def process_catalog_page_selenium(url, out_dir):
    logging.info("Processing catalog %s", url)
    browser.get(url=url)
    text_links = browser.find_elements_by_link_text("View in Unicode transliteration")
    if len(text_links) == 0:
        logging.warning("%s does not have text", url)
        return

    catalog_body = browser.find_element_by_css_selector(".catalog_record_body")
    metadata = get_front_matter(catalog_body.get_attribute('innerHTML'))
    logging.info(metadata)

    dest_file_path = get_file_path(out_dir=out_dir, title_iast=metadata["title_iast"], author_iast=metadata.get("author_iast", ""), catalog_number=metadata.get("Catalog number", ""))
    if os.path.exists(dest_file_path):
        logging.warning("Skipping %s - already exists.", dest_file_path)

    text_url = text_links[0].get_attribute("href")
    file = MdFile(file_path=dest_file_path, frontmatter_type="toml")
    text = get_text(url=text_url)
    text = text.replace("\n", "  \n")
    file.dump_to_file(metadata=metadata, md=text, dry_run=False)


def process_catalog_page_soup(url):
    """Does not work - get template content which is different from actual view in browser."""
    soup = scraping.get_soup(url=url)


def get_docs(out_dir):
    soup = scraping.get_soup("https://etexts.muktabodha.org/DL_CATALOG_USER_INTERFACE/dl_user_interface_list_catalog_records.php?sort_key=title")
    links = soup.select("a")
    for link in links:
        url = "https://etexts.muktabodha.org/DL_CATALOG_USER_INTERFACE/%s" % link["href"]
        process_catalog_page_selenium(url=url, out_dir=out_dir)
        # exit()
