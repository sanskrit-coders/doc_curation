from doc_curation.scraping.misc_sites import veda_com
from doc_curation.scraping.misc_sites.veda_com import ForceMode
from doc_curation_projects.veda.yajuH import vaajasaneyi
import os, regex, logging
from doc_curation.md import library, content_processor
from doc_curation.md.library import arrangement
from doc_curation.md.content_processor import details_helper
from urllib.parse import urljoin


def path_maker(url):
  mode = ForceMode.MANTRA_COMMENT
  # Example: https://xn--j2b3a4c.com/samveda/54
  id_bits = ["%02d" % int(x) for x in url.split("/")[-2:]]
  id = "/".join(id_bits)
  dest_path = os.path.join(vaajasaneyi.TIKA_DIR, id + ".md")
  return (dest_path, mode)


if __name__ == '__main__':
  pass
  veda_com.dump_sequence(url="https://xn--j2b3a4c.com/yajurveda/1/1", path_maker=path_maker, comment_detection_str="पदपाठः")