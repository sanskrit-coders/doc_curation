import glob
import logging
import os

import regex

import doc_curation.md.content_processor.include_helper
from doc_curation.md import library
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.content_processor.include_helper import get_include
from doc_curation.md.library import arrangement
from doc_curation_projects.veda.atharva import paippalaadam
from indic_transliteration import sanscript

import os
import textwrap

import doc_curation.md.content_processor.include_helper
from doc_curation.md.content_processor import include_helper
from doc_curation.utils import text_utils
from doc_curation.md import library
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript


def dump(dry_run, start_id=None):
  suukta_id_to_rk_map = paippalaadam.get_suukta_id_to_rk_map()
  for suukta_id, Rk_ids in suukta_id_to_rk_map.items():
    if start_id is not None and suukta_id < start_id:
      continue
    suukta_md = textwrap.dedent("""
    %s
    """ % (
      get_include("sarvASh_TIkAH", suukta_id=suukta_id, file_name_optitrans="_index.md", h1_level=2)))

    for rk_id in Rk_ids:
      muula_file_path = os.path.join(paippalaadam.MULA_DIR, rk_id)
      muula_md = MdFile(file_path=muula_file_path)
      (metadata, _) = muula_md.read()
      file_name_optitrans = os.path.basename(muula_file_path)
      rk_details = "\n\n## %s" % (metadata["title"])
      rk_details += "\n%s" % get_include("vishvAsa-prastutiH", suukta_id=suukta_id,
                                         file_name_optitrans=file_name_optitrans, h1_level=3)
      rk_details += "\n%s" % get_include("mUlam", suukta_id=suukta_id, file_name_optitrans=file_name_optitrans,
                                         classes=["collapsed"], h1_level=3)
      rk_details += "\n%s" % include_helper.Include("sarvASh_TIkAH", suukta_id=suukta_id, file_name_optitrans=file_name_optitrans, classes=["collapsed"], h1_level=3).to_html_str()

      # dump_content(metadata=title_only_metadata, content=rk_details, suukta_id=suukta_id, rk_id=rk_id, base_dir=paippalaadam.CONTENT_DIR, destination_dir="sarva-prastutiH", dry_run=dry_run)

      suukta_md = suukta_md + rk_details
    md_file_suukta = MdFile(file_path=os.path.join(paippalaadam.CONTENT_DIR, suukta_id + ".md"))
    title_suukta = sanscript.transliterate(suukta_id.split("/")[-1], sanscript.IAST, sanscript.DEVANAGARI)
    md_file_suukta.dump_to_file(metadata={"title": title_suukta}, content=suukta_md, dry_run=dry_run)


def get_include(include_type, suukta_id, file_name_optitrans, h1_level, field_names=None, classes=None, title=None, ):
  if title is None:
    title = sanscript.transliterate(include_type.replace("_", " "), _from=sanscript.OPTITRANS, _to=sanscript.DEVANAGARI)
  file_path = os.path.join(paippalaadam.SAMHITA_DIR_STATIC, include_type, suukta_id, file_name_optitrans)
  if not os.path.exists(file_path):
    return ""
  return include_helper.Include(field_names=field_names, classes=classes,
                                                                      title=title,
                                                                      url=os.path.join("/vedAH/atharva/paippalAdam/saMhitA/",
                                                                                       include_type, suukta_id,
                                                                                       file_name_optitrans).to_html_str(),
                                                                      h1_level=h1_level)


if __name__ == '__main__':
  dump(dry_run=False)
  include_helper.prefill_includes(dir_path=paippalaadam.CONTENT_DIR)

  # library.fix_index_files(paippalaadam.CONTENT_DIR)

