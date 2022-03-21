import os

from doc_curation.md.file import MdFile

from doc_curation.md import library
from doc_curation.md.library import metadata_helper

from doc_curation.scraping.wisdom_lib import serial
from indic_transliteration import sanscript

if __name__ == '__main__':
  out_path = "/home/vvasuki/vishvAsa/vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/shrautam/muller/24/"
  # serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/apastamba-yajna-paribhasa-sutras/d/doc116818.html", out_path=)
  # library.apply_function(fn=library.combine_files_in_dir, dir_path=out_path, dry_run=False)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=out_path, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST) # 
  # for subdir in ["02", "03", "04"]:
  #   metadata_helper.ensure_ordinal_in_title(dir_path=os.path.join(out_path, subdir), transliteration_target=sanscript.IAST)
  # library.apply_function(fn=metadata_helper.set_filename_from_title, dir_path=out_path, source_script=sanscript.IAST, dry_run=False)
  metadata_helper.copy_metadata_and_filename(ref_dir="/home/vvasuki/vishvAsa/vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/shrautam/mUlam", dest_dir="/home/vvasuki/vishvAsa/vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/shrautam/muller")
  pass