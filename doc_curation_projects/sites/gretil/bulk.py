import os
from pathlib import Path

from doc_curation.scraping.misc_sites import gretil

src_dir_base = "/home/vvasuki/sanskrit/raw_etexts/mixed/gretil/gretil.sub.uni-goettingen.de/gretil/"
dest_dir_base = "/home/vvasuki/sanskrit/raw_etexts/mixed/gretil_devanAgarI/"


def devanagarify(src_dir, dest_dir, overwrite=False):
  file_paths = sorted(Path(src_dir).glob("**/*u.htm"))
  for file_path in file_paths:
    filename = gretil.get_filename(file_path)
    dest_file = os.path.join(dest_dir, os.path.dirname(file_path).replace(src_dir, "."), filename)
    gretil.dump_devanaagarii(source_html=file_path, dest_file=dest_file, overwrite=overwrite)
    # exit()


if __name__ == '__main__':
  dir_paths = Path(src_dir_base).glob("*/")
  for dir_path in dir_paths:
    if "6_sres" in str(dir_path):
      continue
    dir_name = os.path.basename(dir_path)
    devanagarify(src_dir=os.path.join(src_dir_base, dir_name), 
                 dest_dir=os.path.join(dest_dir_base, dir_name), overwrite=False)
