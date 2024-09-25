import logging
import os.path, regex

from curation_utils.file_helper import get_storage_name
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.scraping.misc_sites import meghamaalaa
from indic_transliteration import sanscript, aksharamukha_helper


def upanishat():
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/other-titles/naayamatmaa-bhasyam/नायमात्मा-भाष्यम्/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/AraNyakam/kaThopaniShat/varadAchAryaH.md")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/chandogya-upanishat-content/%E0%A4%9B%E0%A4%BE%E0%A4%A8%E0%A5%8D%E0%A4%A6%E0%A5%8B%E0%A4%97%E0%A5%8D%E0%A4%AF%E0%A5%8B%E0%A4%AA%E0%A4%A8%E0%A4%BF%E0%A4%B7%E0%A4%A4%E0%A5%8D-%E0%A4%AA%E0%A5%8D%E0%A4%B0%E0%A4%A5%E0%A4%AE%E0%A4%83/", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/tANDyam/ChAndogyopaniShat/rangarAmAnujaH/")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/katopanishat-content/%e0%a4%95%e0%a4%a0%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%aa%e0%a5%8d%e0%a4%b0%e0%a4%a5%e0%a4%ae%e0%a4%be-%e0%a4%b5%e0%a4%b2%e0%a5%8d%e0%a4%b2%e0%a5%80/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/AraNyakam/kaThopaniShat/rangarAmAnujaH")
  
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/maandookyapanishat-content/%e0%a4%ae%e0%a4%be%e0%a4%a3%e0%a5%8d%e0%a4%a1%e0%a5%82%e0%a4%95%e0%a5%8d%e0%a4%af%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d%e0%a4%95%e0%a4%be%e0%a4%b0%e0%a4%bf%e0%a4%95%e0%a4%be/", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/mANDukyopaniShat/rAmAnuja-sampradAyaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/chandogya-upanishat-content/छान्दोग्योपनिषत्-प्रथमः/", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/tANDyam/ChAndogyopaniShat/rangarAmAnujaH/sasandhiH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/mundakopanishat-content/%e0%a4%ae%e0%a5%81%e0%a4%a3%e0%a5%8d%e0%a4%a1%e0%a4%95%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%aa%e0%a5%8d%e0%a4%b0%e0%a4%a5%e0%a4%ae%e0%a4%ae%e0%a5%81%e0%a4%a3%e0%a5%8d/", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/paippalAdam/muNDakopaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/mundakopanishat-content/%e0%a4%ae%e0%a5%81%e0%a4%a3%e0%a5%8d%e0%a4%a1%e0%a4%95%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%aa%e0%a5%8d%e0%a4%b0%e0%a4%a5%e0%a4%ae%e0%a4%ae%e0%a5%81%e0%a4%a3%e0%a5%8d/", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/prashnopaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/kena-upamishat-content/केनोपनिषत्/", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/jaiminIyam/brAhmaNam/jaiminiya-upaniShad-brAhmaNam/04/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/brihadaaranyaka-upanishat-content/%e0%a4%ac%e0%a5%83%e0%a4%b9%e0%a4%a6%e0%a4%be%e0%a4%b0%e0%a4%a3%e0%a5%8d%e0%a4%af%e0%a4%95%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%85%e0%a4%b7%e0%a5%8d%e0%a4%9f-2/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/bRhadAraNyakopaniShat/rangarAmAnujaH")
  # library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/bRhadAraNyakopaniShat/rangarAmAnujaH", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)

  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/subalopanishat-content/सुबालोपनिषत्-षष्ठः-खण्डः/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/subAlopaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/upanishads/subalopanishat-content/सुबालोपनिषत्-खण्डः/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/subAlopaniShat/rangarAmAnujaH/02.md")
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/upanishads/subalopanishat-content/सुबालोपनिषत्-प्रथमः-खण्ड/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/subAlopaniShat/rangarAmAnujaH/01.md")
  
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/aitereyopanishat-content/%e0%a4%90%e0%a4%a4%e0%a4%b0%e0%a5%87%e0%a4%af%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d/", "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/shAkalam/aitareya-brAhmaNam/upaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/kaushitaki-upanishat-content/प्रथमोऽध्यायः/", "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/kauShItakam/kauShitaki-shAnkhAyana-brAhmaNam/upaniShat/rangarAmAnujaH")
  # library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/kauShItakam/kauShitaki-shAnkhAyana-brAhmaNam/upaniShat/rangarAmAnujaH", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)


  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/taittireeya-upanishat-content/%e0%a4%a4%e0%a5%88%e0%a4%a4%e0%a5%8d%e0%a4%a4%e0%a4%bf%e0%a4%b0%e0%a5%80%e0%a4%af%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%b6%e0%a4%bf%e0%a4%95%e0%a5%8d%e0%a4%b7%e0%a4%be/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/AraNyakam/sarva-prastutiH/05_upaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/svetasvataropanishat-content/श्वेताश्वतरोपनिषत्/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/shvetAshvataropaniShat/rangarAmAnujaH")  
  # library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/shvetAshvataropaniShat/rangarAmAnujaH", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)
  pass


