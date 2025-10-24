from doc_curation.md import library
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript
from doc_curation.md.content_processor import include_helper, section_helper, details_helper

if __name__ == '__main__':
  pass
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/kaivalya-shata-dUShaNI.md")

  # for index in range(1, 4):
  #   library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/%d.md" % index, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, bits_dir_url="/vedAH_yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/%d/" % index)

  # ಕನ್ನಡ
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/people/bahvRchaH/misc.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA,  title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/kriyA/venkaTanAthaH/deshika-prabandhAH/gopAlAchArya_kn_sa/1960/v1/_index.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA, start_index=1) # 

  # देवनागरी
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/nAradaH/JNAnAmRta-sAraH/_index.md", start_index=1)
  library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/nAradaH/JNAnAmRta-sAraH/_index.md", target_frontmantter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/nAradaH/bhAradvAja-saMhitA/hi.md", dry_run=False, source_script=sanscript.DEVANAGARI, start_index=0, max_length=40) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/lokAchArya-shAkhA/varadarAja-sadanuShThAna-darpaNam.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, start_index=0) # 
  # 
  # IAST
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/satem/indo-iranian/indo-aryan/india/articles/russell_central_india_tribes/02_Articles_on_Castes_and_Tribes.md", start_index=1, dest_script=sanscript.IAST)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/satem/indo-iranian/indo-aryan/india/articles/russell_central_india_tribes/00_Meta.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST, mixed_languages_in_titles=True, title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/shrI-vaishNava-brAhmaNas_rangAchAri/13_Daily_Observances/_index.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST, title_index_pattern=None, mixed_languages_in_titles=True, deromanize=False) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kriyA/shrI-vaishNava-brAhmaNas_rangAchAri/13_Daily_Observances.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST, mixed_languages_in_titles=True, start_index=1) # 

  ## ISO
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/rUpakam/sankalpa-sUryodayaH/meta/nArAyaNa-raghunAthau/alt.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.ISO) # 

  # library.apply_function(fn=MdFile.split_to_bits,  dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/meta/articles/sen-bAg_on_shulba-sUtras/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.ISO, mixed_languages_in_titles=False, title_index_pattern=None, maybe_use_dravidian_variant="force", max_length=70) # 

  ## None Script
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/satem/indo-iranian/indo-aryan/india/articles/russell_central_india_tribes.md", dry_run=False, source_script=None, start_index=0)
  # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/parichaya-sanxepAH/en/shrI-vaishNava-brAhmaNas_rangAchAri.md", dry_run=False, source_script=None,  title_index_pattern=None, max_length=30)
  
