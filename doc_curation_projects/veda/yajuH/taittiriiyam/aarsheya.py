import os.path

from doc_curation.md import library
from doc_curation.md.library import arrangement

base_dir_dest = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/ArSheya-kANDa-vibhAgaH"

def praajaapatya():
  # arrangement.make_include_files(dest_dir=os.path.join(base_dir_dest, "1_prAjApatyam/1_pauroDAshikam"), source_dir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/saMhitA/sarva-prastutiH/1/1_darshapUrNamAsAdi", start_index=1, end_index=13, dry_run=False)
  arrangement.make_include_files(dest_dir=os.path.join(base_dir_dest, "1_prAjApatyam/2_pauruDAshika-brAhmaNam"), source_dir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/brAhmaNam/sarva-prastutiH/3/2_darsha-pUrNa-mAsAdi/", start_index=1, end_index=10, dry_run=False)



if __name__ == '__main__':
  praajaapatya()