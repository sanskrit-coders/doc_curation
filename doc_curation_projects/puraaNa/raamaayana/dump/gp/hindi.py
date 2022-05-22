import os
from collections import OrderedDict
from copy import copy

from curation_utils import scraping
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.scraping import html_scraper
from doc_curation_projects.puraaNa import raamaayana
from doc_curation_projects.puraaNa.raamaayana import dump
from indic_transliteration import sanscript

source_file = "/home/vvasuki/vishvAsa/purANam/static/rAmAyaNam/goraxapura-pAThaH/raw/hindi.html"
dest_file = "/home/vvasuki/vishvAsa/purANam/content/rAmAyaNam/goraxapura-pAThaH/hindy-anuvAdaH.md"
dest_path = dest_file.replace(".md", "")

detail_map = OrderedDict([
  ("सूचना (हिन्दी)", [""]),
  ("भागसूचना", ["Numbers"]),
  ("विषय (हिन्दी)", ["Numbers"]),
  ("मूलम् (वचनम्)", ["Uwach"]),
  ("मूलम्", ["Shlok-Color-2", "SHLOK-Black", "SHLOK-Black-1"]),
  ("अनुवाद (हिन्दी)", ["TXT", "TXT-Right"]),
  ("मूलम् (समाप्तिः)", ["para-style-override-5"]),
  ("अनुवाद (समाप्ति)", ["Chapter-End-Text"]),
  ("पादटिप्पनी", ["Footnotes", "Footnotes-Bold", "Footnotes-Right-1"]),
])

format_map = {
  "\n## %s\n\n": ["Heading"],
  "\n### %s\n\n": ["Nayash", "Sub-Heading"],
  "SKIP": ["Page-Break-1"]
}


def dump_all():
  soup = scraping.get_soup(source_file)
  details = html_scraper.soup_to_details(soup=soup, css_selector="body>p",
                                         get_detail_type=lambda tag_classes: html_scraper.get_detail_type(
                                           tag_classes=tag_classes, detail_map=dict(detail_map, **format_map)))
  content = html_scraper.content_from_details(details=details, format_map=format_map)
  md_file = MdFile(file_path=dest_file)
  md_file.dump_to_file(metadata={"title": "हिन्द्यनुवादः"}, content=content, dry_run=False)
    


if __name__ == '__main__':
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  # dump()
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.dirname(dest_file), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)
  # library.shift_indices(dir_path=os.path.join(dest_path, "7_uttarakANDam"), start_index=62, new_index_offset=-2)
  # library.shift_indices(dir_path=os.path.join(dest_path, "3_araNyakANDam"), start_index=58, new_index_offset=-1)
  # library.shift_indices(dir_path=os.path.join(dest_path, "5_sundarakANDam"), start_index=44, new_index_offset=1)
  # dump.update_from_spreadsheet_data(doc_data=raamaayana.get_doc_data(), base_dir=dest_path, dry_run=False)
  # dump.fix_metadata_and_paths(base_dir_ref="/home/vvasuki/vishvAsa/purANam/content/rAmAyaNam/goraxapura-pAThaH/kannaDAnuvAda", base_dir=dest_path, sarga_identifier=lambda x: os.path.basename(x), dry_run=False)
  # library.fix_index_files(dir_path=dest_path, dry_run=False)
  pass
