import os

from doc_curation.md import library
from doc_curation.md.library import metadata_helper
from doc_curation.scraping.wisdom_lib import serial
from doc_curation_projects.vedaanta.brahma_suutra import arrangement
from indic_transliteration import sanscript


def dump_tamil_kaavya():
  serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/tiruvaymoli-english/d/doc1206616.html", out_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/shrIvaiShNava/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/satyamUrtiH/", index=1182, join=True)

def dump_misc():
  serial.dump_series(start_url="https://www.wisdomlib.org/buddhism/book/tattvasangraha-english/d/doc363916.html", out_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/sAmya-vaiShamye/tattvam/sangrahaH/shAnti-raxita-tattva-sangrahaH", index=2014, index_format="%04d")
  


def dump_shankara():
  pass
  # serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/chandogya-upanishad-shankara-bhashya/d/doc1145324.html", out_path="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/tANDyam/ChAndogyopaniShat/shankaraH/en", index=121, index_format="%03d")

  # serial.dump_series(start_url="http://wisdomlib.org/hinduism/book/the-sarva-darsana-samgraha/d/doc79744.html", out_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/sAmya-vaiShamye/tattvam/sangrahaH/mAdhava-sarva-darshana-sangrahaH/en/colwell", index=0, index_format="%02d")
  # serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-sarva-darsana-samgraha/d/doc79743.html", end_url="https://www.wisdomlib.org/hinduism/book/the-sarva-darsana-samgraha/d/doc79743.html", out_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/sAmya-vaiShamye/tattvam/sangrahaH/mAdhava-sarva-darshana-sangrahaH/en/colwell/meta", index=0, index_format="%02d")


def dump_mImAMsA():
  pass
  serial.dump_series(start_url="", out_path="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/tANDyam/ChAndogyopaniShat/shankaraH/en", index=121, index_format="%03d")
  


if __name__ == '__main__':
  pass
  # dump_tamil_kaavya()
  # dump_misc()
  dump_shankara()
  # library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/tANDyam/ChAndogyopaniShat/shankaraH/en/", fn=metadata_helper.set_filename_from_title, source_script=sanscript.DEVANAGARI, file_name_filter=lambda x: not os.path.basename(x).startswith("_"), overwrite=True, dry_run=False)
