import codecs
import glob
import json
import logging
import os
import textwrap

import regex

import doc_curation.md.section
from doc_curation import md
from doc_curation.md import library
from indic_transliteration import sanscript

from doc_curation.md.file import MdFile


static_dir_base = "/home/vvasuki/vishvAsa/vedAH/static/Rk/shAkalam/saMhitA/"
content_dir_base = "/home/vvasuki/vishvAsa/vedAH/content/Rk/shAkalam/saMhitA/"


def dump_content(metadata, content, suukta_id, rk_id, destination_dir, base_dir=static_dir_base, dry_run=False):
  dest_path_Rk = os.path.join(base_dir, destination_dir, suukta_id, sanscript.transliterate(rk_id, sanscript.DEVANAGARI, sanscript.IAST) + ".md")
  md_file = MdFile(file_path=dest_path_Rk)
  import inspect
  md_file.dump_to_file(metadata=metadata, content=inspect.cleandoc(content), dry_run=dry_run)
  md_file.set_filename_from_title(transliteration_source=sanscript.DEVANAGARI, dry_run=dry_run)


def get_include(include_type, suukta_id, file_name_optitrans, field_names=None, classes=None, title=None):
  field_names_str = ""
  if field_names is not None:
    field_names_str = "fieldNames=\"%s\"" % (",".join(field_names))
  classes_str = ""
  if classes is not None:
    classes_str = " ".join(classes)
  extra_attributes = " ".join([field_names_str])
  if title is None:
    title =  sanscript.transliterate(include_type, _from=sanscript.OPTITRANS, _to=sanscript.DEVANAGARI)
  return """<div class="js_include %s" url="%s"  newLevelForH1="3" title="%s" newLevelForH1="3" %s> </div>"""  % (classes_str, os.path.join("/vedAH/Rk/shAkalam/saMhitA/", include_type, suukta_id, file_name_optitrans + ".md"), title, extra_attributes)


def transform(dry_run=False):
  json_paths = glob.glob("/home/vvasuki/sanskrit/raw_etexts/vedaH/Rg/shakala/saMhitA/sAyaNabhAShyam/*/*/*.json", recursive=True)
  suukta_id_to_rk_map = {}
  for json_path in sorted(json_paths):
    with codecs.open(json_path, "r") as fp:
      rk = json.load(fp)
      suukta_id = "%02d/%03d" % (int(rk["classification"]["mandala"]), int(rk["classification"]["sukta"]))
      suukta_rk_map = suukta_id_to_rk_map.get(suukta_id, {})
      bhaashya = regex.sub("<.+?>", "", rk["sayanaBhashya"])
      rk_number = sanscript.transliterate("%02d" % int(rk["classification"]["rik"]), sanscript.IAST, sanscript.DEVANAGARI)
      anukramaNikA_map = {"devataa": rk["attribute"]["devata"], "RShiH": rk["attribute"]["rishi"], "ChandaH": rk["attribute"]["chandas"]}
      padapaatha_lines = rk["padapaatha"]["lines"]
      if isinstance(padapaatha_lines, str):
        padapaatha_lines = [padapaatha_lines]
      samhita_lines = rk["samhitaAux"]["lines"]
      if isinstance(samhita_lines, str):
        samhita_lines = [samhita_lines]
      suukta_rk_map[rk_number] = {"anukramaNikA": anukramaNikA_map, "mantraH": "  \n".join(samhita_lines), "padapAThaH": "  \n".join(padapaatha_lines), "bhAShyam": bhaashya}
      if bhaashya == "":
        logging.warning("No bhAShya for %s", rk["id"])
      suukta_id_to_rk_map[suukta_id] = suukta_rk_map

  for suukta_id in suukta_id_to_rk_map.keys():
    suukta_rk_map = suukta_id_to_rk_map[suukta_id]
    suukta_md = textwrap.dedent("""
    %s
    %s
    """ % ( get_include("jamison_brereton", suukta_id=suukta_id, file_name_optitrans="_index", title="Jamison & Brereton"),
            get_include("jamison_brereton_notes", suukta_id=suukta_id, file_name_optitrans="_index", title="Jamison & Brereton Note", classes=["collapsed"])) )
    for rk_id in sorted(suukta_rk_map.keys()):
      rk_map = suukta_rk_map[rk_id]
      # md_file_Rk = MdFile(file_path=dest_path_Rk)
      from doc_curation import text_data
      title_Rk = text_data.get_rk_title(rk_id=rk_id, rk_text=rk_map["mantraH"])
      title_only_metadata = {"title": title_Rk}
      # dump_content(metadata=metadata, content=rk_map["mantraH"], suukta_id=suukta_id, rk_id=rk_id, destination_dir="mUlam", dry_run=dry_run)
      # dump_content(metadata=metadata, content=rk_map["padapAThaH"], suukta_id=suukta_id, rk_id=rk_id, destination_dir="pada-pAThaH", dry_run=dry_run)
      # rk_map["anukramaNikA"]["title"] = title_Rk
      # dump_content(metadata=rk_map["anukramaNikA"], content="", suukta_id=suukta_id, rk_id=rk_id, destination_dir="anukramaNikA", dry_run=dry_run)
      
      title_optitrans = sanscript.transliterate(data=title_Rk, _from=sanscript.DEVANAGARI, _to=sanscript.OPTITRANS)
      file_name_optitrans = title_optitrans.replace(" ", "_")
      rk_details = textwrap.dedent("""
      ## %s
      %s
      %s
      %s
      %s
      %s
      %s
      %s
      %s
      """) % (
        title_Rk,
        get_include("vishvAsa-prastutiH", suukta_id=suukta_id, file_name_optitrans=file_name_optitrans),
        get_include("mUlam", suukta_id=suukta_id, file_name_optitrans=file_name_optitrans, classes=["collapsed"]),
        get_include("thomson_solcum", suukta_id=suukta_id, file_name_optitrans=file_name_optitrans, classes=["collapsed"], title="Thomson Solcum restoration"),
        get_include("pada-pAThaH", suukta_id=suukta_id, file_name_optitrans=file_name_optitrans, classes=["collapsed"]),
        get_include("anukramaNikA", suukta_id=suukta_id, file_name_optitrans=file_name_optitrans, field_names=["devataa", "RShiH", "ChandaH"], classes=["collapsed"]),
        get_include("sAyaNa-bhAShyam", suukta_id=suukta_id, file_name_optitrans=file_name_optitrans, classes=["collapsed"]),
        get_include("jamison_brereton", suukta_id=suukta_id, file_name_optitrans=file_name_optitrans, classes=["collapsed"], title="Jamison & Brereton"),
        get_include("jamison_brereton_notes", suukta_id=suukta_id, file_name_optitrans=file_name_optitrans, classes=["collapsed"], title="Jamison & Brereton Note"),
      )
      # dump_content(metadata=title_only_metadata, content=rk_details, suukta_id=suukta_id, rk_id=rk_id, base_dir=content_dir_base, destination_dir="sarva-prastutiH", dry_run=dry_run)


      suukta_md = suukta_md + rk_details
    md_file_suukta = MdFile(file_path=os.path.join(content_dir_base, "sarva-prastutiH", suukta_id + ".md"))
    title_suukta = sanscript.transliterate(suukta_id.split("/")[-1], sanscript.IAST, sanscript.DEVANAGARI)
    md_file_suukta.dump_to_file(metadata={"title": title_suukta}, content=suukta_md, dry_run=dry_run)



if __name__ == '__main__':
    transform(dry_run=False)
    md.library.fix_index_files(content_dir_base)