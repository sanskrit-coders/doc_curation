import doc_curation.utils
import regex
from doc_curation.md import content_processor, library
from doc_curation.md.content_processor import footnote_helper
from doc_curation.md.file import MdFile
from doc_curation.utils import sanskrit_helper
from indic_transliteration import sanscript, aksharamukha_helper


def devanaagarify(dir_path, source_script):
  def content_transformer(c, m):
    c = footnote_helper.define_footnotes_near_use(c)
    c = content_processor.transliterate(text=c, source_script=source_script)
    c = doc_curation.utils.sanskrit_helper.fix_lazy_anusvaara(c)
    c = regex.sub(r"\n\*\*(\s+)", "\n\\1**", c)
    c = regex.sub(r"\*\* *(\n+)\*\*", "  \n", c)
    c = regex.sub(r"(?<=[^:])\n+[\t	 ]+", "\n> ", c)
    for x in range(1, 20):
      c = regex.sub("\n(>.+)\n\n+>", "\n\\1  \n>", c)
    return c
  
  library.apply_function(
    fn=MdFile.transform, dir_path=dir_path, 
    content_transformer=content_transformer,
    metadata_transformer=None,
  dry_run=False)

  if source_script == sanscript.TAMIL:
    library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: aksharamukha_helper.manipravaalify(x), dry_run=False)


def fix_anunaasikas(dir_path):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: sanskrit_helper.fix_bad_anunaasikas(x), dry_run=False, silent_iteration=False)

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/sanskrit/", content_transformer=lambda x, y: content_processor.fix_bad_anunaasikas(x), dry_run=False, silent_iteration=True, file_name_filter=lambda x: False not in [y not in str(x) for y in ["sarit", "gitasupersite", "wellcome", "dhaval", "wikisource", "vishvAsa"]])

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/satem/indo-iranian/indo-aryan/jAti-varNa-practice/v1/persons/sage-bloodlines/vishvAmitraH/venkaTanAtha-vedAnta-deshikaH", content_transformer=lambda x, y: sanscript.SCHEMES[sanscript.DEVANAGARI].fix_lazy_anusvaara(x, ignore_padaanta=True, omit_yrl=True), dry_run=False)

  pass

if __name__ == '__main__':
  fix_anunaasikas(dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/gadyam/rAmAnujaH/TIkA/yadugiri-prakAshitam")