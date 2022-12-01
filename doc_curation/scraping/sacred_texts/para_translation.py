import logging

import regex

from doc_curation.md import library

from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.scraping import sacred_texts


def get_main_content(main_content_tag, para_title_to_heading=False):
  elements = main_content_tag.select("p, h1, h2, h3, h4, h5, h6", recursive=False)
  content_out = ""
  for element in elements:
    if element.name == "p":
      if para_title_to_heading:
        para_title = regex.search("(^\d[^ \[.]*)", element.text.strip())
        if para_title is not None:
          para_title = para_title.group(1).strip()
          if para_title.isnumeric():
            para_title = "%02d" % int(para_title)
          else:
            logging.warning("Non numeric element element: %s" % para_title)
          content_out += "## %s\n%s" % (para_title, sacred_texts.get_text(tag=element))
      else:
        content_out += sacred_texts.get_text(tag=element)
    elif element.name.lower().startswith("h"):
      content_out += ("#" * int(element.name[-1])) + " " + sacred_texts.get_text(element)
    content_out += "\n\n"
  return content_out


def split(base_dir):
  library.apply_function(dir_path=base_dir, fn=metadata_helper.set_title_from_filename, transliteration_target=None, dry_run=False)
  library.apply_function(fn=MdFile.split_to_bits, dir_path=base_dir, dry_run=False, source_script=None, title_index_pattern=None)
