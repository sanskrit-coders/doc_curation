import logging
import os
from pathlib import Path

import regex

from doc_curation_projects.veda.Rk import json_lib
from doc_curation.md.file import MdFile
from doc_curation.scraping import html
from doc_curation.scraping.html_scraper import souper


for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


griffith_dir_base = "/home/vvasuki/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/griffith"



def dump(dest_dir, dry_run=False):
  suukta_id_to_rk_map = json_lib.get_suukta_id_to_rk_map()
  for suukta_id in sorted(suukta_id_to_rk_map.keys()):
    if suukta_id <= "08/048":
      continue
    mandala_num = int(suukta_id.split("/")[0])
    suukta_num = int(suukta_id.split("/")[1])
    if mandala_num == 8 and suukta_num >= 49 and suukta_num <= 59:
      # vAlakhilya hymns skipped by Griffith.
      continue
    if mandala_num == 8 and suukta_num >= 49:
      suukta_num = suukta_num - (60-49)
    url =  "https://en.wikisource.org/wiki/The_Rig_Veda/Mandala_%d/Hymn_%d" % (mandala_num, suukta_num)
    suukta_text = souper.get_content_from_element(url=url, text_css_selector="pre")
    if suukta_text is None:
      continue
    suukta_text = "\n%s\n9999. " % suukta_text
    matches = regex.findall("\n(\d+)\.\s+([\s\S]+?)\n\d+\. ", suukta_text, overlapped=True)
    for match in matches:
      rk_num = int(match[0])
      rk_id = "%02d" % rk_num
      content = match[1].strip().replace("\n", "  \n")
      # logging.debug("%d: %s", rk_num, content)
      dest_file = [x for x in os.listdir(os.path.join(dest_dir, suukta_id)) if x.startswith(rk_id)][0]
      dest_file = os.path.join(dest_dir, suukta_id, dest_file)
      # logging.debug("%d: %s", rk_num, dest_file)
      md_file = MdFile(file_path=dest_file)
      md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


if __name__ == '__main__':
  dump(dest_dir=griffith_dir_base)