import logging
import os

import pandas
import regex

from doc_curation.md import library

translation_file = "/home/vvasuki/sanskrit/raw_etexts/vedaH/atharva/shaunaka/griffith.tsv"
translations = pandas.read_csv(translation_file, sep='\t')
translations = translations.set_index("id")


def dump(dest_dir):
  md_files = library.get_md_files_from_path(dir_path=dest_dir, file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d", os.path.basename(x))) > 0)
  for md_file in md_files:
    path_parts = regex.match(".+(\d\d)/(\d\d\d)/(\d\d)_", str(md_file.file_path))
    if path_parts is None:
      continue
    commentary_id = "%d.%d.%d" % (int(path_parts.group(1)), int(path_parts.group(2)),int(path_parts.group(3)))
    if commentary_id not in translations.index.values:
      logging.warning("Could not find: %s", commentary_id)
      continue
    commentary = translations.loc[commentary_id, "Comment"]
    md_file.replace_content_metadata(new_content=str(commentary), dry_run=False)
    # logging.debug("Commentary for %s: %s", commentary_id, commentary)

def dump_suukta_info(dest_dir):
  md_files = library.get_md_files_from_path(dir_path=dest_dir, file_pattern="**/_index.md", file_name_filter=lambda x: len(regex.findall("\\d\\d\\d", os.path.basename(os.path.dirname(x)))) > 0)
  for md_file in md_files:
    path_parts = regex.match(".+(\d\d)/(\d\d\d)", str(md_file.file_path))
    if path_parts is None:
      continue
    id = "%d.%d" % (int(path_parts.group(1)), int(path_parts.group(2)))
    if id not in translations.index.values:
      logging.warning("Could not find: %s", id)
      continue
    commentary = translations.loc[id, "Comment"]
    md_file.replace_content_metadata(new_content=str(commentary), dry_run=False)
    # logging.debug("Commentary for %s: %s", commentary_id, commentary)




if __name__ == '__main__':
  dump_suukta_info(dest_dir="/home/vvasuki/vishvAsa/vedAH/static/atharva/shaunakam/rUDha-saMhitA/griffith")