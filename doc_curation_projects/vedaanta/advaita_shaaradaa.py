import os.path

from doc_curation.scraping.misc_sites import advaita_shaaradaa

dest_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/"


def misc():
  pass
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/moola/BS#BS_C04_S04", os.path.join(dest_dir, "bhAratI-tIrtha-vayyAsika-nyAya-mAlA.md"))

  # advaita_shaaradaa.dump_text("http://advaitasharada.sringeri.net/display/prakarana/vedantasara/devanagari#VS_C00_P10", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/tattvam/prakIrNam/sadAnanda-yogI_vedAnta-sAraH.md", overwrite=True)
  
  
  # advaita_shaaradaa.dump_split_series("shastra-siddanthalesha-sangraha", "SLSK", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/tattvam/prakIrNam/kRShNAnanda-tIrtha-shAstra-siddhAnta-lesha-sangrahaH/sarva-prastutiH/03.md", start_chunk="3")

def brahmasUtram():
  pass
  # advaita_shaaradaa.dump_split_series("brahmasutra-bhashya", "NY", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/tattvam/shankaraH/brahma-sUtrANi/Ananda-jnANa-nyAya-nirNayaH/sarva-prastutiH.md")
  advaita_shaaradaa.dump_split_series("brahmasutra-bhashya", "PP", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/tattvam/shankaraH/brahma-sUtrANi/pancha-pAdikA/mUlam.md")
  advaita_shaaradaa.dump_split_series("brahmasutra-bhashya", "BM", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/tattvam/shankaraH/brahma-sUtrANi/vAchaspati-mishra-bhAmatI/as-prastutiH.md")
  advaita_shaaradaa.dump_split_series("brahmasutra-bhashya", "RP", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/tattvam/shankaraH/brahma-sUtrANi/rAmAnanda-bhAShya-ratna-prabhA/mUlam.md")



def upaniShat():
  pass
  # advaita_shaaradaa.dump_split_series("brihadaranyaka-bhashya", "AB", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/kANvam/shatapatha-brAhmaNam/17_bRhadAraNyakopaniShat/shankaraH/sarva-prastutiH.md")

  # advaita_shaaradaa.dump_split_series("chandogya-bhashya", "AC", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/tANDyam/ChAndogyopaniShat/shankaraH/sarva-prastutiH.md")
  # advaita_shaaradaa.dump_split_series("aitareya-bhashya", "AA", "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/shAkalam/aitareya-brAhmaNam/upaniShat/shankaraH/shankaraH/sarva-prastutiH.md")
  # advaita_shaaradaa.dump_split_series("taittiriya-bhashya", "AT", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/AraNyakam/sarva-prastutiH/05_taittirIyopaniShat/shankaraH/Ananda-giriH.md")
  # advaita_shaaradaa.dump_split_series("taittiriya-bhashya", "TVN", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/AraNyakam/sarva-prastutiH/05_taittirIyopaniShat/shankaraH/vana-mAlA.md")

  # advaita_shaaradaa.dump_text("https://advaitasharada.sringeri.net/display/bhashyaVyakhya/Taitiriya/devanagari?vyakhya=TV", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/AraNyakam/sarva-prastutiH/05_taittirIyopaniShat/shankaraH/vArttikA.md")
  # advaita_shaaradaa.dump_split_series("mandukya-karika-bhashya", "AY", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/mANDukyopaniShat/shankaraH/sarva-prastutiH.md")
  # advaita_shaaradaa.dump_split_series("mundaka-bhashya", "AM", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/paippalAdam/muNDakopaniShat/shankaraH/sarva-prastutiH.md")
  # advaita_shaaradaa.dump_split_series("prashna-bhashya", "AP", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/paippalAdam/prashnopaniShat/shankaraH/sarva-prastutiH.md")
  advaita_shaaradaa.dump_split_series("kathaka-bhashya", "AK", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/AraNyakam/kaThopaniShat/shankaraH/sarva-prastutiH.md", overwrite=True)
  # advaita_shaaradaa.dump_split_series("kena-vakya-bhashya", "AKV", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/jaiminIyam/AraNyakam/upaniShad-brAhmaNam/04/10_kenopaniShat/shankaraH/vAkya-bhAShyam/sarva-prastutiH.md")

  # advaita_shaaradaa.dump_split_series("kena-pada-bhashya", "AKP", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/jaiminIyam/AraNyakam/upaniShad-brAhmaNam/04/10_kenopaniShat/shankaraH/pada-bhAShyam/sarva-prastutiH.md")

  # advaita_shaaradaa.dump_split_series("isha-bhashya", "AIS", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/shAnkarAH/sarva-prastutiH.md")


if __name__ == '__main__':
  pass
  # misc()
  brahmasUtram()
