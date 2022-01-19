from doc_curation.md import library
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

def combine_files():
  library.apply_function(fn=library.combine_files_in_dir, dir_path="/home/vvasuki/vishvAsa/bhAShAntaram/static/prakIrNAryabhAShAH/padya/rAmacharitamAnasa/TIkA/", file_pattern="**/_index.md", dry_run=False)
  library.defolderify_single_md_dirs(dir_path="/home/vvasuki/vishvAsa/bhAShAntaram/static/prakIrNAryabhAShAH/padya/rAmacharitamAnasa/TIkA/", dry_run=False)


if __name__ == '__main__':
  pass
  combine_files()

  # library.defolderify(dir_path="/home/vvasuki/vvasuki-git/vedAH/content/yajuH /taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/haradatta-TIkA", dry_run=False)
  # library.make_full_text_md(source_dir="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/champUH/nItiH/hitopadeshaH")

  ## DEVANAGARI
  # library.fix_index_files(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/saMhitA/mUlam", overwrite=False, dry_run=False)

  ## Kannada
  # library.fix_index_files(dir_path="/home/vvasuki/vishvAsa/kannaDa/static/padya/kumAra-vyAsa-bhArata/vishvAsa-prastuti", transliteration_target=sanscript.KANNADA, overwrite=True, dry_run=False)
