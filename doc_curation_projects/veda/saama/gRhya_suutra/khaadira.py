import os

import regex

from doc_curation.md import library
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper, arrangement, combination
from doc_curation.scraping.sacred_texts import para_translation

content_dir_base = "/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/kauthumam/sUtram/drAhyAyaNaH/khAdira-gRhyam"
static_dir_base = content_dir_base.replace("content", "static")
ref_dir = os.path.join(static_dir_base, "mUlam")


def dump_muulam():
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(os.path.dirname(content_dir_base), "khAdira-gRhyam.md"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 
  # library.apply_function(fn=section_helper.autonumber, dir_path=os.path.join(content_dir_base, "mUlam"))
  
  # library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m: content_processor.make_lines_end_with_pattern(c, ".+[०-९]+"), dir_path=os.path.join(content_dir_base, "mUlam"))
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=os.path.join(content_dir_base, "mUlam"), frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None)
  # veda.migrate_and_include_sUtras(dir_path=os.path.join(content_dir_base, "mUlam"))
  # shutil.move(os.path.join(content_dir_base, "mUlam"), os.path.join(content_dir_base, "sarva-prastutiH"))
  # shutil.copytree(os.path.join(static_dir_base, "mUlam"), os.path.join(static_dir_base, "vishvAsa-prastutiH"))
  library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m: c.replace("mUlam", "vishvAsa-prastutiH"), dir_path=os.path.join(content_dir_base, "sarva-prastutiH"))


def fix_filenames():
  def sub_path_id_maker(x):
    x = str(x)
    base_name = os.path.basename(x)
    if base_name == "_index.md":
      return None
    elif "_" in base_name:
      return arrangement.get_sub_path_id(sub_path=regex.sub(".+/", "", str(x)), basename_id_pattern=r"(\d\du?_\d\d)")
    else:
      return "%s_%s" % (os.path.basename(os.path.dirname(x)), base_name.replace(".md", ""))
  metadata_helper.copy_metadata_and_filename(dest_dir="/home/vvasuki/gitland/vishvAsa/vedAH/static/yajuH/taittirIyam/sUtram/khaadira/gRhyam/oldenberg", ref_dir=ref_dir, sub_path_id_maker=sub_path_id_maker)


def fix_includes():
  md_files = arrangement.get_md_files_from_path(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/sAma/kauthumam/sUtram/drAhyAyaNaH/khAdira-gRhyam/sarva-prastutiH/", file_pattern="**/[0-9][0-9]*.md")
  md_files = [f for f in md_files if os.path.basename(f.file_path) ]
  
  def include_fixer(match):
    return include_helper.alt_include_adder(match=match, source_dir="vishvAsa-prastutiH", alt_dirs=["haradattaH", "sudarshanaH", "oldenberg"])

  for md_file in md_files:
    include_helper.transform_include_lines(md_file=md_file, transformer=include_helper.old_include_remover)
    include_helper.transform_include_lines(md_file=md_file, transformer=include_fixer)
    md_file.transform(content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)


def oldenberg_dest_path_maker(url, base_dir):
  page_number = int(url.split("/")[-1].replace(".htm", "").replace("sbe", ""))
  base_page_number = 29207 + 1
  subpath_parts = [(page_number-base_page_number)/5 + 1, ((page_number-base_page_number) % 5)  + 1]
  subpath = "%d/%d" % (int(subpath_parts[0]), int(subpath_parts[-1]))
  return os.path.join(base_dir, subpath + ".md")


def dump_oldenberg():
  base_dir = ref_dir.replace("mUlam", "oldenberg")
  # doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbe29/sbe29207.htm", outfile_path=os.path.join(content_dir_base, "meta", "oldenberg.md"))
  # 
  # doc_curation.scraping.sacred_texts.dump_serially(start_url="https://www.sacred-texts.com/hin/sbe29/sbe29208.htm", base_dir=base_dir, dest_path_maker=oldenberg_dest_path_maker)
  para_translation.split(base_dir=base_dir)
  metadata_helper.copy_metadata_and_filename(dest_dir=ref_dir.replace("mUlam", "oldenberg"), ref_dir=ref_dir)


def fix_oldenberg():
  base_dir = ref_dir.replace("mUlam", "oldenberg")
  
  work_dir = os.path.join(base_dir, "1/2")
  # library.shift_contents(work_dir, start_index=19, substitute_content_offset=1)
  # library.remove_file_by_index(work_dir, [25])

  work_dir = os.path.join(base_dir, "3/1")
  # library.shift_contents(work_dir, start_index=3, substitute_content_offset=1)
  # library.shift_contents(work_dir, start_index=11, substitute_content_offset=1)
  # library.shift_contents(work_dir, start_index=41, substitute_content_offset=1)

  work_dir = os.path.join(base_dir, "3/2")
  # library.shift_contents(work_dir, start_index=10, substitute_content_offset=1)
  # library.shift_contents(work_dir, start_index=14, substitute_content_offset=1)

  work_dir = os.path.join(base_dir, "3/3")
  # library.shift_contents(work_dir, start_index=23, substitute_content_offset=1)

  work_dir = os.path.join(base_dir, "3/4")
  # library.shift_contents(work_dir, start_index=17, substitute_content_offset=-1)

  work_dir = os.path.join(base_dir, "3/5")
  # library.shift_contents(work_dir, start_index=16, substitute_content_offset=1)
  # library.shift_contents(work_dir, start_index=28, substitute_content_offset=1)

  # work_dir = os.path.join(base_dir, "4/1")
  # library.shift_contents(work_dir, start_index=13, substitute_content_offset=1)

  work_dir = os.path.join(base_dir, "4/2")
  # library.shift_contents(work_dir, start_index=13, substitute_content_offset=1)
  pass


def fix_includes():
  md_files = arrangement.get_md_files_from_path(dir_path=os.path.join(content_dir_base, "sarva-prastutiH"), file_pattern="**/[0-9]*.md")

  def include_fixer(x, current_file_path, *args):
    return include_helper.alt_include_adder(x, current_file_path, source_dir="vishvAsa-prastutiH", alt_dirs=["sarvASh_TIkAH"])

  library.apply_function(fn=MdFile.transform, dir_path=content_dir_base, content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_helper.old_include_remover))
  library.apply_function(fn=MdFile.transform, dir_path=content_dir_base, content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_fixer))

  for md_file in md_files:
    md_file.transform(content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)


def combine():
  subpaths = ["mUlam", "oldenberg", ]
  subpaths = [os.path.join(static_dir_base, subpath) for subpath in subpaths]

  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(static_dir_base, "sarvASh_TIkAH"), dry_run=False)


if __name__ == '__main__':
  # dump_muulam()
  # dump_oldenberg()
  # fix_oldenberg()
  fix_includes()
  # fix_filenames()
  # combine()
  pass
