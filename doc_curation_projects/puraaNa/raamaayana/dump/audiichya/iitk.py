import logging
import os
import textwrap
from urllib.request import urlopen

from bs4 import BeautifulSoup
from tqdm import tqdm

from doc_curation import book_data
from doc_curation.md import get_md_with_pandoc
from doc_curation.md.file import MdFile
from doc_curation.scraping import iitk
from doc_curation.scraping.html_scraper import souper
from indic_transliteration import sanscript

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

unit_info_file = os.path.join(os.path.dirname(book_data.__file__), "raamaayanam/andhra.json")


def dump_sarga(url, out_path, sarga_id, dry_run=False):
  # browser.implicitly_wait(2)
  page_html = urlopen(url)
  soup = BeautifulSoup(page_html.read(), 'lxml')
  shloka_tags = soup.select(".views-row")
  sarga_content = ""
  for (index, shloka_tag) in enumerate(tqdm(shloka_tags)):
    fields = shloka_tag.select(".field-content")
    if index == 0:
      sarga_summary = fields[0].contents[0].replace("[", "").replace("]", "")
      shloka = souper.get_md_paragraph(fields[0].contents[1:])
      sarga_content = get_md_with_pandoc(content_in=sarga_summary, source_format="html")
    else:
      shloka = souper.get_md_paragraph(fields[0].contents)
    shloka = shloka.replace(":", "ः")
    word_meaning = souper.get_md_paragraph(fields[1].contents).replace(":", "ः")
    shloka_meaning = souper.get_md_paragraph(fields[2].contents)
    content = textwrap.dedent("""
        ## श्लोकः
        ### मूलम्
        %s
        
        ### शब्दार्थः
        %s
        
        ### आङ्ग्लानुवादः
        %s
        """) % (shloka, word_meaning, shloka_meaning)
    sarga_content = "%s\n\n%s" % (sarga_content, content)
  md_file = MdFile(file_path=out_path)
  sarga_content = sarga_content.replace(":", "ः").replace("इत्यार्षे", "\n## समाप्तिः\n")
  md_file.dump_to_file(metadata={"title": "%03d" % sarga_id}, content=sarga_content, dry_run=dry_run)


def dump_all_sargas(base_dir):
  for kaanda_index in book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[]):
    if kaanda_index >= 6:
      continue
    sarga_list = book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[kaanda_index])
    for sarga_index in sarga_list:
      logging.info("Kanda %d Sarga %d", kaanda_index, sarga_index)
      out_path = os.path.join(base_dir, "%d" % kaanda_index, "%03d.md" % sarga_index)
      url = "https://www.valmiki.iitk.ac.in/sloka?field_kanda_tid=%d&language=dv&field_sarga_value=%d" % (
      kaanda_index, sarga_index)
      dump_sarga(url=url, out_path=out_path, sarga_id=sarga_index)


def dump_all_sargas(base_dir):
  for kaanda_index in book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[]):
    if kaanda_index >= 6:
      continue
    sarga_list = book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[kaanda_index])
    for sarga_index in sarga_list:
      logging.info("Kanda %d Sarga %d", kaanda_index, sarga_index)
      out_path = os.path.join(base_dir, "%d" % kaanda_index, "%03d.md" % sarga_index)
      url = "https://www.valmiki.iitk.ac.in/sloka?field_kanda_tid=%d&language=dv&field_sarga_value=%d" % (
      kaanda_index, sarga_index)
      dump_sarga(url=url, out_path=out_path, sarga_id=sarga_index)


def dump_commentary(base_dir, commentary_id):
  for kaanda_index in book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[]):
    if kaanda_index >= 6:
      continue
    sarga_list = book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[kaanda_index])
    for sarga_index in sarga_list:
      logging.info("Kanda %d Sarga %d", kaanda_index, sarga_index)
      out_path = os.path.join(base_dir, "%d" % kaanda_index, "%03d.md" % sarga_index)
      url = "https://www.valmiki.iitk.ac.in/commentaries?language=dv&field_commnetary_tid=%d&field_kanda_tid=%d&field_sarga_value=%d" % (
      commentary_id, kaanda_index, sarga_index)
      title_maker = lambda soup, title_prefix: sanscript.transliterate("%03d" % sarga_index, sanscript.IAST,
                                                                       sanscript.DEVANAGARI)
      iitk.dump_item(item_url=url, outfile_path=out_path, title_maker=title_maker)


if __name__ == '__main__':
  pass
  # dump_all_sargas(base_dir="/home/vvasuki/sanskrit/raw_etexts/purANam/rAmAyaNam/Andhra-pAThaH_iitk/")
  # aandhra.fix_title_names(base_dir="/home/vvasuki/sanskrit/raw_etexts/purANam/rAmAyaNam/kumbhakona", base_dir_ref="/home/vvasuki/sanskrit/raw_etexts/purANam/rAmAyaNam/goraxapuram/VR_with_errors", dry_run=False)
  # dump_commentary(base_dir="/home/vvasuki/sanskrit/raw_etexts/purANam/rAmAyaNam/TIkA/bhUShaNa_iitk/", commentary_id=14)
  # dump_commentary(base_dir="/home/vvasuki/sanskrit/raw_etexts/purANam/rAmAyaNam/TIkA/shiromaNI_iitk/", commentary_id=10)
  # dump_commentary(base_dir="/home/vvasuki/sanskrit/raw_etexts/purANam/rAmAyaNam/TIkA/tilaka_iitk/", commentary_id=13)
