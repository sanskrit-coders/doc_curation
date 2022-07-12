from doc_curation.md import library, content_processor


def general_fix(dir_path):
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"’"], replacement=r"ऽ", dry_run=False)
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\s)ऽ(\S+)ऽ(?=[\s-:])"], replacement=r"'\1'", dry_run=False)

  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=[ँ-९]):"], replacement=r"-", dry_run=False)


  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n)([^>\n].+)\n>"], replacement=r"\1\n\n>", dry_run=False)
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"\n+> (?=.{100})"], replacement=r"\n\n>", dry_run=False)
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n)(\t+|   [ \t]+)(?=\S)"], replacement=r"> ", dry_run=False)
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n)(.+\])\t+\*\*"], replacement=r"> \1** ", dry_run=False)
  for i in range(10):
    library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n)> (.+)\n\n+>"], replacement=r"> \1  \n>", dry_run=False)
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n)([^>][^\n]+)\n>"], replacement=r"\1\n\n>", dry_run=False)



