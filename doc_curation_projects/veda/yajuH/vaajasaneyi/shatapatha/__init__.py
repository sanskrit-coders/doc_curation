import csv
import os.path

from doc_curation.md.file import MdFile
from indic_transliteration import sanscript
from tqdm import tqdm

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import section_helper

CONTENT_BASE = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/"

SB_ACCENT = "᳘"
WEBER_EXTRA_ACCENTS = "ॗ"  + "᳟"
WEBER_ACCENTS = SB_ACCENT + WEBER_EXTRA_ACCENTS

def fix_anunaasika(dir_path):
  if "weber" in dir_path:
    library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["ँ"], replacement="ᳫं")
    # Exceptions: 13.1.3 - एॗवैनं स्वगा᳘ 
    library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[f"(?<=[^ᳫ])ं(?=[{WEBER_ACCENTS} ]+[हस])"], replacement="ᳫं")
    library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[f"(?<=[^{WEBER_ACCENTS}])ᳫं([{WEBER_ACCENTS}])"], replacement="\\1ᳫं\\1")


def to_tsv(dir_path, out_path):
  md_files = library.get_md_files_from_path(dir_path=dir_path)
  if not out_path.endswith("tsv"):
    out_path = os.path.join(out_path, os.path.basename(dir_path) + ".tsv")
  os.makedirs(os.path.dirname(out_path), exist_ok=True)
  with open(out_path, 'wt') as out_file:
    tsv_writer = csv.writer(out_file, delimiter='\t')
    for md_file in tqdm(md_files):
      file_id_base = md_file.file_path.replace(os.path.dirname(dir_path) + "/", "").replace(".md", "").replace("/", ".")
      (lines_till_section, sections) = md_file.get_sections()
      for section in sections:
        tsv_writer.writerow([f"{file_id_base}.{sanscript.transliterate(section.title, _to=sanscript.IAST)}", "    ".join(section.lines)])
  pass
