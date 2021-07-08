from doc_curation.md import library
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

if __name__ == '__main__':
  pass
  # library.apply_function(fn=MdFile.fix_lazy_anusvaara, dir_path="/home/vvasuki/vvasuki-git/kAvya/content/shAstram/alankAraH/alankAra-maNihAraH", dry_run=False, ignore_padaanta=True, omit_yrl=True)
  # doc_curation.clear_bad_chars(file_path="/home/vvasuki/sanskrit/raw_etexts/mImAMsA/mImAMsA-naya-manjarI.md", dry_run=False)
  # library.apply_function(fn=MdFile.transliterate_content, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/manuH/medhAtithiH/08", source_scheme=sanscript.IAST, file_name_filter=lambda x: str(x).endswith("Text.md"))

  library.apply_function(fn=MdFile.drop_sections, dir_path="/home/vvasuki/vishvAsa/vedAH/static/Rk/shAkalam/saMhitA/vishvAsa-prastutiH/", title_condition=lambda x: x != "मन्त्रः")
  
