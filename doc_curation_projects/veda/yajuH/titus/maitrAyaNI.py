# Potential approaches: 
# 
# 1. Get pages in the range:
# http://titus.uni-frankfurt.de/texte/etcd/ind/aind/ved/yvw/vs/vs001.htm
# http://titus.uni-frankfurt.de/texte/etcd/ind/aind/ved/yvw/vs/vs040.htm
#
# 2. Use web driver and select text levels.
# 

# noinspection PyUnresolvedReferences
import logging
import os

import regex

from doc_curation import book_data
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library.arrangement import fix_index_files
from doc_curation.scraping.misc_sites import titus
from doc_curation_projects.vedaanta.brahma_suutra import arrangement
from indic_transliteration import sanscript


def dump_text(base_dir, do_transliteration=False):
  unit_info_file = os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/maitrAyaNi/samhitA.json")

  titus_url = "https://titus.uni-frankfurt.de/texte/etcs/ind/aind/ved/yvs/ms/ms.htm"
  for kaanda_index in book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[]):
    for prapaaThaka in book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[kaanda_index]):
      logging.info(f"kaanDa {kaanda_index} {prapaaThaka}", )

      outfile_path = os.path.join(base_dir, f"{kaanda_index}/{prapaaThaka:02}.md")
      if os.path.exists(outfile_path):
        logging.info("Skipping " + outfile_path)
        continue
  
      titus.navigate_to_part(base_page_url=titus_url, level_3_id=kaanda_index, level_3_frame="etaindex", level_4_id=prapaaThaka)
      sentences = titus.get_text()
      content = "  \n".join(sentences)
      content = regex.sub("\n### .+", "", content)
      content = sanscript.transliterate(content, _from="titus", _to=sanscript.DEVANAGARI)
      content = regex.sub(r"[\\॥।]॥", "॥", content)
      md_file = MdFile(file_path=outfile_path)
      md_file.dump_to_file(metadata={"title": f"{prapaaThaka:02}"}, content=content, dry_run=False)
  fix_index_files(dir_path=base_dir)


if __name__ == '__main__':
  dump_text(base_dir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/maitrAyaNIyam/saMhitA/udAttAnkanam")
  pass