def shriibhaashya():
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasya-upanyasa/श्रीभाष्योपन्यासः-adhyaya-01/", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnuja-sampradAyaH/rAmAnujaH/mahAchArya-upanyAsaH")
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/other-titles/vachasudha-vicharaha/%e0%a4%b5%e0%a4%9a%e0%a4%b8%e0%a5%8d%e0%a4%b8%e0%a5%81%e0%a4%a7%e0%a4%be%e0%a4%b5%e0%a4%bf%e0%a4%9a%e0%a4%be%e0%a4%b0%e0%a4%83/", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnuja-sampradAyaH/rAmAnujaH/shrI-bhAShyam/vachas-sudhA-vichAraH.md")

  adhyaaya_map = {
    (1,1): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-1-sribhasyam-content/pada-1-adhyaya-1-sribhasyam-content/sribhasya-01-01-01/",
    (1,2): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-1-sribhasyam-content/pada-2-adhyaya-1-sribhasyam-content/01-02-12-%E0%A4%B8%E0%A4%B0%E0%A5%8D%E0%A4%B5%E0%A4%A4%E0%A5%8D%E0%A4%B0%E0%A4%AA%E0%A5%8D%E0%A4%B0%E0%A4%B8%E0%A4%BF%E0%A4%A6%E0%A5%8D%E0%A4%A7%E0%A5%8D%E0%A4%AF%E0%A4%A7%E0%A4%BF%E0%A4%95%E0%A4%B0/",
    (1,3): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-1-sribhasyam-content/pada-3-adhyaya-1-sribhasyam-content/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-01-03-18-%E0%A4%A6%E0%A5%8D%E0%A4%AF%E0%A5%81%E0%A4%AD%E0%A5%8D%E0%A4%B5%E0%A4%BE%E0%A4%A6%E0%A5%8D/",
    (1,4): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-1-sribhasyam-content/pada-4-adhyaya-1-sribhasyam-content/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-01-04-28-%E0%A4%86%E0%A4%A8%E0%A5%81%E0%A4%AE%E0%A4%BE%E0%A4%A8%E0%A4%BF%E0%A4%95%E0%A4%BE%E0%A4%A7/",
    (2,1): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-2-sribhasyam-content/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-02-01-01-%E0%A4%B8%E0%A5%8D%E0%A4%AE%E0%A5%83%E0%A4%A4%E0%A5%8D%E0%A4%AF%E0%A4%A7%E0%A4%BF%E0%A4%95/",
    (2,2): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-2-sribhasyam-content/pada-2-adhyaya-2-sribhasyam-content/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-02-02-01-%E0%A4%B0%E0%A4%9A%E0%A4%A8%E0%A4%BE%E0%A4%A8%E0%A5%81%E0%A4%AA%E0%A4%AA%E0%A4%A4%E0%A5%8D/",
    (2,3): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-2-sribhasyam-content/pada-3-adhyaya-2-sribhasyam-content/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-02-03-01-%E0%A4%B5%E0%A4%BF%E0%A4%AF%E0%A4%A6%E0%A4%A7%E0%A4%BF%E0%A4%95%E0%A4%B0%E0%A4%A3%E0%A4%AE/",
    (2,4): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-2-sribhasyam-content/pada-4-adhyaya-2-sribhasyam-content/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-02-04-01-%E0%A4%AA%E0%A5%8D%E0%A4%B0%E0%A4%BE%E0%A4%A3%E0%A5%8B%E0%A4%A4%E0%A5%8D%E0%A4%AA%E0%A4%A4/",
    (3,1): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-3-sribhasyam-content/pada-1-adhyaya-3-sribhasyam-content/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-03-01-01-%E0%A4%A4%E0%A4%A6%E0%A4%A8%E0%A5%8D%E0%A4%A4%E0%A4%B0%E0%A4%AA%E0%A5%8D%E0%A4%B0%E0%A4%A4/",
    (3,2): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-3-sribhasyam-content/pada-2-adhyaya-3-sribhasyam-content/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-03-02-01-%E0%A4%B8%E0%A4%A8%E0%A5%8D%E0%A4%A7%E0%A5%8D%E0%A4%AF%E0%A4%BE%E0%A4%A7%E0%A4%BF%E0%A4%95/",
    (3,3): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-3-sribhasyam-content/pada-3-adhyaya-3-sribhasyam-content/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-03-03-01-%E0%A4%B8%E0%A4%B0%E0%A5%8D%E0%A4%B5%E0%A4%B5%E0%A5%87%E0%A4%A6%E0%A4%BE%E0%A4%A8%E0%A5%8D/",
    (3,4): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-3-sribhasyam-content/pada-4-adhyaya-3-sribhasyam-content/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-03-04-01-%E0%A4%AA%E0%A5%81%E0%A4%B0%E0%A5%81%E0%A4%B7%E0%A4%BE%E0%A4%B0%E0%A5%8D%E0%A4%A5%E0%A4%BE/",
    (4,1): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-4/pada-1-adhyaya-4/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-04-01-11-%E0%A4%86%E0%A4%B5%E0%A5%83%E0%A4%A4%E0%A5%8D%E0%A4%A4%E0%A5%8D%E0%A4%AF%E0%A4%A7%E0%A4%BF/",
    (4,2): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-4/pada-2-adhyaya-4/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-04-02-01-%E0%A4%B5%E0%A4%BE%E0%A4%97%E0%A4%A7%E0%A4%BF%E0%A4%95%E0%A4%B0%E0%A4%A3%E0%A4%AE%E0%A5%8D/",
    (4,3): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-4/pada-3-adhyaya-4/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-04-03-01-%E0%A4%85%E0%A4%B0%E0%A5%8D%E0%A4%9A%E0%A4%BF%E0%A4%B0%E0%A4%BE%E0%A4%A6%E0%A5%8D%E0%A4%AF/",
    (4,4): "https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasyam-content/adhyaya-4/pada-4-adhyaya-4/%E0%A4%B6%E0%A5%8D%E0%A4%B0%E0%A5%80%E0%A4%AD%E0%A4%BE%E0%A4%B7%E0%A5%8D%E0%A4%AF%E0%A4%AE%E0%A5%8D-04-04-01-%E0%A4%B8%E0%A4%AE%E0%A5%8D%E0%A4%AA%E0%A4%A6%E0%A5%8D%E0%A4%AF%E0%A4%BE%E0%A4%B5%E0%A4%BF/",
  }
  for adhyaaya in range(1,5):
    for paada in range(1,5):
      meghamaalaa.dump_series(adhyaaya_map[(adhyaaya, paada)], f"/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnuja-sampradAyaH/rAmAnujaH/shrI-bhAShyam/mUlam/ma/{adhyaaya}/{paada}/", filename_from_title=lambda x: regex.match(".+?-(\d\d[A-Z]? .+$)", x).group(1))
  library.fix_index_files("/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnuja-sampradAyaH/rAmAnujaH/shrI-bhAShyam/mUlam/")
  pass


