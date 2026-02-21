from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.utils import sanskrit_helper
from indic_transliteration.sanscript.schemes.brahmic import accent



def details_fix(dir_path):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args, **kwargs: details_helper.transform_details_with_soup(content=c, content_str_transformer=lambda c, *args, **kwargs : accent.to_US_accents(text=c, pauses=r"[।॥]+"), title_pattern=r"विश्वास-प्रस्तुतिः.*", details_css="details", *args, **kwargs))


def content_fix(dir_path):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args, **kwargs: accent.to_US_accents(text=c, pauses=r"[।॥\[]+"))
  

def fix_old_US_notation(dir_path):
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"꣡"], replacement=r"᳓", )
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"[᳕᳡]"], replacement=r"᳙", )


def typo_fix(dir_path):
  pass
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: sanskrit_helper.fix_svara_typos(x))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: sanskrit_helper.undo_taittirIya_forms(x))


details_fix(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/AraNyakam/sarva-prastutiH/04_pitR-medhAdi/")

# fix_old_US_notation("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/AraNyakam/sarva-prastutiH/04_pitR-medhAdi/01_dAhAntam.md")
# fix_old_US_notation("/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content")
# fix_old_US_notation("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/saMhitA/sarva-prastutiH/1/7_aiShTika-yAjamAnAdi/05_dhruvApyAyanAdi-brAhmaNam.md")
# fix_old_US_notation("/home/vvasuki/gitland/vishvAsa/devaH/content")

# content_fix("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/taittirIyam/sArasvata-vibhAgaH/brAhmaNam/Rk/vishvAsa-prastutiH/2/8_kAmya-pashavaH/9_08-16_nAsadIyam/24_brahma_vanam.md")

# typo_fix("/home/vvasuki/gitland/sanskrit/raw_etexts_private")

# typo_fix("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram")

# typo_fix("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram")
