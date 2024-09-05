import os

from doc_curation.md.library import metadata_helper, arrangement, combination
from doc_curation.scraping.wisdom_lib import serial


def dump_translations():
  pass
  # serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-padma-purana/d/doc364121.html", out_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/padma-purANam/deshpANDe/1", index=1)
  # serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-padma-purana/d/doc364139.html", out_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/padma-purANam/deshpANDe/1", index=18)
  # arrangement.shift_indices(dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/padma-purANam/deshpANDe/1", start_index=19, new_index_offset=-1, dry_run=False)
  serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-padma-purana/d/doc364208.html", out_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/padma-purANam/deshpANDe/2", index=1)
  serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-padma-purana/d/doc365220.html", out_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/padma-purANam/deshpANDe/3", index=1, index_format="%03d")
  serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-padma-purana/d/doc365285.html", out_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/padma-purANam/deshpANDe/4", index=1, index_format="%03d")
  serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-padma-purana/d/doc365312.html", out_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/padma-purANam/deshpANDe/5", index=1, index_format="%03d")
  serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-padma-purana/d/doc365432.html", out_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/padma-purANam/deshpANDe/6", index=1, index_format="%03d")
  serial.dump_series(start_url="https://www.wisdomlib.org/hinduism/book/the-padma-purana/d/doc365842.html", out_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/padma-purANam/deshpANDe/7", index=1, index_format="%03d")


if __name__ == '__main__':
    pass
    # dump_tamil_kaavya()
    dump_translations()