def misc():
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/stotras/jitante-shat/%E0%A4%9C%E0%A4%BF%E0%A4%A4%E0%A4%A4%E0%A4%A8%E0%A5%8D%E0%A4%A4%E0%A4%BE-%E0%A4%B8%E0%A5%8D%E0%A4%A4%E0%A5%8B%E0%A4%A4%E0%A5%8D%E0%A4%B0%E0%A4%BE%E0%A4%A3%E0%A4%BF-%E0%A4%B7%E0%A4%9F%E0%A5%8D/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/jitan-te-stotram/_index.md")

  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/other-titles/siddantha-siddanjanam-content/%E0%A4%B8%E0%A4%BF%E0%A4%A6%E0%A5%8D%E0%A4%A7%E0%A4%BE%E0%A4%A8%E0%A5%8D%E0%A4%A4%E0%A4%B8%E0%A4%BF%E0%A4%A6%E0%A5%8D%E0%A4%A7%E0%A4%BE%E0%A4%9E%E0%A5%8D%E0%A4%9C%E0%A4%A8%E0%A4%AE%E0%A5%8D-3/", f"/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/anantAryaH/siddhAnta-siddhAnjanam")
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/other-titles/siddadharma-vijayamangala-dipika/%E0%A4%B8%E0%A4%BF%E0%A4%A6%E0%A5%8D%E0%A4%A7%E0%A4%A7%E0%A4%B0%E0%A5%8D%E0%A4%AE%E0%A4%B5%E0%A4%BF%E0%A4%9C%E0%A4%AF%E0%A4%AE%E0%A4%99%E0%A5%8D%E0%A4%97%E0%A4%B2%E0%A4%A6%E0%A5%80%E0%A4%AA%E0%A4%BF/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/vAdhUla-shrInivAsa-siddha-dharma-vijaya-mangala-dIpikA.md")
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/other-titles/mukthipada-sakthivada/%E0%A4%AE%E0%A5%81%E0%A4%95%E0%A5%8D%E0%A4%A4%E0%A4%BF%E0%A4%AA%E0%A4%A6%E0%A4%B6%E0%A4%95%E0%A5%8D%E0%A4%A4%E0%A4%BF%E0%A4%B5%E0%A4%BE%E0%A4%A6%E0%A4%83/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/vAdAH/venkaTa-laxmaNa-yati-mukti-pada-shakti-vAdaH.md")

  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/other-titles/dashamatha-darsini/%E0%AE%A4%E0%AE%B6%E0%AE%AE%E0%AE%A4-%E0%AE%A4%E0%AE%B0%E0%AF%8D%E0%AE%B6%E0%AE%BF%E0%AE%A8%E0%AF%80/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/dasha-mata-darshinI.md", source_script=sanscript.TAMIL)

  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/other-titles/boogola-kagola-nirnayam/%E0%AE%AA%E0%AF%82%E0%AE%95%E0%AF%8B%E0%AE%B3%E0%AE%95%E0%AE%95%E0%AF%8B%E0%AE%B3-%E0%AE%B5%E0%AE%BF%E0%AE%B7%E0%AE%AF%E0%AE%AE%E0%AF%8D/", "/home/vvasuki/gitland/vishvAsa/jyotiSham/content/astrophysics/history/paurANika-darshanam/bhUgola-khagola-nirNayam.md", source_script=sanscript.TAMIL)

  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/other-titles/vedanta-kaarikaavazhi/vedanta-kaarikaavazhi/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/parichaya-sanxepAH/vedAnta-kArikAvalI/mUlam.md")
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/rahasyatraya-kaarikaavazhi/rahasyatraya-kaarikaavazhi/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/venkaTanAthaH/rahasya-traya-sAraH/kArikAvalI.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/adyatmacintaa/अध्यात्मचिन्ता/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/sundara-jAmAtR-adhyAtma-chintA.md")

  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/sarana-sabdaartha-vicharaha/शरणशब्दार्थविचारः/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/sharaNa-shabdArtha-vichAraH.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/prapatti-anupayatva-vicharaha/प्रपत्त्यनुपायत्व-विचार", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/prapatty-anupAyatva-vichAraH.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/mukthipada-sakthivada/मुक्तिपदशक्तिवादः/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/mukti-pada-shakti-vAdaH.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/brahma-pada-sakti-vadaha/ब्रह्मपदशक्तिवादः/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/brahma-pada-shakti-vAdaH.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/siddantha-toolika/सिद्धान्ततूलिका/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/siddhAnta-tUlikA.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/kaivalya-satadooshani/कैवल्यशतदूषणी/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/kaivaly-shata-dUShaNI.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/saaaraniskarsa-tippani/सारनिष्कर्षटिप्पणी/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/sAra-niShkarSha-TippanI.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/naayamatmaa-bhasyam/नायमात्मा-भाष्यम्/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/nAyam-AtmA-bhAShyam.md")

  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/astasloki-content/astasloki/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/parAshra-bhaTTa-aShTashlokI.md")

  meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/vedartha-sangraha-content/%E0%A4%B5%E0%A5%87%E0%A4%A6%E0%A4%BE%E0%A4%B0%E0%A5%8D%E0%A4%A5%E0%A4%B8%E0%A4%99%E0%A5%8D%E0%A4%97%E0%A5%8D%E0%A4%B0%E0%A4%B9-part-i/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/rAmAnujaH/vedArtha-sangrahaH/mUlam/")
  pass


