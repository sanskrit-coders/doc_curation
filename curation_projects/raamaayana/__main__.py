import logging

from doc_curation.md_helper import MdFile

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


md_file_path = "/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padya/purANa/rAmAyaNa/Andhra/"
MdFile.fix_index_files(dir_path=md_file_path, dry_run=False)
