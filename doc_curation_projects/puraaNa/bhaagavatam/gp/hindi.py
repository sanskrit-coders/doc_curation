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

source_file = "/home/vvasuki/sanskrit/raw_etexts/purANam/bhAgavata-purANam/goraxapura-pAThaH/raw/hindI.html"
dest_file = "/home/vvasuki/gitland/vishvAsa/purANam/content/bhAgavatam/goraxapura-pAThaH/hindy-anuvAdaH.md"
dest_path = dest_file.replace(".md", "")

detail_map = OrderedDict([
  ("सूचना (हिन्दी)", [""]),
  ("भागसूचना", ["Sub-Head-2"]),
  ("विषय (हिन्दी)", ["Numbers"]),
  ("मूलम् (वचनम्)", ["Uwach"]),
  ("मूलम्", ["Shlok-Color-2", "SHLOK-Black", "Gadya", "mantra", "Tavmev-Mata--pita", "TitlePage-Shlok", "Basic-Paragraph"]),
  ("अनुवाद (हिन्दी)", ["TXT", "TXT-Right"]),
  ("मूलम् (समाप्तिः)", ["para-style-override-5"]),
  ("अनुवाद (समाप्ति)", ["Chapter-End-Text"]),
  ("पादटिप्पनी", ["Footnotes", "Footnotes-Bold", "Footnotes-bold", "Footnotes-Right-1", "Footnotes-Right"]),
])

format_map = {
  "\n## %s\n\n": ["Heading"],
  "\n### %s\n\n": ["Nayash", "Sub-Heading"],
  "\n#### %s\n\n": ["Numbers", "Sub-Head-2"],
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
  md_file.dump_to_file(metadata={"title": "हिन्द्यनुवादः"}, content=content, dry_run=False)
    


if __name__ == '__main__':
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  # dump_all()
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.dirname(dest_file), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=dest_path, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)
  # library.shift_indices(dir_path=os.path.join(dest_path, "02_dvitIyaH_skandhaH"), start_index=3, new_index_offset=-1)
  # library.shift_indices(dir_path=os.path.join(dest_path, "05_panchamaH_skandhaH"), start_index=9, new_index_offset=1)
  
  # content_fix.devanaagarify(dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/bhAgavatam/goraxapura-pAThaH/hindy-anuvAdaH/05_panchamaH_skandhaH/09_oMbhattaneya_adhyAya.md", source_script=sanscript.KANNADA)
  # content_fix.devanaagarify(dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/bhAgavatam/goraxapura-pAThaH/hindy-anuvAdaH/05_panchamaH_skandhaH/23_ippattamUraneya_adhyAya.md", source_script=sanscript.KANNADA)
  # content_fix.devanaagarify(dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/bhAgavatam/goraxapura-pAThaH/hindy-anuvAdaH/05_panchamaH_skandhaH/25_ippattaidaneya_adhyAya.md", source_script=sanscript.KANNADA)
  library.apply_function(dir_path=dest_path, fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)

  # library.shift_indices(dir_path=os.path.join(dest_path, "10b_dashamaH_skandhaH_uttarArdhaH"), start_index=1, new_index_offset=49)
  # library.fix_index_files(dir_path=dest_path, dry_run=False)
  pass
