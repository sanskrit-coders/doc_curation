import os
import textwrap

import doc_curation.md.content_processor.include_helper
from doc_curation.md.content_processor import include_helper
from doc_curation_projects.veda.Rk import json_lib
from doc_curation.utils import text_utils
from doc_curation.md import library
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

static_dir_base = "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/"
content_dir_base = "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content/shAkalam/saMhitA/"


def dump(dry_run, start_id=None):
  suukta_id_to_rk_map = json_lib.get_suukta_id_to_rk_map()
  for suukta_id in suukta_id_to_rk_map.keys():
    if start_id is not None and suukta_id < start_id:
      continue
    suukta_rk_map = suukta_id_to_rk_map[suukta_id]
    suukta_md = textwrap.dedent("""
    %s
    """ % (
      get_include("sarvASh_TIkAH", suukta_id=suukta_id, file_name_optitrans="_index.md",                   h1_level=2)))

    for rk_id in sorted(suukta_rk_map.keys()):
      rk_map = suukta_rk_map[rk_id]
      # md_file_Rk = MdFile(file_path=dest_path_Rk)
      title_Rk = text_utils.title_from_text(title_id=rk_id, text=rk_map["mantraH"], target_title_length=None)
      title_Rk += " - " + rk_map["ChandaH"]
      # dump_content(metadata=metadata, content=rk_map["mantraH"], suukta_id=suukta_id, rk_id=rk_id, destination_dir="mUlam", dry_run=dry_run)
      # dump_content(metadata=metadata, content=rk_map["padapAThaH"], suukta_id=suukta_id, rk_id=rk_id, destination_dir="pada-pAThaH", dry_run=dry_run)
      # rk_map["anukramaNikA"]["title"] = title_Rk
      # dump_content(metadata=rk_map["anukramaNikA"], content="", suukta_id=suukta_id, rk_id=rk_id, destination_dir="anukramaNikA", dry_run=dry_run)

      muula_file_path = \
      [x for x in os.listdir(os.path.join(static_dir_base, "mUlam", suukta_id)) if x.startswith(rk_id)][0]
      file_name_optitrans = os.path.basename(muula_file_path)
      rk_details = "\n\n## %s" % (title_Rk)
      rk_details += "\n%s" % get_include("vishvAsa-prastutiH", suukta_id=suukta_id,
                                         file_name_optitrans=file_name_optitrans, h1_level=3)
      rk_details += "\n%s" % get_include("mUlam", suukta_id=suukta_id, file_name_optitrans=file_name_optitrans,
                                         classes=["collapsed"], h1_level=3)
      rk_details += "\n%s" % get_include("sarvASh_TIkAH", suukta_id=suukta_id, file_name_optitrans=file_name_optitrans, h1_level=3)

      # dump_content(metadata=title_only_metadata, content=rk_details, suukta_id=suukta_id, rk_id=rk_id, base_dir=content_dir_base, destination_dir="sarva-prastutiH", dry_run=dry_run)

      suukta_md = suukta_md + rk_details
    md_file_suukta = MdFile(file_path=os.path.join(content_dir_base, "sarva-prastutiH", suukta_id + ".md"))
    title_suukta = sanscript.transliterate(suukta_id.split("/")[-1], sanscript.IAST, sanscript.DEVANAGARI)
    md_file_suukta.dump_to_file(metadata={"title": title_suukta}, content=suukta_md, dry_run=dry_run)


def get_include(include_type, suukta_id, file_name_optitrans, h1_level, field_names=None, classes=None, title=None, ):
  if title is None:
    title = sanscript.transliterate(include_type.replace("_", " "), _from=sanscript.OPTITRANS, _to=sanscript.DEVANAGARI)
  file_path = os.path.join(static_dir_base, include_type, suukta_id, file_name_optitrans)
  if not os.path.exists(file_path):
    return ""
  return include_helper.Include(field_names=field_names, classes=classes, title=title,
                                                                      url=os.path.join("/vedAH_Rk/shAkalam/saMhitA/", include_type, suukta_id,
                                              file_name_optitrans), h1_level=h1_level).to_html_str()


if __name__ == '__main__':
  dump(dry_run=False)
  include_helper.prefill_includes(dir_path=os.path.join(content_dir_base, "sarva-prastutiH"))

  # md.library.fix_index_files(content_dir_base)
