import os

import regex

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from doc_curation.md.content_processor import include_helper
from indic_transliteration import sanscript


def fix_includes():
  md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/vishvAsa/kAvyam/content/TIkA/padyam/kAlidAsaH/raghuvaMsham/mallinAthaH", file_pattern="[0-9][0-9]*.md")

  for md_file in md_files:
    include_helper.transform_include_lines(md_file=md_file, transformer=old_include_remover)
    include_helper.transform_include_lines(md_file=md_file, transformer=include_fixer)
    md_file.transform(content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)

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


def migrate_and_include_shlokas():

  def replacement_maker(text_matched, dest_path):
    return include_helper.vishvAsa_include_maker(dest_path, h1_level=3, title="FILE_TITLE")

  PATTERN_SUTRA = "\n[^#\s<>\[\(][\s\S]+? \s*[०-९\d\.]+\s*?(?=\n|$)"
  library.apply_function(fn=include_helper.migrate_and_replace_texts, text_patterns=[PATTERN_SUTRA], dir_path="/home/vvasuki/vishvAsa/kAvyam/content/TIkA/padyam/kAlidAsaH/raghuvaMsham/", replacement_maker=replacement_maker, title_maker=title_maker, dry_run=False)



def add_includes_to_content(content, metadata):
  chapter_id = os.path.basename(metadata["_file_path"]).replace(".md", "")
  def transformer(match):
    sutra_num_dev = match.group(1)
    sutra_num = int(sanscript.transliterate(sutra_num_dev, sanscript.DEVANAGARI, sanscript.IAST))
    url = "/kAvyam/TIkA/padyam/kAlidAsaH/raghuvaMsham/mallinAthaH/%s/%02d.md" % (chapter_id, sutra_num)
    include_line = library.get_include(url=url, h1_level=4, classes=["collapsed"], title="मल्लिनाथः")
    return "%s  \n%s\n" % (match.group(0), include_line)
  content = regex.sub("॥ *([०-९]+) *॥.*?(?=\n|$)", transformer, content)
  return content


if __name__ == '__main__':
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/TIkA/padyam/kAlidAsaH/raghuvaMsham/sarva-prastutiH", content_transformer=add_includes_to_content) 
  # fix_includes()