import collections
import os

import regex

from doc_curation_projects.puraaNa import mahaabhaarata
import logging

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def get_adhyaaya_to_mp3_map():
  with open(os.path.join(mahaabhaarata.PATH_GP, "meta", "mahAbhArata-mUla-paThanam-GP.txt")) as f:
    mp3_paths = f.readlines().sort()
  adhyaaya_to_mp3_map = collections.defaultdict(list)
  for mp3_path in mp3_paths:
    adhyaaya_id = mp3_path[0:7]
    web_mp3_path = f"https://archive.org/download/mahAbhArata-mUla-paThanam-GP/{mp3_path.strip()}"
    adhyaaya_to_mp3_map[adhyaaya_id].append(web_mp3_path)
  return adhyaaya_to_mp3_map


def set_audio_tag():
  adhyaaya_to_source_file_map = mahaabhaarata.get_adhyaaya_to_source_file_map()
  adhyaaya_to_mp3_map = mahaabhaarata.get_adhyaaya_to_mp3_map()
  # logging.debug(adhyaaya_to_mp3_map)
  dest_md_files = mahaabhaarata.get_adhyaaya_md_files(
    md_file_path="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padya/purANa/mahAbhArata")
  logging.debug(dest_md_files)
  for md_file in dest_md_files:
    # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
    logging.debug(md_file.file_path)
    (parva, adhyaaya) = mahaabhaarata.get_parva_adhyaaya(md_file)
    adhyaaya_id = "%s-%s" % (parva, adhyaaya)
    logging.debug(adhyaaya_id)
    (yml, current_content) = md_file._read_yml_md_file()
    audio_tag = next(iter(regex.findall("<div class.*div>", current_content.replace("\n", " "))), '')
    (_, target_content) = adhyaaya_to_source_file_map[adhyaaya_id]._read_yml_md_file()
    # logging.debug(adhyaaya_to_source_file_map[adhyaaya_id])
    md_file.replace_content_metadata(new_content="%s\n\n%s" % (audio_tag, target_content), dry_run=False)
