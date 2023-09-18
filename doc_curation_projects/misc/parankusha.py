from doc_curation.md.library import metadata_helper
import logging
import os.path

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

from doc_curation.scraping.misc_sites import parankusha


BS_BASE = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shrI-sampradAyaH/rAmAnujaH/shrI-bhAShyam"

def deshika_rts(browser):
  base_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/venkaTanAthaH/rahasya-traya-sAraH/"
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "रहस्यत्रयसारः", "expand:रहस्यत्रयसारः","श्रीगुरुपरंपरासारः"], outdir=os.path.join(outdir, "mUlam"), sequence_start=0)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "42ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "सार-बोधिनी", "expand:सार-बोधिनी","श्रीगुरुपरंपरासारः"], outdir=os.path.join(base_dir, "sAra-bodhinI"), sequence_start=0)
  # 
  library.apply_function(fn=MdFile.transform, dir_path=os.path.join(base_dir, "sAra-bodhinI"), content_transformer=lambda c, m: content_processor.transliterate(c, source_script=sanscript.TAMIL), dry_run=False)


def brahmasuutra(browser, author, text_id, sub_path):
  base_dir = os.path.join(BS_BASE, sub_path)
  if author in ["कपिस्थलं देशिकाचार्याः"]:
    base_dir = base_dir.replace("content", "static")
  for x in range(1, 5):
    for y in range(1, 5):
      os.makedirs(os.path.join(base_dir, str(x), str(y)), exist_ok=True)

  adhyaaya = 1
  # adhyaaya = 2
  # adhyaaya = 3
  # adhyaaya = 4
  
  has_comment = author in ["सेनेश्वराचार्याः", "44ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்"] 
  if adhyaaya == 1:
    if author in ["रामानुजाचार्याः", "अप्पय-दीक्षितः", "सेनेश्वराचार्याः", "कपिस्थलं देशिकाचार्याः", "44ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "श्रीरङ्गरामानुजाचार्याः"]:
      if text_id == "विषयवाक्य-दीपिका":
        parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-1", "expand:Pada-1", "जन्माद्यधिकरणम्"], outdir=os.path.join(base_dir, "1"), has_comment=has_comment, ordinal_start=2)
      else:
        parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-1", "expand:Pada-1", "जिज्ञासाधिकरणम्"], outdir=os.path.join(base_dir, "1"), has_comment=has_comment)
    else:
      parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-1", "expand:Pada-1", "उपोद्घातम्"], outdir=os.path.join(base_dir, "1"), ordinal_start=0, has_comment=has_comment)
  elif adhyaaya == 2:
    parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-2", "expand:Pada-1", "स्मृत्यधिकरणम्"], outdir=os.path.join(base_dir, "2"), has_comment=has_comment)
  elif adhyaaya == 3:
    parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-3", "expand:Pada-1", "तदन्तरप्रतिपत्त्यधिकरणम्"], outdir=os.path.join(base_dir, "3"), has_comment=has_comment)
  elif adhyaaya == 4:
    if author in ["रामानुजाचार्याः", "अप्पय-दीक्षितः", "सेनेश्वराचार्याः", "कपिस्थलं देशिकाचार्याः", "44ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "श्रीरङ्गरामानुजाचार्याः"]:
      parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-4", "expand:Pada-1", "आवृत्त्यधिकरणम्"], outdir=os.path.join(base_dir, "4"), has_comment=has_comment)
    else:
      parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-4", "expand:Pada-1", "उपोद्घातम्"], outdir=os.path.join(base_dir, "4"), has_comment=has_comment)


def shriibhaashyam(browser):
  # brahmasuutra(browser, author="रामानुजाचार्याः", text_id="श्रीभाष्यम्", sub_path="mUlam")
  # brahmasuutra(browser, author="रामानुजाचार्याः", text_id="वेदान्तदीपः", sub_path="vedAnta-dIpaH")
  # brahmasuutra(browser, author="रामानुजाचार्याः", text_id="वेदान्तसारः", sub_path="vedAnta-sAraH")
  # brahmasuutra(browser, author="वेदान्तदेशिकाः", text_id="अधिकरणसारावली", sub_path="venkaTanAthaH/adhikaraNasArAvalI/mUlam")
  # brahmasuutra(browser, author="कुमार-वरदाचार्याः", text_id="चिन्तामणिः", sub_path="adhikaraNasArAvalI/chintAmaNiH")
  # brahmasuutra(browser, author="34ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", text_id="अधिकरणसारावली-पद-योजना", sub_path="adhikaraNasArAvalI/pada-yojanA")
  # brahmasuutra(browser, author="34ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", text_id="अधिकरणसारावली-पद-योजना", sub_path="adhikaraNasArAvalI/pada-yojanA")
  # brahmasuutra(browser, author="अप्पय-दीक्षितः", text_id="नयमयूखमालिका", sub_path="appayya-naya-mayUkha-mAlikA/")
  # brahmasuutra(browser, author="सेनेश्वराचार्याः", text_id="न्याय-कलाप-सङ्ग्रहः", sub_path="seneshvara-nyAya-kalApa-sangrahaH/")
  # brahmasuutra(browser, author="कपिस्थलं देशिकाचार्याः", text_id="अधिकरण-रत्नमाला (सप्रकाशा)", sub_path="adhikaraNa-ratnamAlA/")
  # brahmasuutra(browser, author="44ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", text_id="ब्रह्मसूत्रार्थ-पद्य-मालिका", sub_path="brahma-sUtrArtha-padya-mAlikA/")
  # brahmasuutra(browser, author="श्रीरङ्गरामानुजाचार्याः", text_id="शारीरकशास्त्रार्थ-दीपिका", sub_path="rangarAmAnujaH/shArIrika-shAstrArtha-dIpikA/")
  # brahmasuutra(browser, author="श्रीरङ्गरामानुजाचार्याः", text_id="विषयवाक्य-दीपिका", sub_path="rangarAmAnujaH/viShaya-vAkya-dIpikA/")
  # brahmasuutra(browser, author="श्रीरङ्गरामानुजाचार्याः", text_id="भाव-प्रकाशिका", sub_path="rangarAmAnujaH/bhAva-prakAshikA/")


  library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shrI-sampradAyaH", overwrite=False, dry_run=False)


def raamaanuja_misc(browser):
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "वेदार्थसङ्ग्रहः", "expand:वेदार्थसङ्ग्रहः", "Part-1-30"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shrI-sampradAyaH/rAmAnujaH/vedArtha-sangrahaH/")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "गद्यत्रयम्", "expand:गद्यत्रयम्", "शरणागति गद्यम्"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/gadyam/rAmAnujaH")
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "नित्य-ग्रन्थः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/kriyA/")


