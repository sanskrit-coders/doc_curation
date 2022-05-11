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
  with open(os.path.join(os.path.dirname(mahaabhaarata.PATH_GP), "meta", "mahAbhArata-mUla-paThanam-GP.txt")) as f:
    mp3_paths = f.readlines()
    mp3_paths.sort()
  adhyaaya_to_mp3_map = collections.defaultdict(list)
  doc_data = mahaabhaarata.get_doc_data()
  for mp3_path in mp3_paths:
    adhyaaya_id = mp3_path[1:7]
    reader = doc_data.get_value(id=adhyaaya_id, column_name="पठिता")
    web_mp3_path = f"https://archive.org/download/mahAbhArata-mUla-paThanam-GP/{mp3_path.strip()}"
    audio_tag = f"<div class=\"audioEmbed\"  caption=\"{reader}\" src=\"{web_mp3_path}\"></div>"
    adhyaaya_to_mp3_map[adhyaaya_id].append(audio_tag)
  return adhyaaya_to_mp3_map


def set_audio_tags():
  adhyaaya_to_source_file_map = mahaabhaarata.get_adhyaaya_to_source_file_map()
  adhyaaya_to_mp3_map = get_adhyaaya_to_mp3_map()
  # logging.debug(adhyaaya_to_mp3_map)
  for adhyaaya_id, audio_tags in adhyaaya_to_mp3_map.items():
    # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
    md_file = adhyaaya_to_source_file_map[adhyaaya_id]
    audio_tag_str = '\n'.join(audio_tags)
    audio_detail = f"<details open><summary>श्रावणम् (द्युगङ्गा)</summary>\n\n{audio_tag_str}\n</details>"
    (_, content) = md_file.read()
    content = f"{audio_detail}\n\n{content}"
    md_file.replace_content_metadata(new_content=content, dry_run=False)


if __name__ == '__main__':
  set_audio_tags()