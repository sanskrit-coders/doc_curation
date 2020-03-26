import os
import regex
from doc_curation.md_helper import MdFile


def get_adhyaaya_md_files(md_file_path):
    md_files = MdFile.get_md_files_from_path(dir_path=md_file_path, file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d\\d", os.path.basename(x))) > 0)
    return md_files


def get_kaanda_adhyaaya(md_file):
    kaanda = regex.findall("/\\d_", str(md_file.file_path))[0].replace("/", "").replace("_", "")
    adhyaaya = regex.findall("\\d\\d\\d", str(md_file.file_path))[0]
    return (kaanda, adhyaaya)


def get_adhyaaya_id(md_file):
    (kaanda, adhyaaya) = get_kaanda_adhyaaya(md_file)
    return "%s-%s" % (kaanda, adhyaaya)


def get_adhyaaya_to_source_file_map():
    md_files = get_adhyaaya_md_files(md_file_path="/home/vvasuki/sanskrit/raw_etexts/purANa/rAmAyaNam/kumbhakona")
    final_map = {}
    for md_file in md_files:
        kaanda = regex.findall("/\\d/", str(md_file.file_path))[0].replace("/", "")
        adhyaaya = regex.findall("\\d\\d\\d", str(md_file.file_path))[0]
        adhyaaya_id = "%s-%s" % (kaanda, adhyaaya)
        final_map[adhyaaya_id] = md_file
    return final_map


