import codecs
import glob
import json
import logging
import os

import regex
from indic_transliteration import sanscript

from doc_curation.md_helper import MdFile


dest_dir = "/home/vvasuki/vvasuki-git/saMskAra/content/sangrahaH/shAkalA/saMhitA/sAyaNa-bhAShyam/"


def transform():
  json_paths = glob.glob("/home/vvasuki/sanskrit/raw_etexts/veda/Rg/shakala/saMhitA/sAyaNabhAShyam/*/*/*.json", recursive=True)
  suukta_id_to_md = {}
  for json_path in sorted(json_paths):
    with codecs.open(json_path, "r") as fp:
      rk = json.load(fp)
      suukta_id = "%02d/%03d" % (int(rk["classification"]["mandala"]), int(rk["classification"]["sukta"]))
      suukta_md = suukta_id_to_md.get(suukta_id, "")
      bhaashya = regex.sub("<.+?>", "", rk["sayanaBhashya"])
      rk_number = sanscript.transliterate("%02d" % int(rk["classification"]["rik"]), sanscript.IAST, sanscript.DEVANAGARI)
      attribute_str = "%s। %s। %s।" % (rk["attribute"]["devata"], rk["attribute"]["rishi"], rk["attribute"]["chandas"])
      padapaatha_lines = rk["padapaatha"]["lines"]
      if isinstance(padapaatha_lines, str):
        padapaatha_lines = [padapaatha_lines]
      samhita_lines = rk["samhitaAux"]["lines"]
      if isinstance(samhita_lines, str):
        samhita_lines = [samhita_lines]
      rk_md = "%s\n\n%s %s॥\n\n%s\n\n%s" % (attribute_str, "  \n".join(samhita_lines), rk_number, "  \n".join(padapaatha_lines), bhaashya)
      suukta_md += "\n\n%s" % rk_md
      if bhaashya == "":
        logging.warning("No bhAShya for %s", rk["id"])
      suukta_id_to_md[suukta_id] = suukta_md

  for suukta_id in suukta_id_to_md.keys():
    dest_path = os.path.join(dest_dir, suukta_id + ".md")
    md_file = MdFile(file_path=dest_path)
    title = sanscript.transliterate(suukta_id.split("/")[-1], sanscript.IAST, sanscript.DEVANAGARI)
    md_file.dump_to_file(metadata={"title": title}, md=suukta_id_to_md[suukta_id], dry_run=False)



if __name__ == '__main__':
    transform()
    # MdFile.fix_index_files(dest_dir)