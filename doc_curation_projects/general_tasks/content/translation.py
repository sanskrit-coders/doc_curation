from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile


def add_translation(base_dir):
  # library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda c, m: details_helper.sentences_to_translated_details(c), dry_run=False)
  library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda c, m: details_helper.add_translation(c), dry_run=False)


if __name__ == '__main__':
  add_translation(base_dir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/static/rAmAnuja-sampradAyaH/vyakti-shlokAdi/gurubhyas_tad-gurubhyaH.md")
  pass