import os

import regex

from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


def title_fix():
  ## DEVANAGARI
  # library.apply_function(dir_path="/home/vvasuki/vvasuki-git/pALi/content", fn=MdFile.ensure_ordinal_in_title, transliteration_target=sanscript.DEVANAGARI, dry_run=False)
  # library.apply_function(dir_path="/home/vvasuki/vishvAsa/kAvyam/content/laxaNam/articles/sAhitya-sAraH", fn=metadata_helper.set_filename_from_title, source_script=sanscript.DEVANAGARI, dry_run=False)
  # library.apply_function(dir_path="/home/vvasuki/vishvAsa/kAvyam/content/laxyam/padyam/vIra-kathAH/madhurA-vijayam/sv_sanxepaH", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)
  
  ##### General
  # library.apply_function(fn=MdFile.prepend_file_index_to_title, dir_path="/home/vvasuki/hindutva/hindutva-hugo/content/main/books/vivekAnanda", dry_run=False)
  # library.apply_function(fn=metadata_helper.set_filename_from_title, dir_path="/home/vvasuki/vishvAsa/AgamaH/content/AryaH/hinduism/branches/shaivaH/trikam/abhinavagupta-mUlam/tantrasAraH", skip_dirs=False, dry_run=False)
  
  # md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/TIkA", file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d_\\d\\d", os.path.basename(x))) > 0)
  # library.metadata_helper.add_init_words_to_title(md_files=md_files, target_title_length=30, dry_run=False)
  # library.metadata_helper.set_filenames_from_title(md_files=md_files, dry_run=False)
  
  
  ## KANNADA
  # library.apply_function(dir_path="/home/vvasuki/vishvAsa/kannaDa/static/padya/kumAra-vyAsa-bhArata/vishvAsa-prastuti", fn=metadata_helper.transliterate_title, transliteration_target=sanscript.KANNADA, dry_run=False)
  pass

if __name__ == '__main__':
  # library.apply_function(
  #   fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/purANam/content/rAmAyaNam/goraxapura-pAThaH/kannaDAnuvAda",
  #   content_transformer=None,
  #   metadata_transformer=lambda c, m: metadata_helper.add_value_to_field(m, "unicode_script", "kannada"),
  #   dry_run=False)
  pass

