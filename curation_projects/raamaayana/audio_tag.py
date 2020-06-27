import logging
import os
from pathlib import Path

import regex

from curation_projects import raamaayana

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def get_adhyaaya_to_mp3_map():
    mp3_root = "/home/vvasuki/rAmAyaNa-audio/"
    mp3_paths = Path(mp3_root).glob(pattern="**/*.mp3")
    adhyaaya_to_mp3_map = {}
    for mp3_path in mp3_paths:
        kaanda = regex.findall("Kanda_\\d_", str(mp3_path))[0].replace("Kanda", "").replace("_", "")
        adhyaaya = regex.findall("\\d\\d\\d", str(mp3_path))[0]
        adhyaaya_id = "%s-%s" % (kaanda, adhyaaya)
        web_mp3_path = str(mp3_path).replace(mp3_root, "https://archive.org/download/Ramayana-recitation-Sriram-harisItArAmamUrti-Ghanapaati-v2/").replace("mp3/", "")
        adhyaaya_to_mp3_map[adhyaaya_id] = web_mp3_path
    return adhyaaya_to_mp3_map


if __name__ == '__main__':
    adhyaaya_to_mp3_map = get_adhyaaya_to_mp3_map()
    # logging.debug(adhyaaya_to_mp3_map)
    for md_file in raamaayana.get_adhyaaya_md_files(md_file_path ="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padya/purANa/rAmAyaNa/Andhra/"):
        # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
        logging.debug(md_file.file_path)
        (kaanda, adhyaaya) = raamaayana.get_kaanda_adhyaaya(md_file)
        adhyaaya_id = "%s-%s" % (kaanda, adhyaaya)
        logging.debug(adhyaaya_id)
        (yml, _) = md_file._read_yml_md_file()
        # logging.debug(adhyaaya_to_mp3_map[adhyaaya_id])
        md_file.prepend_to_content('<div class="audioEmbed"  caption="श्रीराम-हरिसीताराममूर्ति-घनपाठिभ्यां वचनम्" src="%s"></div>\n' % adhyaaya_to_mp3_map[adhyaaya_id], dry_run=False)