from doc_curation.md import library
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript
from doc_curation.md.content_processor import include_helper, section_helper, details_helper

if __name__ == '__main__':
  pass
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/vishvAsa/sanskrit/content/vyAkaraNam/pANinIyam/articles/shuddhi-kaumudI.md")

  # for index in range(1, 4):
  #   library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/%d.md" % index, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, bits_dir_url="/vedAH_yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/%d/" % index)

  # ಕನ್ನಡ
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/kannaDa-nuDi/raw_etexts/kosha/shrIvatsa-nighaNTu/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA,  title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/kannaDa-nuDi/raw_etexts/kosha/shrIvatsa-nighaNTu.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA) # 

  # देवनागरी
  # library.apply_function(fn=section_helper.autonumber, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/laxaNam/articles/bhoja-shRngAra-prakAshaH/_index.md")
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/laxyam/gadyam/kAdambarI/bhAnuchandra-TIkA_ocr.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/AsvAdaH/saMskRta-vANmaya-bRhad-itihAsa/04_kAvya", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI) # 

  # IAST
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhma/shAnakara-darshanam/satyanArAyaNa-shAstrI/let_go/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/shrautam/mUlam.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST, mixed_languages_in_titles=False, title_index_pattern=None) # 

  ## ISO
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhma/yoga-vAsiShTha-shAstram/satyanArAyaNa-shAstrI/talks.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.ISO) # 

  ## None Script
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/notes-hugo/content/military/battle-tactics.md", dry_run=False, source_script=None)

  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/notes-hugo/content/military/battle-tactics.md", dry_run=False, source_script=None,  title_index_pattern=None)
  # MdFile(file_path="/home/vvasuki/vvasuki-git/notes-hugo/content/biology/organism/health/disease/contagion/vaccination.md",frontmatter_type=MdFile.TOML).split_to_bits(dry_run=False, source_script=None, title_index_pattern=None)
  #  , title_index_pattern=None
  
