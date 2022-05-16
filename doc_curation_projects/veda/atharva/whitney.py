import logging
import os

import itertools
import pandas
import regex
from bs4 import BeautifulSoup

from curation_utils import file_helper
from doc_curation import book_data
from doc_curation.md import library, get_md_with_pandoc
import roman_numerals

from doc_curation.md.file import MdFile
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.html_scraper.souper import get_html, get_md_paragraphs_with_pandoc, get_md_paragraph

whitney_dir_base = "/home/vvasuki/vishvAsa/vedAH/static/atharva/shaunakam/rUDha-saMhitA/whitney"


def get_suukta_url(kaanda_index, subunit_index):
  kaanda_str = roman_numerals.roman_to_ascii(roman_numerals.convert_to_numeral(kaanda_index))
  subunit_str_url = "%d" % subunit_index
  suukta_subpath = "%02d/%03d.md" % (kaanda_index, subunit_index)
  addition_map = {
    "07/006.md": "_(6,_7)",
    "07/045.md": "_(46,_47)",
    "07/054.md": "_(56,_57._1)",
    "07/055.md": "_(57._2)",
    "07/068.md": "_(70,_71)",
    "07/072.md": "_(75,_76)",
    "07/076.md": "_(80,_81)",
  }
  if suukta_subpath in addition_map.keys():
    subunit_str_url += addition_map[suukta_subpath]
  elif suukta_subpath >= "07/007.md" and suukta_subpath < "07/045.md":
    subunit_str_url += "_(%d)" % (subunit_index + 1)
  elif suukta_subpath >= "07/046.md" and suukta_subpath < "07/068.md":
    subunit_str_url += "_(%d)" % (subunit_index + 2)
  elif suukta_subpath > "07/068.md" and suukta_subpath <= "07/071.md":
    subunit_str_url += "_(%d)" % (subunit_index + 3)
  elif suukta_subpath > "07/072.md" and suukta_subpath < "07/076.md":
    subunit_str_url += "_(%d)" % (subunit_index + 4)
  elif suukta_subpath > "07/076.md" and suukta_subpath < "08":
    subunit_str_url += "_(%d)" % (subunit_index + 5)
  if suukta_subpath.split("/")[0] in ["15", "16"]:
    subunit_str_url = "Paryaya_%s" % subunit_str_url
  else:
    subunit_str_url = "Hymn_%s" % subunit_str_url
  url =  "https://en.wikisource.org/wiki/Atharva-Veda_Samhita/Book_%s/%s" % (kaanda_str, subunit_str_url)
  return url


def fix_content(content):
  return file_helper.clear_bad_chars(content.strip()).replace("\n", "  \n").replace("ç", "ś").replace("Ç", "ś").replace("ḑ", "ḍ").replace("ṱ", "ṭ").replace("\\.", ".")


def get_Rk_comment(tags):
  def is_translation(x):
    return x.name == "p" and  regex.match("^(\d+)[. (]", get_md_paragraph(x).strip()) is not None
  tags = list(itertools.dropwhile(lambda x: not is_translation(x), tags))
  translation = fix_content(get_md_with_pandoc(content_in=tags[0], source_format="html"))
  rk_id = int(regex.match("\s*(\d+)[. (]", translation).group(1))
  notes = list(itertools.takewhile(lambda x: not is_translation(x), tags[1:]))
  tags = list(itertools.dropwhile(lambda x: x in notes, tags[1:]))
  notes = fix_content(get_md_paragraphs_with_pandoc(tags=notes))
  return (rk_id, translation, notes, tags)


