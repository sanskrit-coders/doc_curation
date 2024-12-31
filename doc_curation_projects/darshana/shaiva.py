from doc_curation.scraping import sacred_texts
from doc_curation.scraping.sacred_texts import para_translation as para_translation_st


if __name__ == '__main__':
  pass
  sacred_texts.dump_serially(start_url="https://sacred-texts.com/tantra/maha/maha00.htm", base_dir="/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/AgamaH/mahA-nirvAna-tantram/woodroffe")
