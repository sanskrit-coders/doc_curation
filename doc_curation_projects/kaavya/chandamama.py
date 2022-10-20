from curation_utils import archive_utility
import logging
from urllib.error import HTTPError
import wget, os


# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def get_all(years, out_dir, url_maker):
  logging.info(f"Dumping to {out_dir}")
  os.makedirs(name=out_dir, exist_ok=True)
  for year in years:
    for month in range(1,13):
      url = url_maker(year, month)
      try:
        wget.download(url=url, out=out_dir)
        logging.info(f"Found: {year}/{month:02}")
      except HTTPError:
        logging.info(f"Not found: {year}/{month:02}")
        continue


def get_kannada():
  out_dir = "/home/vvasuki/Documents/books/granthasangrahaH/bhAShA/kannada/chandamama"
  years = list(range(1949, 1956)) + list(range(1957, 1959)) + [1972, 1975,] + list(range(1977, 1983))
  get_all(years, out_dir, url_maker=lambda year, month: f"https://chandamama.in/resources/kannada/{year}/Chandamama_Kannada_{year}_{month:02}.pdf")



def get_telugu():
  out_dir = "/home/vvasuki/Documents/books/granthasangrahaH/bhAShA/telugu/chandamama"
  years = list(range(1947, 2003))
  get_all(years, out_dir, url_maker=lambda year, month: f"https://chandamama.in/resources/teluguNew/{year}/Chandamama-{year}-{month}.pdf")


def get_marathi():
  out_dir = "/home/vvasuki/Documents/books/granthasangrahaH/bhAShA/marAThi/chandamama"
  years = list(range(1960, 2007))
  get_all(years, out_dir, url_maker=lambda year, month: f"https://chandamama.in/resources/marathi/{year}/Chandoba_Marathi_{year}_{month:02}.pdf")


def get_odiya():
  out_dir = "/home/vvasuki/Documents/books/granthasangrahaH/bhAShA/odiya/janhamAmU"
  years = list(range(1976, 1981)) + list(range(1983, 1989)) + [1973, 2002]
  get_all(years, out_dir, url_maker=lambda year, month: f"https://chandamama.in/resources/odiya/{year}/Janhamaamu-Odiya-{year}-{month:02}.pdf")



def get_assamese():
  out_dir = "/home/vvasuki/Documents/books/granthasangrahaH/bhAShA/assamese/chandamama"
  years = list(range(1985, 2014))
  get_all(years, out_dir, url_maker=lambda year, month: f"https://chandamama.in/resources/assamese/{year}/Chandamama_Assamese_{year}_{month:02}.pdf")



def get_malayalam():
  ## അമ്പിളിഅമ്മാവൻ अम्पिळिअम्मावन् 
  out_dir = "/home/vvasuki/Documents/books/granthasangrahaH/bhAShA/malayalam/ampiliammAvan"
  years = list(range(1952, 1955)) + [1971, 1987] + list(range(1976, 1979))
  get_all(years, out_dir, url_maker=lambda year, month: f"https://chandamama.in/resources/malayalam/{year}/Chandamama_Malayalam_{year}_{month:02}.pdf")


def get_bengali():
  ## চাঁদমামা
  out_dir = "/home/vvasuki/Documents/books/granthasangrahaH/bhAShA/bAnglA/chAndamAma"
  years = list(range(1972, 1975)) + [1977, 1979] + list(range(1992, 1997))
  get_all(years, out_dir, url_maker=lambda year, month: f"https://chandamama.in/resources/bengali/{year}/Chandamama_Bengali_{year}_{month:02}.pdf")


def get_hindI():
  out_dir = "/home/vvasuki/Documents/books/granthasangrahaH/bhAShA/hindI/chandAmAmA"
  years = list(range(1949, 2014))
  get_all(years, out_dir, url_maker=lambda year, month: f"https://chandamama.in/resources/hindi/{year}/Chandamama_Hindi_{year}_{month:02}.pdf")


def get_sanskrit():
  out_dir = "/home/vvasuki/Documents/books/granthasangrahaH/bhAShA/sanskrit/chandAmAmA"
  years = list(range(1984, 2013))
  get_all(years, out_dir, url_maker=lambda year, month: f"https://chandamama.in/resources/sanskrit/{year}/Chandamama_Sanskrit_{year}_{month:02}.pdf")


BASE = "/home/vvasuki/Documents/books/granthasangrahaH/bhAShA/"


if __name__ == '__main__':
  # get_telugu()
  # get_malayalam()
  # get_marathi()
  # get_odiya()
  # get_assamese()
  # get_bengali()
  # get_hindI()
  # get_sanskrit()

  archive_utility.update_item(item_id="chandamama_telugu_all", dir_path=os.path.join(BASE, "telugu/chandamama"))
