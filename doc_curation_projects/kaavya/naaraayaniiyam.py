import logging
import os

import regex
from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.remote.remote_connection import LOGGER

from curation_utils import scraping
from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

opts = options.Options()
opts.headless = True
browser = webdriver.Chrome(options=opts)
browser.implicitly_wait(6)


def get_item(id, dir_path):
    import urllib.parse
    dashaka_id = "नारायणीयम्/दशकम्_%s" % sanscript.transliterate(str(id), sanscript.SLP1, sanscript.DEVANAGARI)
    logging.info(dashaka_id)
    item_url = "https://sa.wikisource.org/wiki/" + urllib.parse.quote(dashaka_id)
    logging.info(item_url)
    browser.get(item_url)
    text = browser.find_element_by_css_selector("div.poem").text
    text = text.replace("cअ", "च").replace("cइ", "चि").replace("cई", "ची").replace("cउ", "चु").replace("cऊ", "चू").replace("cऋ", "चृ").replace("cॠ", "चॄ").replace("cऌ", "चॢ").replace("cॡ", "चॣ").replace("cए", "चे").replace("cऐ", "चै").replace("cओ", "चो").replace("cऔ", "चौ").replace("c", "च्").replace("ळ", "ल")
    shlokas = text.split("\n\n")
    outfile_path = os.path.join(dir_path, "%03d.md" % id)
    os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
    with open(outfile_path, "w") as outfile:
        for shloka_id in range(1, len(shlokas) + 1):
            outfile.write("<div class=\"audioEmbed\"  caption=\"सीतालक्ष्मी-वाचनम्\" src=\"https://sanskritdocuments.org/sites/completenarayaneeyam/SoundFiles/%03d/%03d_%02d.mp3\"></div>  \n" % (id, id, shloka_id))
            outfile.writelines(shlokas[shloka_id-1].replace("\n", "  \n") + "\n\n")
    md_file = MdFile(file_path=outfile_path)
    md_file.set_title(sanscript.transliterate("%03d" % id, sanscript.SLP1, sanscript.DEVANAGARI), dry_run=False)


def insert_translation(content, *args):
  def replacement_maker(match):
    text = match.group(0)
    soup = scraping.get_soup(url=f"https://sanskritdocuments.org/sites/completenarayaneeyam/GistHtm/{match.group(2)}gist.htm")
    detail = details_helper.Detail(type="English (Padmini)", content=soup.select_one("body").text).to_html()
    text += f"\n\n{detail}\n\n"
    return text
  content = regex.sub("(\<div[\s\S]+?)(\d\d\d_\d\d)([\s\S]+?)(?=<div|$)", replacement_maker, content)
  return content


if __name__ == '__main__':
  pass
  # for id in range(1, 101):
  #     get_item(id=id, dir_path="/home/vvasuki/sanskrit/raw_etexts/purANa/nArAyaNIyam/" )
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/laxyam/padyam/purANam/nArAyaNIyam", content_transformer=insert_translation, dry_run=False)
