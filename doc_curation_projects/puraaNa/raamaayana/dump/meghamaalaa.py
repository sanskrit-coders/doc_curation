import os

from doc_curation_projects.puraaNa.raamaayana import dump

dest_path = "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/rAmAyaNam/drAviDa-pAThaH/govindarAja-bhUShaNam"

dump.fix_metadata_and_paths(base_dir_ref="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/rAmAyaNam/drAviDa-pAThaH/mUlam", base_dir=dest_path, dry_run=False)
