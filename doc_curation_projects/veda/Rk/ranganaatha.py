import logging
import os

import regex

from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.content_processor.details_helper import Detail
from doc_curation.md.file import MdFile
from doc_curation_projects.veda import Rk
from indic_transliteration import sanscript

IN_DIR = "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/shAkalam/saMhitA/ranganAthaH"

def prep_details(in_dir=IN_DIR):
  def _content_fixer(content, *args, **kwargs):
    def _detail_maker(match):
      local_title = f"रङ्गनाथः - {match.group(1)}"
      detail = Detail(title=local_title, content=match.group(5).strip())
      return f"{match.group(1)}\n\n{detail.to_md_html()}\n\n"
    content = regex.sub(r"(([०-९]+)\.([०-९]+)\.०*([०-९]+)) *\n+([^<]+?[।॥ ]+\4॥) *\n", _detail_maker, content)
    return content
    
  library.apply_function(fn=MdFile.transform, dir_path=in_dir, content_transformer=_content_fixer)


def export_to_files():
  rk_id_to_name = Rk.get_Rk_id_to_name_map_from_muulam()
  def _content_fixer(content, *args, **kwargs):
    if "MISSING" in content:
      return 
    details = details_helper.get_details(content=content, title=".*")
    for detail_tag, detail in details:
      id = detail.title.split(" - ")[-1]
      id_parts = [sanscript.transliterate(x, _from=sanscript.DEVANAGARI, _to=sanscript.IAST)   for x in id.split(".")]
      id_parts = [int(x) for x in id_parts]
      id_fixed = f"{id_parts[0]:02}/{id_parts[1]:03}/{id_parts[2]:02}"
      dest_name = rk_id_to_name[id_fixed]
      dest_path = os.path.join(Rk.commentary_base, f"{id_parts[0]:02}/{id_parts[1]:03}/{dest_name}.md")
      if not os.path.exists(dest_path):
        logging.fatal(f"File {dest_path} does not exist, skipping.")
        exit(1)
      md_file = MdFile(file_path=dest_path)
      md_file.replace_content_metadata(new_content=lambda c, *args, **kwargs: details_helper.insert_duplicate_adjascent(content=c, old_title_pattern="सायण-भा(.*)", new_title="रङ्गनाथः", content_transformer=lambda c: detail.content.replace("\n", " "), *args, **kwargs), dry_run=False)
    return details_helper.detail_remover(content=content, title="रङ्गनाथः.*")

  library.apply_function(fn=MdFile.transform, dir_path=IN_DIR, content_transformer=_content_fixer)

def check_completeness():
  library.list_files_with_missing_details(src_dir=Rk.commentary_base, detail_title="रङ्गनाथः.*")


def add_meta(in_dir=IN_DIR):
  def _content_fixer(content, *args, **kwargs):
    if "MISSING" in content:
      return
    data = regex.sub(r"\n[^\n]+[॒॑][\s\S]+", "", content).strip().replace("\n", " ")
    metadata = kwargs.get('metadata', None)
    path_ints = [int(x.replace(".md", "")) for x in metadata["_file_path"].split("/")[-2:]]
    dest_path = os.path.join(Rk.commentary_base, f"{path_ints[0]:02}/{path_ints[1]:03}/_index.md")
    if not os.path.exists(dest_path):
      logging.fatal(f"File {dest_path} does not exist, skipping.")
      return content
    md_file = MdFile(file_path=dest_path)
    def _append_detail(content, *args, **kwargs):
      detail = details_helper.Detail(title="रङ्गनाथः", content=data)
      return f"{content}\n\n{detail.to_md_html()}\n"
    md_file.replace_content_metadata(new_content=_append_detail, dry_run=False)
    return regex.sub(r"[^॒॑]+?(?=\n[^\n]+[॒॑][\s\S]+)", "", content, count=1).strip()
  library.apply_function(fn=MdFile.transform, dir_path=IN_DIR, content_transformer=_content_fixer)



if __name__ == '__main__':
  pass
  # prep_details()
  # export_to_files()
  # check_completeness()
  add_meta()

