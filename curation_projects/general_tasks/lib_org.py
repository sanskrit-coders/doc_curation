from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

def combine_files():
  library.apply_function(fn=library.combine_files_in_dir, dir_path="/home/vvasuki/vishvAsa/bhAShAntaram/static/prakIrNAryabhAShAH/padya/rAmacharitamAnasa/TIkA/", file_pattern="**/_index.md", dry_run=False)
  library.defolderify_single_md_dirs(dir_path="/home/vvasuki/vishvAsa/bhAShAntaram/static/prakIrNAryabhAShAH/padya/rAmacharitamAnasa/TIkA/", dry_run=False)


if __name__ == '__main__':
  pass
  # combine_files()

  # library.defolderify(dir_path="/home/vvasuki/vvasuki-git/vedAH/content/yajuH /taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/haradatta-TIkA", dry_run=False)
  # library.make_full_text_md(source_dir="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/champUH/nItiH/hitopadeshaH")

  ## DEVANAGARI
  # library.fix_index_files(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/saMhitA/mUlam", overwrite=False, dry_run=False)
  # metadata_helper.ensure_ordinal_in_title(dir_path="/home/vvasuki/vishvAsa/vedAH/content/Rk/shAkalam/aitareya-brAhmaNam/panchikA_3/adhyAya_13_khaNDaH_1-14", first_file_index=25)

  ## Kannada
  # library.fix_index_files(dir_path="/home/vvasuki/vishvAsa/kannaDa/static/padya/kumAra-vyAsa-bhArata/vishvAsa-prastuti", transliteration_target=sanscript.KANNADA, overwrite=True, dry_run=False)
