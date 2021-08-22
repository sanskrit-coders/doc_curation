import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper


def migrate_and_include_shlokas(chapter_id):
  def title_maker(text_matched, index, file_title):
    id_in_text = regex.search("\.([०-९]+)", text_matched).group(1)
    title_id = "%03d" % int(id_in_text)
    title = content_processor.title_from_text(text=text_matched, num_words=2, target_title_length=None,
                                              title_id=title_id)
    return title

  def replacement_maker(text_matched, dest_path):
    return include_helper.vishvAsa_include_maker(dest_path, h1_level=3, title="FILE_TITLE")

  def destination_path_maker(title, original_path):
    return include_helper.static_include_path_maker(title, original_path, path_replacements={"content": "static", ".md": "", "manuH": "manuH/vishvAsa_prastutiH"}, use_preexisting_file_with_prefix=False)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, text_patterns=[include_helper.PATTERN_SHLOKA], dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/%02d.md" % chapter_id, destination_path_maker=destination_path_maker, title_maker=title_maker, replacement_maker=replacement_maker, dry_run=False)


if __name__ == '__main__':
  migrate_and_include_shlokas(chapter_id=3)