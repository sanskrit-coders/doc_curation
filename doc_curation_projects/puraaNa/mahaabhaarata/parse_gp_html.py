import codecs
import os
from copy import copy

from bs4 import BeautifulSoup
import regex

from curation_utils import scraping
from curation_utils.file_helper import get_storage_name
from doc_curation.md import library
from doc_curation.md.content_processor.details_helper import Detail
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.scraping.html_scraper import souper
from indic_transliteration import sanscript
import logging

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

epub_dir = "/home/vvasuki/sanskrit/raw_etexts/purANam/mahAbhAratam/gp/epub_no_img/"


detail_map = {
  "सूचना (हिन्दी)": ["class_106", "class_151", "class_2", "class_236", "class_239", "class_249", "class_281", "class_282", "class_284", "class_285", "class_292", "class_307", "class_316", "class_341", "class_342", "class_347", "class_349", "class_364", "class_385", "class_389", "class_4", "class_40", "class_46", "class_5", "class_53", "class_73", "class_85", "class_93", "class_96"] + ["class_194", "class_195", "class_3", "class_322", "class_343"] + ["class_25", "class_289", "class_299", "class_303"] + ["class_115", "class_124", "class_288", "class_298", "class_302", "class_304", "class_378", "class_47"] + ["class_142", "class_274"] + ["class_181", "class_218"] + ["class_190", "class_312"] + ["class_263", "class_271"] + ["class_293", "class_374"],
  "भागसूचना": ["class_241", "class_280", "class_48"] + ["class_49", "class_50", "class_52"] + ["class_51"] + ["class_50", "class_23", "class_22"] + ["class_100", "class_105", "class_180", "class_240", "class_254", "class_291", "class_390", "class_45", "class_52", "class_92", "class_95"],
  "विषय (हिन्दी)": ["class_53", "class_52", "class_85", "class_93", "class_96"],
  "मूलम् (वचनम्)": ["class_102", "class_113", "class_160", "class_221", "class_309", "class_384", "class_59", "class_69", "class_71", "class_86", "class_88", "class_97"],
  "मूलम्": ["class_182", "class_183", "class_24", "class_258", "class_33", "class_54", "class_57", "class_66", "class_67", ] + ["class_14", "class_15", "class_18", "class_220", "class_246", "class_294", "class_295", "class_329", "class_386", "class_77", "class_81"],
  "मूलम् (समाप्तिः)": ["class_141", "class_159", "class_161", "class_383", "class_387", "class_70", "class_87"] + ["class_72", "class_73", "class_78", "class_79", "class_40"],
  "अनुवाद (हिन्दी)": ["class_55", "class_68", "class_88"],
  "अनुवाद (समाप्ति)": ["class_71"],
  "प्रकाशनसूचना": ["class_13", "class_14", "class_15", "class_16", "class_17", "class_18", "class_19", "class_20"],
  "नमस्कारः": ["class_1", "class_8", "class_21", "class_28"],
}

format_map = {
  "citation_marker": ["class_122", "class_184"],
  "footnote_marker": ["class_56", "class_108", "class_266", "class_360"],
  "footnote_definition_marker": ["class_36", "class_80", "class_134"],
  "footnote_definition": ["class_109", "class_150", "class_290", "class_76", "class_78", "class_91"] + ["class_81", "class_82", "class_83",],
  "footnote_quote": ["class_84", "class_99"],
  "telling_hindi": ["class_60"],

  "image": ["class_58", "class_61", "class_63", "class_64", "class_65", "class_74", "class_89"],
  "caption": ["class_62"] + ["class_155", "class_287"],
  "hr": ["class_388", "class_75", "class_90"]
}


def css_selector_list(classes):
  return ["." + x for x in classes]


def romanize(text):
  return sanscript.transliterate(text, _from=sanscript.DEVANAGARI, _to=sanscript.OPTITRANS)


def get_detail_type(div_class):
  for detail_type, detail_classes in detail_map.items():
    if div_class in detail_classes:
      return detail_type
  return None


def fix_tags(soup):
  ## First, fix some text
  tags = souper.get_tags_matching_css(soup=soup, css_selector_list=css_selector_list(format_map["citation_marker"]))
  for tag in tags:
    tag.string.replace_with(f"[[{tag.text}]]")

  tags = souper.get_tags_matching_css(soup=soup, css_selector_list=css_selector_list(format_map["footnote_marker"]))
  for tag in tags:
    tag.string.replace_with(f"[^{tag.text}]")

  tags = souper.get_tags_matching_css(soup=soup, css_selector_list=css_selector_list(format_map["footnote_definition_marker"]))
  for tag in tags:
    tag.string.replace_with(f"[^{tag.text}]:")

  tags = souper.get_tags_matching_css(soup=soup, css_selector_list=css_selector_list(format_map["footnote_quote"]))
  for tag in tags:
    tag.string.replace_with(f"'''{tag.text}'''")


  tags = souper.get_tags_matching_css(soup=soup, css_selector_list=css_selector_list(format_map["telling_hindi"]))
  for tag in tags:
    tag.string.replace_with(f"_{tag.text}_ ")


