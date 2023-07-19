import os

from doc_curation.md import library
from doc_curation.md.content_processor import section_helper
from doc_curation.md.file import MdFile
from doc_curation_projects.veda.yajuH.vaajasaneyi import shatapatha

# fix_anunaasika(os.path.join(CONTENT_BASE, "weber-srotaH/sasvaram"))
# to_tsv(dir_path=os.path.join(CONTENT_BASE, "weber-srotaH/sasvaram/12"), out_path=os.path.join(os.path.join(CONTENT_BASE, "weber-srotaH/tsv/")))

# library.apply_function(fn=MdFile.transform, dir_path=os.path.join(shatapatha.CONTENT_BASE, "sarva-prastutiH"), content_transformer=lambda c, m: section_helper.section_contents_to_details(content=c, title="मूलम् - Weber"))

# library.apply_function(fn=MdFile.transform, dir_path=os.path.join(shatapatha.CONTENT_BASE, "eggeling/10/01/3.md"), content_transformer=lambda c, m: section_helper.section_contents_to_details(content=c, title="Eggeling"))

# library.dump_matching_files(dir_path=os.path.join(shatapatha.CONTENT_BASE, "eggeling"))
# library.dump_matching_files(dir_path=os.path.join(shatapatha.CONTENT_BASE, "sarva-prastutiH"))

# library.apply_function(fn=section_helper.merge_sections, dir_path=os.path.join(shatapatha.CONTENT_BASE, "sarva-prastutiH/10/01/3.md"), md_files=lambda x: [x.replace("sarva-prastutiH", "eggeling")])

# Manual fix:  10/01/3.md

# section_helper.merge_sections(md_files=[MdFile(file_path=os.path.join(base_dir, "en.md")), MdFile(file_path=os.path.join(base_dir, "bhagavadguNadarpaNam.md")), ], section_hasher=section_helper.section_hash_by_index)
