from doc_curation.md import library
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript
from doc_curation.md.content_processor import include_helper, section_helper, details_helper

if __name__ == '__main__':
  pass
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/kaivalya-shata-dUShaNI.md")

  # for index in range(1, 4):
  #   library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/%d.md" % index,  dry_run=False, source_script=sanscript.DEVANAGARI, bits_dir_url="/vedAH_yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/%d/" % index)

  # ಕನ್ನಡ
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/people/bahvRchaH/misc.md",  dry_run=False, source_script=sanscript.KANNADA,  start_index=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/kriyA/venkaTanAthaH/deshika-prabandhAH/gopAlAchArya_kn_sa/1960/v1/_index.md",  dry_run=False, source_script=sanscript.KANNADA, start_index=1) # 

  # देवनागरी
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/lokAchArya-shAkhA/lokAchAryaH/shrI-vachana-bhUShaNam/kn/vakuLa-bhUShaNa.md", start_index=1)
  library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/padyam/_index.md", target_frontmantter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, start_index=None) 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/vyAkaraNam/pANinIyam/svaraH/shrInivAsa-svara-siddhAnta-chandrikA/00.md", dry_run=False, source_script=sanscript.DEVANAGARI, start_index=1, max_length=40) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/rahasya-traya-sAraH/sarva-prastutiH/1_arthAnushAsana-vibhAgaH/12_sAnga-prapadanAdhikAraH.md",  dry_run=False, source_script=sanscript.DEVANAGARI, start_index=1) # 
  # 
  # IAST
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/vaikhAnasaH/kriyA/goudriaan/daily-worship/07_Worship.md", start_index=1, dest_script=sanscript.IAST)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/vaikhAnasaH/kriyA/goudriaan/daily-worship/07_Worship.md",  dry_run=False, source_script=sanscript.IAST, mixed_languages_in_titles=True, start_index=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/shrI-vaishNava-brAhmaNas_rangAchAri/13_Daily_Observances/_index.md",  dry_run=False, source_script=sanscript.IAST, start_index=None, mixed_languages_in_titles=True, deromanize=False) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/shrI-vaishNava-brAhmaNas_rangAchAri/13_Daily_Observances.md",  dry_run=False, source_script=sanscript.IAST, mixed_languages_in_titles=True, start_index=1) # 

  ## ISO
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/rUpakam/sankalpa-sUryodayaH/meta/nArAyaNa-raghunAthau/alt.md",  dry_run=False, source_script=sanscript.ISO) # 

  # library.apply_function(fn=MdFile.split_to_bits,  dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/meta/articles/sen-bAg_on_shulba-sUtras/",  dry_run=False, source_script=sanscript.ISO, mixed_languages_in_titles=False, start_index=None, maybe_use_dravidian_variant="force", max_length=70) # 

  ## None Script
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/paramparA/kalai-quarrel/kAnchI/varada-tAtArya-survey.md", start_index=0, dest_script=sanscript.IAST)

  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/vaikhAnasaH/kriyA/tirupati-mandiram/N-ramesha/02_HISTORICAL_BACKGROUND.md", dry_run=False, source_script=None, start_index=1)
  # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/history/kAnchI/varadarAja-mandiram/varada-tAtArya-survey", dry_run=False, source_script=None,  start_index=None, max_length=30)
  
