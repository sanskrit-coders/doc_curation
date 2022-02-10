import logging
import regex

from doc_curation.md import content_processor, library
from doc_curation.md.content_processor import include_helper

from indic_transliteration import sanscript

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
    title = content_processor.title_from_text(text=text_without_id, num_words=3, target_title_length=None,
                                              title_id=title_id)
    return title

  def replacement_maker(text_matched, dest_path):
    return include_helper.vishvAsa_include_maker(dest_path, h1_level=3, title="FILE_TITLE")

  PATTERN_SUTRA = "\n[\s\S]+?\s*[०-९\d]+\s*?(?=\n|$)"
  library.apply_function(fn=include_helper.migrate_and_replace_texts, text_patterns=[PATTERN_SUTRA],
                         dir_path=dir_path,
                         replacement_maker=replacement_maker, title_maker=title_maker, dry_run=False)