import codecs
import glob
import json
import logging
import os

import regex

import doc_curation.md.section
from doc_curation import md
from doc_curation.md import library
from indic_transliteration import sanscript

from doc_curation.md.file import MdFile


dest_dir_Rks = "/home/vvasuki/vvasuki-git/vedAH/static/Rk/shAkalam/saMhitA/sAyaNa-bhAShyam/"
dest_dir_suuktas = "/home/vvasuki/vvasuki-git/vedAH/content/Rk/shAkalam/saMhitA/sAyaNa-bhAShyam/"


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
      attribute_str = "%s। %s। %s।" % (rk["attribute"]["devata"], rk["attribute"]["rishi"], rk["attribute"]["chandas"])
      padapaatha_lines = rk["padapaatha"]["lines"]
      if isinstance(padapaatha_lines, str):
        padapaatha_lines = [padapaatha_lines]
      samhita_lines = rk["samhitaAux"]["lines"]
      if isinstance(samhita_lines, str):
        samhita_lines = [samhita_lines]
      rk_md = "## अधिमन्त्रम्\n%s\n\n## मन्त्रः\n%s\n\n## पदपाठः\n%s\n\n## भाष्यम्\n%s" % (attribute_str, "  \n".join(samhita_lines), "  \n".join(padapaatha_lines), bhaashya)
      suukta_rk_map[rk_number] = rk_md
      if bhaashya == "":
        logging.warning("No bhAShya for %s", rk["id"])
      suukta_id_to_rk_map[suukta_id] = suukta_rk_map

  for suukta_id in suukta_id_to_rk_map.keys():
    dest_path_suukta = os.path.join(dest_dir_suuktas, suukta_id + ".md")
    md_file_suukta = MdFile(file_path=dest_path_suukta)
    title = sanscript.transliterate(suukta_id.split("/")[-1], sanscript.IAST, sanscript.DEVANAGARI)
    rk_map = suukta_id_to_rk_map[suukta_id]
    suukta_md = ""
    for rk_id in sorted(rk_map.keys()):
      rk_md = rk_map[rk_id]
      dest_path_Rk = os.path.join(dest_dir_Rks, suukta_id, sanscript.transliterate(rk_id, sanscript.DEVANAGARI, sanscript.IAST) + ".md")
      md_file_Rk = MdFile(file_path=dest_path_Rk)
      rk_text = " ".join(doc_curation.md.section.get_section_lines(lines_in=rk_md.split("\n"), section_title="मन्त्रः"))
      from doc_curation import text_data
      title_Rk = text_data.get_rk_title(rk_id=rk_id, rk_text=rk_text)
      md_file_Rk.dump_to_file(metadata={"title": title_Rk}, content=rk_md, dry_run=dry_run)
      md_file_Rk.set_filename_from_title(transliteration_source=sanscript.DEVANAGARI, dry_run=dry_run)
      dest_path_Rk = md_file_Rk.file_path

      suukta_md = suukta_md + """
      
      <div class="js_include" url="%s"  newLevelForH1="2" includeTitle="false"> </div> 
      """ % dest_path_Rk.replace("/home/vvasuki/vvasuki-git", "").replace("static/", "")

    import inspect
    md_file_suukta.dump_to_file(metadata={"title": title}, content=inspect.cleandoc(suukta_md), dry_run=dry_run)



if __name__ == '__main__':
    # transform(dry_run=False)
    md.library.fix_index_files(dest_dir_suuktas)