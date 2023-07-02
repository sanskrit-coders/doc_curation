import os.path

from indic_transliteration import sanscript

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import details_helper, footnote_helper, commentary_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper


STATIC_DIR_BASE = "/home/vvasuki/gitland/vishvAsa/AgamaH_brAhmaH/static/shrI-sampradAyaH/venkaTanAthaH/tattva-muktA-kalApaH"

TIKA_SOURCE = os.path.join(STATIC_DIR_BASE, "sarvAnkaSha-TikA")
STATIC_DEST = os.path.join(STATIC_DIR_BASE, "sarvASh_TIkAH")



def match_muula_commentary():
  pass
  # library.apply_function(fn=MdFile.transform, dir_path=TIKA_SOURCE, content_transformer=lambda x, y: commentary_helper.transliterate_init_ids(x), dry_run=False)
  # library.apply_function(fn=content_processor.replace_texts, dir_path=TIKA_SOURCE, patterns=["(?<=^|॥[ ०-९]+॥)\s*(\S[\S\s]+?॥ *([०-९]+) *॥)"], replacement="\n\n<details><summary>सर्वाङ्कषटीका - \\2</summary>\n\n\\1\n</details>\n\n")
  ## Interleave from file
  for dir in ["4_buddhi-saraH"]:
  # for dir in os.listdir(STATIC_DEST):
    dir = os.path.join(STATIC_DEST, dir)
    if not os.path.isdir(dir):
      continue
    commentary_helper.move_detail_to_matching_file(dest_dir=dir, source_file=dir.replace("sarvASh_TIkAH", "sarvAnkaSha-TikA") + ".md", source_pattern= "<details.+?summary>सर्वाङ्कषटीका *- *(\S+)</summary>[\s\S]+?</details>\n", dry_run=False)


if __name__ == '__main__':
  match_muula_commentary()
