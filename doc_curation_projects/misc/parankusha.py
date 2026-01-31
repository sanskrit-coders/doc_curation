from doc_curation.md.library import metadata_helper, arrangement
import logging
import os.path

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from doc_curation_projects.kaavya import divyaprabandha
from indic_transliteration import sanscript

from doc_curation.scraping.misc_sites import parankusha


BS_BASE = "/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam"

def deshika_rts(browser):
  base_dir = "/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/rahasya-traya-sAraH/"
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "रहस्यत्रयसारः", "expand:रहस्यत्रयसारः","श्रीगुरुपरंपरासारः"], outdir=os.path.join(base_dir, "mUlam"), ordinal_start=0, source_script=sanscript.TAMIL)
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "42ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "सार-बोधिनी", "expand:सार-बोधिनी","श्रीगुरुपरंपरासारः"], outdir=os.path.join(base_dir, "sAra-bodhinI"), ordinal_start=0, source_script=sanscript.TAMIL)


def brahmasuutra(browser, author, text_id, sub_path):
  base_dir = os.path.join(BS_BASE, sub_path)
  if author in ["कपिस्थलं देशिकाचार्याः"]:
    base_dir = base_dir.replace("content", "static")
  for x in range(1, 5):
    for y in range(1, 5):
      os.makedirs(os.path.join(base_dir, str(x), str(y)), exist_ok=True)


  # adhyaayas = [1, 2, 3, 4]
  adhyaayas = [4]
 
  for adhyaaya in adhyaayas:
    comment_mode = author in ["सेनेश्वराचार्याः", "44ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்"] 
    if adhyaaya == 1:
      if author in "பெருக்காரணை சக்ரவர்த்யாசார்யர்":
        parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "Adhyaya-1", "Pada-3", "द्युभ्वाद्यधिकरणम्"], outdir=os.path.join(base_dir, "1"), comment_mode=comment_mode, ordinal_start=27)

      elif author in ["रामानुजाचार्याः", "अप्पय-दीक्षितः", "सेनेश्वराचार्याः", "कपिस्थलं देशिकाचार्याः", "44ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "श्रीरङ्गरामानुजाचार्याः", "सुदर्शनसूरिः", "பெருக்காரணை சக்ரவர்த்யாசார்யர்"]:
        if text_id == "विषयवाक्य-दीपिका":
          parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "Adhyaya-1", "Pada-1", "जन्माद्यधिकरणम्"], outdir=os.path.join(base_dir, "1"), comment_mode=comment_mode, ordinal_start=2)
        else:
          parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "Adhyaya-1", "Pada-1", "जिज्ञासाधिकरणम्"], outdir=os.path.join(base_dir, "1"), comment_mode=comment_mode)
      else:
        parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "Adhyaya-1", "Pada-1", "उपोद्घातम्"], outdir=os.path.join(base_dir, "1"), ordinal_start=0, comment_mode=comment_mode)
    elif adhyaaya == 2:
      parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "Adhyaya-2", "Pada-1", "स्मृत्यधिकरणम्"], outdir=os.path.join(base_dir, "2"), comment_mode=comment_mode)
    elif adhyaaya == 3:
      parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "Adhyaya-3", "Pada-1", "तदन्तरप्रतिपत्त्यधिकरणम्"], outdir=os.path.join(base_dir, "3"), comment_mode=comment_mode)
    elif adhyaaya == 4:
      if author in ["रामानुजाचार्याः", "अप्पय-दीक्षितः", "सेनेश्वराचार्याः", "कपिस्थलं देशिकाचार्याः", "44ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "श्रीरङ्गरामानुजाचार्याः", "सुदर्शनसूरिः", "பெருக்காரணை சக்ரவர்த்யாசார்யர்"]:
        parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "Adhyaya-4", "Pada-1", "आवृत्त्यधिकरणम्"], outdir=os.path.join(base_dir, "4"), comment_mode=comment_mode)
      else:
        parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "Adhyaya-4", "Pada-1", "उपोद्घातम्"], outdir=os.path.join(base_dir, "4"), comment_mode=comment_mode)

  arrangement.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnuja-sampradAyaH", overwrite=False, dry_run=False)


