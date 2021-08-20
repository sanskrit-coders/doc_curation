import regex

from doc_curation.md import content_processor


def migrate_and_include_shlokas(content, include_path_maker, include_maker, shloka_pattern="\n[^#\s<][\s\S]+?॥\s*[०-९\d\.]+\s*॥.*?", title_before_include=None, shloka_id_maker=None, dry_run=False):
  # For some regexes to work prefectly.
  content = "\n" + content
  matches = regex.findall(shloka_pattern, content)
  for index, shloka_text in enumerate(matches):
    if shloka_pattern is not None:
      shloka_id = shloka_id_maker(shloka_text)
    else:
      shloka_id = "%03d" % (index + 1)
    title = content_processor.title_from_text(text=shloka_text, num_words=2, target_title_length=None, depunctuate=True,
                                       title_id=shloka_id)
    shloka_path = include_path_maker(title)
    from doc_curation.md.file import MdFile
    md_file = MdFile(file_path=shloka_path)
    md_file.dump_to_file(metadata={"title": title}, content=shloka_text, dry_run=dry_run)
    include_text = include_maker(shloka_path)
    if title_before_include is not None:
      title_line = title_before_include % title
      include_text = "%s\n%s" % (title_line, include_text)
    content = content.replace(shloka_text.strip(), "%s\n" % include_text)
  return content


def transform_include_lines(content, transformer):
  content = regex.sub("<div.+js_include.+url=['\"](.+?)['\"][\s\S]+?</div>", transformer, content)
  return content