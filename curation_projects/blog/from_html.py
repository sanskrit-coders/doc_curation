import logging

from doc_curation.blog import wordpress
from doc_curation.md.file import MdFile
from doc_curation.md import library
# Remove all handlers associated with the root logger object.
from indic_transliteration import sanscript

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")
logging.getLogger('charsetgroupprober').setLevel(logging.WARNING)
logging.getLogger("charsetgroupprober").propagate = False
logging.getLogger('sbcharsetprober').setLevel(logging.WARNING)
logging.getLogger("sbcharsetprober").propagate = False

if __name__ == '__main__':
    pass
    # wordpress.scrape_index(url="https://manasataramgini.wordpress.com/the-complete-index/", dry_run=False, dir_path="/home/vvasuki/sanskrit/raw_etexts_english/blogs/manasataramgini")
    # wordpress.scrape_index(url="https://padmavajra.net/index-of-posts/", dry_run=False, dir_path="/home/vvasuki/sanskrit/raw_etexts_english/blogs/padmavajra/")
    wordpress.scrape_index(url="https://vriitrahan.wordpress.com/2021/07/21/archive/", dry_run=False, dir_path="/home/vvasuki/sanskrit/raw_etexts_english/blogs/vriitrahan/")

