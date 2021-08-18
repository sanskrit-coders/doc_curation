import logging

from doc_curation import blog
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
    # wordpress.scrape_index(url="https://manasataramgini.wordpress.com/the-complete-index/", dry_run=False, dir_path="/home/vvasuki/hindu-comm/weblogs/manasataramgini")
    # wordpress.scrape_index(url="https://padmavajra.net/index-of-posts/", dry_run=False, dir_path="/home/vvasuki/hindu-comm/weblogs/padmavajra/")
    # wordpress.scrape_index(url="https://vriitrahan.wordpress.com/2021/07/21/archive/", dry_run=False, dir_path="/home/vvasuki/hindu-comm/weblogs/vriitrahan/")
    # wordpress.scrape_index(url="https://aryaakasha.com/unfiltered-archive/", dry_run=False, dir_path="/home/vvasuki/hindu-comm/weblogs/aryaakasha/")
    wordpress.scrape_index(url="https://cestlaviepriya.wordpress.com/index/", dry_run=False, dir_path="/home/vvasuki/hindu-comm/weblogs/cestlaviepriya")
    # blog.scrape_index_from_anchors(url="https://www.chamuks.in/articles", dir_path="/home/vvasuki/hindu-comm/weblogs/chamuks", anchor_css=".card-footer a[href]", dry_run=False)