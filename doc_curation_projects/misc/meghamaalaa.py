import logging
import os.path

import regex
from doc_curation.md.library import metadata_helper
from curation_utils.file_helper import get_storage_name

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript, aksharamukha_helper

from doc_curation.scraping.misc_sites import meghamaalaa


def upanishat():
  meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/other-titles/naayamatmaa-bhasyam/नायमात्मा-भाष्यम्/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/AraNyakam/kaThopaniShat/varadAchAryaH.md")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/katopanishat-content/%e0%a4%95%e0%a4%a0%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%aa%e0%a5%8d%e0%a4%b0%e0%a4%a5%e0%a4%ae%e0%a4%be-%e0%a4%b5%e0%a4%b2%e0%a5%8d%e0%a4%b2%e0%a5%80/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/AraNyakam/kaThopaniShat/rangarAmAnujaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/maandookyapanishat-content/%e0%a4%ae%e0%a4%be%e0%a4%a3%e0%a5%8d%e0%a4%a1%e0%a5%82%e0%a4%95%e0%a5%8d%e0%a4%af%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d%e0%a4%95%e0%a4%be%e0%a4%b0%e0%a4%bf%e0%a4%95%e0%a4%be/", "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/mANDukyopaniShat/shrI-sampradAyaH")
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/chandogya-upanishat-content/%e0%a4%9b%e0%a4%be%e0%a4%a8%e0%a5%8d%e0%a4%a6%e0%a5%8b%e0%a4%97%e0%a5%8d%e0%a4%af%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%aa%e0%a5%8d%e0%a4%b0%e0%a4%a5%e0%a4%ae%e0%a4%83/", "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/tANDyam/ChAndogyopaniShat/rangarAmAnujaH")
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
  library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/shvetAshvataropaniShat/rangarAmAnujaH", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)
  pass


def shriibhaashya():
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/brahma-sutras/sribhasya-upanyasa/श्रीभाष्योपन्यासः-adhyaya-01/", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shrI-sampradAyaH/rAmAnujaH/mahAchArya-upanyAsaH")
  meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/other-titles/vachasudha-vicharaha/%e0%a4%b5%e0%a4%9a%e0%a4%b8%e0%a5%8d%e0%a4%b8%e0%a5%81%e0%a4%a7%e0%a4%be%e0%a4%b5%e0%a4%bf%e0%a4%9a%e0%a4%be%e0%a4%b0%e0%a4%83/", "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shrI-sampradAyaH/rAmAnujaH/shrI-bhAShyam/vachas-sudhA-vichAraH.md")
  pass


def misc():
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/other-titles/vedanta-kaarikaavazhi/vedanta-kaarikaavazhi/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/parichaya-sanxepAH/vedAnta-kArikAvalI/mUlam.md")
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/rahasyatraya-kaarikaavazhi/rahasyatraya-kaarikaavazhi/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/venkaTanAthaH/rahasya-traya-sAraH/kArikAvalI.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/adyatmacintaa/अध्यात्मचिन्ता/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/sundara-jAmAtR-adhyAtma-chintA.md")

  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/sarana-sabdaartha-vicharaha/शरणशब्दार्थविचारः/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/sharaNa-shabdArtha-vichAraH.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/prapatti-anupayatva-vicharaha/प्रपत्त्यनुपायत्व-विचार", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/prapatty-anupAyatva-vichAraH.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/mukthipada-sakthivada/मुक्तिपदशक्तिवादः/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/mukti-pada-shakti-vAdaH.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/brahma-pada-sakti-vadaha/ब्रह्मपदशक्तिवादः/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/brahma-pada-shakti-vAdaH.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/siddantha-toolika/सिद्धान्ततूलिका/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/siddhAnta-tUlikA.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/kaivalya-satadooshani/कैवल्यशतदूषणी/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/kaivaly-shata-dUShaNI.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/saaaraniskarsa-tippani/सारनिष्कर्षटिप्पणी/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/sAra-niShkarSha-TippanI.md")
  # 
  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/other-titles/naayamatmaa-bhasyam/नायमात्मा-भाष्यम्/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/nAyam-AtmA-bhAShyam.md")

  # meghamaalaa.dump_text("https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/astasloki-content/astasloki/", "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/parAshra-bhaTTa-aShTashlokI.md")

  pass


def kaavyam():
  pass
  # meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/stotras/parasara-bhattar/sri-gunaratnakosaha/श्रीगुणरत्नकोशः-व्याख्-2/", "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/mahAbhAratam/goraxapura-pAThaH/hindy-anuvAdaH/13_anushAsanaparva/01_dAna-dharma-parva/149_viShNu-sahasra-nAma-stotram/TIkA/parAshara-bhaTTaH/shrI-vatsa-vIra-rAghavaH", start_index=1, filename_from_title=True)


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

def rahasya():
  base_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/rahasya-granthaH/"
  base_url = "https://srivaishnavan.com/publications/meghamala/rahasysa-granthas/"
  def dump_series(x, start_index=None, filename_from_title=True):
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


if __name__ == '__main__':
  pass
  bhagavad_vishayam()
  # upanishat()
  # shriibhaashya()
  # misc()
  # puraaNam()
  # rahasya()