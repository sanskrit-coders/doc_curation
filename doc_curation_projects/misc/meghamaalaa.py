import logging
import os.path

from doc_curation.md import library, content_processor
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

from doc_curation.scraping.misc_sites import meghamaalaa


if __name__ == '__main__':
  meghamaalaa.dump_series("https://srivaishnavan.com/publications/meghamala/upanishads/katopanishat-content/%e0%a4%95%e0%a4%a0%e0%a5%8b%e0%a4%aa%e0%a4%a8%e0%a4%bf%e0%a4%b7%e0%a4%a4%e0%a5%8d-%e0%a4%aa%e0%a5%8d%e0%a4%b0%e0%a4%a5%e0%a4%ae%e0%a4%be-%e0%a4%b5%e0%a4%b2%e0%a5%8d%e0%a4%b2%e0%a5%80/", "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/AraNyakam/kaThopaniShat/ranga-rAmAnujaH")