def deshika_nyAyasiddhAnjanam():
  base_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shrI-sampradAyaH/venkaTanAthaH/nyAya-siddhANjanam"
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "न्यायसिद्धाञ्जनम्", "expand:न्यायसिद्धाञ्जनम्", "जडद्रव्यपरिच्छेदः", "उपोद्घातः"], outdir=os.path.join(base_dir, "1_jaDa-dravyam"), sequence_start=0)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "न्यायसिद्धाञ्जनम्", "expand:न्यायसिद्धाञ्जनम्", "जीवपरिच्छेदः", "जीवस्य देहव्यतिरेकनिरूपणम्"], outdir=os.path.join(base_dir, "2_jIvaH"), sequence_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "न्यायसिद्धाञ्जनम्", "expand:न्यायसिद्धाञ्जनम्", "ईश्वरपरिच्छेदः", "ईश्वरलक्षणनिरूपणम्"], outdir=os.path.join(base_dir, "3_IshvaraH"), sequence_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "न्यायसिद्धाञ्जनम्", "expand:न्यायसिद्धाञ्जनम्", "नित्यविभूतिपरिच्छेदः", "नित्यविभूतिलक्षणनिरूपणम्"], outdir=os.path.join(base_dir, "4_nitya-vibhUtiH"), sequence_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "न्यायसिद्धाञ्जनम्", "expand:न्यायसिद्धाञ्जनम्", "बुद्धिपरिच्छेदः", "बुद्धिः"], outdir=os.path.join(base_dir, "5_buddhiH"), sequence_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "न्यायसिद्धाञ्जनम्", "expand:न्यायसिद्धाञ्जनम्", "अद्रव्यपरिच्छेदः", "दशानामेव स्फुटपरिगणनीयानाम् अद्रव्याणां निरूपणम्"], outdir=os.path.join(base_dir, "6_adravyam"), sequence_start=1)
  library.fix_index_files(dir_path=base_dir, overwrite=False, dry_run=False)


