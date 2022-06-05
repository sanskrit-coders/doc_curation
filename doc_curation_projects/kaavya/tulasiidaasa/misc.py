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


detail_map = OrderedDict([
  ("सूचना (हिन्दी)", [""]),
  ("भागसूचना", ["Main-Heading-4", "Vishram"]),
  ("विषय (हिन्दी)", ["Numbers"]),
  ("मूल", ["Shlok-Color-2", "Shlok-Color--1", "Sholk-Black"]),
  ("अनुवाद (हिन्दी)", ["TXT", "No-Paragraph-Style", "TXT-Right", "Text"]),
  ("मूलम् (समाप्तिः)", ["Chapter-End-Text", "ChapterEnd1", "eti"]),
  ("अनुवाद (समाप्ति)", ["chapterend2"]),
  ("पादटिप्पनी", ["Footnotes", "Footnotes-Bold", "Footnotes-bold", "Footnotes-Right-1", "Footnotes-Right"]),
])

format_map = {
  "\n## %s\n\n": ["Main-Heading", "Heading"],
  "\n### %s\n\n": ["Sub-Heading-1", "Sub-Heading", "Sub-Heading-2", "Sub-Heading-3", "Sub-Heading-6", "Sub-Heading-4", "Sub-Heading-5", "pravachan"],
  "\n#### %s\n\n": ["Shlok-Number-1", "Shlok-Number--2", "Doha-colour", "Chopai"],
  "\n###### %s\n\n": ["ath"],
  "SKIP": ["Page-Break"]
}


def dump_all(source_file, dest_file):
  soup = scraping.get_soup(source_file)
  details = html_scraper.soup_to_details(soup=soup, css_selector="body>p",
                                         get_detail_type=lambda tag_classes: html_scraper.get_detail_type(
                                           tag_classes=tag_classes, detail_map=dict(detail_map, **format_map)))
  content = html_scraper.content_from_details(details=details, format_map=format_map)
  content = content.replace(":", "ः")
  md_file = MdFile(file_path=dest_file)
  md_file.dump_to_file(metadata={"title": "हिन्द्य्-अनुवादः"}, content=content, dry_run=False)
  metadata_helper.set_title_from_filename(md_file=md_file, transliteration_target=sanscript.DEVANAGARI, dry_run=False)


def hanumaan_baahuka():
  source_file = "/home/vvasuki/indic-texts/raw_etexts_misc/quasi-hindi/tulasIdAsa/gp_raw/hanuman-bahuk.html"
  dest_file = "/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/prakIrNa/hanumAn-bAhuka.md"
  dest_path = dest_file.replace(".md", "")
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  dump_all(source_file=source_file, dest_file=dest_file)


def janki_mangal():
  source_file = "/home/vvasuki/indic-texts/raw_etexts_misc/quasi-hindi/tulasIdAsa/gp_raw/janki-mangal.html"
  dest_file = "/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/prakIrNa/jAnakI-mangala.md"
  dest_path = dest_file.replace(".md", "")
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  dump_all(source_file=source_file, dest_file=dest_file)


def kavitavali():
  source_file = "/home/vvasuki/indic-texts/raw_etexts_misc/quasi-hindi/tulasIdAsa/gp_raw/kavitavali.html"
  dest_file = "/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/prakIrNa/kavitAvalI.md"
  dest_path = dest_file.replace(".md", "")
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  # dump_all(source_file=source_file, dest_file=dest_file)
  library.apply_function(fn=MdFile.split_to_bits, dir_path=dest_file, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)



def paarvatii_mangal():
  source_file = "/home/vvasuki/indic-texts/raw_etexts_misc/quasi-hindi/tulasIdAsa/gp_raw/parvati-mangal.html"
  dest_file = "/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/prakIrNa/pArvatI_mangal.md"
  dest_path = dest_file.replace(".md", "")
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  dump_all(source_file=source_file, dest_file=dest_file)


def raamaajnaa_prashan():
  source_file = "/home/vvasuki/indic-texts/raw_etexts_misc/quasi-hindi/tulasIdAsa/gp_raw/ramagya-prashan.html"
  dest_file = "/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/prakIrNa/rAmAjnA-prashan.md"
  dest_path = dest_file.replace(".md", "")
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  dump_all(source_file=source_file, dest_file=dest_file)


def shrii_krishna_giitaavalii():
  source_file = "/home/vvasuki/indic-texts/raw_etexts_misc/quasi-hindi/tulasIdAsa/gp_raw/srikrishan-gitavali.html"
  dest_file = "/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/prakIrNa/shrI-kRShNa-gItAvalI.md"
  dest_path = dest_file.replace(".md", "")
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  # dump_all(source_file=source_file, dest_file=dest_file)
  library.apply_function(fn=MdFile.split_to_bits, dir_path=dest_file, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)


def vairaagya_sandiipinii():
  source_file = "/home/vvasuki/indic-texts/raw_etexts_misc/quasi-hindi/tulasIdAsa/gp_raw/vairagya-sandipini.html"
  dest_file = "/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/prakIrNa/vairAgya-sandIpinI.md"
  dest_path = dest_file.replace(".md", "")
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  # dump_all(source_file=source_file, dest_file=dest_file)
  library.apply_function(fn=MdFile.split_to_bits, dir_path=dest_file, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)


def dohavali():
  source_file = "/home/vvasuki/indic-texts/raw_etexts_misc/quasi-hindi/tulasIdAsa/gp_raw/dohavali.html"
  dest_file = "/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/prakIrNa/dohAvalI.md"
  dest_path = dest_file.replace(".md", "")
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  # dump_all(source_file=source_file, dest_file=dest_file)


def barve():
  source_file = "/home/vvasuki/indic-texts/raw_etexts_misc/quasi-hindi/tulasIdAsa/gp_raw/barve-ramayan.html"
  dest_file = "/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/prakIrNa/baravai-rAmAyaNa.md"
  dest_path = dest_file.replace(".md", "")
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  # dump_all(source_file=source_file, dest_file=dest_file)
  library.apply_function(fn=MdFile.split_to_bits, dir_path=dest_file, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)


def vinaya_patrikaa():
  source_file = "/home/vvasuki/indic-texts/raw_etexts_misc/quasi-hindi/tulasIdAsa/gp_raw/vinaya-patrikA.html"
  dest_file = "/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/prakIrNa/vinaya-patrikA.md"
  dest_path = dest_file.replace(".md", "")
  # html_scraper.get_class_counts(html=source_file, css_selector="p")
  # dump_all(source_file=source_file, dest_file=dest_file)
  library.apply_function(fn=MdFile.split_to_bits, dir_path=dest_file, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)


if __name__ == '__main__':
  # hanumaan_baahuka()
  # janki_mangal()
  kavitavali()
  # paarvatii_mangal()
  # raamaajnaa_prashan()
  shrii_krishna_giitaavalii()
  vairaagya_sandiipinii()
  barve()
  # dohavali()
  vinaya_patrikaa()
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/prakIrNa", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=dest_path, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI)
  # library.fix_index_files(dir_path=dest_path, dry_run=False)
  pass
