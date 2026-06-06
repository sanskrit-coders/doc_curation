import glob
import json
import logging
import os
import shutil
from collections import defaultdict
from functools import lru_cache

import tqdm
from matplotlib import scale
from selenium.webdriver.common.by import By

import doc_curation.utils.sanskrit_helper
import regex
from bs4 import BeautifulSoup, Tag
from curation_utils import scraping, file_helper
from doc_curation.ebook import pandoc_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import space_helper, footnote_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement
from doc_curation.utils import sanskrit_helper
from indic_transliteration import sanscript

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


creds = "muktabodha:indology123"

tradition_to_path = {
  "Mantranaya/Vajrayāna" : "/home/vvasuki/gitland/vishvAsa/tipiTaka/content/shAstrapiTaka",
  "Vīraśaiva": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/vIra-shaivaH",
  "Śaiva Siddhānta": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/28-Agama-sampradAyaH/tattvam/sampradAyaH/aShTa-prakaraNa-shAkhA",
  "Late Śaiva Siddhānta": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/28-Agama-sampradAyaH/tattvam/sampradAyaH/aShTa-prakaraNa-shAkhA",
  "Śivadharma": "/home/vvasuki/gitland/vishvAsa/purANam/content/shaivam",
  "Śāmbhava": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/kaulaH_shAktaH/sampradAyaH/shAmbhavaH",
  "Nepalese Sarvāmnāya": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/kaulaH_shAktaH/sampradAyaH/sarvAmnAyaH",
  "Kālīkulakrama": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/kaulaH_shAktaH/sampradAyaH/uttarAmnAyaH_kAlI-kulam_kramaH",
  "Trika": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/kaulaH_shAktaH/sampradAyaH/pUrvAmnAyaH_trikam",
  "Non-dual Śaivism of Kashmir": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/kaulaH_shAktaH/sampradAyaH/pUrvAmnAyaH_trikam",
  "Kubjikā": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/kaulaH_shAktaH/sampradAyaH/pashchimAmnAyaH_kubjikA",
  "Śrīvidyā": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/kaulaH_shAktaH/sampradAyaH/daxiNAmnAyaH_shrI-kulam",
  "Śākta General": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/kaulaH_shAktaH",
  "Kaula General": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/kaulaH_shAktaH",
  "Śaiva General": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/",
  "Bhairava Tantras": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/kaulaH_shAktaH",
  "Northeast Indian Tantra": "/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/kaulaH_shAktaH",
  "Late South Indian Tantra": "/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/sAmya-vaiShamye/articles/tantrAgamAH",
  "Vedānta": "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/",
  "Pāñcarātra": "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH",
  "Vaiṣṇava General": "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/",
  "Tantranibandha": "/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/sAmya-vaiShamye/articles/tantrAgamAH",
  "Yoga": "/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/yogaH",
  "Smārta": "/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/dharmaH/",
  "Pratiṣṭhā": "/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/sthApatyam",
  "Literary Works": "/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxaNam"
}


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


def get_file_path(out_dir, metadata):
  title_iast = metadata["Uniform title"]
  author_iast = metadata.get("Author", None)
  catalog_number = metadata.get("Catalog number", None)
  category = metadata.get("Traditions", ["mixed"])[-1]
  category_optitrans = file_helper.clean_file_path(sanscript.transliterate(data=category, _from=sanscript.IAST, _to=sanscript.OPTITRANS))
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
  file_path = os.path.join(out_dir, category_optitrans, file_helper.clean_file_path(file_path=author_dir), file_path)
  return file_path


def rearrange_library(out_dir):
  code_to_md = get_code_to_md(out_dir=out_dir)
  with open(os.path.join(out_dir, "muktabodha_metadata.json")) as f:
    lib_metadata = json.load(f)
    logging.info(f"Offline - {len(code_to_md)} files, online {len(lib_metadata)} files, to get {len(lib_metadata) - len(code_to_md)}.")
    for (code, metadata) in lib_metadata.items():
      if code not in code_to_md:
        logging.warning(f"Skip {code}")
        continue
      dest_file_path = get_file_path(out_dir=out_dir, metadata=metadata)
      source_md = code_to_md.get(code, None)
      if source_md is None or source_md.file_path == dest_file_path:
        logging.warning(f"Skip {code}")
        continue
      os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
      logging.warning(f"Moving {code}")
      shutil.move(source_md.file_path, dest_file_path)
  file_helper.remove_empty_dirs(out_dir)


def get_text(url):
  # TODO: get past the bot-buster
  (soup, result) = scraping.get_soup(url=url)
  html = soup.select_one("p")
  text = pandoc_helper.get_md_with_pandoc(content_in=html)
  text = sanskrit_helper.fix_lazy_anusvaara(text=text)
  text = sanskrit_helper.fix_bad_anunaasikas(text)
  return text


