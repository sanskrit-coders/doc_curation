import doc_curation.utils.sanskrit_helper
import regex
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import details_helper, ocr_helper, space_helper, section_helper, footnote_helper
from doc_curation.md.file import MdFile
from doc_curation.scraping.misc_sites import ebhaarati
from doc_curation.utils import patterns, sanskrit_helper
from indic_transliteration import tamil_tools, aksharamukha_helper, sanscript


def transformer(x):
  # x = doc_curation.md.content_processor.space_helper.dehyphenate_sanskrit_line_endings(x)
  #x = sanskrit_helper.fix_lazy_anusvaara(x)
  x = tamil_tools.fix_naive_ta_transliterations(x)
  return x

def line_breaker(x):
  return regex.sub("(?<=\S)(?=\n)", "  ", x)



if __name__ == '__main__':
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.non_detail_parts_to_detail(content=c, title="टीका"))
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/svAmi-nArAyaNa-sampradAyaH/laxmI-nArAyaNa-saMhitA/1_kRta-yuga-santAnaH/083.md", content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c, pattern=patterns.PATTERN_MULTI_LINE_SHLOKA_DOUBLE_DANDA))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c, pattern=patterns.PATTERN_2LINE_SHLOKA))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c, pattern=patterns.PATTERN_BOLD_LINES))

  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: section_helper.section_headings_to_details(content=c))


  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/parAshara-vishiShTa-dharma-shAstram/sarva-prastutiH", content_transformer=details_helper.insert_duplicate_adjascent)

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/parAshara-vishiShTa-dharma-shAstram/sarva-prastutiH", content_transformer=lambda c, m: details_helper.transform_detail_contents_with_soup(content=c, metadata=m, transformer=lambda c, m : "\n\n" + content_processor.transliterate(text=c, source_script="tamil"), title_pattern="तमि.*"))

  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.transform_detail_contents_with_soup(content=c, metadata=m, transformer=tamil_nna_fixer, title_pattern="सा.*"))

  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.transform_detail_contents_with_soup(content=c, metadata=m, transformer=line_breaker, title_pattern="विश्वास-प्रस्तुतिः.*"))

  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.transform_detail_contents_with_soup(content=c, metadata=m, transformer=lambda c, m:space_helper.remove_fake_linebreaks(c), title_pattern="गङ्गानथ-तुल्य-वाक्यानि"))


  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.transform_detail_contents_with_soup(content=c, metadata=m, transformer=tamil_nna_fixer, title_pattern="विश्वास-प्रस्तुतिः.*|मूलम्.*"))

  pass
