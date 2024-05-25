import logging
import os.path

from indic_transliteration import sanscript

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import details_helper, footnote_helper, commentary_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper


STATIC_DIR_BASE = "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/static/rAmAnuja-sampradAyaH/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/tattva-muktA-kalApaH/sarvASh_TIkAH"

CONTENT_DIR_BASE = "/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/rAmAnuja-sampradAyaH/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/tattva-muktA-kalApaH/"


def raw_comment_to_details(source_dir, detail_title):
  library.apply_function(fn=content_processor.replace_texts, dir_path=source_dir, patterns=["(?<=^|॥[ ०-९]+॥)\s*(\S[\S\s]+?॥ *([०-९]+) *॥)"], replacement=f"\n\n<details><summary>{detail_title} - \\2</summary>\n\n\\1\n</details>\n\n")


def number_comments(source_dir):
  pass
  # library.apply_function(fn=MdFile.transform, dir_path=TIKA_SOURCE, content_transformer=lambda x, y: commentary_helper.transliterate_init_ids(x), dry_run=False)
  library.apply_function(fn=MdFile.transform, dir_path=source_dir, content_transformer=lambda x, y: details_helper.autonumber_details(x, number_pattern=r"[॥।]? *([०-९]+) *[॥।]?\s*"), dry_run=False)
  # library.apply_function(fn=content_processor.replace_texts, dir_path=source_dir, patterns=["(?<=^|॥[ ०-९]+॥)\s*(\S[\S\s]+?॥ *([०-९]+) *॥)"], replacement="\n\n<details><summary>सर्वाङ्कषा - \\2</summary>\n\n\\1\n</details>\n\n")
  

def match_muula_commentary(source_dir, dest_pattern):
  pass
  number_comments(source_dir=source_dir)

  source_pattern = "<details.+?summary>.+? *- *(\S+)</summary>[\s\S]+?</details>\n"
  # source_pattern = "<details.+?summary>.+?</summary>[\s\S]+?[॥।]? *([०-९]+) *[॥।]?\s*</details>\n"
  ## Interleave from file
  # for dir in ["1_jaDa-dravya-saraH"]:
  for dir in sorted(os.listdir(STATIC_DIR_BASE)):
    if dir.startswith("_") or "_" not in dir:
      continue
    sara_id = int(dir.split("_")[0])
    source_file = [x for x in os.listdir(source_dir) if not x.startswith("_") and "_" in x and int(x.split("_")[0]) == sara_id]
    if len(source_file) != 1:
      logging.warning(f"{source_file}")
      continue
    source_file = source_file[0]
    source_file = os.path.join(source_dir, source_file)
    commentary_helper.move_detail_to_matching_file(dest_dir=os.path.join(STATIC_DIR_BASE, dir), source_file=source_file, source_pattern= source_pattern, dest_pattern=dest_pattern, dry_run=False)


if __name__ == '__main__':
  pass
  # raw_comment_to_details(source_dir=os.path.join(CONTENT_DIR_BASE, "kottamangala-varadaH/subodhinI_kn/"), detail_title="ಕನ್ನಡ")
  # number_comments(source_dir=os.path.join(CONTENT_DIR_BASE, "sarvArtha-siddhiH"))
  # match_muula_commentary(source_dir=os.path.join(CONTENT_DIR_BASE, "sarvArtha-siddhiH"), dest_pattern= "<details.+?summary>सर्वाङ्कषा.*?</summary>[\s\S]+?</details>\n")

  # match_muula_commentary(source_dir=os.path.join(CONTENT_DIR_BASE, "abhinava-ranganAthaH_bhAva-prakAshaH"), dest_pattern= "<details.+?summary>सर्वार्थसिद्धिः.*?</summary>[\s\S]+?</details>\n")
  match_muula_commentary(source_dir=os.path.join(CONTENT_DIR_BASE, "narasiMha-devaH_AnandadAyinI"), dest_pattern= "<details.+?summary>सर्वार्थसिद्धिः.*?</summary>[\s\S]+?</details>\n")
