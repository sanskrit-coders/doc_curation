import os

from doc_curation.md.library import combination

STATIC_ROOT = "/home/vvasuki/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA"

if __name__ == '__main__':
  subpaths = ["thomson_solcum", "vedaweb_annotation", "pada-pAThaH", "hellwig_grammar", "anukramaNikA", "sAyaNa-bhAShyam", "wilson", "jamison_brereton", "jamison_brereton_notes", "griffith", "oldenberg", "macdonell", "geldner", "grassmann", "elizarenkova"]
  subpaths = [os.path.join(STATIC_ROOT, subpath) for subpath in subpaths]
  
  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(STATIC_ROOT, "sarvAH_TIkAH"), dry_run=False)