def shriibhaashyam(browser):
  # brahmasuutra(browser, author="रामानुजाचार्याः", text_id="श्रीभाष्यम्", sub_path="mUlam")
  # brahmasuutra(browser=browser, author="பெருக்காரணை சக்ரவர்த்யாசார்யர்", text_id="श्रीभाष्य-चन्द्रिका", sub_path="perukkAraNai-chakravartI")
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "40ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "expand:श्रीमद्भाष्यार्थमणिप्रवाळदीपिका", "समन्वयः", "अयोग-व्यवच्छेदः", "जिज्ञासाधिकरणम्"], outdir=os.path.join(BS_BASE, "40a-yatiH_maNi-pravALa-dIpikA"), comment_mode=None, ordinal_start=1)

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
  # brahmasuutra(browser, author="सुदर्शनसूरिः", text_id="श्रुतप्रकाशिका", sub_path="sudarshana-sUriH/shruta-prakAshikA/mUlam_rA/")
  # brahmasuutra(browser, author="சொக்கனாவூர் நரஸிம்ஹாசாரியார்", text_id="ஶ்ரீபாஷ்யார்த்ததீபிகை", sub_path="chokkanAvUr-narasiMhaH/")

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "சொக்கனாவூர் நரஸிம்ஹாசாரியார்", "ஶ்ரீபாஷ்யார்த்ததீபிகை", "expand:ஶ்ரீபாஷ்யார்த்ததீபிகை", "समन्वयः", "अयोग-व्यवच्छेदः", "जिज्ञासाधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/chokkanAvUr-narasiMhaH/1", source_script=sanscript.TAMIL)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "சொக்கனாவூர் நரஸிம்ஹாசாரியார்", "ஶ்ரீபாஷ்யார்த்ததீபிகை", "expand:ஶ்ரீபாஷ்யார்த்ததீபிகை", "अविरोधः", "स्मृतिः", "स्मृत्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/chokkanAvUr-narasiMhaH/2", source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "சொக்கனாவூர் நரஸிம்ஹாசாரியார்", "ஶ்ரீபாஷ்யார்த்ததீபிகை", "expand:ஶ்ரீபாஷ்யார்த்ததீபிகை", "साधनम्", "वैराग्यपादः", "तदन्तरप्रतिपत्त्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/chokkanAvUr-narasiMhaH/3", source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "சொக்கனாவூர் நரஸிம்ஹாசாரியார்", "ஶ்ரீபாஷ்யார்த்ததீபிகை", "expand:ஶ்ரீபாஷ்யார்த்ததீபிகை", "प्राप्तिः-फलम्", "आवृत्तिपादः", "आवृत्त्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/chokkanAvUr-narasiMhaH/4", source_script=sanscript.TAMIL)

  arrangement.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnuja-sampradAyaH", overwrite=False, dry_run=False)


def raamaanuja_misc(browser):
  pass
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "वेदार्थसङ्ग्रहः", "expand:वेदार्थसङ्ग्रहः", "Part-1-30"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnuja-sampradAyaH/rAmAnujaH/vedArtha-sangrahaH/")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "गद्यत्रयम्", "expand:गद्यत्रयम्", "शरणागति गद्यम्"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/gadyam/rAmAnujaH")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "नित्य-ग्रन्थः"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/")
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "ஶ்ரீந்ருஸிம்ஹப்ரியா-நித்யம் உரை"], out_file_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/rAmAnujaH/nitya-granthaH/nRsiMhapriyA.md", source_script=sanscript.TAMIL)
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "ஶ்ரீந்ருஸிம்ஹப்ரியா-நித்யம் உரை"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/")


def deshika_nyAyasiddhAnjanam():
  base_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnuja-sampradAyaH/venkaTanAthaH/nyAya-siddhANjanam"
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "न्यायसिद्धाञ्जनम्", "expand:न्यायसिद्धाञ्जनम्", "जडद्रव्यपरिच्छेदः", "उपोद्घातः"], outdir=os.path.join(base_dir, "1_jaDa-dravyam"), ordinal_start=0)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "न्यायसिद्धाञ्जनम्", "expand:न्यायसिद्धाञ्जनम्", "जीवपरिच्छेदः", "जीवस्य देहव्यतिरेकनिरूपणम्"], outdir=os.path.join(base_dir, "2_jIvaH"), ordinal_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "न्यायसिद्धाञ्जनम्", "expand:न्यायसिद्धाञ्जनम्", "ईश्वरपरिच्छेदः", "ईश्वरलक्षणनिरूपणम्"], outdir=os.path.join(base_dir, "3_IshvaraH"), ordinal_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "न्यायसिद्धाञ्जनम्", "expand:न्यायसिद्धाञ्जनम्", "नित्यविभूतिपरिच्छेदः", "नित्यविभूतिलक्षणनिरूपणम्"], outdir=os.path.join(base_dir, "4_nitya-vibhUtiH"), ordinal_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "न्यायसिद्धाञ्जनम्", "expand:न्यायसिद्धाञ्जनम्", "बुद्धिपरिच्छेदः", "बुद्धिः"], outdir=os.path.join(base_dir, "5_buddhiH"), ordinal_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "न्यायसिद्धाञ्जनम्", "expand:न्यायसिद्धाञ्जनम्", "अद्रव्यपरिच्छेदः", "दशानामेव स्फुटपरिगणनीयानाम् अद्रव्याणां निरूपणम्"], outdir=os.path.join(base_dir, "6_adravyam"), ordinal_start=1)
  arrangement.fix_index_files(dir_path=base_dir, overwrite=False, dry_run=False)


