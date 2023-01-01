import os

from doc_curation.md.file import MdFile

from doc_curation.md import library
from doc_curation.md.library import metadata_helper, combination
from doc_curation.md.content_processor import section_helper

from doc_curation.scraping.wisdom_lib import serial
from indic_transliteration import sanscript



if __name__ == '__main__':
  out_path = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/shrautam/muller/24"
  # serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/apastamba-yajna-paribhasa-sutras/d/doc116818.html", out_path=out_path)
  # library.apply_function(fn=combination.combine_files_in_dir, dir_path=out_path, dry_run=False)
  # With this you get 159 sUtras, to be placed in 24/1 .. 24/4. Number matches. 

  # library.apply_function(fn=section_helper.autonumber, dir_path=out_path)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=out_path, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, title_index_pattern=None) # 
  metadata_helper.copy_metadata_and_filename(ref_dir=out_path.replace("muller", "mUlam"), dest_dir=out_path)
  pass