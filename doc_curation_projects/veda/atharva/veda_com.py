from doc_curation.scraping.misc_sites import veda_com
from doc_curation.scraping.misc_sites.veda_com import ForceMode
from doc_curation_projects.veda import atharva
import os
from doc_curation.md import library, content_processor


def path_maker(url):
  mode = ForceMode.NONE
  Rk_id_to_name_map = atharva.get_Rk_id_to_name_map_from_muulam()
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
        return ("SKIP: mantra_mismatch", False)
      else:
        dest_path_bits[2] = 48 + dest_path_bits[3]
        # 11/003_odanaH/13_RtaM_hastAvanejanaM 11/003_odanaH/18_charuM_panchabilamukhaM 30_naivAhamodanaM_na .. 56_brahmaNA_mukhena
  if dest_path_bits[0] == 11 and dest_path_bits[1] == 3 and dest_path_bits[2] >=30:
    mode = ForceMode.MANTRA_COMMENT
  if dest_path_bits[0] == 13 and dest_path_bits[1] == 4:
    suukta_lengths = [13, 8, 7, 17, 6, 5]
    dest_path_bits[1] = 4
    x = 0
    while dest_path_bits[2] > suukta_lengths[x]:
      dest_path_bits[2] = dest_path_bits[2] - suukta_lengths[x]
      dest_path_bits[1] += 1
      x += 1
    if dest_path_bits[1] == 4 and dest_path_bits[2] > 2 and dest_path_bits[2] < 8:
      mode = ForceMode.MANTRA_COMMENT
    elif dest_path_bits[1] == 5 and dest_path_bits[2] > 2:
      mode = ForceMode.MANTRA_COMMENT
    elif dest_path_bits[1] == 6 and dest_path_bits[2] < 3:
      mode = ForceMode.MANTRA_COMMENT
    elif dest_path_bits[1] == 9 and dest_path_bits[2] < 3:
      mode = ForceMode.MANTRA_COMMENT
  if dest_path_bits[0] == 15:
    if dest_path_bits[1] == 2:
      if dest_path_bits[2] in [14, 20]:
        mode = ForceMode.MANTRA_COMMENT
      if dest_path_bits[2] in range(15, 21):
        dest_path_bits[2] += 2
      elif dest_path_bits[2] in range(21, 30):
        dest_path_bits[2] += 4      
        
  dest_path_suffix = "%02d/%03d/%02d" % (dest_path_bits[0], dest_path_bits[1], dest_path_bits[2])
  if dest_path_suffix in ["03/024/03", "05/026/08", "05/026/11", "13/006/04", "13/008/05", "13/008/06"] or dest_path_suffix[0:6] in ["06/139", "07/011", "09/006"]:
    mode = True
  dest_path = os.path.join(atharva.SAMHITA_DIR_STATIC, "sarvASh_TIkAH", Rk_id_to_name_map[dest_path_suffix]) + ".md"
  return (dest_path, mode)


def remove_paryaayas(dest_path_bits, paryaaya_lengths):
  paryaaya = dest_path_bits[2]
  dest_path_bits[2] = dest_path_bits[3]
  if paryaaya > 1:
    for x in range(paryaaya - 1):
      dest_path_bits[2] += paryaaya_lengths[x]


def fix_typos():
  library.apply_function(fn=content_processor.replace_texts, dir_path=atharva.MULA_DIR, patterns=[""], replacement="३॒॑")
  library.apply_function(fn=content_processor.replace_texts, dir_path=atharva.MULA_DIR, patterns=[""], replacement="१॒॑")


if __name__ == '__main__':
  # 19_hetiH_shaphAnutkhidantI.md 32_aghaM_pachyamAnA.md  40_asvagatA_parihNutA.md 57_AdAya_jItaM.md 59_meniH_sharavyA_a.md 
  # 13/004_adhyAtmam/03_sa_dhAtA.md  - 07_pashchAt_prAncha

  # fix_typos()
  # veda_com.dump_sequence(url="https://xn--j2b3a4c.com/atharvaveda/3/24/0/3", path_maker=path_maker, max_mantras=1)
  # veda_com.dump_sequence(url="https://xn--j2b3a4c.com/atharvaveda/5/26/0/8", path_maker=path_maker, max_mantras=10)
  # veda_com.dump_sequence(url="https://xn--j2b3a4c.com/atharvaveda/6/139/0/1", path_maker=path_maker, max_mantras=10)
  # veda_com.dump_sequence(url="https://xn--j2b3a4c.com/atharvaveda/7/11/0/1", path_maker=path_maker, max_mantras=1)
  # veda_com.dump_sequence(url="https://xn--j2b3a4c.com/atharvaveda/8/10/1/1", path_maker=path_maker, max_mantras=88)
  # veda_com.dump_sequence(url="https://xn--j2b3a4c.com/atharvaveda/9/6/4/1", path_maker=path_maker, max_mantras=88)
  
  veda_com.dump_sequence(url="https://xn--j2b3a4c.com/atharvaveda/15/5/0/1", comment_detection_str="क्षेमकरणदास", path_maker=path_maker, max_mantras=21)
  # veda_com.dump_sequence(url="https://xn--j2b3a4c.com/atharvaveda/15/2/0/1", comment_detection_str="क्षेमकरणदास", path_maker=path_maker)