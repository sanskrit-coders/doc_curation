import logging
import os

# Remove all handlers associated with the root logger object.
from curation_projects.mahaabhaarata.md_helper import MdFile

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def set_titles_from_filenames(dir_path, file_pattern="**/*.md", dry_run=False):
    md_files = MdFile.get_md_files_from_path(dir_path=dir_path, file_pattern=file_pattern)
    for md_file in md_files:
        md_file.set_title_from_filename(dry_run=dry_run)


def get_upaakhyaana_and_titles_from_path(dir_path, file_pattern="**/*.md"):
    md_files = MdFile.get_md_files_from_path(dir_path=dir_path, file_pattern=file_pattern, file_name_filter=lambda x: os.path.basename(x) != "_index.md")
    titles = [md_file.get_title() for md_file in md_files]
    upaakhyaanas = [md_file.get_upaakhyaana() for md_file in md_files]
    for row in zip(upaakhyaanas, titles):
        print ("\t".join([str(i) for i in row]))

dir_path = "/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padya/purANa/mahAbhArata/02-sabhA-parva/"
set_titles_from_filenames(dir_path=dir_path, dry_run=False)
get_upaakhyaana_and_titles_from_path(dir_path=dir_path)