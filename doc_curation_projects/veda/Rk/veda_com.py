from doc_curation.scraping.misc_sites import veda_com
from doc_curation.scraping.misc_sites.veda_com import ForceMode
from doc_curation_projects.veda import Rk
import os, regex, logging
from doc_curation.md import library, content_processor
from doc_curation.md.library import arrangement
from doc_curation.md.content_processor import details_helper
from urllib.parse import urljoin

def path_maker(url):
  mode = ForceMode.COMMENT_ONLY
  # Example: https://xn--j2b3a4c.com/samveda/54
  id_bits = ["%02d" % int(x) for x in url.split("/")[-3:]]
  id_bits[1] = "%03d" % int(url.split("/")[-2])
  id = "/".join(id_bits)
  Rk_id_to_name_map = Rk.get_Rk_id_to_name_map_from_muulam()
  dest_path = os.path.join(Rk.commentary_base, "/".join(id_bits[:-1]), Rk_id_to_name_map.get(id) + ".md")
  return (dest_path, mode)


if __name__ == '__main__':
  pass
  veda_com.dump_sequence(url="https://xn--j2b3a4c.com/rigveda/10/136/7", path_maker=path_maker, comment_detection_str="पदपाठः")