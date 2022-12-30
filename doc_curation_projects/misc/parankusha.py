import logging
import os.path

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

from doc_curation.scraping.misc_sites import parankusha


BS_BASE = "/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/"

def get_tamil(browser):
  outdir = "/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/shrI-sampradAyaH/venkaTanAthaH/rahasya-traya-sAraH/mUlam"
  # parankusha.get_texts(
  #   browser=browser,
  #   start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "रहस्यत्रयसारः", "expand:रहस्यत्रयसारः",
  #                "श्रीगुरुपरंपरासारः"],
  #   outdir=outdir)
  library.apply_function(fn=MdFile.transform, dir_path=outdir, content_transformer=lambda c, m: content_processor.transliterate(c, source_script=sanscript.TAMIL), dry_run=False)


def brahmasuutra(browser, author, text_id, sub_path):
  for x in range(1, 5):
    for y in range(1, 5):
      os.makedirs(os.path.join(BS_BASE, sub_path, str(x), str(y)), exist_ok=True)

  # adhyaaya = 1
  # adhyaaya = 2
  adhyaaya = 3
  # adhyaaya = 4
  
  if adhyaaya == 1:
    if author == "रामानुजाचार्याः":
      parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-1", "expand:Pada-1", "जिज्ञासाधिकरणम्"], outdir=os.path.join(BS_BASE, sub_path, "1"))
    else:
      parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-1", "expand:Pada-1", "उपोद्घातम्"], outdir=os.path.join(BS_BASE, sub_path, "1"), sequence_start=0)
  elif adhyaaya == 2:
    parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-2", "expand:Pada-1", "स्मृत्यधिकरणम्"], outdir=os.path.join(BS_BASE, sub_path, "2"))
  elif adhyaaya == 3:
    parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-3", "expand:Pada-1", "तदन्तरप्रतिपत्त्यधिकरणम्"], outdir=os.path.join(BS_BASE, sub_path, "3"))
  elif adhyaaya == 4:
    if author == "रामानुजाचार्याः":
      parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-4", "expand:Pada-1", "आवृत्त्यधिकरणम्"], outdir=os.path.join(BS_BASE, sub_path, "4"))
    else:
      parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", author, text_id, f"expand:{text_id}", "expand:Adhyaya-4", "expand:Pada-1", "उपोद्घातम्"], outdir=os.path.join(BS_BASE, sub_path, "4"))


def shriibhaashyam(browser):
  # brahmasuutra(browser, author="रामानुजाचार्याः", text_id="श्रीभाष्यम्", sub_path="shrI-bhAShyam/mUlam")
  # brahmasuutra(browser, author="रामानुजाचार्याः", text_id="वेदान्तदीपः", sub_path="shrI-bhAShyam/vedAnta-dIpaH")
  # brahmasuutra(browser, author="रामानुजाचार्याः", text_id="वेदान्तसारः", sub_path="shrI-bhAShyam/vedAnta-sAraH")
  # brahmasuutra(browser, author="वेदान्तदेशिकाः", text_id="अधिकरणसारावली", sub_path="shrI-bhAShyam/venkaTanAthaH/adhikaraNasArAvalI/mUlam")
  # brahmasuutra(browser, author="कुमार-वरदाचार्याः", text_id="चिन्तामणिः", sub_path="shrI-bhAShyam/adhikaraNasArAvalI/chintAmaNiH")
  # brahmasuutra(browser, author="34ம் பட்டம் ஶ்ரீமத் அழகியசிங்கர்", text_id="अधिकरणसारावली-पद-योजना", sub_path="shrI-bhAShyam/adhikaraNasArAvalI/pada-yojanA")


  library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/", overwrite=False, dry_run=False)


def raamaanuja_misc(browser):
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "वेदार्थसङ्ग्रहः", "expand:वेदार्थसङ्ग्रहः", "Part-1-30"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/vedArtha-sangrahaH/")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "गद्यत्रयम्", "expand:गद्यत्रयम्", "शरणागति गद्यम्"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/gadyam/rAmAnujaH")
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "नित्य-ग्रन्थः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/shrI-sampradAyaH/kriyA/")


def deshika_misc(browser):
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "शतदूषणी", "expand:शतदूषणी", "ब्रह्मशब्दवृत्त्यनुपपत्तिवादः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/venkaTanAthaH/shatadUShaNI/", sequence_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "पादुका-सहस्रम्", "expand:पादुका-सहस्रम्", "प्रस्तावपद्धतिः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/pAdukA-sahasram", sequence_start=1, has_comment=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "यादवाभ्युदयम्", "expand:यादवाभ्युदयम्", "सर्गः-1"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/yAdavAbhyudayam", sequence_start=1, has_comment=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "हंस-सन्देशः", "expand:हंस-सन्देशः", "प्रथमाश्वासः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/haMsa-sandeshaH", sequence_start=1, has_comment=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "वैश्वदेव-कारिका", "expand:वैश्वदेव-कारिका", "Adhyaya-1"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/shrI-sampradAyaH/kriyA/venkaTanAthaH/", sequence_start=1, has_comment=False)
  
  library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/", overwrite=False, dry_run=False)

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "मीमांसापादुका", "expand:मीमांसापादुका", "धर्मजिज्ञासाधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/mImAMsA/content/mImAMsA-pAdukA/mUlam/", sequence_start=1, has_comment=False)
  # library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/mImAMsA/content/mImAMsA-pAdukA/", overwrite=False, dry_run=False)

def stotra_misc():
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीवत्साङ्कमिश्राः", "श्रीस्तवः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/stotram/kuresha-shrIvatsAnka-mishraH", sequence_start=None, has_comment=False)
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "श्रीपराशरभट्टार्याः", "श्रीगुणरत्नकोशः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/stotram/parAshara-bhaTTaH", sequence_start=None, has_comment=False)




if __name__ == '__main__':
  browser = parankusha.get_logged_in_browser(headless=False)
  shriibhaashyam(browser=browser)
  # adhikaraNa_sArAvalI()
  # raamaanuja_misc(browser)
  # deshika_misc(browser)
  # stotra_misc()
  # get_tamil(browser=browser)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "निक्षेप-रक्षा", "expand:निक्षेप-रक्षा", "expand:उपोद्घातः", "उपोद्घातः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/shrI-sampradAyaH/venkaTanAthaH/nixepa-raxA")
