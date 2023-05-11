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
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/gauDIya-vaiShNavam/kRShNa-bhAvAmRtam.md", start_index=1)
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/gauDIya-vaiShNavam/kRShNa-bhAvAmRtam.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/kriyA/Ahnika-sheShaH_rAmabhadrAchArya-kRtaH/16_ijyA.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, start_index=1) # 
  # 
  # IAST
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/meta/articles/keith/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST, mixed_languages_in_titles=True, title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/meta/articles/keith/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST, mixed_languages_in_titles=True, title_index_pattern=None, deromanize=True) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/shaivaH/meta/articles/davis_on_ritual.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST, start_index=1) # 

  ## ISO
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/shAktaH/yoginIhRdayam_dIpikA-sahitam/padoux-jeanty", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.ISO) # 

  # library.apply_function(fn=MdFile.split_to_bits,  dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/meta/articles/sen-bAg_on_shulba-sUtras/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.ISO, mixed_languages_in_titles=False, title_index_pattern=None, maybe_use_dravidian_variant="force", max_length=70) # 

  ## None Script
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/mishram/lochtefeld_hinduism-encyclopedia.md", dry_run=False, source_script=None, start_index=1)

  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/articles/winternitz-Apastamba-mantra-pATha", dry_run=False, source_script=None,  title_index_pattern=None)
  # MdFile(file_path="/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/presentation/_index.md",frontmatter_type=MdFile.TOML).split_to_bits(dry_run=False, source_script=None, title_index_pattern=None)
  #  , title_index_pattern=None
  
