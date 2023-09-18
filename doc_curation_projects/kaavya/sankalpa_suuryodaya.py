import os.path

from indic_transliteration import sanscript

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import details_helper, footnote_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper


def fix_footnotes(dir_path):
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.define_footnotes_near_use(c), dry_run=False)
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.fix_intra_word_footnotes(c), dry_run=False)


def match_muula_commentary():
  base_file = "/home/vvasuki/gitland/vishvAsa/kAvyam/content/laxyam/rUpakam/sankalpa-sUryodayaH/10_niH-shreyasa-lAbhaH.md"
  # TODO: MANUAL: Insert a EEEEE in the end; also ensure that the final text + commentary have a verse number.
  # TODO: Remove all html tags/ comments.
  
  # library.apply_function(fn=content_processor.replace_texts, dir_path=base_file, patterns=[r"\|"], replacement="।")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=base_file, patterns=["। *।"], replacement="॥")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=base_file, patterns=["(?<=[ँ-९])\:"], replacement="ः")
  # 
  # library.apply_function(fn=content_processor.replace_texts, dir_path=base_file, patterns=[r"EEE+\s*([\S\s]+?)\s*(?=WWW+|QQQ+)"], replacement=r"\nEEEEE\n\n<details><summary>मूलम्</summary>\n\n\1\n</details>\n\n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=base_file, patterns=[r"WWW+\s*(प्रभाविलासः)?\s*([\S\s]+?)\s*(?=WWW+|QQQ+|EEE+)"], replacement=r"\nWWWWW\n\n<details><summary>प्रभाविलासः</summary>\n\n\2\n</details>\n\n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=base_file, patterns=[r"QQQ+\s*(प्रभावली)?\s*([\S\s]+?)\s*(?=WWW+|QQQ+|EEE+)"], replacement=r"\nQQQQQ\n\n<details><summary>प्रभावली</summary>\n\n\2\n</details>\n\n")
  
  tmp_dir = os.path.join(os.path.dirname(base_file), "tmp")
  muula_1 = os.path.join(tmp_dir, "mUlam.md")
  comment_1 = os.path.join(tmp_dir, "prabhAvalI.md")
  comment_2 = os.path.join(tmp_dir, "prabhAvilAsa.md")

  # details_helper.dump_detail_content(source_md=MdFile(file_path=base_file), dest_path=comment_1, titles=["प्रभावली"])
  # details_helper.dump_detail_content(source_md=MdFile(file_path=base_file), dest_path=comment_2, titles=["प्रभाविलासः"])
  # details_helper.dump_detail_content(source_md=MdFile(file_path=base_file), dest_path=muula_1, titles=["मूलम्"])

  # TODO : Manually check and match ॥[ ०-९]+॥ counts in files to be sure.
  # library.apply_function(fn=content_processor.replace_texts, dir_path=muula_1, patterns=["(?<=^|॥[ ०-९]+॥)\s*(\S[\S\s]+?॥ *([०-९]+) *॥)"], replacement="\n\n<details open><summary>विश्वास-प्रस्तुतिः - \\2</summary>\n\n\\1\n</details>\n\n<details><summary>मूलम् - \\2</summary>\n\n\\1\n</details>\n\n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=comment_1, patterns=["(?<=^|॥[ ०-९]+॥)\s*(\S[\S\s]+?॥ *([०-९]+) *॥)"], replacement="\n\n<details><summary>प्रभावली - \\2</summary>\n\n\\1\n</details>\n\n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=comment_2, patterns=["(?<=^|॥[ ०-९]+॥)\s*(\S[\S\s]+?॥ *([०-९]+) *॥)"], replacement="\n\n<details><summary>प्रभाविलासः - \\2</summary>\n\n\\1\n</details>\n\n")
  # 
  # library.apply_function(fn=content_processor.replace_texts, dir_path=tmp_dir, patterns=["\n\n\n+"], replacement="\n\n")

  # Interleave from file
  # library.apply_function(fn=details_helper.interleave_from_file, dir_path=muula_1, source_file=lambda x: x.replace("mUlam", "prabhAvalI"), detail_title=None, dest_pattern= "<details.+?summary>मूलम् *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= "<details.+?summary>प्रभावली *- *(\S+)</summary>[\s\S]+?</details>\n", dry_run=False)
  # library.apply_function(fn=details_helper.interleave_from_file, dir_path=muula_1, source_file=lambda x: x.replace("mUlam", "prabhAvilAsa"), detail_title=None, dest_pattern= "<details.+?summary>प्रभावली *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= "<details.+?summary>प्रभाविलासः *- *(\S+)</summary>[\s\S]+?</details>\n", dry_run=False)

  # TODO: Manually copy over to base file, above footnotes.
  fix_footnotes(dir_path=base_file)
  # library.apply_function(dir_path=os.path.dirname(base_file), fn=metadata_helper.set_filename_from_title, source_script=sanscript.DEVANAGARI, dry_run=False)


if __name__ == '__main__':
  match_muula_commentary()
