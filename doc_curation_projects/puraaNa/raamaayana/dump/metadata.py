import os
from indic_transliteration import sanscript
from doc_curation.md.library import arrangement
from doc_curation.md import library
from doc_curation_projects.puraaNa.raamaayana import dump
from doc_curation.md.library import metadata_helper

BASE_DIR = "/home/vvasuki/gitland/vishvAsa/rAmAyaNam/content/vAlmIkIyam"
DRA_MULA = os.path.join(BASE_DIR, "drAviDa-pAThaH/mUlam/7_uttarakANDam")
DRA_TIKA = os.path.join(BASE_DIR, "drAviDa-pAThaH/govindarAja-bhUShaNam/7_uttarakANDam")

GP_HI = os.path.join(BASE_DIR, "goraxapura-pAThaH/hindy-anuvAdaH/7_uttarakANDam")
GP_KN = os.path.join(BASE_DIR, "goraxapura-pAThaH/kannaDAnuvAda/7_uttarakANDam")


# dump.fix_metadata_and_paths(base_dir_ref=DRA_TIKA, base_dir=GP_HI, dry_run=False)
# arrangement.shift_indices(dir_path=GP_HI, start_index=62, new_index_offset=-2, dry_run=False)

# arrangement.fix_index_files(os.path.dirname(BASE_DIR))
library.apply_function(dir_path=GP_KN, fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, overwrite=True, dry_run=False)
