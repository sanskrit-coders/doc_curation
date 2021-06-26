import os
from pathlib import Path

from doc_curation.scraping import gretil

def devanagarify(src_dir, dest_dir):
    file_paths = sorted(Path(src_dir).glob("**/*u.htm"))
    for file_path in file_paths:
        filename = gretil.get_filename(file_path)
        dest_file = os.path.join(dest_dir, os.path.dirname(file_path).replace(src_dir, ""), filename)
        gretil.dump_devanaagarii(source_html=file_path, dest_file=dest_file)
        # exit()


if __name__ == '__main__':
    devanagarify(src_dir="/home/vvasuki/sanskrit/raw_etexts/mixed/gretil/gretil.sub.uni-goettingen.de/gretil/1_sanskr/", dest_dir="/home/vvasuki/sanskrit/raw_etexts/mixed/gretil_devanAgarI/")