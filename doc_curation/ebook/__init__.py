import logging
import os

import regex

from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library.combination import make_full_text_md


def prep_content(content, detail_to_footnotes=True, appendix=None):
  content = regex.sub(r"\+\+\+(\(.+?\))\+\+\+", r'<span class="inline_comment">\1</span>', content)
  content = regex.sub(r" *\.\.\.\{Loading\}\.\.\.", fr"", content)
  if detail_to_footnotes:
    content = details_helper.add_detail_footnotes(content=content, remove_detail=True)
  if appendix is not None:
    if os.path.exists(appendix):
      md_file = MdFile(file_path=appendix)
      metadata, appendix = md_file.read()
      appendix = f"# Appendix - {metadata['title']}\n\n{appendix}"
    content = f"{content}\n\n{appendix}"
  return content


def via_full_md(source_dir, out_path, converter, overwrite=True, cleanup=True):
  full_md_path = os.path.join(source_dir, "full.md")

  if not os.path.exists(full_md_path):
    full_md_path = make_full_text_md(source_dir=source_dir, detail_to_footnotes=True, overwrite=overwrite)
    if full_md_path is None:
      return
  md_file = MdFile(file_path=full_md_path)

  converter(md_file=md_file, out_path=out_path)

  # Clean up full.md files under source_dir
  if cleanup:
    for dirpath, dirnames, filenames in os.walk(source_dir):
      if "full.md" in filenames:
        os.remove(os.path.join(dirpath, "full.md"))
    logging.info(f"Removed {os.path.join(dirpath, 'full.md')} etc..")
