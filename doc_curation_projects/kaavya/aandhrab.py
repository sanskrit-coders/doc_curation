import random
import time

import regex

from curation_utils import scraping
from doc_curation.md import library
from doc_curation.scraping.misc_sites import aandhrab
from doc_curation_projects.puraaNa.bhaagavatam.gp.hindi import dest_path


def baala():
  aandhrab.dump_series(url="https://andhrabharati.com/strI_bAla/bAlabhASha/SrI_sUryanArAyaNA.html", dest_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/telugu/padyam/vETUri-prabhAkara-shAstrI", a_css="#block-system-main .views-field-title a")


def gItam(overwrite=False):
  # aandhrab.dump_series(url="https://www.andhrabharati.com/kIrtanalu/annamayya/index.php?audio=&cat=&cols=0123456&dispScript=uc%3Ade&inScheme=tr%3Arts&kword=&pageNum=1&pageSize=100&pallavi=&raga=&seq=&vid=&vol=&sort=pallavi", dest_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/kAvyam/gItam/annamAchAryaH", a_css="")
  count = 0 
  dest_path = "/home/vvasuki/gitland/vishvAsa/gItam_vaiShNavam/content/te"
  md_files = library.get_md_files_from_path(dir_path=dest_path)
  sleep_duration = 80*60
  id_start = 10001
  for md_file in md_files:
    metadata, _ = md_file.read()
    if "upstream_url" in metadata:
      matches = regex.findall(r"(?<=id=)(\d+)", metadata["upstream_url"])
      id_start = max(id_start, int(matches[0]))


  for id in range(id_start, 15196):
    count = count + 1
    # Ratelimit 80 per hour.
    if count % 75 == 0:
      scraping.sleep_approx(duration=sleep_duration, jitter=5)
      # time.sleep(random.uniform(1.2, 120.5))
    url = f"https://www.andhrabharati.com/kIrtanalu/annamayya/kirtana.php?id={id}&dispScript=uc:de"
    
    dumped = False
    while not dumped:
      try:
        aandhrab.dump_kIrtana(url=url, dest_path=dest_path, overwrite=overwrite)
        dumped = True
      except ConnectionError as e:
        scraping.sleep_approx(duration=sleep_duration, jitter=5)
        count = 0


if __name__ == '__main__':
  # baala()
  # gItam()
  # aandhrab.dump_from_html_files("/home/vvasuki/Downloads/annamayya_13388_15195", "/home/vvasuki/gitland/vishvAsa/gItam_vaiShNavam/content/te")
  pass