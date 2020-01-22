
def get_adhyaaya_md_files():
    md_file_path = "/home/vvasuki/vvasuki-git/kAvya/content/TIkA/padya/purANa/rAmAyaNa/Andhra/"
    from doc_curation.md_helper import MdFile
    md_files = MdFile.get_md_files_from_path(dir_path=md_file_path, file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d\\d", os.path.basename(x))) > 0)
    return md_files

def get_kaanda_adhyaaya(md_file):
    import regex
    kaanda = regex.findall("/\\d_", str(md_file.file_path))[0].replace("/", "").replace("_", "")
    adhyaaya = regex.findall("\\d\\d\\d", str(md_file.file_path))[0]
    return (kaanda, adhyaaya)