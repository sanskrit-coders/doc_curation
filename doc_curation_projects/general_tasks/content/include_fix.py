import os

from doc_curation.md import library
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript


def add_init_words_to_includes():
  def transformer(match):
    footnote_text = match.group(1)
    return "[%s]" % sanscript.transliterate(footnote_text, sanscript.OPTITRANS, sanscript.DEVANAGARI)
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/smRtiH/manuH/04.md", content_transformer=lambda x, y: include_helper.transform_include_lines(x, transformer=transformer), dry_run=False)


def prefill_vishvAsa_includes():
  import doc_curation_projects
  dirs = doc_curation_projects.vishvAsa_projects
  
  include_helper.prefill_includes(dir_path="/home/vvasuki/gitland/vishvAsa/kannaDa/content/padya/kumAra-vyAsa-bhArata/04_virATa/02.md")
  
  import itertools
  dirs = list(itertools.dropwhile(lambda x: x != "bhAShAntaram", dirs))
  for dir in dirs:
    dir_path = os.path.join("/home/vvasuki/gitland/vishvAsa/", dir)
    include_helper.prefill_includes(dir_path=os.path.join(dir_path, "static"))
    include_helper.prefill_includes(dir_path=os.path.join(dir_path, "content"))


if __name__ == '__main__':
  pass
  # prefill_vishvAsa_includes()
  include_helper.prefill_includes(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content")
