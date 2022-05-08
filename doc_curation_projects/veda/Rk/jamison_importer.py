import logging
import os

import regex

import doc_curation_projects.veda.Rk
from doc_curation_projects import veda
from doc_curation.md.file import MdFile

path_notes = "/home/vvasuki/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/jamison_brereton_notes"
thomson_solcum_dir = "/home/vvasuki/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/thomson_solcum"


def separate_commentaries(dest_path, dry_run=True):
  Rk_id_to_name_map = doc_curation_projects.veda.Rk.get_Rk_id_to_name_map_from_muulam()
  for id in Rk_id_to_name_map.keys():
    Rk_number_str = id.split("/")[-1]
    sUkta_id = "/".join(id.split("/")[:-1])
    file_path = os.path.join(dest_path, id + ".md")
    file_path_new = os.path.join(dest_path, "/".join(id.split("/")[:-1]), Rk_id_to_name_map[id] + ".md")
    if not os.path.exists(file_path) and not os.path.exists(file_path_new):
      prior_rk_number = int(Rk_number_str) - 1
      prior_Rk_file = "%s/%02d" % (sUkta_id, prior_rk_number) + ".md"
      prior_Rk_file = prior_Rk_file.replace("00.md", "_index.md")
      logging.info("Missing: %s Check: %s" % (id + ".md", prior_Rk_file))
      prior_Rk_file_path = os.path.join(dest_path, prior_Rk_file)
      prior_md_file = MdFile(file_path=prior_Rk_file_path)
      [metadata, content] = prior_md_file.read()
      translation_parts = regex.split(pattern="\d+\. ", string=content)
      if prior_Rk_file.endswith("_index.md"):
        translation_parts = content.split(" 1. ")
        # exit()
      for index, translation in enumerate(translation_parts):
        if index == 0:
          Rk_file_path = prior_Rk_file_path # Could be _index.md
        else:
          Rk_file = "%s/%02d" % (sUkta_id, prior_rk_number + index) + ".md"
          Rk_file_path = os.path.join(dest_path, Rk_file)
        md_file = MdFile(file_path=Rk_file_path)
        metadata = {"title": "%02d" % (prior_rk_number  + index)} 
        logging.debug(translation)
        md_file.dump_to_file(metadata=metadata, content=translation, dry_run=dry_run)


if __name__ == '__main__':
  doc_curation_projects.veda.Rk.fix_Rk_file_names(dest_path=thomson_solcum_dir, ignore_missing=False, dry_run=False)
  # separate_commentaries(dry_run=False)
  # def include_generator(file_path):
  #   return """<div class="js_include" url="%s"  newLevelForH1="3" newLevelForH1="2" includeTitle="true"> </div>"""  % (regex.sub(".+/vedAH/static/", "/vedAH/", file_path))
  # veda.include_multi_suukta_comments(dest_path=path_notes, include_generator=include_generator, dry_run=False)
  pass