def deshika_nyAyaparishuddhiH(browser):
  base_dir = "/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/nyAya-parishuddhiH/sarva-prastutiH"
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "expand:न्यायपरिशुद्धिः", "प्रत्यक्षाध्यायः", "प्रथममाह्निकम्", "मङ्गलाचरणं ग्रन्थारम्भसमर्थनञ्च"], outdir=os.path.join(base_dir, "1_pratyaxaH/"), ordinal_start=1)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "expand:न्यायपरिशुद्धिः", "अनुमानाध्यायः", "प्रथममाह्निकम्", "अवतारिका"], outdir=os.path.join(base_dir, "2_anumAnam/"), ordinal_start=1)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "expand:न्यायपरिशुद्धिः", "शब्दाध्यायः", "प्रथममाह्निकम्", "अवतारिका"], outdir=os.path.join(base_dir, "3_shabdaH/"), ordinal_start=1)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "expand:न्यायपरिशुद्धिः", "स्मृत्यध्यायः", "प्रथममाह्निकम्", "स्मृतिप्रामाण्यम्"], outdir=os.path.join(base_dir, "4_smRtiH/"), ordinal_start=1)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "expand:न्यायपरिशुद्धिः", "प्रमेयाध्यायः", "प्रथममाह्निकम्", "अवतारिका"], outdir=os.path.join(base_dir, "5_prameyAH/"), ordinal_start=1)

  arrangement.fix_index_files(dir_path=base_dir, overwrite=False, dry_run=False)


def deshika_misc(browser):
  pass
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "ईशावास्योपनिषद् भाष्यम्"], out_file_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/venkaTanAthaH.md", comment_mode="first")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "शतदूषणी", "expand:शतदूषणी", "ब्रह्मशब्दवृत्त्यनुपपत्तिवादः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnuja-sampradAyaH/rAmAnujaH/venkaTanAthaH/shatadUShaNI/", ordinal_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "पादुका-सहस्रम्", "expand:पादुका-सहस्रम्", "प्रस्तावपद्धतिः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/pAdukA-sahasram", ordinal_start=1, comment_mode=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "यादवाभ्युदयम्", "expand:यादवाभ्युदयम्", "सर्गः-1"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/yAdavAbhyudayam", ordinal_start=1, comment_mode=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "हंस-सन्देशः", "expand:हंस-सन्देशः", "प्रथमाश्वासः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/haMsa-sandeshaH", ordinal_start=1, comment_mode=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "वैश्वदेव-कारिका", "expand:वैश्वदेव-कारिका", "Adhyaya-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTanAthaH/", ordinal_start=1, comment_mode=False)
  
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीनरकेसरी", "सुभाषितनीवी-व्याख्या-नरकेसरीयम्", "expand:सुभाषितनीवी-व्याख्या-नरकेसरीयम्", "अनिपुणपद्धतिः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/subhAShita-nIvI/narakesariH", ordinal_start=1, comment_mode=True)
  # arrangement.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnujaH/", overwrite=False, dry_run=False)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "मीमांसापादुका", "expand:मीमांसापादुका", "धर्मजिज्ञासाधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/mImAMsA/content/mImAMsA-pAdukA/mUlam/", ordinal_start=1, comment_mode=False)
  # arrangement.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/mImAMsA/content/mImAMsA-pAdukA/", overwrite=False, dry_run=False)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "सङ्कल्पसूर्योदयः", "expand:सङ्कल्पसूर्योदयः", "प्रथमोऽङ्कः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/rUpakam/sankalpa-sUryodayaH/mUlam", comment_mode=False)
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "स्तोत्ररत्नभाष्यम्"], out_file_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/shrIvaiShNava-kRtam/yAmunaH/stotra-ratnam/venkaTanAthaH_alt.md", comment_mode=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीरामदेशिकाचार्याः", "தேஶிக ப்ரபந்த வ்யாக்யானம்", "மும்மணிக்கோவை வ்யாக்யானம்"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/deshika-prabandhAH/rAma-deshikaH/", source_script=sanscript.TAMIL, ordinal_start=None)

  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "வகுளாபரண வீரராகவாசார்யர்", "அடைக்கலப்பத்து வ்யாக்யானம்", ], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/deshika-prabandhAH/vakulAbharaNa-vIra-rAghavaH/", source_script=sanscript.TAMIL, ordinal_start=None)

  