def deshika_misc(browser):
  pass
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "शतदूषणी", "expand:शतदूषणी", "ब्रह्मशब्दवृत्त्यनुपपत्तिवादः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shrI-sampradAyaH/rAmAnujaH/venkaTanAthaH/shatadUShaNI/", sequence_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "पादुका-सहस्रम्", "expand:पादुका-सहस्रम्", "प्रस्तावपद्धतिः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/pAdukA-sahasram", sequence_start=1, has_comment=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "यादवाभ्युदयम्", "expand:यादवाभ्युदयम्", "सर्गः-1"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/yAdavAbhyudayam", sequence_start=1, has_comment=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "हंस-सन्देशः", "expand:हंस-सन्देशः", "प्रथमाश्वासः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/haMsa-sandeshaH", sequence_start=1, has_comment=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "वैश्वदेव-कारिका", "expand:वैश्वदेव-कारिका", "Adhyaya-1"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/kriyA/venkaTanAthaH/", sequence_start=1, has_comment=False)
  
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीनरकेसरी", "सुभाषितनीवी-व्याख्या-नरकेसरीयम्", "expand:सुभाषितनीवी-व्याख्या-नरकेसरीयम्", "अनिपुणपद्धतिः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/subhAShita-nIvI/narakesariH", sequence_start=1, has_comment=True)
  # library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnujaH/", overwrite=False, dry_run=False)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "मीमांसापादुका", "expand:मीमांसापादुका", "धर्मजिज्ञासाधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/mImAMsA/content/mImAMsA-pAdukA/mUlam/", sequence_start=1, has_comment=False)
  # library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/mImAMsA/content/mImAMsA-pAdukA/", overwrite=False, dry_run=False)

  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "सङ्कल्पसूर्योदयः", "expand:सङ्कल्पसूर्योदयः", "प्रथमोऽङ्कः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/rUpakam/sankalpa-sUryodayaH/mUlam", has_comment=False)


def deshika_tattvamuktaakalaapa():
  base_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shrI-sampradAyaH/venkaTanAthaH/tattva-muktA-kalApaH"
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "तत्त्वमुक्ताकलापः", "expand:तत्त्वमुक्ताकलापः", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "mUlam"), sequence_start=1, has_comment=False)
  
  # The below are incomplete as of 2023.
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "K.S. வரதாசார்யர் ஸ்வாமி", "सर्वङ्कषा", "expand:सर्वङ्कषा", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "sarvAnkaShA/mUlam"), sequence_start=1, has_comment=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "K.S. வரதாசார்யர் ஸ்வாமி", "ಸುಬೋಧಿನೀ", "expand:ಸುಬೋಧಿನೀ", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "sarvAnkaShA/kn/"), sequence_start=1, has_comment=False)
  # alabhyAmAlA, bhAvaprakAsha
  #
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "सर्वार्थसिद्धिः", "expand:सर्वार्थसिद्धिः", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "sarvArtha-siddhiH"), sequence_start=1, has_comment=False)
  # Anandadayini
  # SarvarthasiddhiGudarthavivruti
  # SarvarthasiddhiGudarthaprakasa
  

  library.fix_index_files(dir_path=base_dir, overwrite=False, dry_run=False)


