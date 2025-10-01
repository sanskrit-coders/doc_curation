import os.path

from doc_curation.md.library import metadata_helper, arrangement
from doc_curation.scraping.misc_sites import iskcon_vedabase


def chaitanya_charita():
  base_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/kAvyam/chaitanya-charitram/chaitanya-charitAmRtam/sarva-prastutiH/"
  # iskcon_vedabase.dump_all(url="https://vedabase.io/en/library/cc/adi/dedication/", dest_dir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/kAvyam/chaitanya-charitram/chaitanya-charitAmRtam/sarva-prastutiH/01_Adi/")
  # iskcon_vedabase.dump_all(url="https://vedabase.io/en/library/cc/madhya/1/advanced-view", dest_dir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/kAvyam/chaitanya-charitram/chaitanya-charitAmRtam/sarva-prastutiH/02_madhya/")
  # iskcon_vedabase.dump_all(url="https://vedabase.io/en/library/cc/antya/1/advanced-view", dest_dir="03_antya/")
  # arrangement.fix_index_files(dir_path=base_dir)
  # arrangement.shift_indices(os.path.join(base_dir, "01_Adi"), new_index_offset=-1)


def bhaagavatam():
  pass
  base_dir = "/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/bhAgavatam/gauDIyo_abhaya-charaNaH"
  # iskcon_vedabase.dump_all(url="https://vedabase.io/en/library/sb/1/dedication/advanced-view", dest_dir=os.path.join(base_dir, "00_meta"))

  for part in range(14, 13):
    pass
    iskcon_vedabase.dump_all(url=f"https://vedabase.io/en/library/sb/{part}/1/advanced-view", dest_dir=os.path.join(base_dir, f"{part:02}"), end_url=f"https://vedabase.io/en/library/sb/{part+1}//advanced-view")

  arrangement.fix_index_files(dir_path=base_dir)
  

def misc():
  pass
  iskcon_vedabase.dump_all(url="https://vedabase.io/en/library/bs/5/advanced-view/", dest_dir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/brahma-saMhitA/", index=5)



if __name__ == '__main__':
  pass
  # chaitanya_charita()
  bhaagavatam()
  misc()