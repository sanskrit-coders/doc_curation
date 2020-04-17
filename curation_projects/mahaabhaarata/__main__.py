import logging
import os

from curation_projects import mahaabhaarata
from doc_curation.md_helper import MdFile

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def set_titles_from_spreadsheet(dir_path, dry_run=False):
    MdFile.fix_titles(
        md_files=mahaabhaarata.get_adhyaaya_md_files(dir_path),
        spreadhsheet_id="1sNH1AWhhoa5VATqMdLbF652s7srTG0Raa6K-sCwDR-8",
        worksheet_name="कुम्भकोणाध्यायाः", id_column="क्रमाङ्कम्", title_column="अन्तिमशीर्षिका", md_file_to_id=mahaabhaarata.get_adhyaaya_id, dry_run=dry_run
    )
    MdFile.devanaagarify_titles(md_files=mahaabhaarata.get_adhyaaya_md_files(dir_path), dry_run=dry_run)


def get_upaakhyaana_and_titles_from_path(dir_path, file_pattern="**/*.md"):
    md_files = MdFile.get_md_files_from_path(dir_path=dir_path, file_pattern=file_pattern)
    titles = [md_file.get_title() for md_file in md_files]
    upaakhyaanas = [md_file.get_upaakhyaana() for md_file in md_files]
    for row in zip(upaakhyaanas, titles):
        print ("\t".join([str(i) for i in row]))

dir_path = "/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padyam/purANam/mahAbhAratam/03-vana-parva/"
# set_titles_from_filenames(dir_path=dir_path, dry_run=True)
# get_upaakhyaana_and_titles_from_path(dir_path=dir_path)
MdFile.fix_index_files(dir_path=dir_path, dry_run=False)
# set_titles_from_spreadsheet(dir_path=dir_path, dry_run=False)