def get_local_source(code, lib_path="/home/vvasuki/Downloads/mukta/"):
  file_paths = glob.glob(f"{lib_path}{code}*")
  if len(file_paths) > 0:
    return file_paths[0]
  else:
    logging.warning(f"Could not get {code}")
    return None


def get_text_from_pre(url):
  logging.info("Processing %s", url)
  (soup, _) = scraping.get_soup(url=url)
  content = soup.select("pre")[0].text
  content = regex.sub("\nMUKTABODHA INDOLOGICAL.+", "", content)
  content = content.replace("||", "॥").replace("|", "।")
  content = regex.sub("॥[॥।]+", "…", content)
  content = content.replace("\n", "  \n")
  content = content.replace("*", r"\*")
  content = regex.sub("\n- *\n", "-  \n", content)
  content = sanskrit_helper.fix_lazy_anusvaara(text=content)
  content = sanskrit_helper.fix_bad_anunaasikas(content)
  return content


def from_iast_text(url):
  content = get_text_from_pre(url=url)
  content = sanscript.transliterate(data=content, _from=sanscript.IAST, _to=sanscript.DEVANAGARI, togglers={}, suspend_on={}, suspend_off={})
  content = content.replace("\"न\्", "ङ्")
  content = sanskrit_helper.fix_lazy_anusvaara(text=content)
  content = sanskrit_helper.fix_bad_anunaasikas(content)
  content = regex.sub("ए-तेxत्स् मय् बे विएwएद् ओन्ल्य् ओन्लिने ओर् दोwन्लोअदेद् फ़ोर् प्रिवते स्तुद्य्। *", "", content)
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
  browser = scraping.get_selenium_chrome(headless=True)

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

  dest_file_path = get_file_path(out_dir=out_dir, metadata=metadata)
  if os.path.exists(dest_file_path):
    logging.info("Skipping %s - already exists.", dest_file_path)
    return

  text_url = text_links[0].get_attribute("href")
  file = MdFile(file_path=dest_file_path, frontmatter_type="toml")
  text = from_iast_text(url=text_url)
  file.dump_to_file(metadata=metadata, content=text, dry_run=False)


def process_catalog_page_soup(url):
  """Does not work - get template content which is different from actual view in browser."""
  (soup, _) = scraping.get_soup(url=url)

# TODO: can be made a bit more efficient by following https://muktalib7.com/DL_CATALOG_ROOT/MUKTABODHA-LIBRARY-DEVANAGARI/DEV-TITLE-LINK-LIST.html or https://muktalib7.com/DL_CATALOG_ROOT/MUKTABODHA-LIBRARY-IAST/UTF8-TITLE-LINK-LIST.html .  
# But they do not include the etexts of the cumulative Muktabodha/IFP collection.
def get_docs(out_dir):
  (soup, _) = scraping.get_soup(
    "https://%s@muktalib7.com/DL_CATALOG_ROOT/DL_CATALOG/DL_CATALOG_USER_INTERFACE/dl_user_interface_list_catalog_records.php?sort_key=title" % creds)
  links = soup.select("a")
  for link in links:
    url = "https://%s@muktalib7.com/DL_CATALOG_ROOT/DL_CATALOG/DL_CATALOG_USER_INTERFACE/%s" % (creds, link["href"])
    process_catalog_page_selenium(url=url, out_dir=out_dir)
    # exit()


@lru_cache(maxsize=20)
def get_code_to_md(out_dir, verbosity=1):
  md_files = library.get_md_files_from_path(out_dir)
  code_to_md = {}
  for md_file in tqdm.tqdm(md_files, desc=f"get_code_to_md {os.path.basename(out_dir)}"):
    (metadata, content) = md_file.read()
    code = metadata.get("Catalog number", None)
    if code is None:
      if verbosity > 0:
        logging.warning(f"skipping {md_file}")
      continue
    code_to_md[code] = md_file
  logging.info(f"Got {len(code_to_md)} files.")
  return code_to_md


def scrape_from_json(out_dir, lib_path="/home/vvasuki/Downloads/mukta/"):
  code_to_md = get_code_to_md(out_dir=out_dir)
  with open(os.path.join(out_dir, "muktabodha_metadata.json")) as f:
    lib_metadata = json.load(f)
    logging.info(f"Offline - {len(code_to_md)} files, online {len(lib_metadata)} files, to get {len(lib_metadata) - len(code_to_md)}.")
    for (code, metadata) in tqdm.tqdm(lib_metadata.items(), desc="file-codes"):
      if code in code_to_md:
        continue
      dest_file_path = get_file_path(out_dir=out_dir, metadata=metadata)
      url = f"https://muktabodha-digital-library.org/texts/DEV/{code}"
      metadata["upstream_url"] = url
      content = get_text_from_pre(url=get_local_source(code=code, lib_path=lib_path))
      metadata["title"] = metadata.get("Uniform title", "UNKNOWN")
      md_file = MdFile(file_path=dest_file_path)
      md_file.dump_to_file(metadata=metadata, content=content, dry_run=False)


