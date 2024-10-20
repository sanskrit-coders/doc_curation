import os

from doc_curation.scraping.wisdom_lib import serial

def dump_tamil_kaavya():
  serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/tiruvaymoli-english/d/doc1206616.html", out_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/shrIvaiShNava/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/satyamUrtiH/", index=1182, join=True)

def dump_misc():
  serial.dump_series(start_url="https://www.wisdomlib.org/buddhism/book/tattvasangraha-english/d/doc363916.html", out_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/sAmya-vaiShamye/tattvam/sangrahaH/shAnti-raxita-tattva-sangrahaH", index=2014, index_format="%04d")
  


if __name__ == '__main__':
  pass
  dump_tamil_kaavya()
  # dump_misc()