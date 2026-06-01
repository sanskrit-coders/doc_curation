import os.path

import regex
import sys
import tqdm

from curation_utils import file_helper, scraping
from doc_curation.md.content_processor import transliterate
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement
from doc_curation.scraping.html_scraper import souper
from indic_transliteration import sanscript


def get_content_text(soup):
  lines = []
  current_line = []

  for elem in soup.select("div, span[trans], br"):
    if elem.get("id") == "sthAdhTitle":
      continue
    if elem.name == "div":
      text = elem.get_text(strip=True)
      if text == "":
        pass
      else:
        current_line.append(text)
    elif elem.name == "span":
      if "titleText" in elem.get("class", "") or elem.parent("id", "") == "sthAdhTitle":
        continue
      if elem.parent.get("id", "") == "adhikranaTitle":
        if current_line:
          lines.append(" ".join(current_line))
          current_line = []
        lines.append(f'## {elem["trans"].strip()}')
      else:
        current_line.append(elem["trans"])
    elif elem.name == "br":
      # commit current line and reset
      if current_line:
        lines.append(" ".join(current_line))
        current_line = []
  return "  \n".join(lines)


def dump_chapter(text, adhyaaya, dest_path):
  url = f"https://niimh.nic.in/ebooks/e-Nighantu/{text}/?mod=read&scriptName=Devanagari&selSthana=1&selAdhyaya={adhyaaya}&selSthOld=1&selAdhOld={adhyaaya}&selAdhi=pUrNa%20adhyAya&showVya=vyaShow&footShowChecked&vyaShowChecked&showFoot=vyaFoot"
  (soup, result) = scraping.get_soup(url=url)
  title = soup.select("#sthAdhTitle #trans")[-1]["trans"]
  title = transliterate(text=title, source_script="baraha_skt", dest_script=sanscript.DEVANAGARI)

  file_name = f"{adhyaaya:02}_{title}.md"
  file_name = file_helper.get_storage_path(file_path=file_name, source_script=sanscript.DEVANAGARI)

  content_table = soup.select_one("#readContent")
  content = get_content_text(content_table)
  content = transliterate(text=content, source_script="baraha_skt", dest_script=sanscript.DEVANAGARI)
  content = regex.sub(r" *\n *\n+", r"\n\n", content)
  
  
  md_file = MdFile(file_path=os.path.join(dest_path, file_name))
  md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=False)
  

def dump_all(text, num_chapters, dest_path):
  for chapter in tqdm.tqdm(range(1, num_chapters+1)):
    dump_chapter(text=text, adhyaaya=chapter, dest_path=dest_path)


if __name__ == '__main__':
  pass
  # dump_all(text="siddhamantra", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/bopa-devaH_siddha-mantraH/", num_chapters=9)
  # dump_all(text="abhidhanamanjari", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/bhiShag-AryaH_abhidhAna-manjarI/", num_chapters=32)
  # dump_all(text="abhidhanaratnamala", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/abhidhAna-ratna-mAlA/", num_chapters=7)
  # dump_all(text="ashtanganighantu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/vAhaTaH_aShTAnga-nighaNTuH/", num_chapters=28)
  # dump_all(text="kaiyadevanighantu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/kaiya-deva-nighaNTuH/", num_chapters=9)
  # 
  # dump_all(text="camatkaranighantu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/rAghava-chamatkAra-nighaNTuH/", num_chapters=1)
  # dump_all(text="dravyagunasangraha", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/chakra-pANi-dattaH_dravya-guNa-sangrahaH/", num_chapters=15)
  # dump_all(text="dhanvantarinighantu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/dhanvantari-nighaNTuH/", num_chapters=9)
  # dump_all(text="nighantushesha", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/hemachandra-nighaNTu-sheShaH/", num_chapters=6)
  # dump_all(text="paryayaratnamala", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/mAdhava-kara-paryAya-ratna-mAlA/", num_chapters=1)
  # dump_all(text="bhavaprakashanighantu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/bhava-mishraH_bhAva-prakAshaH/", num_chapters=24)
  # dump_all(text="madanapalanighantu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/madana-pAlaH/", num_chapters=14)
  # dump_all(text="madanadinighantu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/chandra-nandanaH_madanAdiH_gaNa-nighaNTuH/", num_chapters=32)
  # dump_all(text="madhavadravyaguna", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/mAdhava-dravya-guNaH/", num_chapters=29)
  # dump_all(text="madhavadravyaguna", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/narahariH_rAja-nighaNTuH/", num_chapters=24)
  # sys.exit()
  # 
  dump_all(text="rajavallabhanighantu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/rAja-vallabha-nighaNTuH/", num_chapters=6)
  dump_all(text="laghunighantu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/vyAsa-keshava-rAma-laghu-nighaNTuH/", num_chapters=1)
  dump_all(text="shabdacandrika", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/chakra-pANi-dattaH_shabda-chandrikA/", num_chapters=9)
  dump_all(text="shivakosha", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/shiva-datta-koShaH/", num_chapters=1)
  dump_all(text="siddhasaranighantu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/ravi-guptaH_siddha-sAra-nighaNTuH/", num_chapters=1)

  dump_all(text="shodhalanighantu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/soDhala-nighaNTuH/", num_chapters=11)
  dump_all(text="soushrutanighatu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/amara-siMha-saushruta-nighaNTuH/", num_chapters=35)
  dump_all(text="hrdudayadipakanighantu", dest_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH/bopa-devaH_hRdaya-dIpaka-nighaNTuH/", num_chapters=9)

  arrangement.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/koshaH/AyurvedaH")