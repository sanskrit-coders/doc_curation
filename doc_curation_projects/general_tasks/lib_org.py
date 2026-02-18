from doc_curation.md.library import arrangement


def combine_files(dir_path, author=None):
  pass
  # combination.make_full_text_md(source_dir=dir_path)
  # combination.combine_files_in_dir(md_file=dir_path)
  # combination.combine_parts(dir_path=dir_path, pattern=r"(?P<part_id>.+?)_(?P<name>\d+).md")
  # arrangement.defolderify_single_md_dirs(dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/static/prakIrNAryabhAShAH/padya/rAmacharitamAnasa/TIkA/", dry_run=False)


if __name__ == '__main__':
  pass


  # library.fix_mistaken_nines("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/tattvam/jIva-gosvAmI/ShaT-sandarbhaH/hi/5_bhakti-sandarbhaH/pAThaH", digit_from_last=2)
  # library.highlight_out_of_order_files("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/tattvam/jIva-gosvAmI/ShaT-sandarbhaH/hi/5_bhakti-sandarbhaH/pAThaH", fix_sequence="dry_run_no")

  # arrangement.defolderify_single_md_dirs(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/static/rAmAnuja-sampradAyaH/tattvam/rAmAnujaH/shrI-bhAShyam/adhikaraNa-ratnamAlA", dry_run=False)
  # library.make_full_text_md(source_dir="/home/vvasuki/vvasuki-git/kAvya/content/TIkA/champUH/nItiH/hitopadeshaH")

  ## DEVANAGARI
  # arrangement.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/", overwrite=False, dry_run=False)
  # metadata_helper.ensure_ordinal_in_title(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/Rk/shAkalam/aitareya-brAhmaNam/panchikA_3/adhyAya_13_khaNDaH_1-14", first_file_index=25)

  # arrangement.shift_contents(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/vaikhAnasaH/mantra-saMhitA/mUlam/resnick/5/1", start_index=121, substitute_content_offset=4)
  arrangement.shift_indices(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/vaikhAnasaH/mantra-saMhitA/mUlam/resnick/5/1", start_index=126, new_index_offset=1, dry_run=False)

  ## Kannada
  # arrangement.fix_index_files(dir_path="/home/vvasuki/gitland/vishvAsa/kannaDa/static/padya/kumAra-vyAsa-bhArata/vishvAsa-prastuti", transliteration_target=sanscript.KANNADA, overwrite=True, dry_run=False)

  # metadata_helper.copy_metadata_and_filename(ref_dir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/parAshara-vishiShTa-dharma-shAstram/mUlam-1901", dest_dir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/parAshara-vishiShTa-dharma-shAstram/sarva-prastutiH", dry_run=False)