import os

from doc_curation.md import library
from doc_curation.md.content_processor import details_helper, ocr_helper, space_helper
from doc_curation.md.content_processor import section_helper
from doc_curation.md.file import MdFile
from doc_curation_projects.veda.yajuH.vaajasaneyi import shatapatha

# fix_anunaasika(os.path.join(CONTENT_BASE, "weber-srotaH/sasvaram"))
# to_tsv(dir_path=os.path.join(CONTENT_BASE, "weber-srotaH/sasvaram/12"), out_path=os.path.join(os.path.join(CONTENT_BASE, "weber-srotaH/tsv/")))

# to_tsv(dir_path=os.path.join(CONTENT_BASE, "shrIdhara-pAThaH/sasvaram/12"), out_path=os.path.join(os.path.join(CONTENT_BASE, "weber-srotaH/tsv/")))


# library.apply_function(fn=MdFile.transform, dir_path=os.path.join(shatapatha.CONTENT_BASE, "shrIdhara-pAThaH/sasvaram"), content_transformer=lambda c, m: section_helper.section_contents_to_details(content=c, title="मूलम् - श्रीधरादि"))

# library.apply_function(fn=MdFile.transform, dir_path=os.path.join(shatapatha.CONTENT_BASE, "makoto-fushimi"), content_transformer=lambda c, m: section_helper.section_contents_to_details(content=c, title="मूलम् - Makoto"))

# library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/shrIdhara-pAThaH/sasvaram/14/01/1.md", content_transformer=lambda c, m: section_helper.section_contents_to_details(content=c, title="मूलम् - श्रीधरादि"))

# library.dump_matching_files(dir_path=os.path.join(shatapatha.CONTENT_BASE, "eggeling"))
# library.dump_matching_files(dir_path=os.path.join(shatapatha.CONTENT_BASE, "sarva-prastutiH"))

# library.apply_function(fn=section_helper.merge_sections, dir_path=os.path.join(shatapatha.CONTENT_BASE, "sarva-prastutiH/12"), md_files=lambda x: [x.replace("sarva-prastutiH", "makoto-fushimi")], prepend=False, dry_run=False)

# Manual fix:  10/01/3.md

# library.apply_function(fn=section_helper.merge_sections, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH/14/07/1.md", md_files=lambda x: [x.replace("sarva-prastutiH", "shrIdhara-pAThaH/sasvaram")], prepend=True, dry_run=False)

library.apply_function(fn=MdFile.transform, dir_path=os.path.join(shatapatha.CONTENT_BASE, "sarva-prastutiH"), content_transformer=details_helper.insert_duplicate_before, old_title_pattern="मूलम् - श्रीधरादि")