def dump_Rk_info(dest_dir):
  unit_info_file = os.path.join(os.path.dirname(book_data.__file__), "vedaH/shaunaka/samhitA.json")
  for kaanda_index in book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[]):
    subunit_list = book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[kaanda_index], length_fields=["length_whitney", "length"])
    for subunit_index in subunit_list:
      kaanda_id = "%02d" % kaanda_index
      suukta_id = "%03d" % subunit_index
      suukta_subpath = "%s/%s" % (kaanda_id, suukta_id)
      if suukta_subpath != "13/004":
        continue
      url = get_suukta_url(kaanda_index=kaanda_index, subunit_index=subunit_index)
      logging.info("%s, kaanDa %d adhyaaya %d", url, kaanda_index, subunit_index)
      html = get_html(url=url)
      soup = BeautifulSoup(html, 'html.parser')
      tags = list(soup.select_one(".prp-pages-output").children)
      suukta_id = [x for x in os.listdir(os.path.join(dest_dir, kaanda_id)) if x.startswith(suukta_id)][0]
      suukta_subpath = "%s/%s" % (kaanda_id, suukta_id)
      while len(tags) > 0:
        (rk_num, translation, notes, tags) = get_Rk_comment(tags=tags)
        content = "## Translation\n%s\n\n## Notes\n%s\n" % (translation, notes)
        if kaanda_id == "13" and suukta_id == "004_adhyAtmam":
          if rk_num >= 14 and rk_num <= 21:
            rk_num -= 13
            suukta_subpath = "%s/005_adhyAtmam" % (kaanda_id)
          elif rk_num >= 22 and rk_num <= 28:
            rk_num -= 21
            suukta_subpath = "%s/006_adhyAtmam" % (kaanda_id)
          elif rk_num >= 29 and rk_num <= 45:
            rk_num -= 28
            suukta_subpath = "%s/007_adhyAtmam" % (kaanda_id)
          elif rk_num >= 46 and rk_num <= 51:
            rk_num -= 45
            suukta_subpath = "%s/008_adhyAtmam" % (kaanda_id)
          elif rk_num >= 52:
            rk_num -= 51
            suukta_subpath = "%s/009_adhyAtmam" % (kaanda_id)
        rk_id = "%02d" % rk_num
        dest_files = [x for x in os.listdir(os.path.join(dest_dir, suukta_subpath)) if x.startswith(rk_id)]
        if len(dest_files) == 0:
          logging.warning("Not found: %s", os.path.join(dest_dir, suukta_subpath, rk_id))
          continue
        dest_file = os.path.join(dest_dir, suukta_subpath, dest_files[0])
        # logging.debug("%d: %s", rk_num, dest_file)
        md_file = MdFile(file_path=dest_file)
        md_file.replace_content_metadata(new_content=content, dry_run=False)


def dump_kaanda_info(dest_dir):
  unit_info_file = os.path.join(os.path.dirname(book_data.__file__), "vedaH/shaunaka/samhitA.json")
  for kaanda_index in book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[]):
    kaanda_str = roman_numerals.roman_to_ascii(roman_numerals.convert_to_numeral(kaanda_index))
    url =  "https://en.wikisource.org/wiki/Atharva-Veda_Samhita/Book_%s" % (kaanda_str)
    logging.info("%s, kaanDa %d", url, kaanda_index)
    html = get_html(url=url)
    soup = BeautifulSoup(html, 'html.parser')
    title_tag = soup.select_one(".prp-pages-output b")
    title = title_tag.text
    content_html = str(soup.select_one(".prp-pages-output"))
    content = get_md_with_pandoc(content_in=content_html, source_format="html")
    dest_path = os.path.join(dest_dir, "%02d/_index.md" % kaanda_index)
    md_file = MdFile(file_path=dest_path)
    md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=False)
    # souper.get_content_from_element()



