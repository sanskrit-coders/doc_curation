import os.path

from doc_curation.scraping.misc_sites import advaita_shaaradaa

dest_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/"


def upanishat():
  # advaita_shaaradaa.dump_text("https://anandamakaranda.in/document/bhashya/Taittiriya/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/AraNyakam/sarva-prastutiH/05_taittirIyopaniShat/madhvaH.md")
  advaita_shaaradaa.dump_text("https://anandamakaranda.in/document/bhashya/Isha/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/madhvaH.md")
  advaita_shaaradaa.dump_text("https://anandamakaranda.in/document/bhashya/Katha/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/AraNyakam/kaThopaniShat/madhvaH.md")
  advaita_shaaradaa.dump_text("https://anandamakaranda.in/document/bhashya/Mundaka/", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/paippalAdam/muNDakopaniShat/madhvaH.md")

  advaita_shaaradaa.dump_text("https://anandamakaranda.in/document/bhashya/Satprashna/", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/prashnopaniShat/madhvaH.md")

  advaita_shaaradaa.dump_text("https://anandamakaranda.in/document/bhashya/Aitareya/", "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/shAkalam/aitareya-brAhmaNam/upaniShat/madhvaH.md")


  advaita_shaaradaa.dump_text("https://anandamakaranda.in/document/bhashya/Brha/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/kANvam/shatapatha-brAhmaNam/17_bRhadAraNyakopaniShat/madhvaH.md")
  advaita_shaaradaa.dump_text("https://anandamakaranda.in/document/bhashya/Chandogya/", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/tANDyam/ChAndogyopaniShat/madhvaH.md")
  advaita_shaaradaa.dump_text("https://anandamakaranda.in/document/bhashya/Talavakara/", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/jaiminIyam/brAhmaNam/talavakAra-brAhmaNam/kenopaniShat/madhvaH.md")


if __name__ == '__main__':
  upanishat()
  pass

