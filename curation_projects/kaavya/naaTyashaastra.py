import os

from doc_curation.scraping.wisdom_lib import serial

path_manamohana = "/home/vvasuki/vishvAsa/kAvyam/content/laxaNam/granthaH/nATyashAstram/manamohanAnuvAdaH"


def dump_manamohana():
  # serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-natyashastra/d/doc202310.html", end_url="https://www.wisdomlib.org/hinduism/book/the-natyashastra/d/doc202312.html", out_path=os.path.join(path_manamohana, "00"))
  serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-natyashastra/d/doc202314.html", end_url="https://www.wisdomlib.org/hinduism/book/the-natyashastra/d/doc202327.html", out_path=os.path.join(path_manamohana, "00/intro/1"))
  serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-natyashastra/d/doc210167.html", end_url="https://www.wisdomlib.org/hinduism/book/the-natyashastra/d/doc210184.html", out_path=os.path.join(path_manamohana, "00/intro/2"))
  # serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-natyashastra/d/doc202329.html", out_path=path_manamohana)


if __name__ == '__main__':
  pass
  dump_manamohana()