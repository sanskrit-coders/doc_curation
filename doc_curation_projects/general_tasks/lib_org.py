from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper, arrangement
from indic_transliteration import sanscript

def combine_files():
  library.apply_function(fn=combine_files_in_dir, dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/static/prakIrNAryabhAShAH/padya/rAmacharitamAnasa/TIkA/", file_pattern="**/_index.md", dry_run=False)
  arrangement.defolderify_single_md_dirs(dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/static/prakIrNAryabhAShAH/padya/rAmacharitamAnasa/TIkA/", dry_run=False)


if __name__ == '__main__':
  pass
  # combine_files()

  # library.defolderify(dir_path="/home/vvasuki/vvasuki-git/vedAH/content/yajuH /taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/haradatta-TIkA", dry_run=False)
  # library.make_full_text_md(source_dir="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/champUH/nItiH/hitopadeshaH")

  ## DEVANAGARI
  # library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam", overwrite=False, dry_run=False)
  # metadata_helper.ensure_ordinal_in_title(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/Rk/shAkalam/aitareya-brAhmaNam/panchikA_3/adhyAya_13_khaNDaH_1-14", first_file_index=25)

  arrangement.shift_contents(dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/static/mahAbhAratam/06-bhIShma-parva/03-bhagavad-gItA-parva/saMskRtam/shankaraH/AnandagiriH/13_xetra-xetrajna-yogaH/", start_index=11, substitute_content_offset=-1)

  ## Kannada
  # library.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/kannaDa/static/padya/kumAra-vyAsa-bhArata/vishvAsa-prastuti", transliteration_target=sanscript.KANNADA, overwrite=True, dry_run=False)
