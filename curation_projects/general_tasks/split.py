from doc_curation.md import library
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

if __name__ == '__main__':
  pass
  for index in range(1, 4):
    library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/%d.md" % index, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, bits_dir_url="/vedAH/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/%d/" % index)
  # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/AgamaH/content/hinduism/misc-articles/sanderson_tolerance.md", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.IAST) # ,  indexed_title_pattern=None
  # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH/08/", dry_run=False, source_script=None,  indexed_title_pattern=None)
  # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/vvasuki-git/saMskAra/content/kalpe_svamatam/hinduism/dANDekaraH", dry_run=False, source_script=None,  indexed_title_pattern=None)
  # MdFile(file_path="/home/vvasuki/vvasuki-git/notes-hugo/content/biology/organism/health/disease/contagion/vaccination.md",frontmatter_type=MdFile.TOML).split_to_bits(dry_run=False, source_script=None, indexed_title_pattern=None)
  #  , indexed_title_pattern=None
  
