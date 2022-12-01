import logging

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

from doc_curation.scraping.misc_sites import parankusha


def get_tamil(browser):
  outdir = "/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/shrI-sampradAyaH/venkaTanAthaH/rahasya-traya-sAraH/mUlam"
  # parankusha.get_texts(
  #   browser=browser,
  #   start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "रहस्यत्रयसारः", "expand:रहस्यत्रयसारः",
  #                "श्रीगुरुपरंपरासारः"],
  #   outdir=outdir)
  library.apply_function(fn=MdFile.transform, dir_path=outdir, content_transformer=lambda c, m: content_processor.transliterate(c, source_script=sanscript.TAMIL), dry_run=False)


def shriibhaashyam(browser):
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "श्रीभाष्यम्", "expand:श्रीभाष्यम्", "expand:Adhyaya-1", "expand:Pada-1", "जिज्ञासाधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/shrI-bhAShyam/1/")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "श्रीभाष्यम्", "expand:श्रीभाष्यम्", "expand:Adhyaya-2", "expand:Pada-1", "स्मृत्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/shrI-bhAShyam/2/")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "श्रीभाष्यम्", "expand:श्रीभाष्यम्", "expand:Adhyaya-3", "expand:Pada-1", "तदन्तरप्रतिपत्त्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/shrI-bhAShyam/3/")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "श्रीभाष्यम्", "expand:श्रीभाष्यम्", "expand:Adhyaya-4", "expand:Pada-1", "आवृत्त्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/shrI-bhAShyam/4/")

  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "वेदान्तदीपः", "expand:वेदान्तदीपः", "expand:Adhyaya-1", "expand:Pada-1", "अवतारिका"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/shrI-bhAShyam/vedAnta-dIpaH/1/", sequence_start=0)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "वेदान्तदीपः", "expand:वेदान्तदीपः", "expand:Adhyaya-2", "expand:Pada-1", "स्मृत्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/shrI-bhAShyam/vedAnta-dIpaH/2/")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "वेदान्तदीपः", "expand:वेदान्तदीपः", "expand:Adhyaya-3", "expand:Pada-1", "तदन्तरप्रतिपत्त्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/shrI-bhAShyam/vedAnta-dIpaH/3/")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "वेदान्तदीपः", "expand:वेदान्तदीपः", "expand:Adhyaya-4", "expand:Pada-1", "आवृत्त्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/shrI-bhAShyam/vedAnta-dIpaH/4/")


  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "वेदान्तसारः", "expand:वेदान्तसारः", "expand:Adhyaya-1", "expand:Pada-1", "जिज्ञासाधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/shrI-bhAShyam/vedAnta-sAraH/1/", sequence_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "वेदान्तसारः", "expand:वेदान्तसारः", "expand:Adhyaya-2", "expand:Pada-1", "स्मृत्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/shrI-bhAShyam/vedAnta-sAraH/2/")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "वेदान्तसारः", "expand:वेदान्तसारः", "expand:Adhyaya-3", "expand:Pada-1", "तदन्तरप्रतिपत्त्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/shrI-bhAShyam/vedAnta-sAraH/3/")
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "वेदान्तसारः", "expand:वेदान्तसारः", "expand:Adhyaya-4", "expand:Pada-1", "आवृत्त्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/shrI-bhAShyam/vedAnta-sAraH/4/")


  library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/", overwrite=False, dry_run=False)


def raamaanuja_misc(browser):
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "वेदार्थसङ्ग्रहः", "expand:वेदार्थसङ्ग्रहः", "Part-1-30"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/vedArtha-sangrahaH/")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "गद्यत्रयम्", "expand:गद्यत्रयम्", "शरणागति गद्यम्"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/gadyam/rAmAnujaH")
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "रामानुजाचार्याः", "नित्य-ग्रन्थः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/shrI-sampradAyaH/kriyA/")


def deshika_misc(browser):
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "शतदूषणी", "expand:शतदूषणी", "ब्रह्मशब्दवृत्त्यनुपपत्तिवादः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/venkaTanAthaH/shatadUShaNI/", sequence_start=1)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "पादुका-सहस्रम्", "expand:पादुका-सहस्रम्", "प्रस्तावपद्धतिः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/pAdukA-sahasram", sequence_start=1, has_comment=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "यादवाभ्युदयम्", "expand:यादवाभ्युदयम्", "सर्गः-1"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/yAdavAbhyudayam", sequence_start=1, has_comment=False)
  parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "हंस-सन्देशः", "expand:हंस-सन्देशः", "प्रथमाश्वासः"], outdir="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/venkaTanAthaH/haMsa-sandeshaH", sequence_start=1, has_comment=False)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "वैश्वदेव-कारिका", "expand:वैश्वदेव-कारिका", "Adhyaya-1"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/shrI-sampradAyaH/kriyA/venkaTanAthaH/", sequence_start=1, has_comment=False)
  
  # library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/", overwrite=False, dry_run=False)
  

def adhikaraNa_sArAvalI():
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "अधिकरणसारावली", "expand:अधिकरणसारावली", "expand:Adhyaya-1", "expand:Pada-1", "उपोद्घातम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/venkaTanAthaH/adhikaraNasArAvalI/1/", sequence_start=0)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "अधिकरणसारावली", "expand:अधिकरणसारावली", "expand:Adhyaya-2", "expand:Pada-1", "स्मृत्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/venkaTanAthaH/adhikaraNasArAvalI//2/")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "अधिकरणसारावली", "expand:अधिकरणसारावली", "expand:Adhyaya-3", "expand:Pada-1", "तदन्तरप्रतिपत्त्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/venkaTanAthaH/adhikaraNasArAvalI//3/")
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "अधिकरणसारावली", "expand:अधिकरणसारावली", "expand:Adhyaya-4", "expand:Pada-1", "आवृत्त्यधिकरणम्"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/venkaTanAthaH/adhikaraNasArAvalI//4/")


  library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/rAmAnujaH/", overwrite=False, dry_run=False)



if __name__ == '__main__':
  browser = parankusha.get_logged_in_browser(headless=False)
  # shriibhaashyam(browser=browser)
  # adhikaraNa_sArAvalI()
  # raamaanuja_misc(browser)
  deshika_misc(browser)
  # get_tamil(browser=browser)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "निक्षेप-रक्षा", "expand:निक्षेप-रक्षा", "expand:उपोद्घातः", "उपोद्घातः"], outdir="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/shrI-sampradAyaH/venkaTanAthaH/nixepa-raxA")
