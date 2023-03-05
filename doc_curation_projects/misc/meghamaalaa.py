import logging
import os.path
from doc_curation.md.library import metadata_helper

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

from doc_curation.scraping.misc_sites import meghamaalaa


def upanishat():
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/katopanishat-content/%e0%a4%95%e0%a4%a0%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%aa%e0%a5%8d%e0%a4%b0%e0%a4%a5%e0%a4%ae%e0%a4%be-%e0%a4%b5%e0%a4%b2%e0%a5%8d%e0%a4%b2%e0%a5%80/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/AraNyakam/kaThopaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/maandookyapanishat-content/%e0%a4%ae%e0%a4%be%e0%a4%a3%e0%a5%8d%e0%a4%a1%e0%a5%82%e0%a4%95%e0%a5%8d%e0%a4%af%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d%e0%a4%95%e0%a4%be%e0%a4%b0%e0%a4%bf%e0%a4%95%e0%a4%be/", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/mANDukyopaniShat/shrI-sampradAyaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/chandogya-upanishat-content/%e0%a4%9b%e0%a4%be%e0%a4%a8%e0%a5%8d%e0%a4%a6%e0%a5%8b%e0%a4%97%e0%a5%8d%e0%a4%af%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%aa%e0%a5%8d%e0%a4%b0%e0%a4%a5%e0%a4%ae%e0%a4%83/", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/tANDyam/ChAndogyopaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/mundakopanishat-content/%e0%a4%ae%e0%a5%81%e0%a4%a3%e0%a5%8d%e0%a4%a1%e0%a4%95%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%aa%e0%a5%8d%e0%a4%b0%e0%a4%a5%e0%a4%ae%e0%a4%ae%e0%a5%81%e0%a4%a3%e0%a5%8d/", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/paippalAdam/muNDakopaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/mundakopanishat-content/%e0%a4%ae%e0%a5%81%e0%a4%a3%e0%a5%8d%e0%a4%a1%e0%a4%95%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%aa%e0%a5%8d%e0%a4%b0%e0%a4%a5%e0%a4%ae%e0%a4%ae%e0%a5%81%e0%a4%a3%e0%a5%8d/", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/prashnopaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/kena-upamishat-content/केनोपनिषत्/", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/jaiminIyam/brAhmaNam/jaiminiya-upaniShad-brAhmaNam/04/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/brihadaaranyaka-upanishat-content/%e0%a4%ac%e0%a5%83%e0%a4%b9%e0%a4%a6%e0%a4%be%e0%a4%b0%e0%a4%a3%e0%a5%8d%e0%a4%af%e0%a4%95%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%85%e0%a4%b7%e0%a5%8d%e0%a4%9f-2/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/bRhadAraNyakopaniShat/rangarAmAnujaH")
  library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/bRhadAraNyakopaniShat/rangarAmAnujaH", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)

  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/subalopanishat-content/सुबालोपनिषत्-षष्ठः-खण्डः/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/subAlopaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/upanishads/subalopanishat-content/सुबालोपनिषत्-खण्डः/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/subAlopaniShat/rangarAmAnujaH/02.md")
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/upanishads/subalopanishat-content/सुबालोपनिषत्-प्रथमः-खण्ड/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/subAlopaniShat/rangarAmAnujaH/01.md")
  
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/aitereyopanishat-content/%e0%a4%90%e0%a4%a4%e0%a4%b0%e0%a5%87%e0%a4%af%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d/", "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/shAkalam/aitareya-brAhmaNam/upaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/kaushitaki-upanishat-content/प्रथमोऽध्यायः/", "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/kauShItakam/kauShitaki-shAnkhAyana-brAhmaNam/upaniShat/rangarAmAnujaH")
  # library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/kauShItakam/kauShitaki-shAnkhAyana-brAhmaNam/upaniShat/rangarAmAnujaH", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)


  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/taittireeya-upanishat-content/%e0%a4%a4%e0%a5%88%e0%a4%a4%e0%a5%8d%e0%a4%a4%e0%a4%bf%e0%a4%b0%e0%a5%80%e0%a4%af%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%b6%e0%a4%bf%e0%a4%95%e0%a5%8d%e0%a4%b7%e0%a4%be/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/AraNyakam/sarva-prastutiH/05_upaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/svetasvataropanishat-content/श्वेताश्वतरोपनिषत्/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/shvetAshvataropaniShat/rangarAmAnujaH")  
  library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/shvetAshvataropaniShat/rangarAmAnujaH", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)
  pass


def shriibhaashya():
  meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasya-upanyasa/श्रीभाष्योपन्यासः-adhyaya-01/", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shrI-sampradAyaH/rAmAnujaH/mahAchArya-upanyAsaH")

def misc():
  meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/rahasyatraya-kaarikaavazhi/rahasyatraya-kaarikaavazhi/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/venkaTanAthaH/rahasya-traya-sAraH/kArikAvalI.md")

  meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/adyatmacintaa/अध्यात्मचिन्ता/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/sundara-jAmAtR-adhyAtma-chintA.md")

  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/astasloki-content/astasloki/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/parAshra-bhaTTa-aShTashlokI.md")


if __name__ == '__main__':
  pass
  # upanishat()
  shriibhaashya()
  # misc()