def chillarai(browser):
  pass
  base_dir = "/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/"
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीरामदेशिकाचार्याः", "தேஶிக - சில்லரை ரஹஸ்ய வ்யாக்யானம்", "தத்த்வமாத்ருகை - விளக்க உரை"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/rAma-deshikaH/", source_script=sanscript.TAMIL, ordinal_start=None)
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीरामदेशिकाचार्याः", "expand:தேஶிக - சில்லரை ரஹஸ்ய வ்யாக்யானம்", "expand:தத்த்வநவநீதம் - விளக்க உரை", "Adhyaya-1"], out_file_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/rAma-deshikaH/tattva-navanItam.md", comment_mode=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीरामदेशिकाचार्याः", "expand:தேஶிக - சில்லரை ரஹஸ்ய வ்யாக்யானம்", "expand:உபகார-ஸங்க்ரஹம் விளக்க உரை", "अधिकारः-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/upakAra-sangrahaH/rAma-deshikaH", source_script=sanscript.TAMIL, ordinal_start=None, comment_mode=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीरामदेशिकाचार्याः", "expand:தேஶிக - சில்லரை ரஹஸ்ய வ்யாக்யானம்", "ஸார ஸங்க்ரஹம் விளக்க உரை"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/rAma-deshikaH/", source_script=sanscript.TAMIL, ordinal_start=None)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "சில்லரை ரஹஸ்யம்", "பரமதபங்கம்", "சில விசேஷக் குறிப்புக்கள்"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/para-mata-bhangaH/mUlam", source_script=sanscript.TAMIL, ordinal_start=1, comment_mode=True)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "சில்லரை ரஹஸ்யம்", "ஸம்ப்ரதாயபரிஶுத்தி", "Adhyaya-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/sampradAya-parishuddhiH/mUlam", source_script=sanscript.TAMIL, ordinal_start=1, comment_mode=True)
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "சில்லரை ரஹஸ்யம்", "expand:தத்த்வபதவீ", "Adhyaya-1"], out_file_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/abhaya-pradAna-sAraH/mUlam.md", comment_mode=False)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "சில்லரை ரஹஸ்யம்", "expand:அபயப்ரதாநஸாரம்", "ப்ரபந்த அவதாரம்"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/abhaya-pradAna-sAraH/mUlam", source_script=sanscript.TAMIL, ordinal_start=1, comment_mode=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "சில்லரை ரஹஸ்யம்", "முநிவாஹநபோகம்"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/mUlam", source_script=sanscript.TAMIL, ordinal_start=None, comment_mode=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "சில்லரை ரஹஸ்யம்", "expand:உபகார-ஸங்க்ரஹம்", "अधिकारः-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/upakAra-sangrahaH", source_script=sanscript.TAMIL, ordinal_start=None, comment_mode=False)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "சில்லரை ரஹஸ்யம்", "ஸார ஸங்க்ரஹம்"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/mUlam", source_script=sanscript.TAMIL, ordinal_start=None, comment_mode=False)
  parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "மைஸூர் ஆண்டவன்", "ಶ್ರೀವೈಷ್ಣವದಿನಚರೀ ವ್ಯಾಖ್ಯಾನಮ್",], out_file_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/venkaTa-nAtha-shAkhA/venkaTanAthaH/deshika-prabandhAH/08_shrI-vaiShNava-dinacharI.md", source_script=sanscript.KANNADA, overwrite=True)
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "மைஸூர் ஆண்டவன்", "ಅರ್ಥಪಂಚಕ ವ್ಯಾಖ್ಯಾನಮ್",], out_file_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/artha-panchakam.md", source_script=sanscript.KANNADA)
  parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "மைஸூர் ஆண்டவன்", "ತಿರುಚ್ಚಿನ್ನಮಾಲೈ ವ್ಯಾಖ್ಯಾನಮ್",], out_file_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/chillarai-rahasyangaL/tiruch-chinna-mAlai.md", source_script=sanscript.KANNADA)


  arrangement.fix_index_files(dir_path=base_dir, overwrite=False, dry_run=False)


def deshika_tattvamuktaakalaapa():
  base_dir = "/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/tattva-muktA-kalApaH"
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "तत्त्वमुक्ताकलापः", "expand:तत्त्वमुक्ताकलापः", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "mUlam"), ordinal_start=1, comment_mode=False)
  
  # The below are incomplete as of 2023.
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "K.S. வரதாசார்யர் ஸ்வாமி", "सर्वङ्कषा", "expand:सर्वङ्कषा", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "kottamangala-varadaH/sarvAnkaShA/tmp"), ordinal_start=1, comment_mode=True)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "K.S. வரதாசார்யர் ஸ்வாமி", "ಸುಬೋಧಿನೀ", "expand:ಸುಬೋಧಿನೀ", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "kottamangala-varadaH/subodhinI_kn/"), ordinal_start=1, comment_mode=True)
  # alabhyAmAlA, bhAvaprakAsha
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "सर्वार्थसिद्धिः", "expand:सर्वार्थसिद्धिः", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "sarvArtha-siddhiH/tmp"), ordinal_start=1, comment_mode=True)
  # Anandadayini
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "नरसिंहदेवः (नरसिंहराजः)", "आनन्ददायिनी", "expand:आनन्ददायिनी", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "narasiMha-devaH_AnandadAyinI/tmp"), ordinal_start=1, comment_mode=True)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "अभिनवरङ्गनाथब्रह्मतन्त्रपरकालमहादेशिकाः", "भावप्रकाशः", "expand:भावप्रकाशः", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "abhinava-ranganAthaH_bhAva-prakAshaH/tmp"), ordinal_start=1, comment_mode=True)

  # SarvarthasiddhiGudarthavivruti
  # SarvarthasiddhiGudarthaprakasa
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "अलभ्यलाभः", "expand:अलभ्यलाभः", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "uttaMUru-vIrarAghavaH_alabhya-lAbhaH/"), ordinal_start=1, comment_mode=True)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीमत्सौम्यवरदरामानुजार्याः", "सर्वार्थसिद्धिगूढार्थप्रकाशः", "expand:सर्वार्थसिद्धिगूढार्थप्रकाशः", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "sarvArtha-siddhiH/saumya-varada-rAmAnuja_gUDhArtha-prakAshaH/"), ordinal_start=1, comment_mode=True)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीमद्वाधूलश्रीनिवासाचार्याः", "सर्वार्थसिद्धिगूढार्थविवृतिः", "expand:सर्वार्थसिद्धिगूढार्थविवृतिः", "जडद्रव्यसरः"], outdir=os.path.join(base_dir, "sarvArtha-siddhiH/vAdhUla-shrInivAsaH_gUDhArtha-vivRtiH/"), ordinal_start=1, comment_mode=True)

  arrangement.fix_index_files(dir_path=base_dir, overwrite=False, dry_run=False)


