from doc_curation.md import library
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

if __name__ == '__main__':
  pass

  # library.apply_function(fn=library.combine_files_in_dir, dir_path="/home/vvasuki/vishvAsa/mImAMsA/content/pUrvA/granthAH/shabara-bhAShyam/06", file_pattern="_index.md", dry_run=False)
  # library.defolderify_single_md_dirs(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH", dry_run=False)

  # library.defolderify(dir_path="/home/vvasuki/vvasuki-git/vedAH/content/yajuH /taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/haradatta-TIkA", dry_run=False)
  # library.make_full_text_md(source_dir="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/champUH/nItiH/hitopadeshaH")

  ## DEVANAGARI
  # library.fix_index_files(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/saMhitA/mUlam", overwrite=False, dry_run=False)

  ## Kannada
  library.fix_index_files(dir_path="/home/vvasuki/vishvAsa/kannaDa/static/padya/kumAra-vyAsa-bhArata/vishvAsa-prastuti", transliteration_target=sanscript.KANNADA, overwrite=True, dry_run=False)
