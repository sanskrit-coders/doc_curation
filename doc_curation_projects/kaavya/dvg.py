import os

from doc_curation.md import library
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


content_dir_base = "/home/vvasuki/vishvAsa/kannaDa/content/padya/DVG/kagga"
static_dir_base = content_dir_base.replace("content", "static")
ref_dir = os.path.join(static_dir_base, "vishvAsa-prastutiH")

def fix_muula():
  
  library.apply_function(fn=metadata_helper.remove_post_numeric_title_text, dir_path=os.path.join(static_dir_base, "mUla"), dry_run=False)
  library.apply_function(fn=metadata_helper.add_init_words_to_title, dir_path=os.path.join(static_dir_base, "mUla"), target_title_length=30, num_words=2, script=sanscript.KANNADA, dry_run=False)
  library.apply_function(fn=metadata_helper.set_filename_from_title, dir_path=os.path.join(static_dir_base, "mUla"), source_script=sanscript.KANNADA, dry_run=False)


def fix_content():
  # include_helper.transform_include_lines(md_file=MdFile(file_path=os.path.join(content_dir_base, "0.md"), transformer=lambda x: include_helper.include_basename_fixer(x, ref_dir=ref_dir))
  library.apply_function(fn=MdFile.transform, dir_path=os.path.join(content_dir_base, "0.md"), content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_helper.prefill_include))


if __name__ == '__main__':
  pass
  # metadata_helper.copy_metadata_and_filename(ref_dir=os.path.join(static_dir_base, "mUla"), dest_dir=ref_dir)
  # fix_muula()
  fix_content()
