from doc_curation.scraping.misc_sites import vedic_scriptures
from doc_curation.scraping.misc_sites.vedic_scriptures import ForceMode
from doc_curation_projects.veda.atharva import shaunakam
import os, regex, logging
from doc_curation.md import library, content_processor
from doc_curation.md.library import arrangement
from doc_curation.md.file import MdFile
from doc_curation.md.content_processor import details_helper
from urllib.parse import urljoin
from doc_curation.utils import text_utils

def path_maker(url):
  # Example: https://vedicscriptures.in/atharvaveda/3/4/0/6
  mode = ForceMode.MANTRA
  Rk_id_to_name_map = shaunakam.get_Rk_id_to_name_map_from_muulam()
  dest_path_bits = url.split("atharvaveda/")[-1].replace("/0/", "/").split("/")
  dest_path_bits = [int(x) for x in dest_path_bits]
  if len(dest_path_bits) == 4:
    if dest_path_bits[0] == 8:
      paryaaya_lengths = [13, 10, 8, 16, 16, 4]
      remove_paryaayas(dest_path_bits, paryaaya_lengths)
    if dest_path_bits[0] == 9:
      paryaaya_lengths = [17, 13, 9, 10, 10, 14]
      if dest_path_bits[2] < 4:
        remove_paryaayas(dest_path_bits, paryaaya_lengths)
      elif dest_path_bits[2] in [4, 5]:
        # Succeding Rk pairs (or triplets in some cases) are to be collapsed into 1 for paryAya-s 4 and 5. This should be done manually.
        return (os.path.join(shaunakam.SAMHITA_DIR_STATIC, f"sarvASh_TIkAH/09/006_atithi-satkAraH/{dest_path_bits[2]}_{dest_path_bits[3]}.md"), ForceMode.COMMENT)
      else:
        dest_path_bits[2] = 48 + dest_path_bits[3]
  if dest_path_bits[0] == 11 and dest_path_bits[1] == 3 and dest_path_bits[2] >=30:
    mode = ForceMode.MANTRA
  if dest_path_bits[0] == 13 and dest_path_bits[1] == 4:
    suukta_lengths = [13, 8, 7, 17, 6, 5]
    dest_path_bits[1] = 4
    x = 0
    while dest_path_bits[2] > suukta_lengths[x]:
      dest_path_bits[2] = dest_path_bits[2] - suukta_lengths[x]
      dest_path_bits[1] += 1
      x += 1
    if dest_path_bits[1] == 4 and dest_path_bits[2] > 2 and dest_path_bits[2] < 8:
      mode = ForceMode.MANTRA
    elif dest_path_bits[1] == 5 and dest_path_bits[2] > 2:
      mode = ForceMode.MANTRA
    elif dest_path_bits[1] == 6 and dest_path_bits[2] < 3:
      mode = ForceMode.MANTRA
    elif dest_path_bits[1] == 9 and dest_path_bits[2] < 3:
      mode = ForceMode.MANTRA
  if dest_path_bits[0] == 15:
    if dest_path_bits[1] == 2:
      # Mantra to be split into multiple files. Manual attention needed.
      if dest_path_bits[2] in [14, 20]:
        mode = ForceMode.MANTRA
      if dest_path_bits[2] in range(15, 21):
        dest_path_bits[2] += 2
      elif dest_path_bits[2] in range(21, 30):
        dest_path_bits[2] += 4
    if dest_path_bits[1] == 5:
      # Mantra split into multiple files. Manual attention required.
      mantra_map = {5: 5, 7: 8, 9: 11, 11: 14, 13: 17, 15: 20}
      if dest_path_bits[2] > 4:
        if dest_path_bits[2] in mantra_map.keys():
          mode = ForceMode.MANTRA
          dest_path_bits[2] = mantra_map[dest_path_bits[2]]
        elif dest_path_bits[2] - 1 in mantra_map.keys() and dest_path_bits[2] - 1 != 15:
          dest_path_bits[2] = mantra_map[dest_path_bits[2] - 1] + 2
        else:
          return ("SKIP: mantra_mismatch", ForceMode.NONE)
    if dest_path_bits[1] == 6:
      # Mantra split into multiple files. Manual attention required.
      if dest_path_bits[2] == 22:
        mode = ForceMode.MANTRA
      elif dest_path_bits[2] >= 23:
        dest_path_bits[2] += 1
  if dest_path_bits[0] == 16:
    if dest_path_bits[1] == 8:
      if dest_path_bits[2] > 4:
        mode = ForceMode.MANTRA
  if dest_path_bits[0] == 19:
    if dest_path_bits[1] == 36:
      mantra_map = {1: 2, 2: 1}
      if dest_path_bits[2] in mantra_map.keys():
        dest_path_bits[2] = mantra_map[dest_path_bits[2]]

  dest_path_suffix = "%02d/%03d/%02d" % (dest_path_bits[0], dest_path_bits[1], dest_path_bits[2])
  if dest_path_suffix in ["03/024/03", "05/026/08", "05/026/11", "13/006/04", "13/008/05", "13/008/06", "18/004/13"] or dest_path_suffix[0:6] in ["06/139", "07/011", "09/006"]:
    mode = ForceMode.MANTRA
  if dest_path_suffix in ["15/014/03", "19/023/03", "20/098/01", "20/098/02", "20/132/05", "20/134/05"]:
    mode = ForceMode.MANTRA
  dest_path = os.path.join(shaunakam.SAMHITA_DIR_STATIC, "sarvASh_TIkAH", Rk_id_to_name_map[dest_path_suffix]) + ".md"
  return (dest_path, mode)


