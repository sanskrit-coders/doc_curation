from doc_curation.md import library
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

if __name__ == '__main__':
  pass
  # for index in range(1, 4):
  #   library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/%d.md" % index, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, bits_dir_url="/vedAH/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/%d/" % index)

  # ಕನ್ನಡ
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhma/brahma-sUtrANi/shankaraH/sachchidAnandendraH/v1", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA,  title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/shAstram/granthaH/saMskRta-nATakagaLu/4_xINakAla.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.KANNADA) # 

  # देवनागरी
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/shaivaH/trikam/somAnanda-shivadRShTiH.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhma/brahma-sUtrANi/shankaraH/", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI) # 

  # IAST
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/rangapriya-on-festivals/03_ChAturmAsya.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/notes-hugo/content/places/travel.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST,  title_index_pattern=None) # 

  # None Script
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/notes-hugo/content/history/homo/sapiens/proto-asian/sino-tibetan/tibeto-burman/tibet.md", dry_run=False, source_script=None,  title_index_pattern=None)
  # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/notes-hugo/content/power/electricity/inverter.md", dry_run=False, source_script=None,  title_index_pattern=None)
  # MdFile(file_path="/home/vvasuki/vvasuki-git/notes-hugo/content/biology/organism/health/disease/contagion/vaccination.md",frontmatter_type=MdFile.TOML).split_to_bits(dry_run=False, source_script=None, title_index_pattern=None)
  #  , title_index_pattern=None
  
