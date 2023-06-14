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

from doc_curation_projects.veda.yajuH.vaajasaneyi import shatapatha
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes import brahmic
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.scraping.misc_sites import titus
from doc_curation.md import library, content_processor
from doc_curation.md.library import metadata_helper
from doc_curation import book_data
from doc_curation.md.file import MdFile

base_dir = os.path.join(shatapatha.CONTENT_BASE, "weber-srotaH/sasvaram")
devanagari = sanscript.SCHEMES[sanscript.DEVANAGARI]


def fix_accents(sentences):
  new_accent = "ॗ"
  old_accent = "᳡"
  for index, sentence in enumerate(sentences):
    # sentence = accent.to_shatapatha_svara(scheme=devanagari, text=sentence)
    # sentence = accent.move_accent_to_previous_syllable(scheme=devanagari, text=sentence, new_accent="ॗ", old_accent="ॗ")
    sentence = regex.sub("॥।", "…", sentence)
    sentence = regex.sub("᳘\s*([॥।])", "᳟\\1", sentence)
    sentence = regex.sub("᳘ॗ", "ॗ", sentence)
    if sentence.startswith("ॗ"):
      for i in range(-1, -index - 1, -1):
        if not sentences[index + i].startswith("#"):
          sentences[index + i] = accent.add_accent_to_end(scheme=devanagari, text=sentences[index + i], accent="᳟᳟")
          sentences[index] = regex.sub("^ॗ", "", sentence)
          break
    else:
      sentences[index] = sentence


def fix_text(text):
  lines = text.split("\n")
  fix_accents(sentences=lines)
  return "\n".join(lines)


def dump_text(base_dir, do_transliteration=False):
  unit_info_file = os.path.join(os.path.dirname(book_data.__file__), "data/book_data/vedaH/vAjasaneyi/shatapatha.json")
  
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
      for index, sentence in enumerate(sentences):
        # sentence = roman.RomanScheme.simplify_accent_notation(sentence)
        sentence = sentence.replace("/", ".")
        if do_transliteration:
          if kaanda_index == 12:
            sentence = sanscript.transliterate(sentence, sanscript.IAST, sanscript.DEVANAGARI)
          else:
            sentence = sanscript.transliterate(sentence, sanscript.TITUS, sanscript.DEVANAGARI)
          sentence += "  "
        lines.append(sentence)
      fix_accents(lines)  
      md_file = MdFile(file_path=outfile_path)
      md_file.dump_to_file(metadata={"title": "%02d" % sarga_index}, content="\n".join(lines), dry_run=False)

  library.fix_index_files(dir_path=base_dir, dry_run=False)
  library.apply_function(fn=metadata_helper.set_title_from_filename, dir_path=base_dir, frontmatter_type=MdFile.TOML, dry_run=False, transliteration_target=sanscript.DEVANAGARI) # 


if __name__ == '__main__':
  # dump_text(base_dir=base_dir, do_transliteration=True)
  # library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda c, m: fix_text(c))
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=base_dir, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, title_index_pattern=None) # 
  library.apply_function(fn=content_processor.replace_texts, dir_path=base_dir, patterns=["(?<=## )(?=[०-९]\n)"], replacement="०")
  pass
