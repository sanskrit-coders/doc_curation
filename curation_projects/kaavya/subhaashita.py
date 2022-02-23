from doc_curation.md import library
from doc_curation.md.file import MdFile

from doc_curation.subhaashita import importer
from doc_curation.subhaashita.db import toml_md_db
from doc_curation.subhaashita.importer import subhaashita_ratna_bhaandaagaara
from indic_transliteration import sanscript

PATH_DB_SA = "/home/vvasuki/sanskrit/raw_etexts/kAvyam/padyam/subhAShitam/db_toml_md__sa__padya"


def dump_mss():
  quotes = importer.import_from_mss_tsv()
  toml_md_db.add(quotes, base_path=PATH_DB_SA)


def prep_srb():
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/laxyam/padyam/subhAShitam/subhAShita-ratna-bhANDAgAram/04_chitraprakaraNam/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/laxyam/padyam/subhAShitam/subhAShita-ratna-bhANDAgAram/02_sAmAnyaprakaraNam_p1/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)
  library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/laxyam/padyam/subhAShitam/subhAShita-ratna-bhANDAgAram/03_rAjaprakaraNam/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)

  pass

def dump_srb():
  # quotes = subhaashita_ratna_bhaandaagaara.from_dir(sub_dir="01_mangalAcharaNaprakaraNam", deduce_from_title="topics")
  # quotes = subhaashita_ratna_bhaandaagaara.from_dir(sub_dir="04_chitraprakaraNam/12_jAtivarNanam", deduce_from_title="topics")
  # quotes = subhaashita_ratna_bhaandaagaara.from_dir(sub_dir="04_chitraprakaraNam/", deduce_from_title="types")
  # quotes = subhaashita_ratna_bhaandaagaara.from_dir(sub_dir="02_sAmAnyaprakaraNam_p1", deduce_from_title="topics")
  # quotes = subhaashita_ratna_bhaandaagaara.from_dir(sub_dir="05_anyoktiprakaraNam", deduce_from_title="types")
  # quotes = subhaashita_ratna_bhaandaagaara.from_dir(sub_dir="03_rAjaprakaraNam", deduce_from_title="topics")
  quotes = subhaashita_ratna_bhaandaagaara.from_dir(sub_dir="06_navarasaprakaraNam", deduce_from_title="topics")
  toml_md_db.add(quotes, base_path=PATH_DB_SA)
  pass


if __name__ == '__main__':
  # dump_mss()
  # dump_srb()
  prep_srb()
  pass