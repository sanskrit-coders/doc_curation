import os
import shutil

from doc_curation_projects.veda import Rk
from doc_curation.md import library
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


def fix_purusha_suukta():
  comment_dirs = ["vishvAsa-prastutiH", "mUlam", "pada-pAThaH", "anukramaNikA", "sAyaNa-bhAShyam",  "jamison_brereton", "griffith", "thomson_solcum"]
  comment_dirs = ["thomson_solcum"]
  for dir in comment_dirs:
    dir_path = "/home/vvasuki/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/%s/10/090/" % dir
    # library.shift_indices(dir_path=dir_path, start_index=9, new_index_offset=1, end_index=14, dry_run=False)
    # shutil.move("%s/08_tasmAdyajnAtsarvahutaH_sambhRtaM.md" % dir_path, "%s/09_tasmAdyajnAtsarvahutaH_sambhRtaM.md" % dir_path)
    library.apply_function(dir_path=dir_path, fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)


if __name__ == '__main__':
  # fix_purusha_suukta()
  Rk.fix_Rk_file_names(os.path.join(Rk.SAMHITA_DIR_STATIC, "geldner"), dry_run=False, ignore_missing=True)
  