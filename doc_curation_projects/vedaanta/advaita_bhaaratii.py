import os.path

from doc_curation.scraping.misc_sites import advaita_shaaradaa

dest_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/"




if __name__ == '__main__':
  pass
  advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/BS", os.path.join(dest_dir, "jNAnANanda-bhAratI_tamiL.md"))

  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/moola/BS#BS_C04_S04", os.path.join(dest_dir, "bhAratI-tIrtha-vayyAsika-nyAya-mAlA.md"))
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/Gita", os.path.join("/home/vvasuki/gitland/vishvAsa/mahAbhAratam/content/shlokashaH/bhagavad-gItA-parva", "shankaraH/tamil/sudarshana-rAma-subrahmaNya-rAjA.md"))

  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/Mundaka", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/paippalAdam/muNDakopaniShat/shankaraH.md", overwrite=True)
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/Isha", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/shankaraH.md", overwrite=True)
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/Kena_pada", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/jaiminIyam/brAhmaNam/talavakAra-brAhmaNam/kenopaniShat/shankaraH_padam.md", overwrite=True)
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/Kena_vakya", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/jaiminIyam/brAhmaNam/talavakAra-brAhmaNam/kenopaniShat/shankaraH_vAkyam.md", overwrite=True)
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/Kathaka", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/AraNyakam/kaThopaniShat/shankaraH.md", overwrite=True)
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/Prashna", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/paippalAdam/prashnopaniShat/shankaraH.md", overwrite=True)
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/Mandukya", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/mANDukyopaniShat/shankaraH/tamiL.md", overwrite=True)
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/Taitiriya", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/AraNyakam/sarva-prastutiH/05_taittirIyopaniShat/shankaraH/tamiL.md", overwrite=True)
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/Aitareya", "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/shAkalam/aitareya-brAhmaNam/upaniShat/shankaraH.md", overwrite=True)
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/Chandogya", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/tANDyam/ChAndogyopaniShat/shankaraH.md", overwrite=True)
  # advaita_shaaradaa.dump_text("https://advaitabharati.sanatanasampatti.in/display/bhashya/Brha", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/bRhadAraNyakopaniShat/shankaraH/tamiL.md", overwrite=True)
