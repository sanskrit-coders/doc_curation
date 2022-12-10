from doc_curation.md import library
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript
from doc_curation.md.content_processor import include_helper, section_helper, details_helper

if __name__ == '__main__':
  pass
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/baudhAyanaH/gRhyam/mUlam.md")

  # for index in range(1, 4):
  #   library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/%d.md" % index, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, bits_dir_url="/vedAH_yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/%d/" % index)

  # ಕನ್ನಡ
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/kannaDa/content/padya/shAnti-grAma-narasiMha-mUrti.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA,  title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhma/shAnakara-darshanam/articles/satyanArAyaNa-shAstrI/garaNi-rAdhAkRShNaH/ramaNa", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA) # 

  # देवनागरी
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/sAmrAjya-nibandhanam.md")
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/devaH/content/AryaH/hindukaH/viShNuH/padyam/kAnchI-devarAjaH.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 
  library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/vaiShNavaH/pAncharAtrAgamaH/viShvaksena-saMhitA.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, start_index=1) # 

  # IAST
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/vedAH/content/meta/articles/staal/discovering_vedas", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST, start_index=1) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/articles/vaisheShika-sUtrANi_moise_thITe/3_translation.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST, mixed_languages_in_titles=True, title_index_pattern=None) # 

  ## ISO
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhma/yoga-vAsiShTha-shAstram/satyanArAyaNa-shAstrI/talks.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.ISO) # 

  # library.apply_function(fn=MdFile.split_to_bits,  dir_path="/home/vvasuki/vishvAsa/bhAShAntaram/content/tamiL/4k-divya-prabandha/hart/10_pEriya_thirumOzhi_thirumangai_azhvar_pAsurams_948_-2031.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.ISO, mixed_languages_in_titles=False, title_index_pattern=None, maybe_use_dravidian_variant="force", max_length=70) # 

  ## None Script
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="", dry_run=False, source_script=None, start_index=0)

  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/economics/assets/goods/tradeables.md", dry_run=False, source_script=None,  title_index_pattern=None)
  # MdFile(file_path="/home/vvasuki/vishvAsa/notes-hugo/content/sapiens/branches/Aryan/kentum/germanic/english/USA/articles/expansion_of_england_seel.md",frontmatter_type=MdFile.TOML).split_to_bits(dry_run=False, source_script=None, title_index_pattern=None)
  #  , title_index_pattern=None
  
