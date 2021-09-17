from doc_curation.md import library
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


def fix_muula():
  
  library.apply_function(fn=metadata_helper.remove_post_numeric_title_text, dir_path="/home/vvasuki/vishvAsa/kannaDa/static/padya/DVG/kagga/mUla", dry_run=False)
  library.apply_function(fn=metadata_helper.add_init_words_to_title, dir_path="/home/vvasuki/vishvAsa/kannaDa/static/padya/DVG/kagga/mUla", target_title_length=30, num_words=2, script=sanscript.KANNADA, dry_run=False)
  library.apply_function(fn=metadata_helper.set_filename_from_title, dir_path="/home/vvasuki/vishvAsa/kannaDa/static/padya/DVG/kagga/mUla", transliteration_source=sanscript.KANNADA, dry_run=False)


def fix_content():
  pass


if __name__ == '__main__':
  pass
  # metadata_helper.copy_metadata_and_filename(ref_dir="/home/vvasuki/vishvAsa/kannaDa/static/padya/DVG/kagga/mUla", dest_dir="/home/vvasuki/vishvAsa/kannaDa/static/padya/DVG/kagga/vishvAsa-prastuti")
  # fix_muula()
  include_helper.transform_include_lines(md_file=MdFile(file_path="/home/vvasuki/vishvAsa/kannaDa/content/padya/DVG/kagga/0.md"), transformer=lambda x: include_helper.include_basename_fixer(x, ref_dir="/home/vvasuki/vishvAsa/kannaDa/static/padya/DVG/kagga/vishvAsa-prastuti"))