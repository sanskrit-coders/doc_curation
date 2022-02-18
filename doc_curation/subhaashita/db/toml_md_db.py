import logging
import os
import sys

from doc_curation import subhaashita
from doc_curation.md.file import MdFile


def add(quotes, base_path, dry_run=False):
  for quote in quotes:
    key = quote.get_key()
    dir_path = base_path
    for letter in key[:5]:
      dir_path = os.path.join(dir_path, letter)
    (metadata, md) = quote.to_metadata_md()
    file_path = os.path.join(dir_path, key + ".md")
    while os.path.exists(file_path):
      md_file = MdFile(file_path=file_path)
      (metadata_old, md_old) = md_file.read()
      quote_old = subhaashita.Quote.from_metadata_md(metadata=metadata_old, md=md_old)
      if quote.text != quote_old.text:
        logging.warning("Quote key clash detected: %s (%s vs %s)", key, quote.text, quote_old.text)
        # TODO: Add logic to create/ check against new file.
        key = quote.get_key(max_length=len(key) + 5)
        if len(key) >= subhaashita.HARD_MAX_KEY_LENGTH:
          key_parts = key.split("_")
          index = 1 if len(key_parts) == 1 else int(key_parts[1]) + 1
          key = "%s_%d" % (key, index)
          logging.warning("Quote key clash - forced to enumerate: %s (%s vs %s)", key, quote.text, quote_old.text)
          # sys.exit()
        file_path = os.path.join(dir_path, key + ".md")
        continue
      else:
        metadata_new = metadata_old.copy()
        metadata_new.update(metadata)
        metadata = metadata_new
        break
        # TODO : Continue this.
    md_file = MdFile(file_path=file_path)
    md_file.dump_to_file(metadata=metadata, content=md, dry_run=dry_run)