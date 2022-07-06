import logging
import os
import shutil
from pathlib import Path

import regex

from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import combination
from doc_curation_projects.veda import Rk

STATIC_ROOT = "/home/vvasuki/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA"



def fix_bare_Rk_files():
  source_paths = sorted(Path("/home/vvasuki/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH").glob("**/*.md"))
  source_paths = [str(f) for f in source_paths if regex.match(".+/\d\d\.md$", str(f))]
  rk_id_to_name = Rk.get_Rk_id_to_name_map_from_muulam()
  for source_path in source_paths:
    md_file = MdFile(file_path=source_path)
    details = details_helper.extract_details_from_file(md_file=md_file)
    Rk_id_numerical = Rk.rk_id_from_path(source_path)
    if Rk_id_numerical not in rk_id_to_name:
      logging.warning(f"{Rk_id_numerical} not found. Skipping.")
      continue
    dest_md_file_path = os.path.join(os.path.dirname(source_path), rk_id_to_name[Rk_id_numerical] + ".md")
    assert os.path.exists(dest_md_file_path), source_path
    assert len(details) == 1, source_path
    assert details[0].select_one("summary").text == "+Jamison Brereton Notes", source_path
    dest_md_file = MdFile(file_path=dest_md_file_path)
    dest_md_file.transform(content_transformer=lambda c, m: details_helper.insert_after_detail(content=c, metadata=m, title="+Jamison Brereton", new_element=details[0]))
    os.remove(source_path)


def combine():
  subpaths = ["thomson_solcum", "vedaweb_annotation", "pada-pAThaH", "hellwig_grammar", "anukramaNikA", "sAyaNa-bhAShyam", "wilson", "jamison_brereton", "jamison_brereton_notes", "griffith", "oldenberg", "macdonell", "geldner", "grassmann", "elizarenkova"]
  subpaths = [os.path.join(STATIC_ROOT, subpath) for subpath in subpaths]

  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(STATIC_ROOT, "sarvAH_TIkAH"), dry_run=False)


if __name__ == '__main__':
  fix_bare_Rk_files()