def kaavyam():
  pass
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/stotras/parasara-bhattar/sri-gunaratnakosaha/श्रीगुणरत्नकोशः-व्याख्-2/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/mahAbhAratam/goraxapura-pAThaH/hindy-anuvAdaH/13_anushAsanaparva/01_dAna-dharma-parva/149_viShNu-sahasra-nAma-stotram/TIkA/parAshara-bhaTTaH/shrI-vatsa-vIra-rAghavaH", start_index=1)
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/stotras/kooratazhwan/panchastavam/वरदराजस्तवव्याख्यानम्/", "/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/shrIvaiShNava-kRtam/kUresha-shrIvatsAnka-mishraH/TIkA/rAmAnujaH", start_index=1)
  meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/stotras/yamunacharyar/stotraratnam/%E0%A4%B5%E0%A5%87%E0%A4%A6%E0%A4%BE%E0%A4%A8%E0%A5%8D%E0%A4%A4%E0%A4%BE%E0%A4%9A%E0%A4%BE%E0%A4%B0%E0%A5%8D%E0%A4%AF%E0%A4%B8%E0%A5%8D%E0%A4%AF-%E0%A4%B8%E0%A5%8D%E0%A4%A4%E0%A5%8B%E0%A4%A4%E0%A5%8D/", "/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/shrIvaiShNava-kRtam/yAmunaH/stotra-ratnam/venkaTanAth-TikA.md")


