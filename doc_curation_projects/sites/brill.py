from doc_curation.scraping.misc_sites import brill
import os
import logging

def haribhakti():
  base_url = "https://brill.com/edcollchap-oa/book/9789004537651"
  base_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/hari-bhakti-vilAsaH/"
  brill.dump_chapter(f"{base_url}/BP000002.xml", os.path.join(base_dir, "1_guruH.md"), overwrite=True)
  brill.dump_chapter(f"{base_url}/BP000003.xml", os.path.join(base_dir, "2_dIxA.md"), overwrite=True)
  brill.dump_chapter(f"{base_url}/BP000004.xml", os.path.join(base_dir, "3_shaucham.md"), overwrite=True)
  brill.dump_chapter(f"{base_url}/BP000005.xml", os.path.join(base_dir, "4_vaiShNavAlankAraH.md"), overwrite=True)
  brill.dump_chapter(f"{base_url}/BP000006.xml", os.path.join(base_dir, "5_adhiShThAnam.md"), overwrite=True)

  brill.dump_chapter(f"{base_url}/BP000001.xml", os.path.join(base_dir, "meta/broo_intro.md"))
  brill.dump_chapter(f"{base_url}/front-8.xml", os.path.join(base_dir, "meta/broo_preface.md"))
  brill.dump_chapter(f"{base_url}/front-8.xml", os.path.join(base_dir, "meta/broo_preface.md"))


  library.apply_function(dir_path=base_dir, fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)


if __name__ == '__main__':
  haribhakti()