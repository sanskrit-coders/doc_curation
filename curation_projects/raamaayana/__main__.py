import logging

from curation_projects import raamaayana
from doc_curation.md_helper import MdFile

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


md_file_path = "/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padyam/purANam/rAmAyaNam/AndhrapAThaH"
# MdFile.fix_index_files(dir_path=md_file_path, dry_run=False)
# MdFile.fix_titles(
#     md_files=raamaayana.get_adhyaaya_md_files(md_file_path),
#     spreadhsheet_id="1xqVBhDwRzcEL7HlCJhxmnG1aOFFk6B8gGZ4GuBZynf8",
#     worksheet_name="शीर्षिकाः", id_column="id", title_column="अन्तिमशीर्षिका", md_file_to_id=raamaayana.get_adhyaaya_id, dry_run=False
# )
MdFile.devanaagarify_titles(md_files=raamaayana.get_adhyaaya_md_files(md_file_path), dry_run=False)