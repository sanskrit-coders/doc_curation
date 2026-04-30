import os.path

from doc_curation.scraping.misc_sites import advaita_shaaradaa

dest_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/"


def misc():
  pass
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/moola/BS#BS_C04_S04", os.path.join(dest_dir, "bhAratI-tIrtha-vayyAsika-nyAya-mAlA.md"))

  # advaita_shaaradaa.dump_text("http://advaitasharada.sringeri.net/display/prakarana/vedantasara/devanagari#VS_C00_P10", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/tattvam/prakIrNam/sadAnanda-yogI_vedAnta-sAraH.md", overwrite=True)
  
  
  advaita_shaaradaa.dump_2pane_series("https://advaitasharada.sringeri.net/display/splitWindow/shastra-siddanthalesha-sangraha/SLSK/SLS_C03_S01/SLSK_SLS_C01_S05_SS01_VD00345", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/tattvam/prakIrNam/kRShNAnanda-tIrtha-shAstra-siddhAnta-lesha-sangrahaH/sarva-prastutiH/03.md")



if __name__ == '__main__':
  pass
  misc()