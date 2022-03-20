import itertools
import os
import shutil
from pathlib import Path

import regex

from doc_curation.md import content_processor, library
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

import logging

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def migrate_and_include_sUtras(dir_path):
  def get_title_id(text_matched):
    id_in_text = regex.search("([०-९]+) *$", text_matched).group(1)
    title_id = "%02d" % int(sanscript.transliterate(id_in_text, sanscript.DEVANAGARI, sanscript.IAST))
    return title_id

  def title_maker(text_matched, index, file_title):
    title_id = get_title_id(text_matched=text_matched)
    text_without_id = regex.sub(" *([०-९]+) *$", "", text_matched)
    title = content_processor.title_from_text(text=text_without_id, num_words=3, target_title_length=50,
                                              title_id=title_id)
    return title

  def replacement_maker(text_matched, dest_path):
    return include_helper.vishvAsa_include_maker(dest_path, h1_level=3, title="FILE_TITLE")

  PATTERN_SUTRA = "\n[\s\S]+?\s*[०-९\d]+\s*?(?=\n|$)"
  library.apply_function(fn=include_helper.migrate_and_replace_texts, text_patterns=[PATTERN_SUTRA],
                         dir_path=dir_path,
                         replacement_maker=replacement_maker, title_maker=title_maker, dry_run=False)


def set_basic_content(static_dir_base, content_path_maker=None):
  shutil.copytree(os.path.join(static_dir_base, "mUlam"), os.path.join(static_dir_base, "vishvAsa-prastutiH"), dirs_exist_ok=True)
  # library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m: c.replace("mUlam", "vishvAsa-prastutiH"), dir_path=os.path.join(content_dir_base, "sarva-prastutiH"))
  md_file_paths = sorted(filter(lambda x: not str(x).endswith("_index.md"), Path(os.path.join(static_dir_base, "mUlam")).glob("**/*.md")))
  md_file_paths = [str(x) for x in md_file_paths]
  def get_content_path(static_path):
    content_path = static_path.replace("static", "content")
    return regex.sub(r"mUlam/(\d/\d\d)/.+", r"sarva-prastutiH/\1.md", content_path)
  if content_path_maker is None:
    content_path_maker = get_content_path
  content_include_list = itertools.groupby(md_file_paths, get_content_path)

  for content_includes in content_include_list:
    md_file = MdFile(file_path=content_includes[0])

    include_lines = [include_helper.vishvAsa_include_maker(x.replace('mUlam', 'vishvAsa-prastutiH'), h1_level=2, title='FILE_TITLE') for x in content_includes[1]]
    content = "\n\n".join(include_lines)
    title = metadata_helper.get_title_from_filename(md_file.file_path, transliteration_target=sanscript.DEVANAGARI)
    md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=False)