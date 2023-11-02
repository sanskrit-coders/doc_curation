import logging

from doc_curation import blog
from doc_curation.blog import wordpress, substack
from doc_curation.scraping.misc_sites import sambhashana_sandesha
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


BASE_PATH = f"/home/vvasuki/gitland/hindu-comm"


def word_clouds():
  stop_words = ["https", "groups", "group", "google", "http", "unsubscribe", "namaste", "PM", "AM", "Source"]
  library.dump_word_cloud(src_path=f"{BASE_PATH}/weblogs/manasataramgini",
                          dest_path="word-clouds/general.png", stop_words=stop_words)
  library.dump_word_cloud(src_path=f"{BASE_PATH}/weblogs/padmavajra", dest_path="word-clouds/general.png",
                          stop_words=stop_words)
  library.dump_word_cloud(src_path=f"{BASE_PATH}/weblogs/cestlaviepriya",
                          dest_path="word-clouds/general.png", stop_words=stop_words)


def dump_wordpress():
  wordpress.scrape_index(url="https://manasataramgini.wordpress.com/the-complete-index/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/manasataramgini")
  wordpress.scrape_index(url="https://padmavajra.net/index-of-posts/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/padmavajra/")
  wordpress.scrape_index(url="https://vriitrahan.wordpress.com/2021/07/21/archive/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/vriitrahan/")
  wordpress.scrape_index(url="https://aryaakasha.com/unfiltered-archive/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/aryaakasha/")
  wordpress.scrape_index(url="https://cestlaviepriya.wordpress.com/index/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/cestlaviepriya")
  wordpress.scrape_index(url="https://agnimaan.wordpress.com/index-of-all-posts/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/agnimaan")

def dump_wordpress_monthly():

  init_year_month_str = "2023/04"
  wordpress.scrape_monthly_indexes(url="https://dothemath.ucsd.edu/", dir_path=f"{BASE_PATH}/weblogs/non-hindu/doTheMath", init_year_month_str=init_year_month_str, dry_run=False)

  wordpress.scrape_monthly_indexes(url="https://svargaonearth.wordpress.com", dir_path=f"{BASE_PATH}/weblogs/non-hindu/svargaOnEarth", init_year_month_str=init_year_month_str, final_year_month_str="current", dry_run=False)

  wordpress.scrape_monthly_indexes(url="https://suganyasmusingsscribblings.wordpress.com/", dir_path=f"{BASE_PATH}/weblogs/suganya", init_year_month_str=init_year_month_str, dry_run=False)
  wordpress.scrape_monthly_indexes(url="https://westhunt.wordpress.com/", dir_path=f"{BASE_PATH}/weblogs/non-hindu/westhunt", init_year_month_str=init_year_month_str, dry_run=False)
  
  # Gone private
  #wordpress.scrape_monthly_indexes(url="https://pradyaus.wordpress.com/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/pradyaus")
  
  wordpress.scrape_monthly_indexes(url="https://indianphilosophyblog.org/", dir_path=f"{BASE_PATH}/weblogs/indianphilosophyblog", init_year_month_str=init_year_month_str, dry_run=False)
  wordpress.scrape_monthly_indexes(url="https://animeshnagarblog.wordpress.com/", dir_path=f"{BASE_PATH}/weblogs/animeshnagarblog", init_year_month_str=init_year_month_str, dry_run=False)
  wordpress.scrape_monthly_indexes(url="https://aryanthought.wordpress.com/", dir_path=f"{BASE_PATH}/weblogs/aryanthought", init_year_month_str=init_year_month_str, dry_run=False)
  wordpress.scrape_monthly_indexes(url="https://goghritam.wordpress.com/", dir_path=f"{BASE_PATH}/weblogs/goghritam", init_year_month_str=init_year_month_str, dry_run=False)

  wordpress.scrape_monthly_indexes(url="https://vajrin.wordpress.com/", dir_path=f"{BASE_PATH}/weblogs/vajrin", init_year_month_str=init_year_month_str, dry_run=False)

  wordpress.scrape_monthly_indexes(url="https://www.gnxp.com/WordPress/", dir_path=f"{BASE_PATH}/weblogs/non-hindu/gnxp_razib", init_year_month_str=init_year_month_str, dry_run=False, delay=30, reverse=False)


  # NOn-updated. One-time-dump done.
  # wordpress.scrape_monthly_indexes(url="https://musingsofhh.wordpress.com/", dir_path=f"{BASE_PATH}/weblogs/musingsofhh", init_year_month_str=None, dry_run=False)

  ## TODO: 
  # https://gairikshita.wordpress.com/
  # https://jigyaasaa.wordpress.com/ - dropdown.
  # https://vajrin.wordpress.com/ - multi page scroll
  #   wordpress.scrape_monthly_indexes(url="https://balramshukla.wordpress.com/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/balramshukla")
  pass


