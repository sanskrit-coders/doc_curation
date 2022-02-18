from doc_curation.subhaashita import importer
from doc_curation.subhaashita.db import toml_md_db

PATH_DB_SA = "/home/vvasuki/sanskrit/raw_etexts/kAvyam/padyam/subhAShitam/db_toml_md__sa"


def dump_mss():
  quotes = importer.import_from_mss_tsv()
  toml_md_db.add(quotes, base_path=PATH_DB_SA)

  
if __name__ == '__main__':
  dump_mss()
  
  pass