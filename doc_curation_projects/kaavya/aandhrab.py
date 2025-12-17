import random
import time

from doc_curation.scraping.misc_sites import aandhrab
from doc_curation_projects.puraaNa.bhaagavatam.gp.hindi import dest_path


def baala():
  aandhrab.dump_series(url="https://andhrabharati.com/strI_bAla/bAlabhASha/SrI_sUryanArAyaNA.html", dest_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/telugu/padyam/vETUri-prabhAkara-shAstrI", a_css="#block-system-main .views-field-title a")


def gItam():
  # aandhrab.dump_series(url="https://www.andhrabharati.com/kIrtanalu/annamayya/index.php?audio=&cat=&cols=0123456&dispScript=uc%3Ade&inScheme=tr%3Arts&kword=&pageNum=1&pageSize=100&pallavi=&raga=&seq=&vid=&vol=&sort=pallavi", dest_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/kAvyam/gItam/annamAchAryaH", a_css="")
  count = 0 
  for id in range(301, 15196):
    count = count + 1
    # TODO: blocked due to bot activity. Must fix.
    if count % 70 == 0:
      time.sleep(60)
      # time.sleep(random.uniform(1.2, 120.5))
    aandhrab.dump_kIrtana(url=f"https://www.andhrabharati.com/kIrtanalu/annamayya/kirtana.php?id={id}&dispScript=uc:de", dest_path="/home/vvasuki/gitland/vishvAsa/gItam_vaiShNavam/content/te")


if __name__ == '__main__':
  # baala()
  gItam()
  pass