def yaamuna(browser):
  pass
  base_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/rAmAnuja-sampradAyaH/yAmunaH/siddhi-trayam"
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=.., frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI) # 
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "திருநாங்கூர் அண்ணங்கராசாரியார்", "सिद्धित्रय-व्याख्यानम्", "expand:सिद्धित्रय-व्याख्यानम्", "Sidhdhi-आत्मसिद्धि"], outdir=os.path.join(base_dir, "annangarAchArya-vyAkhyAnam"), ordinal_start=1, comment_mode=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "गूढप्रकाशः", "expand:गूढप्रकाशः", "आत्मसिद्धि"], outdir=os.path.join(base_dir, "vIrarAghava-gUDha-prakAshaH"), ordinal_start=1, comment_mode=False)

  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "42ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "गीतार्थसङ्ग्रहप्रकाशिका"], out_file_path="/home/vvasuki/gitland/vishvAsa/mahAbhAratam/content/vyAsaH/shlokashaH/bhagavad-gItA-parva/meta/yAmuna-gItArtha-sangrahaH/42-injimeDu-yati-TIkA", source_script=sanscript.TAMIL)
  parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "விஷ்ணுதாஸன்", "ஸ்ரீ சதுஶ்ஶ்லோகீ விவரணம்"], out_file_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/chatush-shlokI/ta_viShNudAsaH.md", source_script=sanscript.TAMIL)



def stotra_misc(browser):
  pass
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीवत्साङ्कमिश्राः", "श्रीस्तवः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/stotram/kuresha-shrIvatsAnka-mishraH", ordinal_start=None, comment_mode=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीपराशरभट्टार्याः", "श्रीगुणरत्नकोशः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/stotram/parAshara-bhaTTaH", ordinal_start=None, comment_mode=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेङ्कटाध्वरिः", "लक्ष्मीसहस्रम्", "expand:लक्ष्मीसहस्रम्", "प्रारम्भस्तबकः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/stotram/venkaTAdhvarI/laxmIsahasram/", ordinal_start=1, comment_mode=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "கோடிகன்னிகாதானம் லக்ஷ்மீகுமார ஐயாக்ருஷ்ணதாதாசார்யர் ஸ்வாமி", "காமாஸிகாஷ்டகஸாரம்"], outdir="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/kAvyam/padyam/shrIvaiShNava-kRtam/venkaTanAthaH/stotram/kAmAsikAShTakam", ordinal_start=None, comment_mode=False, source_script=sanscript.TAMIL)
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "34ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "ஶ்ரீலக்ஷ்மீந்ருஸிம்ஹன் அடைக்கலப்பத்து"],  out_file_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/34-tamAhobila-yatiH/laxmI-nRsiMhADaikkalap-pattu", source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "41ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "expand:दशावतार वेदपादस्तवः", "0"],   outdir="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/kAvyam/padyam/shrIvaiShNava-kRtam/41-tamAhobila-yatiH/dashAvatAra-veda-pAda-stavaH", comment_mode=False, source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "44ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "expand:दयासागरशतकम्", "0"],   outdir="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/kAvyam/padyam/shrIvaiShNava-kRtam/44-tamAhobila-yatiH/dayA-sAgara-shatakam", comment_mode=False, source_script=sanscript.TAMIL)
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "மஹர்ஷி வாஸுதேவாசார்யர்", "காமாஸிகாஷ்டகம் வ்யாக்யானம்"], out_file_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/kAvyam/padyam/shrIvaiShNava-kRtam/venkaTanAthaH/stotram/kAmAsikAShTakam/vangIpura-vAsudevaH", source_script=sanscript.TAMIL)
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीरामदेशिकाचार्याः", "தேஶிக ஸ்தோத்ர வ்யாக்யானம்", "காமாஸிகாஷ்டகம் உரை"], out_file_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/kAvyam/padyam/shrIvaiShNava-kRtam/venkaTanAthaH/stotram/kAmAsikAShTakam/rAmadeshikaH.md", source_script=sanscript.TAMIL)
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "நெடுந்தெரு. ரா. பத்மநாபாசாரியர்", "ஸ்ரீ ஆதிவண்ஶடகோபயதீந்த்ர மஹாதேஶிகன் அந்தாதியின் உரை"], out_file_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/Adi-vaN-shaThakopAntAdi.md", source_script=sanscript.TAMIL)