def puraaNam():
  pass
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/divya-desha-vaibhavam/sriranga-mahatmyam-content/श्रीरङ्गमाहात्म्यम्-part-01/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/garuDa-purANam/shrIranga-mAhAtmyam", start_index=4, filename_from_title=False)
  # 
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/divya-desha-vaibhavam/sri-yadavadri-mahatmyam-content/%e0%a4%af%e0%a4%be%e0%a4%a6%e0%a4%b5%e0%a4%be%e0%a4%a6%e0%a5%8d%e0%a4%b0%e0%a4%bf%e0%a4%a6%e0%a4%b0%e0%a5%8d%e0%a4%b6%e0%a4%a8%e0%a4%ae%e0%a5%8d-part-1/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/sthala-purANam/yAdavAdri-darshanam", filename_from_title=False)
  # 
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/divya-desha-vaibhavam/sri-kurukkoor-mahatmyam/नवतिरुप्पति-माहात्मियम्/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/sthala-purANam/kurukkUr-nava-tirupadi-nidhi-vana-xetra-mAhAtmyam", start_index=2, filename_from_title=False)
  # 
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/divya-desha-vaibhavam/sri-bootapuri-mahatmyam/श्रीमद्-भूतपुरीमाहात्म्/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/sthala-purANam/bhUta-purI-mAhAtmyam", start_index=2, filename_from_title=False)
  # 
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/divya-desha-vaibhavam/sri-brindaranya-mahatmyam/श्रीबृन्दारण्यक्षेत्रम/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/sthala-purANam/bRndAraNya-xetra-mAhAtmyam", start_index=2, filename_from_title=False)
  # 
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/divya-desha-vaibhavam/srimad-ahobila-mahatmyam/श्रीमदहोबिलमाहात्म्यं-part-1/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/sthala-purANam/ahobila-mAhAtmyam", start_index=3, filename_from_title=False)

  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/puranas/vishnu-purana-content/amsa-01/श्रीविष्णुपुराणम्-amsa-01-ady-01/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/viShNu-purANam/viShNuchitta-TIkA/01/", start_index=None, filename_from_title=lambda x: regex.match(".+(\d\d)", x).group(1))
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/puranas/vishnu-purana-content/amsa-02/amsa-02-ady-01/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/viShNu-purANam/viShNuchitta-TIkA/02/", start_index=None, filename_from_title=lambda x: regex.match(".+(\d\d)$", x).group(1))
  meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/puranas/vishnu-purana-content/amsa-03/श्रीविष्णुपुराणम्-amsa-03-ady-01-2/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/viShNu-purANam/viShNuchitta-TIkA/03/", start_index=None, filename_from_title=lambda x: regex.match(".+(\d\d)", x).group(1))
  meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/puranas/vishnu-purana-content/amsa-04/amsa-04-ady-01-10/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/viShNu-purANam/viShNuchitta-TIkA/04/", start_index=None, filename_from_title=lambda x: regex.match(".+(\d\d)", x).group(1))
  meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/puranas/vishnu-purana-content/amsa-05/श्रीविष्णुपुराणम्-amsa-05-ady-01-10/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/viShNu-purANam/viShNuchitta-TIkA/05/", start_index=None, filename_from_title=lambda x: regex.match(".+(\d\d)", x).group(1))


