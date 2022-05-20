import collections
import os
from copy import copy

import regex

from curation_utils import scraping
from curation_utils.file_helper import get_storage_name
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.scraping.html_scraper import souper, soup_to_details, get_detail_type
from doc_curation_projects.puraaNa import mahaabhaarata
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
  "मूलम्": ["class_182", "class_183", "class_24", "class_258", "class_33", "class_54", "class_57", "class_66", "class_67", ] + ["class_14", "class_15", "class_18", "class_220", "class_246", "class_294", "class_295", "class_329", "class_386", "class_77", "class_81"] + ["class_244"],
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
    if tag.string is None:
      logging.warning(f"Check {tag}")
    else:
      tag.string.replace_with(f"'''{tag.text}'''")


  tags = souper.get_tags_matching_css(soup=soup, css_selector_list=css_selector_list(format_map["telling_hindi"]))
  for tag in tags:
    tag.string.replace_with(f"_{tag.text}_ ")


def content_from_details(details):
  content = ""
  for detail in details:
    if detail.type == "footnote_definition":
      content += "\n" + detail.content.replace("]:. ", "]:") + "\n"
    elif detail.type == "caption":
      continue
    else:
      if detail.type == "मूलम्":
        detail_vishvaasa = copy(detail)
        detail_vishvaasa.type = "विश्वास-प्रस्तुतिः"
        content += "\n" + detail_vishvaasa.to_html() + "\n"
      content += "\n" + detail.to_html() + "\n"
  return content


def get_content(source_path):
  soup = scraping.get_soup(source_path)
  
  fix_tags(soup=soup)

  details = soup_to_details(soup=soup, css_selector="body>div", get_detail_type=lambda tag_classes: get_detail_type(tag_classes=tag_classes, detail_map=dict(detail_map, **format_map)))

  content = content_from_details(details=details)
  
  content = content.replace("⁠", "").replace(" ", "").replace("।।", "॥")
  
  return content


def dump_nav_point(nav_point, toc_to_opf_contents, base_path, urls=None, index_in=None, dry_run=False):
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
    
    dump_nav_point(nav_point=part, toc_to_opf_contents=toc_to_opf_contents, base_path=os.path.join(base_path, get_storage_name(title)), urls=urls, index_in=index_alt+1)
  if len(content_links) != 0 and not title.endswith("पर्व"):
    content_src = scraping.clean_url(content_links[0]["src"])
    if urls is not None and content_src not in urls:
      return 
    if padded_index:
      dest_path = os.path.join(base_path, padded_index + ".md")
    else:
      dest_path=os.path.join(base_path, get_storage_name(title) + ".md")
    logging.info(f"Dumping {content_src} to {dest_path}. {title}")
    content = get_content(source_path=os.path.join(epub_dir, content_src))
    for additional_content_src in toc_to_opf_contents[content_src]:
      logging.info(f"Additional {additional_content_src}")
      content += "\n\n" + get_content(source_path=os.path.join(epub_dir, additional_content_src))
    md_file = MdFile(file_path=dest_path)
    md_file.dump_to_file(metadata={"title_full": title}, content=content, dry_run=dry_run)
    metadata_helper.set_title_from_filename(md_file=md_file, dry_run=dry_run)



def dump_all(base_path, urls=None, dry_run=False):
  soup_toc = scraping.get_soup(os.path.join(epub_dir, "toc.ncx"), 'xml')
  toc_content_srcs = [scraping.clean_url(x["src"]) for x in soup_toc.select("content")]
  soup_opf = scraping.get_soup(os.path.join(epub_dir, "content.opf"), 'xml')
  opf_content_srcs = [scraping.clean_url(x["href"]) for x in soup_opf.select("item") if "xhtml" in x["media-type"]]
  toc_to_opf_contents = collections.defaultdict(list)
  current_toc_src = ""
  for src in opf_content_srcs:
    if src in toc_content_srcs:
      current_toc_src = src
    else:
      toc_to_opf_contents[current_toc_src].append(src)

  for x in soup_toc.select("navMap>navPoint"):
    dump_nav_point(nav_point=x, toc_to_opf_contents=toc_to_opf_contents, base_path=base_path, urls=urls, dry_run=dry_run)
  # library.fix_index_files(dir_path=base_path)
  # library.fix_index_files(dir_path="/home/vvasuki/vishvAsa/purANam/content/mahAbhAratam/meta/gItA-mudraNAlayAvRttiH")
  pass


def check_toc():
  soup_toc = scraping.get_soup(os.path.join(epub_dir, "toc.ncx"), 'xml')
  previous_parva = None
  for text in soup_toc.select("text"):
    parva_match = regex.match("[०-९]+", text.string)
    if parva_match is None:
      continue
    parva = int(sanscript.transliterate(parva_match.group(0), _from=sanscript.DEVANAGARI, _to=sanscript.OPTITRANS))
    if parva == 1:
      previous_parva = parva
      continue
    if parva != previous_parva + 1:
      logging.warning(f"Check {text.string} Previous Parva: {previous_parva}")
    previous_parva = parva


if __name__ == '__main__':
  pass
  missing_navpoints = ["2/OEBPS/part0385_u2.xhtml", "2/OEBPS/part0393_u3.xhtml", "2/OEBPS/part0395_u2.xhtml", "2/OEBPS/part0404_u3.xhtml", "6/OEBPS/part0102.xhtml", "6/OEBPS/part0110_u1.xhtml"]
  dump_all(base_path=mahaabhaarata.PATH_GP, urls=missing_navpoints)
  # check_toc()