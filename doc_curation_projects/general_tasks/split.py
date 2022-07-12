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
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/parAsharaH/mAdhavIyam.md")
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/laxyam/rUpakam/gorUru-shrInivAsa-mUrtiH/putrikA-gRham.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/laxyam/padyam/jagannAtha-paNDitaH/bhAminI-vilAsaH.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI) # 

  # IAST
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhma/shAnakara-darshanam/satyanArAyaNa-shAstrI/let_go/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/bhAShAntaram/content/tamiL/4k-divya-prabandha/hart/_index.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.ISO, mixed_languages_in_titles=False, title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/bhAShAntaram/content/tamiL/4k-divya-prabandha/hart/10_pEriya_thirumOzhi_thirumangai_azhvar_pAsurams_948_-2031.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.ISO, mixed_languages_in_titles=False, title_index_pattern=None, maybe_use_dravidian_variant="force", max_length=70) # 

  ## ISO
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhma/yoga-vAsiShTha-shAstram/satyanArAyaNa-shAstrI/talks.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.ISO) # 

  ## None Script
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/notes-hugo/content/sapiens/branches/Trans-eurasian/japan/spirituality/hagakure/bennet-translation/0/HAGAKURE_IN_CONTEXT.md", dry_run=False, source_script=None)

  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/notes-hugo/content/sapiens/branches/Trans-eurasian/japan/spirituality/hagakure/bennet-translation/0.md", dry_run=False, source_script=None,  title_index_pattern=None)
  # MdFile(file_path="/home/vvasuki/vvasuki-git/notes-hugo/content/biology/organism/health/disease/contagion/vaccination.md",frontmatter_type=MdFile.TOML).split_to_bits(dry_run=False, source_script=None, title_index_pattern=None)
  #  , title_index_pattern=None
  
