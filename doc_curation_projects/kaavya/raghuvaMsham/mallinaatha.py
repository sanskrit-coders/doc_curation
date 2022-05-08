import regex

from doc_curation_projects.smRti.manu import content
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile


def title_maker(text_matched, index=None, file_title=None):
  match = regex.search("॥ *(\d+) *॥ *$", text_matched)
  return "%02d" % int(match.group(1))


def migrate_and_include_commentary():
  text_processor = lambda x: regex.sub("^.+?\n", "", x)

  def replacement_maker(text_matched, dest_path):
    init_num = int(regex.match("॥ *(\d+)", text_matched).group(1))
    title_num = int(title_maker(text_matched=text_matched))
    if init_num == title_num:
      include_line = include_helper.vishvAsa_include_maker(dest_path, h1_level=4, classes=["collapsed"], title="मल्लिनाथ-टीका")
      return "॥ %d ॥  \n%s" % (init_num, include_line)
    else:
      return text_matched

  PATTERN_TIKA = "॥ *\d+ *॥[\s\n]+[^॥\n]+?ति *॥[\s\S]+? *॥ *[\d]+ *?॥ *(?=\n|$)"
  library.apply_function(fn=include_helper.migrate_and_replace_texts, dir_path="/home/vvasuki/vishvAsa/kAvyam/content/TIkA/padyam/kAlidAsaH/raghuvaMsham/mallinAthaH", text_patterns = [PATTERN_TIKA], migrated_text_processor=text_processor, replacement_maker=replacement_maker,
                         title_maker=title_maker, dry_run=False)


if __name__ == '__main__':
  pass
  migrate_and_include_commentary()
