import os.path

from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.library import arrangement, metadata_helper
from indic_transliteration import sanscript

SUBFOLDER_MAPPINGS = {

  # Level 1 - समन्वयः (samanvayaH)
  '1/1': '1_ayoga-vyavachChedaH',           # अयोग-व्यवच्छेदः
  '1/2': '2_aspaShTa-jIvAdi-lingakaH',       # अस्पष्टजीवादि-लिङ्गकः
  '1/3': '3_spaShTa-jIvAdi-lingakaH',        # स्पष्टजीवादि-लिङ्गकः
  '1/4': '4_chAyAnusArI',                 # छायानु-सारि

  # Level 2 - अविरोधः (avirodhaH)
  '2/1': '1_smRtiH',                       # स्मृतिः
  '2/2': '2_tarkaH',                   # तर्कपादः
  '2/3': '3_viyat',                   # वियत्पादः
  '2/4': '4_prANaH',                   # प्राणपादः

  # Level 3 - साधनम् (sAdhanam)
  '3/1': '1_vairAgyam',                # वैराग्यपादः
  '3/2': '2_ubhayalingatA_brahmaNaH',                 # उभयलिङ्गं
  '3/3': '3_guNopasaMhAraH',               # गुणोपसंहारः
  '3/4': '4_angAni',                    # अङ्गपादः

  # Level 4 - प्राप्तिः-फलम् (prAptiH-phalam)
  '4/1': '1_AvRttiH',                  # आवृत्तिपादः
  '4/2': '2_utkrAntiH',                    # उत्क्रान्तिः
  '4/3': '3_gatiH',                    # गतिपादः
  '4/4': '4_muktiH',                   # मुक्तिपादः

  '1': '1_samanvayaH',           # समन्वयः
  '2': '2_avirodhaH',             # अविरोधः
  '3': '3_sAdhanam',              # साधनम्
  '4': '4_prAptiH',        # प्राप्तिः-फलम्
}

def adhikaraNa_sAra():
  ref_dir = "/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH"
  dest_dir = "/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/venkaTa-nAthaH/adhikaraNa-sArAvalI/sarva-prastutiH/"
  padakRtya_dir = dest_dir.replace("sarva-prastutiH", "34-ahobila-yatiH_pada-yojanA")
  kumAra_dir = dest_dir.replace("sarva-prastutiH", "kumAra-varadaH_chintAmaNiH")
  # arrangement.rename_subfolders(ref_map=ref_dir, dest_path=dest_dir, ref_map_mode="basedir", dry_run=False)
  # arrangement.rename_subfolders(ref_map=ref_dir, dest_path=padakRtya_dir, ref_map_mode="basedir", dry_run=False)
  # arrangement.rename_subfolders(ref_map=ref_dir, dest_path=kumAra_dir, ref_map_mode="basedir", dry_run=False)
  # metadata_helper.copy_metadata_and_filename(dest_dir=dest_dir, ref_dir=ref_dir, sub_path_id_maker=None, dry_run=True)

  # arrangement.shift_indices(dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/venkaTa-nAthaH/adhikaraNa-sArAvalI/34-ahobila-yatiH_pada-yojanA/4_prAptiH/4_muktiH", start_index=1, new_index_offset=-1, dry_run=False)

  library.apply_function(fn=details_helper.interleave_from_file, dir_path=dest_dir, source_file=lambda x: x.replace("sarva-prastutiH", "34-ahobila-yatiH_pada-yojanA"), detail_title="३४-तमाहोबिल-यतिः", dest_pattern= r"<details.+?summary>विश्वास-प्रस्तुतिः *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= r"(?<=\n|^)(\d+)\..+?(?=$|\n\n\d+\.)", dry_run=False,  use_dest_number=True)
  # library.apply_function(fn=details_helper.interleave_from_file, dir_path=dest_dir, source_file=lambda x: x.replace("sarva-prastutiH", "kumAra-varadaH_chintAmaNiH"), detail_title="कुमार-वरदः", dest_pattern= r"<details.+?summary>विश्वास-प्रस्तुतिः *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= r"(?<=\n|^)(\d+)\.[\s\S]+?(?=\n\n\d+\.|$)", dry_run=False, use_dest_number=True)


if __name__ == '__main__':
  pass
  ref_dir = "/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH"
  # arrangement.rename_subfolders(ref_map=ref_dir, dest_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/venkaTa-nAthaH/adhikaraNa-sArAvalI/sarva-prastutiH", ref_map_mode="ref_dir", dry_run=False)
  # library.apply_function(fn=metadata_helper.set_filename_from_title, dir_path=ref_dir, skip_dirs=False, source_script=sanscript.DEVANAGARI, overwrite=True, dry_run=False)
  # library.apply_function(fn=metadata_helper.set_title_from_filename, dir_path=ref_dir, overwrite=True, dry_run=False)

  # metadata_helper.copy_metadata_and_filename(dest_dir="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/40a-yatiH_maNi-pravALa-dIpikA", ref_dir=ref_dir, sub_path_id_maker=lambda x: os.path.basename(x), dry_run=True)
  adhikaraNa_sAra()