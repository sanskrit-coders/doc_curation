from doc_curation.md import library, content_processor
from doc_curation.utils import patterns

CONTENT_DIR_SAMHITA = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/saMhitA/sAyaNaH"

CONTENT_DIR_ARANYAKA = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/AraNyakam/sAyaNaH"

def dump_all(web_ids, dir_path):
  pass
  from doc_curation.scraping.html_scraper import selenium
  web_ids = web_ids
  for index, web_id in enumerate(web_ids):
    selenium.dump_pages(url="http://www.vedamu.org/PageViewerText.aspx?DivId=%d" % web_id, out_path="%s/v%d.md" % (dir_path, index + 1), next_button_css="[name=\"ctl00$ContentPlaceHolder1$imgNext\"]", content_css="td.txtMultiLineSearch", page_id_css_selector='[name="ctl00$ContentPlaceHolder1$txtPageNo"]', skip_existing=False)


def fix_all(dir_path=CONTENT_DIR_SAMHITA):
  pass
  # library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m:content_processor.markdownify_newlines(c), dir_path=dir_path)
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["‌", "", "", "", "", "", ""], replacement="")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["", " ?ँ्"], replacement="ꣳ")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["", ""], replacement="ꣳ॑")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[f"({patterns.DEVANAGARI_NON_MATRA}{patterns.DEVANAGARI_MATRA}*)"], replacement=r"॑\1॒")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[""], replacement="ऽ")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[""], replacement="ऽऽ")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[""], replacement="“")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[""], replacement="”")

  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["य़"], replacement="य")


if __name__ == '__main__':
  # dump_all(web_ids=[2086, 2087, 2088, 2089, 2083, 2084, 2085, 2091, 2092], dir_path=CONTENT_DIR_SAMHITA)
  # fix_all(dir_path=CONTENT_DIR_SAMHITA)
  # dump_all(web_ids=[1956], dir_path=CONTENT_DIR_ARANYAKA)
  fix_all(dir_path=CONTENT_DIR_ARANYAKA)
