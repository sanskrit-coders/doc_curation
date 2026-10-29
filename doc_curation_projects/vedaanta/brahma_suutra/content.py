from doc_curation import sanskrit as sanskrit_helper
import regex
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor.footnote import helper as footnote_helper
from doc_curation.md.content_processor import details as details_helper, ocr_helper, space_helper, section_helper
from doc_curation.md.file import MdFile
from doc_curation.sanskrit import hyphenator
from doc_curation.scraping.misc_sites import ebhaarati
from doc_curation import sanskrit as sanskrit_helper
from doc_curation.utils import patterns
from indic_transliteration import tamil_tools, aksharamukha_helper, sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent
from doc_curation.llm import opencode
from doc_curation.md.content_processor.details import maker
from doc_curation.md.content_processor.commentary import interleaver

def process_dir(dir_path):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args, **kwargs: maker.generic_sanskrit_vipra_mUla(c))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args, **kwargs: details_helper.transform_details_with_soup(content=c,content_str_transformer=lambda x, *args, **kwargs : hyphenator.hyphene(x), title_pattern="विश्वास-.*"))


def insert_commentary(dest_path):
  if "rAmAnujaH" in dest_path:
    pass
    # interleaver.interleave_TIkA_below_mUla(dest_file=dest_path, commentary_file=dest_path.replace("/sarva-prastutiH/", "/sudarshana-sUriH/shruta-prakAshikA/mUlam_rA/"))

  opencode.insert_translation_details(
    md_path=dest_path,
    translation_dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/en/thibaut/1/2",
    start_file="_index.md", end_file=None,
    end_after=r"Here .+? the adhikaraṇa",
    model_id="opencode-go/deepseek-v4.1-flash",)
    # opencode-go/deepseek-v4.1-flash
    # opencode/muse-spark-1.3-contributor-free
  


if __name__ == '__main__':
  # process_dir("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/2_aspaShTa-jIvAdi-lingakaH/12_sarvatraprasiddhyadhikaraNam.md")
  insert_commentary("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/2_aspaShTa-jIvAdi-lingakaH/12_sarvatraprasiddhyadhikaraNam.md")

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/tattvam/shankaraH/brahma-sUtrANi/sarva-prastutiH/01/01/10_jyotishcharaNAdhikaraNam.md", content_transformer=lambda c, *args, **kwargs: details_helper.transform_details_with_soup(content=c,content_str_transformer=lambda x, *args, **kwargs : hyphenator.hyphene(x), title_pattern="विश्वास-.*"))
  pass
