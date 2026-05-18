import logging

import regex

# Remove all handlers associated with the root logger object.

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


def markdownify_plain_text(text_in):
  text = regex.sub(r"(?<=\S) *\n", r"  \n", text_in.strip())
  text = regex.sub(r"^ +", "", text, flags=regex.MULTILINE)
  text = regex.sub(r"^ +$", "", text, flags=regex.MULTILINE)
  return text


