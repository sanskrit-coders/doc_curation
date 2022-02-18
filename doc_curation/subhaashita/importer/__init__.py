import sys

import pandas
import regex

from doc_curation.subhaashita import Subhaashita
from indic_transliteration import sanscript


def import_from_mss_tsv():
  quote_df = pandas.read_csv("/home/vvasuki/sanskrit/raw_etexts/mixed/gretil_devanAgarI/5_poetry/5_subhas/mahA-subhAShita-sangraha_1_per_line_dev.tsv", sep="\t", keep_default_na=False)
  quote_df = quote_df.set_index("ID")
  quotes = []
  for mss_id in quote_df.index:
    text = str(quote_df.loc[mss_id].quote)
    text = regex.sub(r"। *", "।  \n", text)
    quote = Subhaashita(text=text, secondary_sources=[mss_id], script=sanscript.DEVANAGARI)
    quotes.append(quote)
  return quotes

