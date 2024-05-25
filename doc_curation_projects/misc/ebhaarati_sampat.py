import os.path

from doc_curation.scraping.misc_sites import ebhaarati

def sv():
  BRAHMA_SUUTRA_BASE = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnuja-sampradAyaH"
  # ebhaarati.dump_article(url="https://www.ebharatisampat.in/readbook3?bookid=Mjk0ODc3MDcyMDQ4MTA0&pageno=MjI0MjQyNjk5NTk=", outfile_path=BRAHMA_SUUTRA_BASE)
  # ebhaarati.dump_article(url="https://www.ebharatisampat.in/read_chapter?bookid=ODkxNDUzNDgxODQwNDA0", outfile_path=os.path.join(BRAHMA_SUUTRA_BASE, "laxmI-pura-shrInivAsaH"))
  # ebhaarati.dump_article(url="https://www.ebharatisampat.in/readbook3?bookid=MjYyMzYyOTMxMDAyNTA0&pageno=MjI0MjQyNjk5NTk=", outfile_path=os.path.join(BRAHMA_SUUTRA_BASE, "venkaTanAthaH"))
  # ebhaarati.dump_article(url="https://www.ebharatisampat.in/readbook3?bookid=MDQ4MDIwMzQxNDAxNTA0&pageno=MjI0MjQyNjk5NTk=", outfile_path=os.path.join(BRAHMA_SUUTRA_BASE, "rAmAnujaH/shrI-bhAShyam/vAtsya-varada-tattva-sAraH"))
  # ebhaarati.dump_article(url="https://www.ebharatisampat.in/read_chapter?bookid=NDQyNzU2MDEyNjczMzA0", outfile_path=os.path.join(BRAHMA_SUUTRA_BASE, "rAmAnujaH/shrI-bhAShyam/rAjagopAlaH/"))
  # ebhaarati.dump_article(url="https://www.ebharatisampat.in/read_chapter?bookid=ODkxNDUzNDgxODQwNDA0", outfile_path=os.path.join(BRAHMA_SUUTRA_BASE, "rAmAnujaH/shrI-bhAShyam/rAmAnuja-tAtAryaH/"))
  # ebhaarati.dump_article(url="https://www.ebharatisampat.in/readbook3?bookid=Njg4MzIzOTYxMjM0NDA0&pageno=MjI0MjQyNjk5NTk=", outfile_path=os.path.join(BRAHMA_SUUTRA_BASE, "anantAryaH/"))
  # ebhaarati.dump_article(url="https://www.ebharatisampat.in/read_chapter?bookid=MjUxMTUwODUxMDI3NDA0", outfile_path=os.path.join(BRAHMA_SUUTRA_BASE, "rAmAnujaH/shrI-bhAShyam/sudarshana-sUriH/"))
  # ebhaarati.dump_article(url="https://www.ebharatisampat.in/readbook3?bookid=MjQwOTM4NjcxMDQyNDA0&pageno=MjI0MjQyNjk5NTk=", outfile_path=os.path.join(BRAHMA_SUUTRA_BASE, "rAmAnujaH/shrI-bhAShyam/"))
  # ebhaarati.dump_article(url="https://www.ebharatisampat.in/readbook3?bookid=NDY0MTgwMzcxNjMzNDA0&pageno=MjI0MjQyNjk5NTk=", outfile_path=os.path.join(BRAHMA_SUUTRA_BASE, "rAmAnujaH/shrI-bhAShyam/"))
  # ebhaarati.dump_article(url="https://www.ebharatisampat.in/read_chapter?bookid=MDkyMDY5NjMyNDA3MjA0", outfile_path=os.path.join(BRAHMA_SUUTRA_BASE, "rAmAnujaH/shrI-bhAShyam/"))
  ebhaarati.dump_article(url="https://www.ebharatisampat.in/read_chapter?bookid=NDMxNTQ0OTIyNjk4MjA0", outfile_path=os.path.join(BRAHMA_SUUTRA_BASE, "rAmAnujaH/shrI-bhAShyam/"))

def miimaamsaa():
  ebhaarati.dump_article(url="https://www.ebharatisampat.in/read_chapter?bookid=ODE0ODc3NjQxODAwNTA0", outfile_path="/home/vvasuki/gitland/vishvAsa/mImAMsA/content/dharmapurI-rAmAnujaH")


def smrti():
  ebhaarati.dump_article(url="https://www.ebharatisampat.in/readbook3?bookid=NDg4ODU5MDg4Mzk4MjY0&pageno=MjI0MjQyNjk5NTk=", outfile_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/hiraNyakeshI/gRhyam/paddhatiH/AchAra-bhUShaNam.md")
  

if __name__ == '__main__':
  # sv()
  smrti()
  # miimaamsaa()
  pass