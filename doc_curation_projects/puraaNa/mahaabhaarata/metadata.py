import collections
import logging
import os
import shutil

from curation_utils import file_helper
from doc_curation.md.library import metadata_helper
from doc_curation_projects.puraaNa import mahaabhaarata
from doc_curation.md.file import MdFile

# Remove all handlers associated with the root logger object.
from indic_transliteration import sanscript

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def set_titles_from_spreadsheet(worksheet_name="कार्यावली", dry_run=False):
  doc_data = mahaabhaarata.get_doc_data(worksheet_name=worksheet_name)
  adhyaaya_to_source_file_map = mahaabhaarata.get_adhyaaya_to_source_file_map()
  for id in sorted(doc_data.get_df().index.values.tolist()):
    if id == "":
      continue
    title = sanscript.transliterate(id[3:], sanscript.OPTITRANS, sanscript.DEVANAGARI) + " " + doc_data.get_value(id=id, column_name="अध्यायनाम")
    md_file = adhyaaya_to_source_file_map[id]
    md_file.set_title(title=title, dry_run=dry_run)
    metadata_helper.set_filename_from_title(md_file=md_file, dry_run=dry_run)


def set_upaakhyaana_from_spreadsheet(worksheet_name="कार्यावली", dry_run=False):
  doc_data = mahaabhaarata.get_doc_data(worksheet_name=worksheet_name)
  adhyaaya_to_source_file_map = mahaabhaarata.get_adhyaaya_to_source_file_map()
  upaparva_to_upaakhyaanas = collections.defaultdict(list)
  for id in sorted(doc_data.get_df().index.values.tolist()):
    if id == "":
      continue
    upaakhyaana = doc_data.get_value(id=id, column_name="उपाख्यानम्")
    if upaakhyaana == "":
      continue
    upaparva = doc_data.get_value(id=id, column_name="उपपर्वनाम")
    if upaakhyaana not in upaparva_to_upaakhyaanas[upaparva]:
      upaparva_to_upaakhyaanas[upaparva].append(upaakhyaana)
    upaakhyaana_title = "%02d %s" % (upaparva_to_upaakhyaanas[upaparva].index(upaakhyaana) + 1, upaakhyaana)
    upaakhyaana_dir = file_helper.get_storage_name(upaakhyaana_title)
    md_path = adhyaaya_to_source_file_map[id].file_path
    if os.path.basename(os.path.dirname(md_path)) == upaakhyaana_dir:
      continue
    dest_dir = os.path.join(os.path.dirname(md_path), upaakhyaana_dir)
    os.makedirs(dest_dir, exist_ok=True)
    index_md_file = MdFile(file_path=os.path.join(dest_dir, "_index.md"))
    index_md_file.dump_to_file(metadata={"title": upaakhyaana_title}, content="", dry_run=dry_run)
    if not dry_run:
      shutil.move(src=md_path, dst=os.path.join(dest_dir, os.path.basename(md_path)))


def get_upaakhyaana_and_titles_from_path(dir_path, file_pattern="**/*.md"):
  md_files = MdFile.get_md_files_from_path(dir_path=dir_path, file_pattern=file_pattern)
  titles = [md_file.get_title() for md_file in md_files]
  upaakhyaanas = [md_file.get_upaakhyaana() for md_file in md_files]
  for row in zip(upaakhyaanas, titles):
    print("\t".join([str(i) for i in row]))


if __name__ == '__main__':
  pass
  # get_upaakhyaana_and_titles_from_path(dir_path=dir_path)
  # MdFile.fix_index_files(dir_path=dir_path, dry_run=False)
  # set_titles_from_spreadsheet(dry_run=False)
  set_upaakhyaana_from_spreadsheet(dry_run=False)
