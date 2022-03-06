import os

import regex
from bs4 import BeautifulSoup

from doc_curation.scraping import sacred_texts
from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.wisdom_lib import para_translation

static_dir_base = "/home/vvasuki/vishvAsa/vedAH_Rk/static/shAnkhAyanam/sUtram/shAnkhAyanaH/gRhyam"
content_dir_base = static_dir_base.replace("static/", "content/")
ref_dir = os.path.join(static_dir_base, "vishvAsa-prastutiH")



def oldenberg_dest_path_maker(url, base_dir):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  title = souper.title_from_element(soup, title_css_selector="h1")
  title = title.replace(" I,", "1,").replace(" II,", "2,")
  subpath = regex.sub("\D+", " ", title).strip().replace(" ", "_")
  subpath = "/".join(["%02d" % int(x) for x in subpath.split("_")])
  return os.path.join(base_dir, subpath + ".md")


if __name__ == '__main__':
  # para_translation.dump_serially(start_url="https://www.wisdomlib.org/hinduism/book/sankhayana-grihya-sutra/d/doc116455.html", base_dir=ref_dir.replace("vishvAsa-prastutiH", "oldenberg"), dest_path_maker=oldenberg_dest_path_maker)
  # para_translation.split(base_dir=ref_dir.replace("vishvAsa-prastutiH", "oldenberg"))
  sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbe29/sbe29002.htm", outfile_path=os.path.join(content_dir_base, "meta", "oldenberg.md"))
  pass
