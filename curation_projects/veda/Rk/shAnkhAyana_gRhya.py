import os

import regex
from bs4 import BeautifulSoup

from doc_curation.scraping.html_scraper import souper
from doc_curation.scraping.wisdom_lib import para_translation

ref_dir = "/home/vvasuki/vishvAsa/vedAH/static/Rk/shAnkhAyanam/sUtram/shAnkhAyanaH/gRhyam/vishvAsa-prastutiH/"



def oldenberg_dest_path_maker(url, base_dir):
  html = souper.get_html(url=url)
  soup = BeautifulSoup(html, 'html.parser')
  title = souper.title_from_element(soup, title_css_selector="h1")
  title = title.replace(" I,", "1,").replace(" II,", "2,")
  subpath = regex.sub("\D+", " ", title).strip().replace(" ", "_")
  subpath = "/".join(["%02d" % int(x) for x in subpath.split("_")])
  return os.path.join(base_dir, subpath + ".md")


if __name__ == '__main__':
  para_translation.dump_serially(start_url="https://www.wisdomlib.org/hinduism/book/sankhayana-grihya-sutra/d/doc116455.html", base_dir=ref_dir.replace("vishvAsa-prastutiH", "oldenberg"), dest_path_maker=oldenberg_dest_path_maker)
  para_translation.split(base_dir=ref_dir.replace("vishvAsa-prastutiH", "oldenberg"))
  pass
