import regex

from doc_curation.md import library
from doc_curation.md.content_processor import include_helper
from doc_curation_projects.veda.yajuH import taittiriiyam

def migrate_and_include_mantras(dir_path):
  library.apply_function(fn=taittiriiyam.migrate_and_include_Rk_details, dir_path=dir_path, dry_run=False, rk_title_pattern="विश्वास-प्रस्तुतिः")
  include_helper.prefill_includes(dir_path=dir_path)

if __name__ == '__main__':
  migrate_and_include_mantras(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/saMhitA/sarva-prastutiH/5/6/01_hiraNyavarNAsh_shuchayaH.md")