import os
from collections import OrderedDict
from copy import copy

from curation_utils import scraping
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.scraping import html_scraper
from doc_curation_projects.general_tasks import content_fix
from doc_curation_projects.puraaNa import raamaayana
from doc_curation_projects.puraaNa.raamaayana import dump
from indic_transliteration import sanscript

source_file = "/home/vvasuki/indic-texts/raw_etexts_misc/quasi-hindi/tulasIdAsa/gp_raw/shri-ramchritmanas_marAThI.html"
dest_file = "/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/rAmacharitamAnasa/goraxapura-pATha/marAThy-anuvAda.md"
dest_path = dest_file.replace(".md", "")

detail_map = OrderedDict([
  ("सूचना (हिन्दी)", [""]),
  ("भागसूचना", ["Main-Heading-4", "para-style-override-5"]),
  ("विषय (हिन्दी)", ["Numbers"]),
  ("मूल (चौपाई)", ["Shlok-Color--1-1", "Shlok-Color--1", "Shlok-Color--1-6", "Shlok-Color--1-2", "Shlok-Color--1-4", "Shlok-Color--1-5", "Shlok-Color--1-3"]),
  ("मूल (दोहा)", ["Shlok-Color-2", "Shlok-Color--1",]),
  ("मूल (श्लोक)", ["Shlok-Black"]),
  ("अनुवाद (हिन्दी)", ["TXT", "No-Paragraph-Style"]),
  ("मूलम् (समाप्तिः)", ["Chapter-End-Text", "Chapter-End-Text"]),
  ("अनुवाद (समाप्ति)", []),
  ("पादटिप्पनी", ["Footnotes", "Footnotes-Bold", "Footnotes-bold", "Footnotes-Right-1", "Footnotes-Right"]),
])

format_map = {
  "\n## %s\n\n": ["Heading"],
  "\n### %s\n\n": ["Sub-Heading-1", "Sub-Heading", "Sub-Heading-2", "Sub-Heading-3", "Sub-Heading-6", "Sub-Heading-4", "Sub-Heading-5", "pravachan"],
  "\n#### %s\n\n": ["Shortha-Doha"],
  "\n###### %s\n\n": ["Shlok-Number"],
  "SKIP": ["Page-Break"]
}


def dump_all():
  soup = scraping.get_soup(source_file)
  details = html_scraper.soup_to_details(soup=soup, css_selector="body>p",
                                         get_detail_type=lambda tag_classes: html_scraper.get_detail_type(
                                           tag_classes=tag_classes, detail_map=dict(detail_map, **format_map)))
  content = html_scraper.content_from_details(details=details, format_map=format_map)
  md_file = MdFile(file_path=dest_file)
  md_file.dump_to_file(metadata={"title": "मराठ्यनुवादः"}, content=content, dry_run=False)
    


if __name__ == '__main__':
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  dump_all()
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.dirname(dest_file), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=dest_path, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)
  # library.fix_index_files(dir_path=dest_path, dry_run=False)
  pass
