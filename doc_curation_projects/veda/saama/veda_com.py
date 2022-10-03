from doc_curation.scraping.misc_sites import veda_com
from doc_curation.scraping.misc_sites.veda_com import ForceMode
from doc_curation_projects.veda import saama
import os, regex, logging
from doc_curation.md import library, content_processor
from doc_curation.md.library import arrangement
from doc_curation.md.content_processor import details_helper
from urllib.parse import urljoin


def path_maker(url):
  mode = ForceMode.MANTRA_COMMENT
  # Example: https://xn--j2b3a4c.com/samveda/54
  (_, Rk_num_to_name_map) = saama.get_Rk_id_to_name_map_from_muulam()
  Rk_id_int = int(url.split("samveda/")[-1])
  Rk_id = "%04d"  % Rk_id_int
  if Rk_id not in Rk_num_to_name_map:
    Rk_id_prev = "%04d"  % (Rk_id_int - 1)
    dest_path = os.path.join(saama.TIKA_DIR, Rk_num_to_name_map.get(Rk_id_prev).replace(Rk_id_prev, Rk_id) + ".md")
  else:
    dest_path = os.path.join(saama.TIKA_DIR, Rk_num_to_name_map.get(Rk_id) + ".md")
  return (dest_path, mode)


if __name__ == '__main__':
  pass
  veda_com.dump_sequence(url="https://xn--j2b3a4c.com/samveda/1", path_maker=path_maker, comment_detection_str="पदपाठः")