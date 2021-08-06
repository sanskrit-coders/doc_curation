import logging

import regex

# Remove all handlers associated with the root logger object.

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def markdownify_plain_text(text_in):
  text = text_in.replace("\n", "  \n")
  text = regex.sub("^  $", "", text)
  return text


def get_md_with_pandoc(content_in, source_format, pandoc_extra_args=['--atx-headers']):
  import pypandoc
  filters = None
  content = pypandoc.convert_text(source=content_in, to="gfm-raw_html", format=source_format,
                                     extra_args=pandoc_extra_args,
                                     filters=filters)
  content = regex.sub("</?div[^>]*?>", "", content)
  content = regex.sub("\n\n+", "\n\n", content)
  return content
