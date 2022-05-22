import os
from collections import OrderedDict
from copy import copy

from curation_utils import scraping
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.scraping import html_scraper
from doc_curation_projects.puraaNa import raamaayana
from doc_curation_projects.puraaNa.raamaayana import dump
from indic_transliteration import sanscript

source_file = "/home/vvasuki/sanskrit/raw_etexts/purANam/adhyAtma-rAmAyaNam/goraxapura-pAThaH/raw/kannada.html"
dest_file = "/home/vvasuki/vishvAsa/purANam/content/adhyAtma-rAmAyaNam/goraxapura-pAThaH/kannaDAnuvAda.md"
dest_path = dest_file.replace(".md", "")

detail_map = OrderedDict([
  ("ಸೂಚನಾ", ["No-Paragraph-Style", "TXT-Bold", "Title-Page---Tavmewa-Mata", "Shlok-Black"]),
  ("ಭಾಗಸೂಚನಾ", ["description"]),
  ("ಮೂಲಮ್ (ವಾಚನಮ್)", ["Uvach"]),
  ("ಮೂಲಮ್", ["Shlok"]),
  ("ಅನುವಾದ", ["Text", "TXT-Right"]),
  ("ಮೂಲಮ್ (ಸಮಾಪ್ತಿಃ)", ["ChapterEnd"]),
  ("ಅನುವಾದ (ಸಮಾಪ್ತಿಃ)", ["para-style-override-2"]),
  ("ಟಿಪ್ಪನೀ", ["Footnotes-4", "Footnotes", "Footnote-Shloka-1", "Footnotes-1", "Footnote-Shloka", "Footnotes-5", "Footnotes-6", "Footnotes-2", "Footnotes-Right-1", "FootnoteShlok-1"]),
])

format_map = {
  "\n## %s\n\n": ["Chapter-Heading"],
  "\n### %s\n\n": ["Sub-Heading"],
  "\n#### %s\n\n": ["Shlok-Number"],
  "SKIP": ["Page-Break"]
}


def dump_all():
  soup = scraping.get_soup(source_file)
  details = html_scraper.soup_to_details(soup=soup, css_selector="body>p",
                                         get_detail_type=lambda tag_classes: html_scraper.get_detail_type(
                                           tag_classes=tag_classes, detail_map=dict(detail_map, **format_map)))
  content = html_scraper.content_from_details(details=details, format_map=format_map)
  md_file = MdFile(file_path=dest_file)
  md_file.dump_to_file(metadata={"title": "ಕನ್ನಡಾನುವಾದ"}, content=content, dry_run=False)
    


if __name__ == '__main__':
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  # dump_all()
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=dest_file, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(dest_path, "0"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=dest_path, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA)
  # dump.fix_metadata_and_paths(base_dir_ref="/home/vvasuki/vishvAsa/purANam/content/rAmAyaNam/goraxapura-pAThaH/hindy-anuvAdaH", base_dir=dest_path, sarga_identifier=lambda x: os.path.basename(x), dry_run=False)
  library.apply_function(
    fn=MdFile.transform, dir_path=dest_path,
    content_transformer=None,
    metadata_transformer=lambda c, m: metadata_helper.add_value_to_field(m, "unicode_script", "kannada"),
    dry_run=False)
  # library.fix_index_files(dir_path=dest_path, dry_run=False)
  pass
