# Potential approaches: 
# 
# 1. Get pages in the range:
# http://titus.uni-frankfurt.de/texte/etcs/ind/aind/ved/yvw/sbm/sbm001.htm
# http://titus.uni-frankfurt.de/texte/etcs/ind/aind/ved/yvw/sbm/sbm100.htm
# Downside: Matching with kaanda and adhyaaya is harder. 
#
# 2. Use web driver and select text levels.
# 

# noinspection PyUnresolvedReferences
import logging
import os
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes import roman

from doc_curation import titus, text_data

browser = titus.browser

def dump_text(base_dir, do_transliteration=False):
    unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "shatapatha.json")

    titus_url = "http://titus.uni-frankfurt.de/texte/etcs/ind/aind/ved/yvw/sbm/sbm.htm"
    for kaanda_index in text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[]):
        sarga_list = text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[kaanda_index])
        for sarga_index in sarga_list:
            logging.info("kaanDa %d adhyaaya %d", kaanda_index, sarga_index)

            outfile_path = os.path.join(base_dir, "%02d" % (kaanda_index), "%02d" % sarga_index + ".md")
            if os.path.exists(outfile_path):
                logging.info("Skipping " + outfile_path)
                continue

            titus.navigate_to_part(base_page_url=titus_url, level_3_id=kaanda_index, level_4_id=sarga_index)
            sentences = titus.get_text()
            lines = ["\n"]
            for sentence in sentences:
                sentence = roman.RomanScheme.simplify_accent_notation(sentence)
                if do_transliteration:
                    sentence = roman.RomanScheme.to_shatapatha_svara(sentence)
                    sentence = sanscript.transliterate(sentence, sanscript.TITUS, sanscript.DEVANAGARI)
                lines.append(sentence + ".  \n")
            os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
            with open(outfile_path, "w") as outfile:
                outfile.writelines(lines)


if __name__ == '__main__':
    dump_text(base_dir="/home/vvasuki/sanskrit/raw_etexts/shatapatha_brAhmaNa/sb_gretil", do_transliteration=False)
    browser.close()
    pass