def raamaayaNam():
  pass
  def sarga_detector(x):
    sarga_match = regex.match("\D*(\d\d+) *S.+rga", x)
    if sarga_match is not None:
      return sarga_match.group(1)
    else:
      logging.warning(f"No sarga detected in {x}")
      return x
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/srimad-ramayanam/srimad-valmiki-ramayanam/srimad-ramayanam-content/srimad-ramayanam-baala-kaanda-sarga-01/", "/home/vvasuki/gitland/vishvAsa/rAmAyaNam/content/vAlmIkIyam/drAviDa-pAThaH/govindarAja-bhUShaNam/1_bAlakANDam", start_index=1, filename_from_title=sarga_detector)

  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/srimad-ramayanam/srimad-valmiki-ramayanam/srimad-valmiki-ramayan-ayodhya-kaanda/01-sarga-अयोध्याकाण्डम्/", "/home/vvasuki/gitland/vishvAsa/rAmAyaNam/content/vAlmIkIyam/drAviDa-pAThaH/govindarAja-bhUShaNam/2_ayodhyAkANDam", start_index=66, filename_from_title=sarga_detector)

  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/srimad-ramayanam/srimad-valmiki-ramayanam/srimad-valmiki-ramayan-aranya-kaanda/01-sarga-%E0%A4%85%E0%A4%AF%E0%A5%8B%E0%A4%A7%E0%A5%8D%E0%A4%AF%E0%A4%BE%E0%A4%95%E0%A4%BE%E0%A4%A3%E0%A5%8D%E0%A4%A1%E0%A4%AE%E0%A5%8D-2/", "/home/vvasuki/gitland/vishvAsa/rAmAyaNam/content/vAlmIkIyam/drAviDa-pAThaH/govindarAja-bhUShaNam/3_araNyakANDam", start_index=1, filename_from_title=sarga_detector)

  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/srimad-ramayanam/srimad-valmiki-ramayanam/srimad-valmiki-ramayan-kishkinda-kanda/01-sarga-%E0%A4%95%E0%A4%BF%E0%A4%B7%E0%A5%8D%E0%A4%95%E0%A4%BF%E0%A4%A8%E0%A5%8D%E0%A4%A7%E0%A4%BE%E0%A4%95%E0%A4%BE%E0%A4%A3%E0%A5%8D%E0%A4%A1%E0%A4%83/", "/home/vvasuki/gitland/vishvAsa/rAmAyaNam/content/vAlmIkIyam/drAviDa-pAThaH/govindarAja-bhUShaNam/4_kiShkindhAkANDam", start_index=1, filename_from_title=sarga_detector)

  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/srimad-ramayanam/srimad-valmiki-ramayanam/srimad-ramayan-sundara-kaanda/01-sarga-%E0%A4%B8%E0%A5%81%E0%A4%A8%E0%A5%8D%E0%A4%A6%E0%A4%B0%E0%A4%95%E0%A4%BE%E0%A4%A3%E0%A5%8D%E0%A4%A1%E0%A4%83/", "/home/vvasuki/gitland/vishvAsa/rAmAyaNam/content/vAlmIkIyam/drAviDa-pAThaH/govindarAja-bhUShaNam/5_sundarakANDam", start_index=1, filename_from_title=sarga_detector)

  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/srimad-ramayanam/srimad-valmiki-ramayanam/srimad-valmiki-ramayan-yuddha-kaanda/01-sarga-%E0%A4%AF%E0%A5%81%E0%A4%A6%E0%A5%8D%E0%A4%A7%E0%A4%95%E0%A4%BE%E0%A4%A3%E0%A5%8D%E0%A4%A1%E0%A4%83/", "/home/vvasuki/gitland/vishvAsa/rAmAyaNam/content/vAlmIkIyam/drAviDa-pAThaH/govindarAja-bhUShaNam/6_yuddhakANDam", start_index=91, filename_from_title=sarga_detector)

  meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/srimad-ramayanam/srimad-valmiki-ramayanam/srimad-valmiki-ramayan-uttara-kaanda/01-sarga-%E0%A4%89%E0%A4%A4%E0%A5%8D%E0%A4%A4%E0%A4%B0%E0%A4%95%E0%A4%BE%E0%A4%A3%E0%A5%8D%E0%A4%A1%E0%A4%83/", "/home/vvasuki/gitland/vishvAsa/rAmAyaNam/content/vAlmIkIyam/drAviDa-pAThaH/govindarAja-bhUShaNam/7_uttarakANDam", start_index=9, end_index=9, filename_from_title=sarga_detector)


