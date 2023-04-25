import os

import regex
from indic_transliteration import sanscript

from doc_curation.md import library
from doc_curation.md.library import metadata_helper, arrangement
from doc_curation.scraping.misc_sites import veda_com
from doc_curation.scraping.misc_sites.veda_com import ForceMode
from doc_curation_projects.veda.yajuH import vaajasaneyi
from doc_curation_projects.veda.yajuH.vaajasaneyi.maadhyandina.samhitaa import ref_dir


def fix_filenames(dry_run=False):
  # library.apply_function(dir_path=ref_dir, fn=metadata_helper.set_filename_from_title, source_script=sanscript.DEVANAGARI, dry_run=dry_run)

  # metadata_helper.copy_metadata_and_filename(dest_dir=ref_dir.replace("mUlam", "sarvASh_TIkAH"), ref_dir=ref_dir, sub_path_id_maker=None)
  metadata_helper.copy_metadata_and_filename(dest_dir=ref_dir.replace("mUlam", "vishvAsa-prastutiH"), ref_dir=ref_dir, sub_path_id_maker=None)



def path_maker(url):
  mode = ForceMode.MANTRA_COMMENT
  # Example: https://xn--j2b3a4c.com/samveda/54
  id_bits = ["%02d" % int(x) for x in url.split("/")[-2:]]
  id = "/".join(id_bits)
  dest_path = os.path.join(vaajasaneyi.TIKA_DIR, id + ".md")
  return (dest_path, mode)


if __name__ == '__main__':
  pass
  # veda_com.dump_sequence(url="https://xn--j2b3a4c.com/yajurveda/1/1", path_maker=path_maker, comment_detection_str="पदपाठः")
  fix_filenames()