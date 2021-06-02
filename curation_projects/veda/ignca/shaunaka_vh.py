import logging
import os
import glob
import itertools

from more_itertools import peekable
from doc_curation import text_data
from doc_curation.md.file import MdFile
from doc_curation.md import library
from indic_transliteration import sanscript
from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.remote.remote_connection import LOGGER

LOGGER.setLevel(logging.WARNING)
from urllib3.connectionpool import log as urllibLogger

urllibLogger.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def dump_text(base_dir):
  opts = options.Options()
  opts.headless = False
  browser = webdriver.Chrome(options=opts)
  browser.implicitly_wait(6)
  unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "vedaH/shaunaka/samhitA.json")

  for kaanda_index in text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[]):
    subunit_list = text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[kaanda_index])
    for subunit_index in subunit_list:
      logging.info("kaanDa %d adhyaaya %d", kaanda_index, subunit_index)

      outfile_path = os.path.join(base_dir, "%02d" % (kaanda_index), "%03d.md" % subunit_index)
      if os.path.exists(outfile_path):
        logging.info("Skipping " + outfile_path)
        continue

      url = "http://vedicheritage.gov.in/samhitas/atharvaveda-samhitas/shaunaka-samhita/kanda-%02d-sukta-%03d/" % (
      kaanda_index, subunit_index)
      logging.info("url %s to %s", url, outfile_path)
      browser.get(url=url)
      text = browser.find_element_by_id("videotext").text
      text = text.replace("\n", "  \n")
      title_tags = browser.find_elements_by_css_selector("#videotext  strong")
      title = "%03d" % subunit_index
      if len(title_tags) > 0:
        title = "%03d %s" % (subunit_index, title_tags[0].text)
      title = sanscript.transliterate(title, sanscript.HK, sanscript.DEVANAGARI)
      md_file = MdFile(file_path=outfile_path)
      md_file.dump_to_file(metadata={"title": title}, content=text, dry_run=False)

  browser.close()


dest_dir_suuktas = "/home/vvasuki/vvasuki-git/vedAH/content/atharva/shaunakam/rUDha-saMhitA/"


def separate_rks(dry_run=False):
  dest_dir_Rks = "/home/vvasuki/vvasuki-git/vedAH/static/atharva/shaunakam/rUDha-saMhitA/mUlam/"
  suukta_paths = glob.glob("/home/vvasuki/vvasuki-git/vedAH/content/atharva/shaunakam/rUDha-saMhitA_alt/*/*.md",
                           recursive=True)

  for suukta_path in suukta_paths:
    md_file = MdFile(file_path=suukta_path)
    [metadata, md] = md_file.read_md_file()
    lines = md.split("\n")
    meta_lines = list(itertools.takewhile(lambda line: "॒" not in line and "॑" not in line, lines))
    lines = list(itertools.dropwhile(lambda line: "॒" not in line and "॑" not in line, lines))
    lines = [line for line in lines if line != ""]
    rk_id = 0
    chapter_id = suukta_path.split("/")[-2]
    suukta_id = metadata["title"].split()[0]
    suukta_id_roman = sanscript.transliterate(suukta_id, sanscript.DEVANAGARI, sanscript.IAST)
    suukta_title = " ".join(metadata["title"].split()[1:]).replace("।", "").strip()
    dest_path_suukta = os.path.join(dest_dir_suuktas, chapter_id, suukta_id_roman + ".md")
    rk_map = {}
    while(len(lines) > 0):
      lines_rk = list(itertools.takewhile(lambda line: "॥" not in line, lines))
      lines_rk.append(lines[len(lines_rk)])
      if len(lines) == len(lines_rk):
        lines = []
      else:
        lines = lines[len(lines_rk):]
      rk_id = rk_id + 1
      rk_md = "\n".join(lines_rk)

      rk_id_str = sanscript.transliterate("%02d" % rk_id, sanscript.IAST, sanscript.DEVANAGARI) 
      from doc_curation import text_data
      title_Rk = text_data.get_rk_title(rk_id=rk_id_str, rk_text=rk_md)
      dest_path_Rk = os.path.join(dest_dir_Rks, chapter_id, suukta_id_roman, sanscript.transliterate(rk_id_str, sanscript.DEVANAGARI, sanscript.IAST) + ".md")
      md_file_Rk = MdFile(file_path=dest_path_Rk)
      md_file_Rk.dump_to_file(metadata={"title": title_Rk}, content=rk_md, dry_run=dry_run)
      md_file_Rk.set_filename_from_title(transliteration_source=sanscript.DEVANAGARI, dry_run=dry_run)
      rk_map[rk_id_str] = md_file_Rk.file_path

    suukta_md = ""
    for rk_id in sorted(rk_map.keys()):
      dest_path_Rk = rk_map[rk_id]
      suukta_md = suukta_md + """
      <div class="js_include" url="%s"  newLevelForH1="2" includeTitle="false"> </div> 
      """ % dest_path_Rk.replace("/home/vvasuki/vvasuki-git", "").replace("static/", "")

    import textwrap
    suukta_md = """
    ## परिचयः
    %s
    
    ## पाठः
    %s
    """ % ("\n    ".join(meta_lines), suukta_md)
    md_file_suukta = MdFile(file_path=dest_path_suukta)
    md_file_suukta.dump_to_file(metadata={"title": "%s %s" % (suukta_id, suukta_title)}, content=textwrap.dedent(suukta_md), dry_run=dry_run)
    md_file_suukta.set_filename_from_title(transliteration_source=sanscript.DEVANAGARI, dry_run=dry_run)


if __name__ == '__main__':
  # dump_text(base_dir="/home/vvasuki/sanskrit/raw_etexts/vedaH/atharva/shaunaka/saMhitA_VH")
  # separate_rks()

  library.fix_index_files(dest_dir_suuktas)
  pass
