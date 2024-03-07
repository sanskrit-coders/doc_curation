import regex

from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.content_processor import include_helper
from doc_curation_projects.veda.yajuH import taittiriiyam

def migrate_and_include_mantras(dir_path):
  library.apply_function(fn=taittiriiyam.migrate_and_include_Rk_details, dir_path=dir_path, dry_run=False, rk_title_pattern="विश्वास-प्रस्तुतिः - ऋक्")
  include_helper.prefill_includes(dir_path=dir_path)

def fix_includes(dir_path):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_helper.old_include_remover, url_to_exclude=".+vishvAsa.+"))
  def include_fixer(x, current_file_path, *args):
    return include_helper.alt_include_adder(x, current_file_path, source_dir="vishvAsa-prastutiH", alt_dirs=["mUlam","sarvASh_TIkAH"])

  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_fixer))
  include_helper.prefill_includes(dir_path=dir_path)


if __name__ == '__main__':
  # fix_includes(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/brAhmaNam/sarva-prastutiH/1/5/08_atharva-shira-iShTakAH_indro_dadhIcho.md")
  # migrate_and_include_mantras(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/saMhitA/sarva-prastutiH/3/4/04_jayahomamantrAH_tatprashaMsA_cha.md")

  include_helper.prefill_includes(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/paddhatiH/shrIvaiShNavaH/shrInivAsa-deshikaH/01_pUrva-prayogaH/01_angAni/02_udakashAntiH/06_japaH.md")
  pass