def content_from_details(details):
  content = ""
  for detail in details:
    if detail.type == "FOOTNOTE_DEFINITION":
      content += "\n" + detail.content + "\n"
    else:
      if detail.type == "मूलम्":
        detail_vishvaasa = copy(detail)
        detail_vishvaasa.type = "विश्वास-प्रस्तुतिः"
        content += "\n" + detail_vishvaasa.to_html() + "\n"
      content += "\n" + detail.to_html() + "\n"
  return content


def parse_body_divs(soup):
  details = []
  divs = soup.select("body>div")
  for div in divs:
    if div.text == "":
      continue
    div_class = div["class"][0]
    if div_class in format_map["footnote_definition"]:
      details.append(Detail(type="FOOTNOTE_DEFINITION", content=div.text.replace("]:. ", "]:")))
      continue
    detail_type = get_detail_type(div_class=div_class)
    if len(details) > 0 and details[-1].type == detail_type:
      details[-1].content = f"{details[-1].content.strip()}  \n{div.text.strip()}\n"
    else:
      details.append(Detail(type=detail_type, content=div.text.strip()))
  return details


def dump_content(source_path, dest_path, title_full, dry_run=False):
  logging.info(f"Dumping {source_path} to {dest_path}. {title_full}")
  soup = scraping.get_soup(source_path)
  
  fix_tags(soup=soup)

  details = parse_body_divs(soup=soup)

  content = content_from_details(details=details)
  
  content = content.replace("⁠", "").replace(" ", "").replace("।।", "॥")
  
  md_file = MdFile(file_path=dest_path)
  
  md_file.dump_to_file(metadata={"title_full": title_full}, content=content, dry_run=dry_run)
  metadata_helper.set_title_from_filename(md_file=md_file, dry_run=dry_run)




def dump_nav_point(nav_point, base_path, index_in=None, dry_run=False):
  parts = nav_point.find_all(name="navPoint", recursive=False)
  content_links = nav_point.find_all(name="content", recursive=False)
  title_in = nav_point.select_one("navLabel>text").text
  index_str = regex.match("[\d०-९]+", title_in)
  padded_index = None
  if index_str is not None:
    index = int(romanize(index_str.group(0)))
    if title_in.endswith("पर्व"):
      padded_index = "%02d" % index
    else:
      padded_index = "%03d" % index
    title = f"{padded_index} " + regex.sub(f"{index_str.group(0)}[- .]+", "", title_in)
  else:
    if index_in is not None:
      title = "%02d %s" % (index_in, title_in)
    else:
      title = title_in
  for index_alt, part in enumerate(parts):
    # if padded_index is None:
    #   title = "%02d %s" % (index_alt + 1, title)
    if regex.match("Mahabharata_Bhag", os.path.basename(base_path)):
      base_path = os.path.dirname(base_path)
    
    dump_nav_point(nav_point=part, base_path=os.path.join(base_path, get_storage_name(title)), index_in=index_alt+1)
  if len(content_links) != 0 and not title.endswith("पर्व"):
    content_src = content_links[0]["src"]
    if padded_index:
      dest_path = os.path.join(base_path, padded_index + ".md")
    else:
      dest_path=os.path.join(base_path, get_storage_name(title) + ".md")
    dump_content(source_path=os.path.join(epub_dir, content_src), dest_path=dest_path, title_full=title, dry_run=dry_run)



def dump_all(toc_xml, base_path, dry_run=False):
  # soup = scraping.get_soup(toc_xml, 'xml')
  # for x in soup.select("navMap>navPoint"):
  #   dump_nav_point(x, base_path=base_path, dry_run=dry_run)
  library.fix_index_files(dir_path=base_path)
  library.fix_index_files(dir_path="/home/vvasuki/vishvAsa/purANam/content/mahAbhAratam/meta/gItA-mudraNAlayAvRttiH")
  pass


if __name__ == '__main__':
  dump_all(toc_xml=os.path.join(epub_dir, "toc.ncx"), base_path="/home/vvasuki/vishvAsa/purANam/content/mahAbhAratam/goraxapura-pAThaH")