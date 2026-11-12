# Download Taittiriya Brahmana from TITUS
# 3 kANDAs with 8, 8, 9 prapaaThakas respectively

import logging
import os
import regex

from doc_curation import book_data
from doc_curation.md.file import MdFile
from doc_curation.scraping.misc_sites import titus
from indic_transliteration import sanscript


def dump_text(base_dir):
    unit_info_file = os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/taittirIya/mUlam/brAhmaNa.json")

    titus_url = "https://titus.uni-frankfurt.de/texte/etcs/ind/aind/ved/yvs/tb/tb.htm"
    for kaanda_index in book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[]):
        prapaaThaka_count = book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[kaanda_index])
        for prapaaThaka in prapaaThaka_count:
            logging.info(f"kaanDa {kaanda_index} prapaaThaka {prapaaThaka}")

            outfile_path = os.path.join(base_dir, f"{kaanda_index:02d}", f"{prapaaThaka:02d}.md")
            if os.path.exists(outfile_path):
                logging.info("Skipping " + outfile_path)
                continue

            titus.navigate_to_part(base_page_url=titus_url, level_3_id=kaanda_index, level_3_frame="etaindex", level_4_id=prapaaThaka)
            sentences = titus.get_text()
            content = "  \n".join(sentences)
            content = regex.sub(r"\n### .+", "", content)
            # Fix TITUS encoding: ái -> aí, áu -> aú (diphthongs with udAtta)
            content = regex.sub(r"ái", r"ai\u0301", content)
            content = regex.sub(r"áu", r"au\u0301", content)
            content = sanscript.transliterate(content, _from="titus", _to=sanscript.DEVANAGARI)
            content = regex.sub(r"[॥।]॥", "॥", content)
            md_file = MdFile(file_path=outfile_path)
            md_file.dump_to_file(metadata={"title": f"{prapaaThaka:02d}"}, content=content, dry_run=False)


if __name__ == '__main__':
    base_dir = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/brAhmaNam/mUlam/titus/"
    dump_text(base_dir=base_dir)
    titus.browser.close()