def rahasya():
  base_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/rahasya-granthaH/"
  base_url = "https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/"
  def dump_series(x, start_index=None):
    name = [x for x in x.split("/") if x != "" ][-1]
    meghamaalaa.dump_series(base_url + x, os.path.join(base_dir, f"{get_storage_name(text=name, max_length=20, source_script=sanscript.TAMIL)}") , start_index=start_index, filename_from_title=filename_from_title, source_script=sanscript.TAMIL)
  
  def dump_single(x):
    name = [x for x in x.split("/") if x != "" ][-1]
    meghamaalaa.dump_text(base_url + x, os.path.join(base_dir, f"{get_storage_name(text=name, max_length=20, source_script=sanscript.TAMIL)}.md"), source_script=sanscript.TAMIL)

  dump_series(x="paranda-rahasyam/அவதாரிகை-ஸம்பூர்ணம்/", start_index=4)


def bhagavad_vishayam():
  base_dir = "/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/shrIvaiShNava/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/"
  base_url = "https://srivaishnavan.com/publications/meghamala/bhagavad-visayam/"
  # meghamaalaa.dump_series(base_url + "6000-padi", os.path.join(base_dir, "6k") , start_index=None, source_script=sanscript.TAMIL_SUB, overwrite=True)
  # meghamaalaa.dump_series(base_url + "9000-padi", os.path.join(base_dir, "9k") , start_index=None, source_script=sanscript.TAMIL_SUB, overwrite=True)
  # meghamaalaa.dump_series(base_url + "12000-36000-padi/centum-01/01-01-12000-36000-padi/", os.path.join(base_dir, "12k/01") , start_index=None, source_script=sanscript.TAMIL_SUB, overwrite=True)
  # meghamaalaa.dump_series(base_url + "12000-36000-padi/centum-02/02-01-12000-36000-padi/", os.path.join(base_dir, "12k/02") , start_index=None, source_script=sanscript.TAMIL_SUB, overwrite=True)
  # meghamaalaa.dump_series(base_url + "12000-36000-padi/centum-03/03-01-12000-36000-padi/", os.path.join(base_dir, "12k/03") , start_index=None, source_script=sanscript.TAMIL_SUB, overwrite=True)
  # meghamaalaa.dump_series(base_url + "12000-36000-padi/centum-04/04-01-12000-36000-padi/", os.path.join(base_dir, "12k/04") , start_index=None, source_script=sanscript.TAMIL_SUB, overwrite=True)

  library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda x, y: aksharamukha_helper.manipravaalify(x), dry_run=False)
  # library.apply_function(dir_path=base_dir, fn=metadata_helper.set_filename_from_title, dry_run=False)


def fix_text(dir_path):
  pass
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: meghamaalaa.fix_text(x, source_script=sanscript.DEVANAGARI), dry_run=False, silent_iteration=False)

if __name__ == '__main__':
  pass
  # raamaayaNam()
  # bhagavad_vishayam()
  kaavyam()
  # upanishat()
  # shriibhaashya()
  # fix_text("/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnuja-sampradAyaH/rAmAnujaH/shrI-bhAShyam/mUlam/ma")
  # misc()
  # puraaNam()
  # rahasya()