def tattva_misc(browser):
  pass
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "लक्ष्मीपुरं श्रीनिवासाचार्याः", "मान-मेय-रहस्य-श्लोकवार्त्तिकम्", "expand:मान-मेय-रहस्य-श्लोकवार्त्तिकम्", "expand:प्रयोजनवाक्यार्थः", "प्रवृत्तिक्रमः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/sAmya-vaiShamye/tattvam/sangrahaH/laxmIpura-shrInivAsa-mAna-meya-rahasya-shloka-vArttikam", ordinal_start=746, comment_mode=True)
  # En and kn translations of the above are mechanical, and bad as of 2025.
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "लक्ष्मीपुरं श्रीनिवासाचार्याः", "मान-मेय-रहस्य-श्लोकवार्त्तिकम् (कन्नड)", "expand:मान-मेय-रहस्य-श्लोकवार्त्तिकम् (कन्नड)", "expand:ಟೇಬಲ್", "ಒಳ್ಳೆಯದಾಗಲಿ!"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/sAmya-vaiShamye/tattvam/sangrahaH/laxmIpura-shrInivAsa-mAna-meya-rahasya-shloka-vArttikam/kn", source_script="kannada")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेङ्कटरमणार्याः", "सनातनविज्ञानसमुदयः", "expand:सनातनविज्ञानसमुदयः", "सनातनभौतिकविज्ञानम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/padArthAH/venkaTaramaNa-sanAtana-vijJNAna-samudayaH/", ordinal_start=None)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "शोकहर्तृपुरं रामानुजाचार्याः", "षड्विंशकसपर्या"], outdir="/home/vvasuki/gitland/vishvAsa/sanskrit/content/shixA/granthAH/yajur-vedaH/kRShNaH/upashixA/ShaD-viMshati-sUtrANi", comment_mode="last", source_script=sanscript.DEVANAGARI)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "V.K. ராமாநுஜாசார்யர்", "expand:மீமாம்ஸா ஸங்க்ரஹம்", "प्रमाणम्", "विधिः"], outdir="/home/vvasuki/gitland/vishvAsa/mImAMsA/content/karma-kANDam/12-adhyAyAH/granthAH/rAmAnuja-sampradAyaH/vk-rAmAnuja-sangrahaH", comment_mode=None, source_script=sanscript.TAMIL, timeout=20)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "V.K. ராமாநுஜாசார்யர்", "expand:श्रौतम्", "முகவுரை",], outdir="/home/vvasuki/gitland/vishvAsa/vedAH/content/meta/kalpaH/shrautam/vk-rAmAnuja-sangrahaH", comment_mode=None, source_script=sanscript.TAMIL, timeout=20)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "V.K. ராமாநுஜாசார்யர்", "expand:श्रौतम्", "முகவுரை",], outdir="/home/vvasuki/gitland/vishvAsa/vedAH/content/meta/kalpaH/shrautam/vk-rAmAnuja-sangrahaH", comment_mode=None, source_script=sanscript.TAMIL, timeout=20)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "expand:गूढप्रकाशः", "आत्मसिद्धि",], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/siddhi-trayam/uttamUr-vIrarAghava-gUDha-prakAshaH", comment_mode=None, source_script=sanscript.DEVANAGARI, timeout=20)
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "गीतासारः"], out_file_path="/home/vvasuki/gitland/vishvAsa/mahAbhAratam/content/vyAsaH/shlokashaH/bhagavad-gItA-parva/meta/yAmuna-gItArtha-sangrahaH/uttamUr-vIra-rAghavaH.md", source_script=sanscript.TAMIL)
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "गीतासारः"], out_file_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/nixepa-raxA/uttamUr-vIra-rAghava-sAraH.md", source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "expand:सत्पथसञ्चारः", "धर्मजिज्ञासाधिकरणम्",], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/uttamUru-vIrarAghavaH/sat-patha-sanchAraH", comment_mode=None, source_script=sanscript.DEVANAGARI, timeout=20)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "expand:உபநிஷத்ஸாரம்", "முகவுரை",], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/uttamUru-vIrarAghavaH/upaniShat-sAraH", comment_mode=None, source_script=sanscript.TAMIL, timeout=20)
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "शोकहर्तृपुरं रामानुजाचार्याः", "expand:सप्तलक्षणपरिष्कारः", "expand:उपोद्घातः", "उपोद्घातः"], outdir="/home/vvasuki/gitland/vishvAsa/sanskrit/content/shixA/granthAH/yajur-vedaH/kRShNaH/sapta-laxaNam", comment_mode="last", source_script=sanscript.DEVANAGARI)



