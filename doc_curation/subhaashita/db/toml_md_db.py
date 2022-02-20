import logging
import os
import sys
from copy import copy

from doc_curation import subhaashita
from doc_curation.md.file import MdFile
from sanskrit_data import collection_helper

from doc_curation.subhaashita import CommentaryKey
import editdistance


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
      quote_keys = quote.get_variant_keys()
      quote_old_keys = quote_old.get_variant_keys()
      distance = editdistance.eval(quote_keys[0], quote_old_keys[0]) / float(max(len(quote_keys[0]), len(quote_old_keys[0]))) 
      if distance > 0.1:
        logging.warning("Quote key clash %0.2f detected: (%s vs %s)\n(%s vs %s)", distance, quote_keys[0], quote_old_keys[0], quote.get_text(), quote_old.get_text())
        key = quote.get_key(max_length=len(key) + 5)
        if len(key) >= subhaashita.HARD_MAX_KEY_LENGTH:
          key_parts = key.split("_")
          index = 1 if len(key_parts) == 1 else int(key_parts[1]) + 1
          key = "%s_%d" % (key, index)
          logging.warning("Quote key clash - forced to enumerate: %s (%s vs %s)", key, quote.commentaries[CommentaryKey.TEXT], quote_old.commentaries[CommentaryKey.TEXT])
          # sys.exit()
        file_path = os.path.join(dir_path, key + ".md")
        continue
      else:
        metadata = collection_helper.update_with_lists_as_sets(metadata_old, metadata)
        quote_text = quote.get_text()
        commentaries = quote.commentaries
        quote.commentaries = copy(quote_old.commentaries)
        quote.commentaries.update(commentaries)
        old_variants = quote_old.get_variants()
        if quote_keys[0] not in quote_old_keys:
          old_variants.append(quote_text)
          quote.set_variants(old_variants)
        (_, md) = quote.to_metadata_md()
        break
    md_file = MdFile(file_path=file_path)
    md_file.dump_to_file(metadata=metadata, content=md, dry_run=dry_run)