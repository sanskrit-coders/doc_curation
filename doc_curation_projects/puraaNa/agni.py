import os

import regex

from doc_curation.md import library, content_processor

from doc_curation.md.library import arrangement
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


BASE_DIR = "/home/vvasuki/gitland/vishvAsa/purANam/content/agni-purANam/"


def set_titles(dry_run=False):
  md_files = library.get_md_files_from_path(dir_path=BASE_DIR, file_pattern="**/???.md")
  chapter_id_to_file = {}
  for md_file in md_files:
    chapter_id = int(os.path.basename(md_file.file_path).replace(".md", ""))
    chapter_id_to_file[chapter_id] = md_file
  index_md = MdFile(file_path=os.path.join(BASE_DIR, "_index.md"))
  (_, content) = index_md.read()
  matches = regex.finditer("(?<=\n)([०-९]+) +(\S[^\n]+?) (?=[०-९]+)", content)
  for match in matches:
    chapter_id = int(sanscript.transliterate(match.group(1), _to=sanscript.IAST))
    if chapter_id == 221:
      continue
    md_file = chapter_id_to_file[chapter_id]
    (metadata, _) = md_file.read()
    title = f"{metadata['title']} {match.group(2).strip()}"
    md_file.set_title(title, dry_run=dry_run)
    metadata_helper.set_filename_from_title(md_file=md_file, dry_run=dry_run)
  pass


def fix_content():
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/agni-purANam", patterns=["\n॥"], replacement="॥")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/agni-purANam", patterns=["\(([०-९]+)\)"], replacement=r"[^\1]")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/agni-purANam", patterns=["(?<=\n)([०-९]+) "], replacement=r"[^\1]: ")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/agni-purANam", patterns=["(?<=\n):श् +(.+?)(?=\n|$)"], replacement=r"\{\1\}")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/agni-purANam", patterns=["(?<=\n):ए +(.+?)(?=\n|$)"], replacement=r"\{\1\}")
  pass


if __name__ == '__main__':
  # set_titles(dry_run=False)
  fix_content()