def upanishat(browser):
  pass
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "திருக்கள்ளம் நரஸிம்ஹராகவாசார்யர் ஸ்வாமி", "ஈஶாவாஸ்யோபநிஷத்ஸாரம் - தமிழ் உரை"], out_file_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/tirukkaLLam-narasiMhaH.md", source_script=sanscript.TAMIL)

  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "ஈஶாவாஸ்யோபநிஷத்விவரணம்"], out_file_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/uttamUr-vIrarAghava-vivaraNam.md", source_script=sanscript.TAMIL)
  # parankusha.dump_to_file(browser=browser, start_nodes=["विद्यास्थानानि", "மஹர்ஷி வாஸுதேவாசார்யர்", "ஈஶாவாஸ்யோபநிஷத்வ்யாக்யாநம்"], out_file_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/vangIpura-vAsudevaH.md", source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "மஹர்ஷி வாஸுதேவாசார்யர்", "expand:கேநோபநிஷத்வ்யாக்யாநம்", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/jaiminIyam/AraNyakam/upaniShad-brAhmaNam/04/10_kenopaniShat/vangIpura-vAsudevaH", source_script=sanscript.TAMIL, ordinal_start=None)
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "திருக்கள்ளம் நரஸிம்ஹராகவாசார்யர் ஸ்வாமி", "expand:கேநோபநிஷத்ஸாரம் - தமிழ் உரை", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/jaiminIyam/AraNyakam/upaniShad-brAhmaNam/04/10_kenopaniShat/tirukkaLLam-narasiMhaH", source_script=sanscript.TAMIL)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "மஹர்ஷி வாஸுதேவாசார்யர்", "expand:கடோபநிஷத்வ்யாக்யாநம்", "expand:1", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/AraNyakam/kaThopaniShat/vangIpura-vAsudevaH/", source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "மஹர்ஷி வாஸுதேவாசார்யர்", "expand:ப்ரஶ்நோபநிஷத்வ்யாக்யாநம்", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/paippalAdam/prashnopaniShat/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/paippalAdam/prashnopaniShat/vangIpura-vAsudevaH.md", source_script=sanscript.TAMIL, ordinal_start=None)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीरंगाचार्याः", "ईशावास्योपनिषत् श्रीरंगाचार्यभाष्यम्", "expand:ईशावास्योपनिषत् श्रीरंगाचार्यभाष्यम्", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/rangAchAryaH", ordinal_start=None)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "कूरनारायणमुनिः", "ईशावास्योपनिषत् कूरनारायणभाष्यम्", "expand:ईशावास्योपनिषत् कूरनारायणभाष्यम्", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/kUra-nArAyaNaH", ordinal_start=None)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "गोपालानन्दस्वामी", "ईशावास्योपनिषत् सुबोधिनी", "expand:ईशावास्योपनिषत् सुबोधिनी", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/gopAlAnanda-subodhinI", ordinal_start=None)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानन्दाचार्याः", "ईशावास्योपनिषत् आनन्दभाष्यम्", "expand:ईशावास्योपनिषत् आनन्दभाष्यम्", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat/gopAlAnanda-subodhinI", ordinal_start=None)
  # arrangement.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat", overwrite=False, dry_run=False)
  # library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)
  # library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/IshAvAsyopaniShat", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "45ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "expand:கடோபநிஷத்ஸாரம் - தமிழ் உரை", "1", "1"], outdir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/AraNyakam/kaThopaniShat/45-ahobila-yatiH/", comment_mode="last", source_script=sanscript.TAMIL, ordinal_start=1)



