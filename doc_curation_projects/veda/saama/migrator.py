import logging
import os

import doc_curation.md.content_processor.stripper
import doc_curation.md.library.metadata_helper
import regex

import doc_curation.md.content_processor.include_helper
import doc_curation.md.library.arrangement
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

PATTERN_RK = "\n[^#<>\[\(][^॥]+?॥\s*[०-९\d-:]+\s*॥.*?(?=\n|$)"
PATH_ALL_SAMHITA = "/home/vvasuki/gitland/vishvAsa/vedAH/content/sAma/kauthumam/saMhitA/"


def title_maker(text_matched, index, file_title):
  title_id = regex.search("॥\s*([०-९\d-:]+)\s*॥", text_matched).group(1)
  title_id = title_id.replace(":", "_")
  title = doc_curation.md.library.metadata_helper.title_from_text(text=text_matched, num_words=2, target_title_length=None,
                                                                  title_id=title_id)
  return title


def migrate_and_include_shlokas():

  def replacement_maker(text_matched, dest_path):
    return include_helper.vishvAsa_include_maker(dest_path, h1_level=2, title="FILE_TITLE")

  def destination_path_maker(title, original_path):
    return include_helper.static_include_path_maker(title, original_path, path_replacements={"content": "static", ".md": "", "saMhitA": "saMhitA/mUlam"}, use_preexisting_file_with_prefix=False)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, text_patterns=[PATTERN_RK], dir_path=PATH_ALL_SAMHITA, destination_path_maker=destination_path_maker, title_maker=title_maker, replacement_maker=replacement_maker, dry_run=False)
