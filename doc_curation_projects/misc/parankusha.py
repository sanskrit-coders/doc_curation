import logging

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from doc_curation.scraping import parankusha
from indic_transliteration import sanscript


def get_tamil(browser):
  outdir = "/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/shrI-sampradAyaH/venkaTanAthaH/rahasya-traya-sAraH/mUlam"
  # parankusha.get_texts(
  #   browser=browser,
  #   start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "रहस्यत्रयसारः", "expand:रहस्यत्रयसारः",
  #                "श्रीगुरुपरंपरासारः"],
  #   outdir=outdir)
  library.apply_function(fn=MdFile.transform, dir_path=outdir, content_transformer=lambda c, m: content_processor.transliterate(c, source_script=sanscript.TAMIL), dry_run=False)


if __name__ == '__main__':
  browser = parankusha.get_logged_in_browser(headless=False)
  get_tamil(browser=browser)
  # parankusha.get_texts(browser=browser, start_nodes=["विद्यास्थानानि", "वेदान्तदेशिकाः", "देशिक-स्तोत्राणि", "expand:देशिक-स्तोत्राणि", "Stotram-श्री अभीतिस्तवः"], outdir="/home/vvasuki/sanskrit/raw_etexts/kAvyam/stotram/vedAnta-deshikaH/")