def dump_suukta_info(dest_dir):
  unit_info_file = os.path.join(os.path.dirname(book_data.__file__), "vedaH/shaunaka/samhitA.json")
  missing_anukramaNI = ["02/021", "02/022", "02/023",]
  for kaanda_index in book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[]):
    subunit_list = book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[kaanda_index], length_fields=["length_whitney", "length"])
    for subunit_index in subunit_list:
      suukta_subpath = "%02d/%03d" % (kaanda_index, subunit_index)
      if suukta_subpath <= "02/020" or suukta_subpath >= "20":
        continue
      if suukta_subpath in missing_anukramaNI:
        continue
      url = get_suukta_url(kaanda_index=kaanda_index, subunit_index=subunit_index)
      logging.info("%s, kaanDa %d adhyaaya %d", url, kaanda_index, subunit_index)
      html = get_html(url=url)
      soup = BeautifulSoup(html, 'html.parser')
      title_tag = soup.select_one(".prp-pages-output b")
      title = title_tag.text
      suukta_comment_tags = soup.select(".prp-pages-output > [style='line-height:1.4; font-size: 83%;']")
      tags = [x for x in suukta_comment_tags[0].find_all(recursive=False) if x.name == "p"]
      comemnt_texts = [x.text for x in tags if not x.text.startswith("Translate")]
      content = "## Comment\n%s" % "\n\n".join(comemnt_texts)
      translation_texts = [x.text for x in tags if x.text.startswith("Translate")]
      if len(translation_texts) >= 1:
        content += "\n\n## Translations\n%s" % translation_texts[0]
      dest_path = os.path.join(dest_dir, "%s/_index.md" % suukta_subpath)
      md_file = MdFile(file_path=dest_path)
      md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=False)


def dump_anukramaNii(dest_dir):
  unit_info_file = os.path.join(os.path.dirname(book_data.__file__), "vedaH/shaunaka/samhitA.json")
  missing_anukramaNI = ["02/020.md", "02/021.md", "02/022.md", "02/023.md",]
  for kaanda_index in book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[]):
    subunit_list = book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[kaanda_index], length_fields=["length_whitney", "length"])
    for subunit_index in subunit_list:
      suukta_subpath = "%02d/%03d.md" % (kaanda_index, subunit_index)
      if suukta_subpath <= "16/000.md" or suukta_subpath >= "20":
        continue
      if suukta_subpath in missing_anukramaNI:
        continue
      url = get_suukta_url(kaanda_index=kaanda_index, subunit_index=subunit_index)
      logging.info("%s, kaanDa %d adhyaaya %d", url, kaanda_index, subunit_index)
      html = get_html(url=url)
      soup = BeautifulSoup(html, 'html.parser')
      title_tag = soup.select_one(".prp-pages-output b")
      title = title_tag.text
      anukramaNii_tag = souper.find_matching_tag(tags=soup.select(".prp-pages-output p"), filter=lambda x: x.text.startswith("["))
      if anukramaNii_tag is None:
        anukramaNii_tag = souper.find_matching_tag(tags=soup.select(".prp-pages-output div.hanging-indent"), filter=lambda x: x.text.startswith("["))
      anukramaNii = anukramaNii_tag.text
      dest_path = os.path.join(dest_dir, suukta_subpath)
      md_file = MdFile(file_path=dest_path)
      md_file.dump_to_file(metadata={"title": title}, content=anukramaNii, dry_run=False)
      # suukta_info = soup.select(".prp-pages-output .hanging-indent +p")[0].text
      # translation_info = soup.select(".prp-pages-output .hanging-indent +p+p")[0].text
      # suukta_text = souper.get_content_from_element(url=url, text_css_selector="")
      
      pass
      # md_file.replace_content(new_content=str(commentary), dry_run=False)
      # logging.debug("Commentary for %s: %s", commentary_id, commentary)


if __name__ == '__main__':
  # dump_anukramaNii(dest_dir=os.path.join(whitney_dir_base, "anukramaNikA"))
  # dump_kaanda_info(dest_dir=os.path.join(whitney_dir_base, "notes"))
  # dump_suukta_info(dest_dir=os.path.join(whitney_dir_base, "notes"))
  dump_Rk_info(dest_dir=os.path.join(whitney_dir_base, "notes"))