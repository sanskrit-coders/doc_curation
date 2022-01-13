import logging

from doc_curation import blog
from doc_curation.blog import wordpress, substack
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
    wordpress.scrape_index(url="https://manasataramgini.wordpress.com/the-complete-index/", dry_run=False, dir_path="/home/vvasuki/hindu-comm/weblogs/manasataramgini")
    wordpress.scrape_index(url="https://padmavajra.net/index-of-posts/", dry_run=False, dir_path="/home/vvasuki/hindu-comm/weblogs/padmavajra/")
    wordpress.scrape_index(url="https://vriitrahan.wordpress.com/2021/07/21/archive/", dry_run=False, dir_path="/home/vvasuki/hindu-comm/weblogs/vriitrahan/")
    wordpress.scrape_index(url="https://aryaakasha.com/unfiltered-archive/", dry_run=False, dir_path="/home/vvasuki/hindu-comm/weblogs/aryaakasha/")
    wordpress.scrape_index(url="https://cestlaviepriya.wordpress.com/index/", dry_run=False, dir_path="/home/vvasuki/hindu-comm/weblogs/cestlaviepriya")
    # wordpress.scrape_index(url="https://agnimaan.wordpress.com/index-of-all-posts/", dry_run=False, dir_path="/home/vvasuki/hindu-comm/weblogs/agnimaan")
    # 
    # wordpress.scrape_monthly_indexes(url="https://westhunt.wordpress.com/", dir_path="/home/vvasuki/hindu-comm/weblogs/westhunt", init_year_month_str=None, dry_run=False)
    # wordpress.scrape_monthly_indexes(url="https://indianphilosophyblog.org/", dir_path="/home/vvasuki/hindu-comm/weblogs/indianphilosophyblog", init_year_month_str=None, dry_run=False)
    # wordpress.scrape_monthly_indexes(url="https://animeshnagarblog.wordpress.com/", dir_path="/home/vvasuki/hindu-comm/weblogs/animeshnagarblog", init_year_month_str=None, dry_run=False)
    # wordpress.scrape_monthly_indexes(url="https://aryanthought.wordpress.com/", dir_path="/home/vvasuki/hindu-comm/weblogs/aryanthought", init_year_month_str=None, dry_run=False)
    # wordpress.scrape_monthly_indexes(url="https://goghritam.wordpress.com/", dir_path="/home/vvasuki/hindu-comm/weblogs/goghritam", init_year_month_str=None, dry_run=False)
    # 
    # wordpress.scrape_monthly_indexes(url="https://vajrin.wordpress.com/", dir_path="/home/vvasuki/hindu-comm/weblogs/vajrin", init_year_month_str=None, dry_run=False)

    ## TODO: 
    # https://gairikshita.wordpress.com/
    # https://jigyaasaa.wordpress.com/ - dropdown.
    # https://vajrin.wordpress.com/ - multi page scrollhttps://t.co/0bIGUYvlY7
    # https://twitter.com/manassarov/status/1480293685535326211/photo/2
    # substack.scrape_free_articles_from_index_anchors(url="https://indianhistory.substack.com/archive", dir_path="/home/vvasuki/hindu-comm/weblogs/indianhistory", dry_run=False)
    # substack.scrape_free_articles_from_index_anchors(url="https://razib.substack.com/archive", dir_path="/home/vvasuki/hindu-comm/weblogs/razib", dry_run=False)
    # substack.scrape_free_articles_from_index_anchors(url="https://hindoohistory.substack.com/archive", dir_path="/home/vvasuki/hindu-comm/weblogs/hindoohistory", dry_run=False)
    # substack.scrape_free_articles_from_index_anchors(url="https://nemets.substack.com/archive", dir_path="/home/vvasuki/hindu-comm/weblogs/nemets", dry_run=False)


    # blog.scrape_index_from_anchors(url="https://www.chamuks.in/articles", dir_path="/home/vvasuki/hindu-comm/weblogs/chamuks", anchor_css=".card-footer a[href]", dry_run=False)
