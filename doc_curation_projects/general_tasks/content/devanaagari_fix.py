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
    c = regex.sub(r"\|\|", "॥", c)
    c = regex.sub(r"\|", "।", c)
    # c = regex.sub(r"\n\*\*(\s+)", "\n\\1**", c)
    # c = regex.sub(r"\*\* *(\n+)\*\*", "  \n", c)
    # c = regex.sub(r"(?<=[^:])\n+[\t	 ]+", "\n> ", c)
    # for x in range(1, 20):
    #   c = regex.sub("\n(>.+)\n\n+>", "\n\\1  \n>", c)
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
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: sanskrit_helper.fix_lazy_anusvaara(x), dry_run=False, silent_iteration=False)
  pass


if __name__ == '__main__':
  pass
  fix_anunaasikas(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/kriyA/venkaTanAthaH/AhAra-niyamaH.md")
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/vAyu-purANam/dvi-khaNDa-saMskaraNam", content_transformer=lambda x, y: sanskrit_helper.fix_repha_duplication(x), dry_run=False, silent_iteration=False)
  # devanaagarify(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/kriyA/mADabhUShi-vIrarAghava-sachcharitra-sudhA-nidhiH.md", source_script="telugu")
