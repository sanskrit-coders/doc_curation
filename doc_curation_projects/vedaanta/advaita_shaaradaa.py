import os.path

from doc_curation.scraping.misc_sites import advaita_shaaradaa

dest_dir = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/content/shAnkara-darshanam/"

if __name__ == '__main__':
  pass
  advaita_shaaradaa.dump_text("https://advaitasharada.sringeri.net/display/prakarana/nyayarakshamani", os.path.join(dest_dir, "appayyaH/nyAya-raxA-maNiH.md"))

