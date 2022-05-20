import logging

import regex

from doc_curation_projects import raamaayana
from doc_curation_projects.puraaNa.raamaayana import  content
from doc_curation.md.file import MdFile
from doc_curation.md import library

# Remove all handlers associated with the root logger object.
from indic_transliteration import sanscript

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


md_file_path = "/home/vvasuki/vishvAsa/purANam/content/rAmAyaNam"

def get_titles_english():
  titles_english = MdFile.get_metadata_field_values(md_files=raamaayana.get_adhyaaya_md_files(md_file_path), field_name="title_english")
  unnumbered_titles = [regex.sub("^\d+ ", "", x) for x in titles_english]
  logging.info("\n".join(unnumbered_titles))


def get_titles():
  titles_english = MdFile.get_metadata_field_values(md_files=raamaayana.get_adhyaaya_md_files(md_file_path), field_name="title")
  unnumbered_titles = [regex.sub("^[०-९0-9]+ ", "", x) for x in titles_english]
  logging.info("\n".join(unnumbered_titles))


def get_numbers():
  titles_english = MdFile.get_metadata_field_values(md_files=raamaayana.get_adhyaaya_md_files(md_file_path), field_name="title_english")
  numbers = [regex.sub("^([०-९0-9]+) .+", "\\1", x) for x in titles_english]
  logging.info("\n".join(numbers))


# get_audio_file_data()
# get_titles_english()
# get_numbers()
# library.fix_index_files(dir_path=md_file_path, dry_run=False)

# library.fix_field_values(
#     md_files=raamaayana.get_adhyaaya_md_files(md_file_path),
#     spreadhsheet_id="1AkjjTATqaY5dVN10OqdNQSa8YBTjtK2_LBV0NoxIB7w",
#     worksheet_name="गोरक्षपुरपाठः", id_column="id", value_column="साङ्क-शीर्षिका", md_file_to_id=raamaayana.get_adhyaaya_id,
#   post_process_fn=lambda x: sanscript.transliterate(x, sanscript.OPTITRANS, sanscript.DEVANAGARI), md_frontmatter_field_name="title", dry_run=False
# )
# library.set_filenames_from_titles(dir_path=md_file_path, source_script=sanscript.DEVANAGARI, file_name_filter=lambda x: regex.match("^\\d\\d\\d_", os.path.basename(x)) is not None, dry_run=False)


# library.devanaagarify_titles(md_files=raamaayana.get_adhyaaya_md_files(md_file_path), dry_run=False)


content.update()