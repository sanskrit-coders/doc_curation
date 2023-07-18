import os

from doc_curation.md.library import metadata_helper, arrangement
from doc_curation.md.content_processor import details_helper
from doc_curation.utils import patterns
import regex
from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from doc_curation.md.content_processor import include_helper
from indic_transliteration import sanscript

CONTENT_DIR = "/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/brAhmaH/shrI-sampradAyaH/venkaTanAthaH/tattva-muktA-kalApaH/"


def get_title_id(text_matched):
  id_in_text = regex.search("([०-९]+)", text_matched).group(1)
  title_id = "%03d" % int(id_in_text)
  return title_id

def title_maker(text_matched, index, file_title):
  title_id = get_title_id(text_matched=text_matched)
  title = metadata_helper.title_from_text(text=text_matched, num_words=2, target_title_length=None,
                                                                  title_id=title_id)
  return title


def migrate_and_include_shlokas():

  def replacement_maker(text_matched, dest_path):
    inc = include_helper.vishvAsa_include_maker(dest_path, h1_level=3, title="FILE_TITLE")
    detail = details_helper.Detail(title="विश्वास-प्रस्तुतिः", content=text_matched)
    return f"{detail.to_md_html()}\n\n{inc}"

  def destination_path_maker(title, original_path):
    return include_helper.static_include_path_maker(title, original_path, path_replacements={"content": "static", ".md": "", "mUlam": "sarvASh_TIkAH"}, use_preexisting_file_with_prefix=False)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, text_patterns=[patterns.PATTERN_SHLOKA], dir_path=CONTENT_DIR, destination_path_maker=destination_path_maker, title_maker=title_maker, migrated_text_processor=lambda x: details_helper.Detail(
    title="मूलम्", content=x).to_md_html(), replacement_maker=replacement_maker, dry_run=False)


if __name__ == '__main__':
  # migrate_and_include_shlokas()
  # fix_includes()
  # include_helper.prefill_includes(dir_path=dest_dir)
  pass