def divya_prabandha(browser):
  pass
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "திருக்குருகைப்பிரான் பிள்ளான்", "expand:திருவாறாயிரப்படி", "முதல் பத்து", "முதல் திருமொழி"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/6k_tiruk-kurugaip-pirAn-piLLAn/rA/", comment_mode=None, source_script=sanscript.TAMIL)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "காஞ்சீ அண்ணங்கராசாரியார்", "ராமாநுஜ நூற்றந்தாதி பதவுரை"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/aNNangarAchAryaH/", ordinal_start=None, comment_mode="last", source_script=sanscript.TAMIL)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "காஞ்சீ அண்ணங்கராசாரியார்", "முதல் திருவந்தாதி பதவுரை"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/aNNangarAchAryaH/", ordinal_start=None, comment_mode="last", source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "காஞ்சீ அண்ணங்கராசாரியார்", "இரண்டாம் திருவந்தாதி விளக்கவுரை"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/aNNangarAchAryaH/", ordinal_start=None, comment_mode="last", source_script=sanscript.TAMIL)


  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "காஞ்சீ அண்ணங்கராசாரியார்", "expand:பெரியாழ்வார் திருமொழி பதவுரை", "expand:பத்து-1", "திருமொழி-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/10_pEriya_tirumOLHi_tirumangai-ALHvAr_948-2031/aNNangarAchAryaH/padav-urai", comment_mode="last", source_script=sanscript.TAMIL)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "காஞ்சீ அண்ணங்கராசாரியார்", "expand:பெரியாழ்வார் திருமொழி விளக்கவுரை", "expand:பத்து-1", "திருமொழி-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/10_pEriya_tirumOLHi_tirumangai-ALHvAr_948-2031/aNNangarAchAryaH/viLakkav-urai", comment_mode="last", source_script=sanscript.TAMIL)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "காஞ்சீ அண்ணங்கராசாரியார்", "expand:பெரியாழ்வார் திருமொழி விளக்கவுரை", "expand:பத்து-1", "திருமொழி-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/aNNangarAchAryaH/padav-urai", comment_mode="last", source_script=sanscript.TAMIL)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "காஞ்சீ அண்ணங்கராசாரியார்", "expand:பெரியாழ்வார் திருமொழி விளக்கவுரை", "expand:பத்து-1", "திருமொழி-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/aNNangarAchAryaH/viLakkav-urai", comment_mode="last", source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "காஞ்சீ அண்ணங்கராசாரியார்", "expand:நாச்சியார் திருமொழி விளக்கவுரை", "திருமொழி-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/03_nAchchiyAr-tirumoLHi_ANDAL_504-646/aNNangarAchAryaH", comment_mode="last", source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "காஞ்சீ அண்ணங்கராசாரியார்", "expand:நாச்சியார் திருமொழி விளக்கவுரை", "திருமொழி-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/03_nAchchiyAr-tirumoLHi_ANDAL_504-646/aNNangarAchAryaH/viLakkav_urai", comment_mode="last", source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "காஞ்சீ அண்ணங்கராசாரியார்", "expand:நாச்சியார் திருமொழி பதவுரை", "திருமொழி-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/03_nAchchiyAr-tirumoLHi_ANDAL_504-646/aNNangarAchAryaH/padav_urai", comment_mode="last", source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "காஞ்சீ அண்ணங்கராசாரியார்", "expand:பெருமாள் திருமொழி பதவுரை", "திருமொழி-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/04_perumAL-tirumoLHi_kulashEkhara_647-751/aNNangarAchAryaH/padav_urai", comment_mode="last", source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "காஞ்சீ அண்ணங்கராசாரியார்", "expand:பெருமாள் திருமொழி விளக்கவுரை", "திருமொழி-1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/04_perumAL-tirumoLHi_kulashEkhara_647-751/aNNangarAchAryaH/viLakkav_urai", comment_mode="last", source_script=sanscript.TAMIL)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "மன்னார்குடி ஸ்வாமி", "expand:द्रमिडोपनिषत्तात्पर्यरत्नावलिः - व्याख्यानम्", "उपोद्घातः", "0"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/venkaTa-nAthAryaH/dramiDopaniShat-tAtparya-ratnAvalI/mannAr-guDi-svAmI/", comment_mode="last", source_script=sanscript.TAMIL, ordinal_start=0)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "45ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", "expand:திருப்பாவை உபன்யாசம்", "उपोद्घातः", "0"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/02_tiruppAvai_ANDAL_474-503/45-ahobila-yatiH", comment_mode="last", source_script=sanscript.TAMIL, ordinal_start=0)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "திருக்குடந்தை ஆண்டவன்", "expand:பகவத்விஷய ஸாரம்", "1", "1"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/kumbhakoNANDavan/", comment_mode=None, source_script=sanscript.TAMIL)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "expand:ப்ரபந்தரக்ஷை", "expand:பெரியாழ்வார் திருமொழி வ்யாக்யாநம்", "expand:முதல் பத்து", "முதல் திருமொழி"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/01_tiruppallaNDu_tirumoLHi_pEriyaLHvar_1-473/tirumoLHi/uttamUr-vIrarAghavaH/1/1", comment_mode=None, source_script=sanscript.TAMIL, timeout=20)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "expand:ப்ரபந்தரக்ஷை", "expand:பெரிய திருமொழி வ்யாக்யாநம்", "expand:முதல் பத்து", "முதல் திருமொழி"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/10_pEriya_tirumOLHi_tirumangai-ALHvAr_948-2031/uttamUr-vIrarAghavaH/1/1", comment_mode=None, source_script=sanscript.TAMIL, timeout=20)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "expand:ப்ரபந்தரக்ஷை", "expand:திருவாய்மொழி வ்யாக்யாநம்", "expand:முதல் பத்து", "முதல் திருமொழி"], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/uttamUr-vIrarAghavaH/", comment_mode=None, source_script=sanscript.TAMIL, timeout=20)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "expand:ப்ரபந்தரக்ஷை", "கண்ணிநுண்சிறுத்தாம்பு வ்யாக்யாநம்",], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/uttamUr-vIrarAghavaH/", comment_mode=None, source_script=sanscript.TAMIL, timeout=20)
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "உத்தமூர் வீரராகவாசார்யர்", "திருப்பள்ளியெழுச்சி",], outdir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/uttamUr-vIrarAghavaH/", comment_mode=None, source_script=sanscript.TAMIL, timeout=20)


# Current - काञ्ची अण्णङ्कराचारियार्
if __name__ == '__main__':
  browser = parankusha.get_logged_in_browser(headless=False)
  # shriibhaashyam(browser=browser)
  # divya_prabandha(browser=browser)


  # yaamuna(browser)
  # raamaanuja_misc(browser)
  # deshika_misc(browser)
  # chillarai(browser)
  # deshika_tattvamuktaakalaapa(browser=browser)
  # stotra_misc(browser=browser)
  # deshika_rts(browser=browser)
  tattva_misc(browser=browser)
  # deshika_nyAyasiddhAnjanam(browser=browser)
  # deshika_nyAyaparishuddhiH(browser=browser)
  # upanishat(browser=browser)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "निक्षेप-रक्षा", "expand:निक्षेप-रक्षा", "expand:उपोद्घातः", "उपोद्घातः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/vaiShNavaH/rAmAnuja-sampradAyaH/venkaTanAthaH/nixepa-raxA")
