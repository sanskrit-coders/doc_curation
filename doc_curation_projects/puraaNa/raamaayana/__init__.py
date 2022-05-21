import os
import regex
from doc_curation.md.file import MdFile
from doc_curation.md import library


def get_adhyaaya_md_files(md_file_path):
    md_files = library.get_md_files_from_path(dir_path=md_file_path, file_pattern="**/*.md", file_name_filter=lambda x: regex.match("^\\d\\d\\d_", os.path.basename(x)) is not None)
    return md_files


def get_adhyaaya_id(p):
    p = str(p)
    kaanda_index_match = regex.search("/0?(\d)_", p)
    sarga_index_match = regex.search("(\d\d\d)", p)
    if kaanda_index_match is not None and sarga_index_match is not None:
        sarga_id = "%s-%s" % (kaanda_index_match.group(1), sarga_index_match.group(1))
        return sarga_id
    return None


def get_adhyaaya_to_source_file_map():
    md_files = get_adhyaaya_md_files(md_file_path="/home/vvasuki/sanskrit/raw_etexts/purANa/rAmAyaNam/kumbhakona")
    final_map = {}
    for md_file in md_files:
        kaanda = regex.findall("/\\d/", str(md_file.file_path))[0].replace("/", "")
        adhyaaya = regex.findall("\\d\\d\\d", str(md_file.file_path))[0]
        adhyaaya_id = "%s-%s" % (kaanda, adhyaaya)
        final_map[adhyaaya_id] = md_file
    return final_map


def get_doc_data(worksheet_name="गोरक्षपुरपाठः"):
    from curation_utils.google import sheets
    doc_data = sheets.IndexSheet(spreadhsheet_id="1AkjjTATqaY5dVN10OqdNQSa8YBTjtK2_LBV0NoxIB7w", worksheet_name=worksheet_name, id_column="id", google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json')
    return doc_data