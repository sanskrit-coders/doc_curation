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

from doc_curation import titus, text_data

browser = titus.browser

def dump_text(base_dir, do_transliteration=False):
    unit_info_file = os.path.join(os.path.dirname(text_data.__file__), "vedaH/vAjasaneyi/samhitA.json")

    titus_url = "http://titus.uni-frankfurt.de/texte/etcd/ind/aind/ved/yvw/vs/vs.htm"
    for kaanda_index in text_data.get_subunit_list(json_file=unit_info_file, unit_path_list=[]):
        logging.info("kaanDa %d", kaanda_index)

        outfile_path = os.path.join(base_dir, "%02d.md" % (kaanda_index))
        if os.path.exists(outfile_path):
            logging.info("Skipping " + outfile_path)
            continue

        titus.navigate_to_part(base_page_url=titus_url, level_3_id=kaanda_index, level_3_frame="etaindexb")
        sentences = titus.dump_text()
        os.makedirs(name=os.path.dirname(outfile_path), exist_ok=True)
        with open(outfile_path, "w") as outfile:
            outfile.write("  \n".join(sentences))


if __name__ == '__main__':
    dump_text(base_dir="/home/vvasuki/sanskrit/raw_etexts/veda/vAjasaneyi/samhitA/")
    browser.close()
    pass
