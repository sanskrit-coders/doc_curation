import glob
import json
import logging
import os
import shutil
import unicodedata
import zipfile
from collections import defaultdict
from functools import lru_cache

import tqdm

import regex
from bs4 import BeautifulSoup, Tag
from curation_utils import scraping, file_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor.footnote import helper as footnote_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement
from doc_curation import sanskrit as sanskrit_helper
from indic_transliteration import sanscript

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


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


def get_file_path(out_dir, metadata):
  title_iast = metadata.get("Uniform title", metadata.get("title", "UNKNOWN"))
  author_iast = metadata.get("Author", None)
  catalog_number = metadata.get("Catalog number", None)
  traditions = metadata.get("Traditions") or ["mixed"]
  if isinstance(traditions, str):
    traditions = [traditions]
  category = traditions[-1]
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


def get_local_source(code, lib_path="/home/vvasuki/Downloads/mukta/"):
  file_paths = glob.glob(f"{lib_path}{code}*")
  if len(file_paths) > 0:
    return file_paths[0]
  else:
    logging.warning(f"Could not get {code}")
    return None


def has_devanagari(text):
  return regex.search(r"[\u0900-\u097F]", text) is not None


def fix_devanaagarii(content):
  content = content.replace("||", "॥").replace("|", "।")
  content = regex.sub("॥[॥।]+", "…", content)
  content = sanskrit_helper.fix_lazy_anusvaara(text=content)
  content = sanskrit_helper.fix_bad_anunaasikas(content)
  content = sanskrit_helper.fix_repha_duplication(text=content)
  return content


def from_iast(content):
  """Transliterates and cleans up IAST e-text content."""
  content = sanscript.transliterate(data=content, _from=sanscript.IAST, _to=sanscript.DEVANAGARI, togglers={}, suspend_on={}, suspend_off={})
  content = content.replace("\"न्", "ङ्")
  content = fix_devanaagarii(content=content)
  content = regex.sub("ए-तेxत्स् मय् बे विएwएद् ओन्ल्य् ओन्लिने ओर् दोwन्लोअदेद् फ़ोर् प्रिवते स्तुद्य्। *", "", content)
  return content


def get_text_from_pre_content(content):
  content = regex.sub("\nMUKTABODHA INDOLOGICAL.+", "", content)
  # Download zips come both in Devanagari and in IAST; detect the script on the raw text, since fix_devanaagarii turns IAST word separators into danda-s.
  iast = not has_devanagari(content)
  content = fix_devanaagarii(content=content)
  content = content.replace("\n", "  \n")
  content = content.replace("*", r"\*")
  content = regex.sub("\n- *\n", "-  \n", content)
  if iast:
    content = from_iast(content=content)
  return content


def get_text_from_soup(soup):
  pre_tags = soup.select("pre")
  if len(pre_tags) == 0:
    return None
  return get_text_from_pre_content(content=pre_tags[0].text)


def get_text_from_pre(url):
  """Gets the e-text content from a local file path or a URL."""
  logging.info("Processing %s", url)
  (soup, _) = scraping.get_soup(url=url)
  return get_text_from_soup(soup=soup)


def get_text_from_html(html):
  return get_text_from_soup(soup=BeautifulSoup(html, features="html.parser"))


def get_front_matter(html):
  """Parses the metadata block at the head of a Muktabodha e-text."""
  frontmatter = {}
  soup = BeautifulSoup(html, features="lxml")
  item_heads = soup.select("span.listItemName")
  for item_head in item_heads:
    tag = item_head.text.replace(":", "")
    tag = tag.strip()
    values = frontmatter.get(tag, [])
    value_item = item_head.next_sibling
    while isinstance(value_item, Tag) and value_item.name == "br":
      value_item = value_item.next_sibling
    while isinstance(value_item, Tag) and value_item.has_attr("class") and value_item["class"][0] == "listItem":
      values.extend([value_item.text.strip()])
      value_item = value_item.next_sibling
    if len(values) == 0:
      continue
    if tag in ['Catalog number', 'Uniform title', 'Main title', 'Description', 'Notes', 'Publication country']:
      frontmatter[tag] = values[0]
    else:
      frontmatter[tag] = values
  if 'E-text' in frontmatter:
    frontmatter.pop('E-text')
  return frontmatter


MONTHS = {month[:3].lower(): index for (index, month) in enumerate(
  ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], start=1)}


def get_revision(notes):
  """Gets the last 'Revision N: Mon D, YYYY' note as a sortable tuple."""
  matches = regex.findall(r"Revision (\d+): *([A-Za-z]+)\.? *(\d+), *(\d{4})", notes or "")
  if len(matches) == 0:
    return None
  (number, month, day, year) = matches[-1]
  return (int(number), int(year), MONTHS.get(month[:3].lower(), 0), int(day))


def flatten_front_matter(frontmatter):
  flattened = {}
  for (key, value) in frontmatter.items():
    if isinstance(value, list) and key not in ["Traditions"]:
      value = "\n".join(value)
    flattened[key] = value
  return flattened


