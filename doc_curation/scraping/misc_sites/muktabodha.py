import logging
import os

from selenium.webdriver.common.by import By

import doc_curation.utils.sanskrit_helper
import regex
from bs4 import BeautifulSoup, Tag
from curation_utils import scraping, file_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import space_helper, footnote_helper
from doc_curation.md.file import MdFile
from doc_curation.utils import sanskrit_helper
from indic_transliteration import sanscript

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


creds = "muktabodha:indology123"
browser = scraping.get_selenium_chrome(headless=True)


def get_title(title_iast_in):
  title_iast = title_iast_in.replace("Part ", "").replace("Volume ", "").replace("volume ", "").replace("Vol. ",
                                                                                                        "").replace(
    "with ", "").replace("text ", "").replace("version ", "").replace("by ", "").replace("commentary ", "").replace(
    "commentaries ", "").replace("rescension ", "").replace("ṣṃ", "ṣm").strip()
  return title_iast


def get_author(author_iast_in):
  author_iast = author_iast_in.replace("anonymous", "").replace("attributed ", "").replace("to ", "").replace("to: ",
                                                                                                              "").replace(
    "chapters ", "").replace("thru ", "").strip()
  return author_iast


def get_file_path(out_dir, title_iast, author_iast=None, catalog_number=None):
  title_optitrans = sanscript.transliterate(data=title_iast, _from=sanscript.IAST, _to=sanscript.OPTITRANS)
  if author_iast is None:
    author_dir = "unknown"
  else:
    author_dir = sanscript.transliterate(data=author_iast, _from=sanscript.IAST, _to=sanscript.OPTITRANS)
  file_path = title_optitrans
  if catalog_number is not None:
    file_path = f"{title_optitrans}__{catalog_number.strip()}"
  file_path = f"{file_path}.md"
  file_path = file_helper.clean_file_path(file_path=file_path)
  file_path = os.path.join(out_dir, file_helper.clean_file_path(file_path=author_dir), file_path)
  return file_path



def get_text(url):
  logging.info("Processing %s", url)
  soup = scraping.get_soup(url=url)
  content = soup.select("pre")[0].text
  content = regex.sub("\nMUKTABODHA INDOLOGICAL.+", "", content)
  content = content.replace("||", "॥").replace("|", "।")
  content = regex.sub("॥[॥।]+", "…", content)
  content = regex.sub("\n- *\n", "-  \n", content)
  return content


def from_iast_text(url):
  content = get_text(url=url)
  content = sanscript.transliterate(data=content, _from=sanscript.IAST, _to=sanscript.DEVANAGARI, togglers={}, suspend_on={}, suspend_off={})
  content = content.replace("\"न\्", "ङ्")
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
  frontmatter["title"] = sanscript.transliterate(data=frontmatter["title_iast"], _from=sanscript.IAST,
                                                 _to=sanscript.DEVANAGARI)
  return frontmatter


def process_catalog_page_selenium(url, out_dir):
  logging.info("Processing catalog %s", url)
  # For some reason, soup does not manage to get the full source. Content of div.catalog_record_body is empty. Hence using selenium.
  
  browser.get(url=url)
  text_links = browser.find_elements(By.LINK_TEXT, "View in Unicode transliteration")
  # The below yields rare transliteration errors, such as  तडिच्चञ्चलमायुश्च कस्य स्याज्जगतो [धृ]तिः ॥ in kulArNavatantra:30.
  # text_links = browser.find_elements_by_link_text("View in Unicode devanagari")
  if len(text_links) == 0:
    logging.warning("%s does not have text", url)
    return

  catalog_body = browser.find_element(By.CSS_SELECTOR, ".catalog_record_body")
  metadata = get_front_matter(catalog_body.get_attribute('innerHTML'))
  logging.info(metadata)

  dest_file_path = get_file_path(out_dir=out_dir, title_iast=metadata["title_iast"],
                                 author_iast=metadata.get("author_iast", None),
                                 catalog_number=metadata.get("Catalog number", None))
  if os.path.exists(dest_file_path):
    logging.warning("Skipping %s - already exists.", dest_file_path)
    return

  text_url = text_links[0].get_attribute("href")
  file = MdFile(file_path=dest_file_path, frontmatter_type="toml")
  text = from_iast_text(url=text_url)
  text = sanskrit_helper.fix_lazy_anusvaara(text=text)
  text = sanskrit_helper.fix_bad_anunaasikas(text)
  text = regex.sub("ए-तेxत्स् मय् बे विएwएद् ओन्ल्य् ओन्लिने ओर् दोwन्लोअदेद् फ़ोर् प्रिवते स्तुद्य्। *", "", text)
  text = text.replace("\n", "  \n")
  file.dump_to_file(metadata=metadata, content=text, dry_run=False)


def process_catalog_page_soup(url):
  """Does not work - get template content which is different from actual view in browser."""
  soup = scraping.get_soup(url=url)

# TODO: can be made a bit more efficient by following https://muktalib7.com/DL_CATALOG_ROOT/MUKTABODHA-LIBRARY-DEVANAGARI/DEV-TITLE-LINK-LIST.html or https://muktalib7.com/DL_CATALOG_ROOT/MUKTABODHA-LIBRARY-IAST/UTF8-TITLE-LINK-LIST.html .  
# But they do not include the etexts of the cumulative Muktabodha/IFP collection.
def get_docs(out_dir):
  soup = scraping.get_soup(
    "https://%s@muktalib7.com/DL_CATALOG_ROOT/DL_CATALOG/DL_CATALOG_USER_INTERFACE/dl_user_interface_list_catalog_records.php?sort_key=title" % creds)
  links = soup.select("a")
  for link in links:
    url = "https://%s@muktalib7.com/DL_CATALOG_ROOT/DL_CATALOG/DL_CATALOG_USER_INTERFACE/%s" % (creds, link["href"])
    process_catalog_page_selenium(url=url, out_dir=out_dir)
    # exit()

def fix_footnotes(dir_path):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.inline_comments_to_footnotes(c), dry_run=False)
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.fix_intra_word_footnotes(c), dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.define_footnotes_near_use(c), dry_run=False)



def fix_lines(dir_path):
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n|^)प् *।.+\) *"], replacement="")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n)[ \t]+"], replacement="")

  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=[\S]) *\n(?=\S)"], replacement=r" ")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=[।॥]) *(?=[^०-९\s])"], replacement=r"  \n")
  


if __name__ == '__main__':
  text = from_iast_text(url="https://%s@muktalib7.com/DL_CATALOG_ROOT/DL_CATALOG/DL_CATALOG_USER_INTERFACE/dl_user_interface_create_utf8_text.php?hk_file_url=..%%2FTEXTS%%2FETEXTS%%2FmaliniivijayottaraHK.txt&miri_catalog_number=M00160" % creds)