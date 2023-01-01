CONTENT_DIR = "/home/vvasuki/gitland/vishvAsa/purANam/content/mudgala-purANam/"


def fix_all(dir_path=CONTENT_DIR):
  pass
  # library.apply_function(fn=MdFile.transform, content_transformer=lambda c, m:content_processor.markdownify_newlines(c), dir_path=dir_path)

  # library.apply_function(fn=MdFile.transform, dir_path=CONTENT_DIR, content_transformer=lambda x, y: content_processor.fix_lazy_anusvaara(x), dry_run=False)

  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["\n +",], replacement="")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["(?<=[।॥]) *\n",], replacement="  \n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["(?<=[॥]) *\n",], replacement="\n\n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["(?<=उवाच *। *)\n",], replacement=r"\n\n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["\n+Pageखं.+ ([०-९\d]+) *\n+(\S.+॥\n)",], replacement=r"\n\2\n\n[[\1]]\n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["Page *ख.+ ([०-९\d]+) *\n",], replacement=r"[[\1]]\n\n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["(?<=\]\])\n(?=\S)",], replacement=r"\n\n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["(?=॥ *श्रीगणेशाय)",], replacement=r"\n\n## \n")

  # library.apply_function(fn=section_helper.autonumber, dir_path=dir_path)
  # library.apply_function(fn=metadata_helper.set_title_from_filename, dir_path=dir_path, frontmatter_type=MdFile.TOML, dry_run=False, transliteration_target=sanscript.DEVANAGARI) # 
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=dir_path, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 

  # library.apply_function(fn=metadata_helper.set_title_from_content, dir_path=dir_path, title_extractor=metadata_helper.iti_naama_title_extractor)
  # library.apply_function(fn=metadata_helper.set_filename_from_title, dir_path=dir_path)

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/mudgala-purANam/4_gajAnana-charitam/06.md", content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c))
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/mudgala-purANam/5_lambodara-charitam/26.md", content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c))


if __name__ == '__main__':
  pass
  # dump_all()
  fix_all()
