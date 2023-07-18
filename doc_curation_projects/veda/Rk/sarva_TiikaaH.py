import logging
import os
import shutil
from pathlib import Path

import regex

from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import combination
from doc_curation_projects.veda import Rk

STATIC_ROOT = "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA"
TIKA_BASE = os.path.join(STATIC_ROOT, "sarvASh_TIkAH")


def fix_bare_Rk_files():
  source_paths = sorted(Path(TIKA_BASE).glob("**/*.md"))
  source_paths = [str(f) for f in source_paths if regex.match(".+/\d\d_.+\.md$", str(f))]
  rk_id_to_name = Rk.get_Rk_id_to_name_map_from_muulam()
  for source_path in source_paths:
    md_file = MdFile(file_path=source_path)
    details = details_helper.extract_detail_tags_from_file(md_file=md_file)
    Rk_id_numerical = Rk.rk_id_from_path(source_path)
    if Rk_id_numerical not in rk_id_to_name:
      logging.warning(f"{Rk_id_numerical} not found. Skipping.")
      continue
    dest_md_file_path = os.path.join(os.path.dirname(source_path), rk_id_to_name[Rk_id_numerical] + ".md")
    assert os.path.exists(dest_md_file_path), source_path
    assert len(details) == 1, source_path
    assert details[0].select_one("summary").text == "+Jamison Brereton Notes", source_path
    dest_md_file = MdFile(file_path=dest_md_file_path)
    dest_md_file.transform(content_transformer=lambda c, m: details_helper.insert_adjascent_detail(content=c, metadata=m, title="+Jamison Brereton", new_element=details[0]))
    os.remove(source_path)


def combine():
  subpaths = ["thomson_solcum", "vedaweb_annotation", "pada-pAThaH", "hellwig_grammar", "anukramaNikA", "sAyaNa-bhAShyam", "wilson", "jamison_brereton", "jamison_brereton_notes", "griffith", "oldenberg", "macdonell", "geldner", "grassmann", "elizarenkova"]
  subpaths = [os.path.join(STATIC_ROOT, subpath) for subpath in subpaths]

  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(STATIC_ROOT, "sarvAH_TIkAH"), dry_run=False)


def update_commentary(commentary_dir, commentary_name, dry_run=False):
  dest_paths = sorted(Path(TIKA_BASE).glob("**/*.md"))
  dest_paths = [str(f) for f in dest_paths if regex.match(".+/\d\d_.+\.md$", str(f))]
  # rk_id_to_name = Rk.get_Rk_id_to_name_map_from_muulam()
  for dest_path in dest_paths:
    source_path = dest_path.replace("sarvASh_TIkAH", commentary_dir)
    if not os.path.exists(source_path):
      logging.warning(f"Skipping {source_path}")
      continue
    source_md = MdFile(file_path=source_path)
    (metadata, content) = source_md.read()
    md_file = MdFile(file_path=dest_path)
    md_file.transform(content_transformer=lambda c, m: details_helper.transform_details_with_soup(content=c, metadata=m, transformer=details_helper.detail_content_replacer_soup, title=commentary_name, new_text=content), dry_run=dry_run)


def sanaatana_adhimantra():
  dest_paths = sorted(Path(TIKA_BASE).glob("**/*.md"))
  dest_paths = [str(f) for f in dest_paths if regex.match(".+/\d\d_.+\.md$", str(f))]
  # rk_id_to_name = Rk.get_Rk_id_to_name_map_from_muulam()
  for dest_path in dest_paths:
    md_file = MdFile(file_path=dest_path)
    (metadata, content) = md_file.read()
    detail_content = "\n- देवता - " + metadata["devataa"]
    detail_content += "\n- ऋषिः - " + metadata["RShiH"]
    detail_content += "\n- छन्दः - " + metadata["ChandaH"]
    detail = details_helper.Detail(title="अधिमन्त्रम् - sa", content=detail_content)
    content = f"{detail.to_md_html()}\n\n{content}"
    md_file.dump_to_file(metadata=metadata, content=content, dry_run=False)


if __name__ == '__main__':
  pass
  # update_commentary(commentary_dir="vedaweb_annotation", commentary_name="Vedaweb annotation")
  sanaatana_adhimantra()
  # fix_bare_Rk_files()