def dump_substack():
  substack.scrape_free_articles_from_index_anchors(url="https://thedharmadispatch.substack.com/archive", dir_path=f"{BASE_PATH}/weblogs/dharma-dispatch", dry_run=False)
  substack.scrape_free_articles_from_index_anchors(url="https://newsletter.smallbets.co/archive", dir_path=f"{BASE_PATH}/weblogs/non-hindu/smallbets", dry_run=False)
  substack.scrape_free_articles_from_index_anchors(url="https://machiavellianhindu.substack.com/archive", dir_path=f"{BASE_PATH}/weblogs/machiavellianhindu", dry_run=False)
  substack.scrape_free_articles_from_index_anchors(url="https://vikramdialogues.substack.com/archive", dir_path=f"{BASE_PATH}/weblogs/vikramdialogues", dry_run=False)
  substack.scrape_free_articles_from_index_anchors(url="https://eruditus.substack.com/archive", dir_path=f"{BASE_PATH}/weblogs/eruditus", dry_run=False)
  substack.scrape_free_articles_from_index_anchors(url="https://razib.substack.com/archive", dir_path=f"{BASE_PATH}/weblogs/non-hindu/razib", dry_run=False)
  substack.scrape_free_articles_from_index_anchors(url="https://hindoohistory.substack.com/archive", dir_path=f"{BASE_PATH}/weblogs/hindoohistory", dry_run=False)
  substack.scrape_free_articles_from_index_anchors(url="https://nemets.substack.com/archive", dir_path=f"{BASE_PATH}/weblogs/non-hindu/nemets", dry_run=False)
  substack.scrape_free_articles_from_index_anchors(url="https://rasajournal.substack.com/archive", dir_path=f"{BASE_PATH}/weblogs/rasajournal", dry_run=False)
  substack.scrape_free_articles_from_index_anchors(url="https://ekavali.substack.com/archive", dir_path=f"{BASE_PATH}/weblogs/ekavali", dry_run=False)
  substack.scrape_free_articles_from_index_anchors(url="https://bharadvajatmaja.substack.com/archive", dir_path=f"{BASE_PATH}/weblogs/bharadvajatmata", dry_run=False)
  pass


def dump_mags():
  # sambhashana_sandesha.dump_year(year=2023, dest_path=f"{BASE_PATH}/mags/saMbhAShaNa-sandesha")
  # sambhashana_sandesha.dump_year(year=2022, dest_path=f"{BASE_PATH}/mags/saMbhAShaNa-sandesha")
  sambhashana_sandesha.dump_year(year=2021, dest_path=f"{BASE_PATH}/mags/saMbhAShaNa-sandesha")


if __name__ == '__main__':
  pass
  # word_clouds()
  # dump_mags()
  # blog.organize_by_date(dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/satem/indo-iranian/indo-aryan/jAti-varNa-practice/v1/persons/sage-bloodlines/bhRguH/dvitIyajanmani_bhRguH/chyavanaH/ApnavAna/aurvaH/jamadagniH/MT_charitram")
  dump_wordpress()
  dump_wordpress_monthly()
  dump_substack()

  # blog.scrape_index_from_anchors(url="https://www.chamuks.in/articles", dir_path=f"{BASE_PATH}/weblogs/chamuks", anchor_css=".card-footer a[href]", dry_run=False)
