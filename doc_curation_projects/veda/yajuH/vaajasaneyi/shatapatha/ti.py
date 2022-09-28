# Potential approaches: 
# 
# 1. Get pages in the range:
# http://titus.uni-frankfurt.de/texte/etcs/ind/aind/ved/yvw/sbm/sbm001.htm
# http://titus.uni-frankfurt.de/texte/etcs/ind/aind/ved/yvw/sbm/sbm100.htm
# Downside: Matching with kaanda and adhyaaya is harder. 
#
# 2. Use web driver and select text levels.
# 

# noinspection PyUnresolvedReferences
import logging
import os, regex
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes import roman

from doc_curation.scraping.misc_sites import titus
from doc_curation.md import library
from doc_curation.md.library import metadata_helper
from doc_curation import book_data
from doc_curation.md.file import MdFile

base_dir = "/home/vvasuki/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/weber-srotaH/sasvaram-alt"


def dump_text(base_dir, do_transliteration=False):
  unit_info_file = os.path.join(os.path.dirname(book_data.__file__), "vedaH/vAjasaneyi/shatapatha.json")

  titus_url = "http://titus.uni-frankfurt.de/texte/etcs/ind/aind/ved/yvw/sbm/sbm.htm"
  for kaanda_index in book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[]):
    sarga_list = book_data.get_subunit_list(file_path=unit_info_file, unit_path_list=[kaanda_index])
    for sarga_index in sarga_list:
      logging.info("kaanDa %d adhyaaya %d", kaanda_index, sarga_index)

      outfile_path = os.path.join(base_dir, "%02d" % (kaanda_index), "%02d" % sarga_index + ".md")
      if os.path.exists(outfile_path):
        logging.info("Skipping " + outfile_path)
        continue

      titus.navigate_to_part(base_page_url=titus_url, level_3_id=kaanda_index, level_4_id=sarga_index)
      sentences = titus.get_text()
      lines = ["\n"]
      for sentence in sentences:
        # sentence = roman.RomanScheme.simplify_accent_notation(sentence)
        sentence = sentence.replace("/", ".")
        if do_transliteration:
          if kaanda_index == 12:
            sentence = sanscript.transliterate(sentence, sanscript.IAST, sanscript.DEVANAGARI)
          else:
            sentence = sanscript.transliterate(sentence, sanscript.TITUS, sanscript.DEVANAGARI)
          sentence = roman.RomanScheme.to_shatapatha_svara(sentence)
        if not sentence.startswith("#"):
          sentence += "  "
        lines.append(sentence)
      md_file = MdFile(file_path=outfile_path)
      md_file.dump_to_file(metadata={"title": "%02d" % sarga_index}, content="\n".join(lines), dry_run=False)


if __name__ == '__main__':
  dump_text(base_dir=base_dir, do_transliteration=True)
  library.fix_index_files(dir_path=base_dir, dry_run=False) 
  library.apply_function(fn=metadata_helper.set_title_from_filename, dir_path=base_dir, frontmatter_type=MdFile.TOML, dry_run=False, transliteration_target=sanscript.DEVANAGARI) # 

  pass
