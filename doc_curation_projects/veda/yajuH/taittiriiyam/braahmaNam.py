import regex

from doc_curation.md import library
from doc_curation.md.content_processor import include_helper


def migrate_and_include_mantras(dir_path):
  text_processor = lambda x: regex.sub("## मन्त्रः.+?\n", "", x)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, dir_path=dir_path, text_patterns = ["## मन्त्रः\s*?\n[\\s\\S]+?(?=\n## |$)"], destination_path_maker=lambda title, original_path: include_helper.static_include_path_maker(title, original_path, path_replacements={"content": "static", ".md": ""}), migrated_text_processor=text_processor, replacement_maker=lambda w, x: include_helper.vishvAsa_include_maker(x, h1_level=4, classes=["collapsed"]), dry_run=False)


if __name__ == '__main__':
  migrate_and_include_mantras(dir_path="/home/vvasuki/vishvAsa/vedAH_yajuH/content/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/1/4/8.md")