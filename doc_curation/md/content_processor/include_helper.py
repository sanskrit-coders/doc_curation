import regex

from doc_curation.md import content_processor


def migrate_and_include_texts(content, include_path_maker, include_maker, text_pattern="\n[^#\s<][\s\S]+?॥\s*[०-९\d\.]+\s*॥.*?", title_before_include_str_fmt=None, title_maker=None, dry_run=False):
  # For some regexes to work prefectly.
  content = "\n" + content
  matches = regex.findall(text_pattern, content)
  if title_maker is None:
    def title_maker(text, index):
      title = content_processor.title_from_text(text=text, num_words=2, target_title_length=None, depunctuate=True,
                                                title_id=index)
      return title
  for index, text in enumerate(matches):
    title = title_maker(text=text, index=index)
    text_path = include_path_maker(title)
    from doc_curation.md.file import MdFile
    md_file = MdFile(file_path=text_path)
    md_file.dump_to_file(metadata={"title": title}, content=text, dry_run=dry_run)
    include_text = include_maker(text_path)
    if title_before_include_str_fmt is not None:
      title_line = title_before_include_str_fmt % title
      include_text = "%s\n%s" % (title_line, include_text)
    content = content.replace(text.strip(), "%s\n" % include_text)
  return content


def transform_include_lines(content, transformer):
  content = regex.sub("<div.+js_include.+url=['\"](.+?)['\"][\s\S]+?</div>", transformer, content)
  return content