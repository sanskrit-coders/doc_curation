from doc_curation.md import library, content_processor
from doc_curation.utils import patterns

CONTENT_DIR = "/home/vvasuki/vishvAsa/vedAH_yajuH/content/taittirIyam/saMhitA/sAyaNaH"

def dump_all():
  pass
  from doc_curation.scraping.html_scraper import selenium
  web_ids = [2086, 2087, 2088, 2089, 2083, 2084, 2085, 2091, 2092]
  for index, web_id in enumerate(web_ids):
    selenium.dump_pages(url="http://www.vedamu.org/PageViewerText.aspx?DivId=%d" % web_id, out_path="%s/v%d.md" % (CONTENT_DIR, index+1), next_button_css="[name=\"ctl00$ContentPlaceHolder1$imgNext\"]", content_css="td.txtMultiLineSearch", page_id_css_selector='[name="ctl00$ContentPlaceHolder1$txtPageNo"]')


def fix_all(dir_path=CONTENT_DIR):
  pass
  # library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m:content_processor.markdownify_newlines(c), dir_path=dir_path)
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["‌", "", "", "", "", ""], replacement="")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["", " ?ँ्"], replacement="ꣳ")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["", ""], replacement="ꣳ॑")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[f"({patterns.DEVANAGARI_NON_MATRA}{patterns.DEVANAGARI_MATRA}*)"], replacement=r"॑\1॒")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[""], replacement="ऽ")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[""], replacement="ऽऽ")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[""], replacement="“")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[""], replacement="”")


if __name__ == '__main__':
  # dump_all()
  # fix_all()
  fix_all(dir_path="/home/vvasuki/vishvAsa/vedAH_yajuH/content/taittirIyam/saMhitA/sarva-prastutiH/4")