def fix_footnotes(dir_path):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args, **kwargs: footnote_helper.inline_comments_to_footnotes(c), dry_run=False)
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args, **kwargs: footnote_helper.fix_intra_word_footnotes(c), dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args, **kwargs: footnote_helper.define_footnotes_near_use(c), dry_run=False)



def fix_lines(dir_path):
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n|^)प् *।([०-९]]+)\) *"], replacement=r"[[\1]]")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n)[ \t]+"], replacement="")

  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=[\S]) *\n(?=\S)"], replacement=r" ")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=[।॥]) *(?=[^०-९\s])"], replacement=r"  \n")
  

def get_tradition_to_metadata(src_dir="/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/mukta"):
  tradition_to_metadatas = defaultdict(dict)
  with open(os.path.join(src_dir, "muktabodha_metadata.json")) as f:
    lib_metadata = json.load(f)
    for (code, metadata) in tqdm.tqdm(lib_metadata.items()):
      traditions = metadata.get("Traditions", ["mixed"])
      for tradition in traditions:
        tradition_to_metadatas[tradition][code] = metadata
  return tradition_to_metadatas




def update_website(src_dir="/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/mukta"):
  code_to_md = get_code_to_md(out_dir=src_dir)
  with open(os.path.join(src_dir, "muktabodha_metadata.json")) as f:
    lib_metadata = json.load(f)
  logging.info(f"Offline - {len(code_to_md)} files, online {len(lib_metadata)} files, to get {len(lib_metadata) - len(code_to_md)}.")
  tradition_to_metadatas_actual = get_tradition_to_metadatas_actual()
  for (code, metadata) in tqdm.tqdm(lib_metadata.items()):
    if code not in code_to_md:
      logging.warning(f"Skip {code}")
      continue
    traditions = metadata.get("Traditions", ["mixed"])
    tradition_main = traditions[0]
    dest_path = tradition_to_path.get(tradition_main, None)
    if dest_path is None:
      logging.warning(f"Skipping {tradition_main} {code}")
      continue
    if code in tradition_to_metadatas_actual[tradition_main]:
      continue
    code_to_dest_md = get_code_to_md(out_dir=dest_path, verbosity=0)
    if code not in code_to_dest_md:
      source_md = code_to_md[code]
      dest_path_final = os.path.join(dest_path, "mukta-bodha-mUlam","/".join(source_md.file_path.split("/")[-2:]))
      os.makedirs(os.path.dirname(dest_path_final), exist_ok=True)
      logging.info(f"Copying to {dest_path_final}")
      shutil.copy(source_md.file_path, dest_path_final)
      arrangement.fix_index_files(dest_path, dry_run=False)

  dump_tradition_to_metadatas(src_dir)


def dump_tradition_to_metadatas(src_dir: str):
  tradition_to_metadatas = get_tradition_to_metadata(src_dir=src_dir)
  for tradition, code_to_metadata in tradition_to_metadatas.items():
    category_optitrans = file_helper.clean_file_path(
      sanscript.transliterate(data=tradition, _from=sanscript.IAST, _to=sanscript.OPTITRANS))
    dest_path = tradition_to_path.get(tradition, None)
    if dest_path is None:
      continue
    dest_path = os.path.join(dest_path,
                             file_helper.get_storage_name(category_optitrans, source_script=sanscript.IAST) + ".json")
    with open(dest_path, "w") as f:
      json.dump(code_to_metadata, f, sort_keys=False, ensure_ascii=False, indent=2)


def get_tradition_to_metadatas_actual():
  
  tradition_to_metadatas_actual = defaultdict(dict)
  for tradition in tradition_to_path.keys():
    category_optitrans = file_helper.clean_file_path(
      sanscript.transliterate(data=tradition, _from=sanscript.IAST, _to=sanscript.OPTITRANS))
    dest_path = tradition_to_path.get(tradition, None)
    if dest_path is None:
      continue
    dest_path = os.path.join(dest_path,
                             file_helper.get_storage_name(category_optitrans, source_script=sanscript.IAST) + ".json")
    if os.path.exists(dest_path):
      with open(dest_path) as f:
        code_to_metadata = json.load(f)
        tradition_to_metadatas_actual[tradition] = code_to_metadata
  return tradition_to_metadatas_actual


if __name__ == '__main__':
  # text = from_iast_text(url="https://%s@muktalib7.com/DL_CATALOG_ROOT/DL_CATALOG/DL_CATALOG_USER_INTERFACE/dl_user_interface_create_utf8_text.php?hk_file_url=..%%2FTEXTS%%2FETEXTS%%2FmaliniivijayottaraHK.txt&miri_catalog_number=M00160" % creds)
  # rearrange_library("/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/mukta")
  pass
  # dump_tradition_to_metadatas("/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/mukta")
  # get_tradition_to_metadatas_actual()
  update_website()