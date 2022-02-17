import pandas


def import_from_mss_tsv():
  quote_df = pandas.read_csv("/home/vvasuki/sanskrit/raw_etexts/mixed/gretil_devanAgarI/5_poetry/5_subhas/mahA-subhAShita-sangraha_1_per_line_dev.tsv", sep="\t", keep_default_na=False)
  quote_df = quote_df.set_index("index")
  