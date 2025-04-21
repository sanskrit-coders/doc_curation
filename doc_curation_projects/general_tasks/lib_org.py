from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper, arrangement, combination
from indic_transliteration import sanscript


def combine_files(dir_path):
  pass

  # combination.make_full_text_md(source_dir=dir_path)
  # combination.combine_files_in_dir(md_file=dir_path)
  # combination.combine_parts(dir_path=dir_path, pattern=r"(?P<part_id>.+?)_(?P<name>\d+).md")
  # arrangement.defolderify_single_md_dirs(dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/static/prakIrNAryabhAShAH/padya/rAmacharitamAnasa/TIkA/", dry_run=False)


if __name__ == '__main__':
  pass
  # combine_files("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/static/rAmAnuja-sampradAyaH/tattvam/rAmAnujaH/shrI-bhAShyam/adhikaraNa-ratnamAlA")

  # library.fix_mistaken_nines("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/tattvam/jIva-gosvAmI/ShaT-sandarbhaH/hi/5_bhakti-sandarbhaH/pAThaH", digit_from_last=2)
  # library.highlight_out_of_order_files("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/tattvam/jIva-gosvAmI/ShaT-sandarbhaH/hi/5_bhakti-sandarbhaH/pAThaH", fix_sequence="dry_run_no")

  # arrangement.defolderify_single_md_dirs(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/static/rAmAnuja-sampradAyaH/tattvam/rAmAnujaH/shrI-bhAShyam/adhikaraNa-ratnamAlA", dry_run=False)
  # library.make_full_text_md(source_dir="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/champUH/nItiH/hitopadeshaH")

  ## DEVANAGARI
  # arrangement.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/shankaraH/brahma-sUtrANi/thibaut", overwrite=True, dry_run=False)
  # metadata_helper.ensure_ordinal_in_title(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/Rk/shAkalam/aitareya-brAhmaNam/panchikA_3/adhyAya_13_khaNDaH_1-14", first_file_index=25)

  # arrangement.shift_contents(dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/static/mahAbhAratam/06-bhIShma-parva/03-bhagavad-gItA-parva/saMskRtam/shankaraH/AnandagiriH/13_xetra-xetrajna-yogaH/", start_index=1, substitute_content_offset=-2, dry_run=True)
  # arrangement.shift_indices(dir_path="/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/strI-dharma-paddhatiH/sarva-prastutiH/02_jIvat-patikA-dharmAntaram", start_index=1, new_index_offset=-2, dry_run=False)

  ## Kannada
  # arrangement.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/kannaDa/static/padya/kumAra-vyAsa-bhArata/vishvAsa-prastuti", transliteration_target=sanscript.KANNADA, overwrite=True, dry_run=False)

  metadata_helper.copy_metadata_and_filename(ref_dir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/parAshara-vishiShTa-dharma-shAstram/mUlam-1901", dest_dir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/parAshara-vishiShTa-dharma-shAstram/sarva-prastutiH", dry_run=False)