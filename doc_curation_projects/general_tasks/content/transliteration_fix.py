import doc_curation.utils
import regex
from doc_curation.md import content_processor, library
from doc_curation.md.content_processor import footnote_helper, ocr_helper
from doc_curation.md.file import MdFile
from doc_curation.utils import sanskrit_helper
from indic_transliteration import sanscript, aksharamukha_helper, tamil_tools

# 
def devanaagarify(dir_path, source_script):
  def content_transformer(c, m):
    c = footnote_helper.define_footnotes_near_use(c)
    c = content_processor.transliterate(text=c, source_script=source_script)
    if source_script == sanscript.TAMIL:
      c = aksharamukha_helper.manipravaalify(c)
    c = doc_curation.utils.sanskrit_helper.fix_lazy_anusvaara(c)
    c = regex.sub(r"\|\|", "॥", c)
    c = regex.sub(r"\|", "।", c)
    # c = regex.sub(r"‘", "ऽ", c)
    # c = regex.sub(r"\n\t+", "\n> ", c)
    # c = regex.sub(r"\<span style\=\"text\-decoration\:underline\;\"\>(.+?)</span>", r"<u>\1</u>", c)

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



def fix_anunaasikaadi(dir_path, level=0):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: sanskrit_helper.fix_anunaasikaadi(x, level=level), dry_run=False, silent_iteration=False)
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: ocr_helper.misc_manipravaala_typos(x), dry_run=False, silent_iteration=False)
  pass



if __name__ == '__main__':
  pass
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/vAyu-purANam/dvi-khaNDa-saMskaraNam", content_transformer=lambda x, y: sanskrit_helper.fix_repha_duplication(x), dry_run=False, silent_iteration=False)
  # devanaagarify(dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/satem/indo-iranian/indo-aryan/jAti-varNa-practice/v1/persons/sage-bloodlines/bhRguH/dvitIyajanmani_bhRguH/chyavanaH/ApnavAna/aurvaH/jamadagniH/chakravarti-kulam/villivalam-nArAyaNaH.md", source_script="tamil")
  devanaagarify(dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/para-mata-bhangaH/mUlam.md", source_script="tamil_subscripted")
  # devanaagarify(dir_path="/home/vvasuki/gitland/vishvAsa/mahAbhAratam/content/meta/articles/ranganAthaH_vyAsa-rahasya/_index.md", source_script="kannada")
  # devanaagarify(dir_path="/home/vvasuki/gitland/vishvAsa/sanskrit/content/vyAkaraNam/pANinIyam/samAsaH/articles/samAsa-chandrikA.md", source_script=sanscript.IAST)
  # fix_anunaasikaadi(dir_path="/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/padyam/purANam/nArAyaNIyam/mAhAtmyam.md")
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/english/content/prose/hindu/indologist/max-muller/india_what_it_can_teach_us.md", content_transformer=lambda x, y: sanskrit_helper.fix_sacred_texts_transliteration(x), dry_run=False, silent_iteration=False)
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/", content_transformer=lambda x, y: tamil_tools.set_tamil_soft_consonants(x), dry_run=False, silent_iteration=False)
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/shrIvaiShNava/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam", content_transformer=lambda x, y: tamil_tools.fix_naive_ta_transliterations(x), dry_run=False, silent_iteration=False)
