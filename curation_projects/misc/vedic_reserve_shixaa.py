import logging
import os

from doc_curation.scraping import html


logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def dump_text(url, output_dir_path):
    outfile_path = os.path.join(output_dir_path, url.split("/")[-1].replace(".html", ".md"))
    html.dump_text_from_element(url=url, outfile_path=outfile_path, text_css_selector="#vedictext", title_css_selector="#vedictext > h3 > a")
    

def dump_shikshaa():
  dump_text(url="https://vedicreserve.miu.edu/shiksha/madhusudani_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/vyala_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/vyali_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/shaishiriya_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/shaunaka_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/hayagrivi_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/shamana_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/svaravyanjana_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/svarankusha_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/")


  dump_text(url="https://vedicreserve.miu.edu/shiksha/varnaratnapradipika_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/amoghanandini_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/laghvamoghanandini_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/avasananirnaya_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/galadrik_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/kanva_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/katyayana_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/katyayani_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/keshava_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/keshavi_padyatmika_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/kaushiki_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/kramasandhana_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/madhyandina_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/laghumadhyandina_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/parashara_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/pratishakhyapradipa_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/manahsvara_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/mallasharma_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/mandavya_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/yajurvidhana_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/yagyavalkya_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/vasishthi_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/vedaparibhashasutra_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/vedaparibhashakarika_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/shodashashloki_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/svarabhaktilakshanaparishishtha_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/svarashtaka_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/")


  dump_text(url="https://vedicreserve.miu.edu/shiksha/atreya1_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/atreya2_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/apishali_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/aranya_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/kalanirnaya_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/kaundinya_hyd_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/kaundinya_mysore_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/kauhaliya_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/carayaniya_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/bharadvaja_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/pari_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/pluta_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/lakshmikanta_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/laugakshi_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/vararuchi_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/vasishthi_tirupati_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/vasishtha_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/veda_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/vyasa_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/shambhu_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/shyamayaniya_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/sarvasammata_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/siddhanta_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/svara_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/svarasarabhutavarnakrama_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH")


  dump_text(url="https://vedicreserve.miu.edu/shiksha/naradiya_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/sAma-vedaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/lomasiya_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/sAma-vedaH")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/gautami_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/sAma-vedaH")


  dump_text(url="https://vedicreserve.miu.edu/shiksha/manduki_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/atharva-vedaH/")

  dump_text(url="https://vedicreserve.miu.edu/shiksha/paniniya_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/varna_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA")


def dump_upashikshaa():
  dump_text(url="https://vedicreserve.miu.edu/shiksha/athakari_lakshanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/rigvarnakramalakshanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/bonda_lakshanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/rig_vilanghya.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/vrithavyakti.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/svarashtaka.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/jata_patala_karika.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/Rg-vedaH/upashixA/")

  dump_text(url="https://vedicreserve.miu.edu/shiksha/padakarikaratnamala.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/padachandrika.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/pratijna_sutra.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/shuklaH/upashixA/")

  dump_text(url="https://vedicreserve.miu.edu/shiksha/visargangulipradarshanaprakarah.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/yajur_veda_saptalakshana.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Antanirdesha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Arunashamanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/ardhantyam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/ingya_ratnam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/uccodarki.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/kampa_sutra.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Jatamani.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/jatavalli.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/jata_siddhanta_candrika.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Trikrama_Lakshanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/dvitvalakshanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Naradabaith.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Naradabaith_Vyakhya.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Pranava_Vichara.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/yanadeshadirhginishedha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/yamapatti.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  # dump_text(url="https://vedicreserve.miu.edu/shiksha/yohiprapti_shiksha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Yohi_Bhashya.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Ravanabaith.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Ravanabaith_paribhasha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/varnakrama_lakshanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/visarjaniya_lakshanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Vaidyanatha_Baith.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Shakhashamanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Shadvimshati_Sutra.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/svara_panchashat.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/svara_samparki.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Svaravadhanalakshana.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/yajur-vedaH/kRShNaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/stobhapada_lakshanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/sAma-vedaH/upashixA/")
  # dump_text(url="https://vedicreserve.miu.edu/shiksha/sama_veda_saptalakshana.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/sAma-vedaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/samalakshanadipika.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/sAma-vedaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/dantyoshthavidhi.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/atharva-vedaH/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/jata_lakshanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/tritiya_samgraha.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/Pindalakshanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/vyakti_lakshanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/svarabhaktivishaya_lakshanam.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/upashixA/")
  dump_text(url="https://vedicreserve.miu.edu/shiksha/varnakrama_darpana.html", output_dir_path="/home/vvasuki/sanskrit/raw_etexts/shixA/upashixA/")


if __name__ == '__main__':
  dump_upashikshaa()
