import os
import regex

from doc_curation.md import library
from doc_curation.md.file import MdFile


PATH_GP = "/home/vvasuki/vishvAsa/purANam/content/mahAbhAratam/goraxapura-pAThaH"
PATH_KUMBH = "/home/vvasuki/sanskrit/raw_etexts/purANa/mahAbhArata/kumbhakonam"

def get_adhyaaya_md_files(md_file_path):
    md_files = library.get_md_files_from_path(dir_path=md_file_path, file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d\\d", os.path.basename(x))) > 0)
    return md_files


def get_parva_adhyaaya(md_file):
    parva = regex.findall("/\\d\\d-", str(md_file.file_path))[0].replace("/", "").replace("-", "")
    adhyaaya = regex.findall("\\d\\d\\d", str(md_file.file_path))[-1]
    return (parva, adhyaaya)


def get_adhyaaya_id(md_file):
    (parva, adhyaaya) = get_parva_adhyaaya(md_file=md_file)
    return "%03d-%03d" % (int(parva), int(adhyaaya))


def get_adhyaaya_to_source_file_map(md_path=PATH_GP):
    md_files = get_adhyaaya_md_files(md_file_path=md_path)
    final_map = {}
    for md_file in md_files:
        parva = regex.findall("\\d\\d\\D", str(md_file.file_path))[0][0:2]
        adhyaaya = regex.findall("\\d\\d\\d", str(md_file.file_path))[0]
        adhyaaya_id = "%s-%s" % (parva, adhyaaya)
        final_map[adhyaaya_id] = md_file
    return final_map


def get_doc_data(worksheet_name="कार्यावली"):
    from curation_utils.google import sheets
    doc_data = sheets.IndexSheet(spreadhsheet_id="1sNH1AWhhoa5VATqMdLbF652s7srTG0Raa6K-sCwDR-8", worksheet_name=worksheet_name, id_column="पर्व-अध्यायः", google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json')
    return doc_data


