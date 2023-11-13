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
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/kannaDa/content/padya/shAnti-grAma-narasiMha-mUrti.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA,  title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhma/shAnakara-darshanam/articles/satyanArAyaNa-shAstrI/garaNi-rAdhAkRShNaH/ramaNa", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA) # 

  # देवनागरी
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/abheda-darshanam/praty-abhijnA/utpaladevaH_Ishvara-pratyabhiJNA-kArikA/abhinavagupta-vimarshinI/bhAskarakaNTha-TIkA", start_index=1)
  library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/paddhatiH/shrIvaiShNavaH/shrInivAsa-deshikaH/02_apara-prayogaH/11_punas-saMskAraH.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/paddhatiH/shrIvaiShNavaH/shrInivAsa-deshikaH/02_apara-prayogaH/00.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, start_index=1) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/mANDukyopaniShat/shankaraH/_index.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, start_index=1) # 
  # 
  # IAST
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/yogaH/en/deshikAchAr.md", start_index=1, dest_script=sanscript.IAST)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/parichaya-sanxepAH/yatIndra-mata-dIpikA/govindAchArya.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST, mixed_languages_in_titles=True, title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/mANDukyopaniShat/shankaraH/_index.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST, mixed_languages_in_titles=True, title_index_pattern=None, deromanize=True) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/parichaya-sanxepAH/yatIndra-mata-dIpikA/mUlam.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST, start_index=0) # 

  ## ISO
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/satem/indo-iranian/indo-aryan/jAti-varNa-practice/v1/articles/sons_of_sarasvatI.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.ISO) # 

  # library.apply_function(fn=MdFile.split_to_bits,  dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/meta/articles/sen-bAg_on_shulba-sUtras/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.ISO, mixed_languages_in_titles=False, title_index_pattern=None, maybe_use_dravidian_variant="force", max_length=70) # 

  ## None Script
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/english/content/prose/hindu/indologist-bio/max-muller", dry_run=False, source_script=None, start_index=1)

  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/sAmya-vaiShamye/bases/texts.md", dry_run=False, source_script=None,  title_index_pattern=None)
  
