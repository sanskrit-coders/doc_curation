import os

import regex

from curation_utils import file_helper
from doc_curation.md import library, include_helper
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript


def migrate_and_include_shlokas():
  def include_maker(shloka_path):
    url = shloka_path.replace("/home/vvasuki/vishvAsa/", "/").replace("/static/", "/")
    return library.get_include(url=url, h1_level=4)

  def shloka_id_maker(shloka_text):
    id_in_text = sanscript.transliterate(regex.search("॥\s*([०-९\d\.]+)\s*॥", shloka_text).group(1), sanscript.DEVANAGARI, sanscript.OPTITRANS)
    id_in_text = regex.search("\.?\s*(\d+)\s*$", id_in_text).group(1)
    return "%03d" % int(id_in_text)

  def include_path_maker(title, dest_dir):
    return os.path.join(dest_dir, "%s.md" % file_helper.get_storage_name(text=title))

  def content_transformer(content, dest_dir, dry_run):
    return include_helper.migrate_and_include_shlokas(content=content, shloka_id_maker=shloka_id_maker, include_maker=include_maker, include_path_maker=lambda x: include_path_maker(title=x, dest_dir=dest_dir, title_before_include="### %s", dry_run=dry_run))

  library.apply_function(fn=MdFile.transform_content, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/12.md", content_transformer=lambda x, dry_run: content_transformer(x, dest_dir="/home/vvasuki/vishvAsa/kalpAntaram/static/smRtiH/manuH/vishvAsa_prastutiH/12/"), dry_run=False)
  

if __name__ == '__main__':
  pass
  # library.apply_function(fn=MdFile.fix_lazy_anusvaara, dir_path="/home/vvasuki/sanskrit/raw_etexts/kalpaH/shUdra-kamalAkaraH_sAnuvAdaH_ocr.md", dry_run=False, ignore_padaanta=True, omit_yrl=True)
  # doc_curation.clear_bad_chars(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/mImAMsA-naya-manjarI.md", dry_run=False)
  # library.apply_function(fn=MdFile.transliterate_content, dir_path="/home/vvasuki/vishvAsa/vedAH/static/Rk/shAkalam/saMhitA/thomson_solcum", source_scheme=sanscript.IAST)
  # library.apply_function(fn=MdFile.replace_in_content_lines, dir_path="/home/vvasuki/vishvAsa/purANam/static/rAmAyaNam/audIchya-pAThaH/vishvAsa-prastutiH", pattern="^[a-zA-Z-].+", replacement="", dry_run=False)
  # library.apply_function(fn=MdFile.drop_sections, dir_path="/home/vvasuki/vishvAsa/purANam/static/rAmAyaNam/audIchya-pAThaH/vishvAsa-prastutiH", title_condition=lambda x: x != "मूलम्")
  # library.apply_function(fn=MdFile.make_paras, dir_path="/home/vvasuki/vishvAsa/vedAH/static/Rk/shAkalam/saMhitA/jamison_brereton_notes")
  migrate_and_include_shlokas()
  