def remove_paryaayas(dest_path_bits, paryaaya_lengths):
  paryaaya = dest_path_bits[2]
  dest_path_bits[2] = dest_path_bits[3]
  if paryaaya > 1:
    for x in range(paryaaya - 1):
      dest_path_bits[2] += paryaaya_lengths[x]


def fix_typos():
  for dir in [shaunakam.MULA_DIR, shaunakam.TIKA_DIR]:
    library.apply_function(fn=MdFile.transform, dir_path=dir, content_transformer=lambda c, m: vedic_scriptures.fix_text(c, muula_text="mUlam" in dir))
  


def check_completeness():
  matches = library.list_matching_files(dir_path=shaunakam.MULA_DIR, content_condition=lambda x: "VS" not in x, file_name_filter=lambda x: not str(x).endswith("_index.md"))
  matches = [regex.sub("_.+?(?=/|$)", "", x).replace("/0", "/") for x in matches]
  matches = [regex.sub("(/\d+)$", r"/0\1", x) for x in matches]
  matches = [urljoin("https://vedicscriptures.in/atharvaveda/", x[1:]) for x in matches]
  logging.info("\n".join(matches))


if __name__ == '__main__':
  pass
  # vedic_scriptures.dump_sequence(url="https://vedicscriptures.in/atharvaveda/7/75/0/1", path_maker=path_maker)
  # check_completeness()
  
  # Special attention:
  # vedic_scriptures.dump_sequence(url="https://vedicscriptures.in/atharvaveda/9/6/4/1", path_maker=path_maker, max_mantras=21)
  # vedic_scriptures.dump_sequence(url="https://vedicscriptures.in/atharvaveda/20/98/0/1", path_maker=path_maker, max_mantras=2)
  # 
  fix_typos()

  # arrangement.shift_contents(os.path.join(shaunakam.TIKA_DIR, "16/008"), start_index=5, substitute_content_offset=-3, end_index=28, replacer=lambda md_file, x: details_helper.replace_with_detail_from_content(md_file=md_file, content=x, title="Whitney", dry_run=False))
  # arrangement.shift_contents(os.path.join(shaunakam.TIKA_DIR, "16/008"), start_index=5, substitute_content_offset=-3, end_index=28, replacer=lambda md_file, x: details_helper.replace_with_detail_from_content(md_file=md_file, content=x, title="Griffith", dry_run=False))

  # vedic_scriptures.dump_sequence(url="https://vedicscriptures.in/atharvaveda/20/132/0/5", path_maker=path_maker, max_mantras=1)
  # vedic_scriptures.dump_sequence(url="https://vedicscriptures.in/atharvaveda/15/14/0/3", path_maker=path_maker, max_mantras=21)
  # vedic_scriptures.dump_sequence(url="https://vedicscriptures.in/atharvaveda/16/9/0/1", comment_detection_str="क्षेमकरणदास", path_maker=path_maker)

