import logging

from doc_curation import blog
from doc_curation.blog import wordpress, substack, rss
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
  wordpress.scrape_index(url="https://vriitrahan.wordpress.com/2021/07/21/archive/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/vriitrahan/")
  wordpress.scrape_index(url="https://manasataramgini.wordpress.com/the-complete-index/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/manasataramgini")
  wordpress.scrape_index(url="https://vansatakopadaya.wordpress.com/index-of-all-posts/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/vansatakopadaya")
  wordpress.scrape_index(url="https://padmavajra.net/index-of-posts/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/padmavajra/")
  wordpress.scrape_index(url="https://aryaakasha.com/unfiltered-archive/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/aryaakasha/")
  wordpress.scrape_index(url="https://cestlaviepriya.wordpress.com/index/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/cestlaviepriya")
  wordpress.scrape_index(url="https://gairikshita.wordpress.com/2026/06/10/206/", dir_path=f"{BASE_PATH}/weblogs/kastUri-gairikshita", dry_run=False)
  # wordpress.scrape_index(url="https://agnimaan.wordpress.com/index-of-all-posts/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/agnimaan")

def dump_wordpress_monthly():

  wordpress.scrape_monthly_indexes(url="https://thesidhantin.wordpress.com/", dir_path=f"{BASE_PATH}/weblogs/thesidhantin", init_year_month_str="2025/03", dry_run=False)

  init_year_month_str = "2025/07"

  wordpress.scrape_monthly_indexes(url="https://adbhutam.wordpress.com/", dir_path=f"{BASE_PATH}/weblogs/adbhutam_subbu_advaita", init_year_month_str=init_year_month_str, dry_run=False)

  wordpress.scrape_monthly_indexes(url="https://dothemath.ucsd.edu/", dir_path=f"{BASE_PATH}/weblogs/non-hindu/doTheMath", init_year_month_str=init_year_month_str, dry_run=False)

  wordpress.scrape_monthly_indexes(url="https://romaharshana.wordpress.com/", dir_path=f"{BASE_PATH}/weblogs/aniketa_romaharshana", init_year_month_str=init_year_month_str, dry_run=False)

  # Slow scan
  # wordpress.scrape_monthly_indexes(url="https://svargaonearth.wordpress.com", dir_path=f"{BASE_PATH}/weblogs/non-hindu/svargaOnEarth", init_year_month_str=init_year_month_str, final_year_month_str="current", dry_run=False)

  # wordpress.scrape_monthly_indexes(url="https://suganyasmusingsscribblings.wordpress.com/", dir_path=f"{BASE_PATH}/weblogs/suganya", init_year_month_str=init_year_month_str, dry_run=False)
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

  # wordpress.scrape_monthly_indexes(url="https://visadavaak.wordpress.com/", dir_path=f"{BASE_PATH}/weblogs/visadavaak_tk", init_year_month_str="2016/06", dry_run=False)

  ## TODO: 
  # https://gairikshita.wordpress.com/
  # https://jigyaasaa.wordpress.com/ - dropdown.
  # https://vajrin.wordpress.com/ - multi page scroll
  #   wordpress.scrape_monthly_indexes(url="https://balramshukla.wordpress.com/", dry_run=False, dir_path=f"{BASE_PATH}/weblogs/balramshukla")
  pass


def dump_medium():
  # The selenium index scrape (medium.scrape_medium_blog) is defeated by Medium's
  # security-verification challenge; the RSS feed carries the same full content.
  rss.scrape(profile_url="https://satyan-sharma.medium.com/", dist_dir=f"{BASE_PATH}/weblogs/satyan-sharma")


SUBSTACK_TARGETS = [
  ("https://psugam.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/psugam"),
  ("https://devnmsura.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/devnmsura"),
  ("https://immanentdomain.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/immanentdomain"),
  ("https://naavalam.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/naavalam"),
  ("https://www.thelongmemory.in/archive?sort=new", f"{BASE_PATH}/weblogs/long-memory"),
  ("https://jamvasu.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/singh-AkANkShA"),
  ("https://mravinderreddy.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/mravinderreddy"),
  ("https://razib.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/non-hindu/razib"),
  ("https://krishnants.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/krishnants"),
  ("https://mylapore.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/mylapore-devanAthan"),
  ("https://ramaseshanchandrasekaran.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/ramaseshan"),
  ("https://cshc.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/cshc"),
  ("https://thamizhlabs.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/thamizhlabs"),
  ("https://tsering.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/bauddham/tsering"),
  ("https://www.stoneageherbalist.com/archive?sort=new", f"{BASE_PATH}/weblogs/non-hindu/stoneageherbalist"),
  (["https://frontierdharma.substack.com/archive?sort=new", "https://hindoohistory.substack.com/archive?sort=new"], f"{BASE_PATH}/weblogs/hindoohistory_frontierdharma"),
  ("https://thedharmadispatch.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/dharma-dispatch"),
  ("https://jhalazalimsingh.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/jhalazalimsingh"),
  ("https://williamjames17.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/williamjames17"),
  ("https://sadashree.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/sadashree"),
  ("https://newsletter.smallbets.co/archive?sort=new", f"{BASE_PATH}/weblogs/non-hindu/smallbets"),
  ("https://machiavellianhindu.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/machiavellianhindu"),
  ("https://vikramdialogues.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/vikramdialogues"),
  ("https://eruditus.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/eruditus"),
  ("https://nemets.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/non-hindu/nemets"),
  ("https://rasajournal.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/rasajournal"),
  ("https://ekavali.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/ekavali"),
  ("https://bharadvajatmaja.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/bharadvajatmata"),
  # Dead publication (404): https://singhhakanksha02.substack.com/archive
  ("https://www.newdelhireviewofbooks.in/archive?sort=new", f"{BASE_PATH}/weblogs/non-hindu/delhi-book-review"),
  ("https://epbutler.substack.com/archive?sort=new", f"{BASE_PATH}/weblogs/non-hindu/epbutler"),
]


def dump_substack():
  for (url, dir_path) in SUBSTACK_TARGETS:
    substack.scrape_free_articles_from_index_anchors(url=url, dir_path=dir_path, dry_run=False)


def fix_substack_archives(dry_run=False):
  """Deduplicate existing Substack archives and correct their dates/titles using the archive API."""
  for (url, dir_path) in SUBSTACK_TARGETS:
    substack.fix_archive(url=url, dir_path=dir_path, dry_run=dry_run, quarantine_dir="/tmp/opencode/substack_duplicates")


def dump_mags():
  for year in (2023, 2024, 2025, 2026):
    sambhashana_sandesha.dump_year(year=year, dest_path=f"{BASE_PATH}/mags/saMbhAShaNa-sandesha")


if __name__ == '__main__':
  pass
  # word_clouds()
  # dump_mags()
  # blog.organize_by_date(dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/satem/indo-iranian/indo-aryan/jAti-varNa-practice/v1/persons/sage-bloodlines/bhRguH/dvitIyajanmani_bhRguH/chyavanaH/ApnavAna/aurvaH/jamadagniH/MT_charitram")
  dump_medium()
  # dump_wordpress_monthly()
  # dump_substack()
  # dump_wordpress()
  # 
  # blog.scrape_index_from_anchors(url="https://www.chamuks.in/articles", dir_path=f"{BASE_PATH}/weblogs/chamuks", anchor_css=".card-footer a[href]", dry_run=False)
