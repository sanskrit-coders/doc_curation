import os

import doc_curation.scraping.sacred_texts
from doc_curation.scraping.sacred_texts import para_translation

content_dir_base = "/home/vvasuki/vishvAsa/vedAH/content/"


def dump_oldenberg_intros():
  doc_curation.scraping.sacred_texts.dump_meta_article(url="https://www.sacred-texts.com/hin/sbe30/sbe30002.htm", outfile_path=os.path.join(content_dir_base, "meta/sUtram", "oldenberg.md"))
  pass


if __name__ == '__main__':
  dump_oldenberg_intros()