def yaamuna_siddhitraya(browser):
  pass
  base_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shrI-sampradAyaH/yAmunaH/siddhi-trayam"
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=.., frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI) # 
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "திருநாங்கூர் அண்ணங்கராசாரியார்", "सिद्धित्रय-व्याख्यानम्", "expand:सिद्धित्रय-व्याख्यानम्", "Sidhdhi-आत्मसिद्धि"], outdir=os.path.join(base_dir, "annangarAchArya-vyAkhyAnam"), ordinal_start=1, has_comment=False)
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "गूढप्रकाशः", "expand:गूढप्रकाशः", "आत्मसिद्धि"], outdir=os.path.join(base_dir, "vIrarAghava-gUDha-prakAshaH"), ordinal_start=1, has_comment=False)


def stotra_misc(browser):
  pass
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीवत्साङ्कमिश्राः", "श्रीस्तवः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/stotram/kuresha-shrIvatsAnka-mishraH", sequence_start=None, has_comment=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीपराशरभट्टार्याः", "श्रीगुणरत्नकोशः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/stotram/parAshara-bhaTTaH", sequence_start=None, has_comment=False)
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेङ्कटाध्वरिः", "लक्ष्मीसहस्रम्", "expand:लक्ष्मीसहस्रम्", "प्रारम्भस्तबकः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/stotram/venkaTAdhvarI/laxmIsahasram/", ordinal_start=1, has_comment=False)


def tattva_misc(browser):
  pass
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "लक्ष्मीपुरं श्रीनिवासाचार्याः", "मान-मेय-रहस्य-श्लोकवार्त्तिकम्", "expand:मान-मेय-रहस्य-श्लोकवार्त्तिकम्", "expand:प्रयोजनवाक्यार्थः", "प्रवृत्तिक्रमः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/mishram/mAna-meya-rahasya-shloka-vArttikam", ordinal_start=746, has_comment=True)
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेङ्कटरमणार्याः", "सनातनविज्ञानसमुदयः", "expand:सनातनविज्ञानसमुदयः", "सनातनभौतिकविज्ञानम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/padArthAH/venkaTaramaNa-sanAtana-vijJNAna-samudayaH/", ordinal_start=None)


def upanishat(browser):
  pass
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीरंगाचार्याः", "ईशावास्योपनिषत् श्रीरंगाचार्यभाष्यम्", "expand:ईशावास्योपनिषत् श्रीरंगाचार्यभाष्यम्", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/rangAchAryaH", ordinal_start=None)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "कूरनारायणमुनिः", "ईशावास्योपनिषत् कूरनारायणभाष्यम्", "expand:ईशावास्योपनिषत् कूरनारायणभाष्यम्", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/kUra-nArAyaNaH", ordinal_start=None)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "गोपालानन्दस्वामी", "ईशावास्योपनिषत् सुबोधिनी", "expand:ईशावास्योपनिषत् सुबोधिनी", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/gopAlAnanda-subodhinI", ordinal_start=None)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानन्दाचार्याः", "ईशावास्योपनिषत् आनन्दभाष्यम्", "expand:ईशावास्योपनिषत् आनन्दभाष्यम्", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/gopAlAnanda-subodhinI", ordinal_start=None)
  # library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat", overwrite=False, dry_run=False)
  library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)


if __name__ == '__main__':
  browser = parankusha.get_logged_in_browser(headless=False)
  # shriibhaashyam(browser=browser)
  # yaamuna_siddhitraya(browser)
  # raamaanuja_misc(browser)
  deshika_misc(browser)
  # stotra_misc()
  # deshika_rts(browser=browser)
  # tattva_misc(browser=browser)
  # deshika_nyAyasiddhAnjanam()
  # upanishat(browser=browser)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "निक्षेप-रक्षा", "expand:निक्षेप-रक्षा", "expand:उपोद्घातः", "उपोद्घातः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/vaiShNavaH/shrI-sampradAyaH/venkaTanAthaH/nixepa-raxA")
