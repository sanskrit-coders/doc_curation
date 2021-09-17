import os

import regex

from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

if __name__ == '__main__':
  pass
  # library.apply_function(dir_path="/home/vvasuki/vvasuki-git/pALi/content", fn=MdFile.ensure_ordinal_in_title, transliteration_target=sanscript.DEVANAGARI, dry_run=False)
  
  # MdFile.set_titles_from_filenames(dir_path="/home/vvasuki/vvasuki-git/notes-hugo/content/history/history_of_the_indian_people", transliteration_target=None, dry_run=False)
  # library.apply_function(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/saMhitA/mUlam", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, dry_run=False)
  
  # library.apply_function(fn=MdFile.prepend_file_index_to_title, dir_path="/home/vvasuki/hindutva/hindutva-hugo/content/main/books/vivekAnanda", dry_run=False)

  title_post_processor = None
  # title_post_processor = lambda x: regex.sub("^मन्त्रः +", "", x)
  # library.apply_function(fn=MdFile.add_init_words_to_section_titles, dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/3.md", dry_run=False, title_post_processor=title_post_processor, num_words=2)
  
  # md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/TIkA", file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d_\\d\\d", os.path.basename(x))) > 0)
  # library.metadata_helper.add_init_words_to_title(md_files=md_files, target_title_length=30, dry_run=False)
  # library.metadata_helper.set_filenames_from_title(md_files=md_files, dry_run=False)