def get_download_metadata(html, code):
  """Gets md frontmatter for an e-text in a Muktabodha download zip."""
  metadata = flatten_front_matter(frontmatter=get_front_matter(html=html))
  # File names in the download zips carry the catalog number as used by the catalog json and by existing md files; the number in the body may be zero-padded differently (eg. M00401 vs M04001).
  metadata["Catalog number"] = code
  metadata["title"] = metadata.get("Uniform title", "UNKNOWN")
  metadata["upstream_url"] = f"https://muktabodha-digital-library.org/texts/DEV/{code}"
  return metadata


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
      source_path = get_local_source(code=code, lib_path=lib_path)
      content = get_text_from_pre(url=source_path) if source_path is not None else None
      if content is None:
        logging.warning(f"Skipping {code} - no local etext in {lib_path}.")
        continue
      dest_file_path = get_file_path(out_dir=out_dir, metadata=metadata)
      url = f"https://muktabodha-digital-library.org/texts/DEV/{code}"
      metadata["upstream_url"] = url
      metadata["title"] = metadata.get("Uniform title", "UNKNOWN")
      md_file = MdFile(file_path=dest_file_path)
      md_file.dump_to_file(metadata=metadata, content=content, dry_run=False)


def update_from_download(zip_path, out_dir, update_existing=False, dry_run=False):
  """Brings a Muktabodha library mirror (out_dir) up to date with a library download zip.

  The zip is the "download all" file from the library site, eg. muktalib_IAST_download_2026-08-24.zip or muktalib_DEV_download_*.zip; the script of each etext (IAST or Devanagari) is detected from its content.

  - Etexts without an md file in out_dir are written as md files (frontmatter from the zip's metadata block, traditions from muktabodha_metadata.json if known, else "mixed"), and are added to muktabodha_metadata.json.
  - Etexts whose text differs from the local md file are only rewritten if update_existing is set; their frontmatter is otherwise left untouched, and they are merely reported as outdated.

  :param update_existing: Refresh the text of md files which already exist.
  """
  code_to_md = get_code_to_md(out_dir=out_dir)
  json_path = os.path.join(out_dir, "muktabodha_metadata.json")
  with open(json_path) as f:
    lib_metadata = json.load(f)
  stats = defaultdict(int)
  new_metadata = {}
  with zipfile.ZipFile(zip_path) as archive:
    etext_paths = sorted([path for path in archive.namelist() if path.lower().endswith((".htm", ".html"))])
    logging.info(f"{len(etext_paths)} etexts in {zip_path}; {len(code_to_md)} indexed in {out_dir}.")
    for etext_path in tqdm.tqdm(etext_paths, desc="update_from_download"):
      code = os.path.basename(etext_path).split(" ")[0]
      html = archive.read(etext_path).decode("utf-8")
      content = get_text_from_html(html=html)
      if content is None:
        logging.warning(f"Skipping {etext_path} - no etext found.")
        stats["skipped"] += 1
        continue
      download_metadata = get_download_metadata(html=html, code=code)
      md_file = code_to_md.get(code)
      if md_file is not None:
        (metadata, old_content) = md_file.read()
        download_revision = get_revision(notes=download_metadata.get("Notes"))
        local_revision = get_revision(notes=metadata.get("Notes"))
        if _comparable_content(old_content) == _comparable_content(content):
          stats["unchanged"] += 1
          continue
        if not update_existing:
          logging.warning(f"Text of {code} differs from {md_file.file_path} (revision upstream: {download_revision}, local: {local_revision}). Set update_existing=True to refresh it.")
          stats["outdated"] += 1
          continue
        logging.info(f"Updating {md_file.file_path} (revision upstream: {download_revision}, local: {local_revision})")
        if download_revision is not None and (local_revision is None or download_revision > local_revision) and "Notes" in download_metadata:
          metadata["Notes"] = download_metadata["Notes"]
        md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)
        stats["updated"] += 1
        continue
      metadata = {**download_metadata, **lib_metadata.get(code, {})}
      metadata.setdefault("Traditions", ["mixed"])
      dest_file_path = get_file_path(out_dir=out_dir, metadata=metadata)
      MdFile(file_path=dest_file_path).dump_to_file(metadata=metadata, content=content, dry_run=dry_run)
      new_metadata[code] = metadata
      stats["new"] += 1
  if len(new_metadata) > 0:
    logging.info(f"Adding {len(new_metadata)} etexts to {json_path}")
    lib_metadata.update(new_metadata)
    if not dry_run:
      with open(json_path, "w") as f:
        json.dump(lib_metadata, f, sort_keys=False, ensure_ascii=False, indent=2)
  get_code_to_md.cache_clear()
  logging.info(f"New: {stats['new']}; updated: {stats['updated']}; outdated: {stats['outdated']}; unchanged: {stats['unchanged']}; skipped: {stats['skipped']}.")


def _comparable_content(content):
  """Normalizes md content for comparison across download snapshots."""
  content = unicodedata.normalize("NFC", content)
  return "\n".join([line.rstrip() for line in content.split("\n")]).strip()


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
    dest_path = os.path.join(dest_path, "mukta-bodha-mUlam",
                                 file_helper.get_storage_name(category_optitrans, source_script=sanscript.IAST) + ".json")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
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
    dest_path = os.path.join(dest_path, "mukta-bodha-mUlam",
                             file_helper.get_storage_name(category_optitrans, source_script=sanscript.IAST) + ".json")
    if os.path.exists(dest_path):
      with open(dest_path) as f:
        code_to_metadata = json.load(f)
        tradition_to_metadatas_actual[tradition] = code_to_metadata
  return tradition_to_metadatas_actual
