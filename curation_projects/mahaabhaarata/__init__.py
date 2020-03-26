import os
import regex
from doc_curation.md_helper import MdFile


def get_adhyaaya_md_files(md_file_path):
    md_files = MdFile.get_md_files_from_path(dir_path=md_file_path, file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d\\d", os.path.basename(x))) > 0)
    return md_files


def get_parva_adhyaaya(md_file):
    parva = regex.findall("/\\d\\d-", str(md_file.file_path))[0].replace("/", "").replace("-", "")
    adhyaaya = regex.findall("\\d\\d\\d", str(md_file.file_path))[-1]
    return (parva, adhyaaya)


def get_adhyaaya_id(md_file):
    (parva, adhyaaya) = get_parva_adhyaaya(md_file=md_file)
    return "%03d-%03d" % (int(parva), int(adhyaaya))


def get_adhyaaya_to_source_file_map():
    md_files = get_adhyaaya_md_files(md_file_path="/home/vvasuki/sanskrit/raw_etexts/purANa/mahAbhArata/kumbhakonam")
    final_map = {}
    for md_file in md_files:
        parva = regex.findall("/\\d\\d/", str(md_file.file_path))[0].replace("/", "")
        adhyaaya = regex.findall("\\d\\d\\d", str(md_file.file_path))[0]
        adhyaaya_id = "%s-%s" % (parva, adhyaaya)
        final_map[adhyaaya_id] = md_file
    return final_map





