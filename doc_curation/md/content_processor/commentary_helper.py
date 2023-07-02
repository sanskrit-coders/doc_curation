import logging
from bs4 import BeautifulSoup, NavigableString

import regex

from indic_transliteration import sanscript
import regex

from doc_curation.md import content_processor, library
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement
from doc_curation.utils import patterns


def separate_parts(content, exclusion_pattern, inclusion_pattern=patterns.DEVANAGARI, replacement=r"\1\n\n<details><summary>मूलम्</summary>\n\n\2\n</details>\n\n"):
  content = regex.sub(rf"({exclusion_pattern})\s*({inclusion_pattern}[\s\S]+?)\s*(?={exclusion_pattern})", replacement, content)
  return content


def transliterate_init_ids(content, id_pattern=r"॥ *([०-९]+) *॥", source_script=sanscript.DEVANAGARI, dest_script=sanscript.IAST):
  """
  
  Sometimes, content may contain different but related identically numbered sections (eg. shloka and commentary). For fu
  rther processing, it may be convenient to distinguish them based on which appears first.
  
  :param content: 
  :param id_pattern: 
  :param source_script: 
  :param dest_script: 
  :return: 
  """
  matches = list(regex.finditer(id_pattern, content))
  ids = [x.group(1) for x in matches]
  id_counts = {}
  for id in ids:
    id_counts[id] = id_counts.get(id, 0) + 1

  for id, count in id_counts.items():
    if count != 2:
      logging.warning(f"{id} count is {count}. Skipping.")
    else:
      particular_id_pattern = regex.sub(r"\(.+?\)", id, id_pattern)
      replacement = regex.sub(r"\(.+?\)", sanscript.transliterate(id, source_script, dest_script), id_pattern).replace(" *", "")
      content = regex.sub(particular_id_pattern, replacement, content, count=1)
  
  return content


def move_detail_to_matching_file(dest_dir, source_file, dest_id_maker=None, dest_pattern="<details.+?summary>मूलम्</summary>[\s\S]+?॥ *([०-९]+) *॥\s*</details>\n*", source_pattern="(?<=\n|^)([\d०-९೦-೯]+).+\n", dry_run=False):
  source_md = MdFile(file_path=source_file)
  (_, source_content) = source_md.read()
  source_match_map = content_processor.get_quasi_section_int_map(source_content, source_pattern)

  dest_md_files = library.get_md_files_from_path(dir_path=dest_dir)  
  if dest_id_maker is None:
    def dest_id_maker(x): 
      return arrangement.get_sub_path_id(x.file_path.replace(dest_dir, ""))
  for md_file in dest_md_files:
    index_str = dest_id_maker(md_file)
    if not index_str.isnumeric():
      logging.warning(f"Could not get index for: {index_str} in file {md_file.file_path}")
      continue
    index = int(index_str)
    if index not in source_match_map:
      logging.warning(f"Could not get commentary for: {index} in file {md_file.file_path}")
      continue
    (dest_metadata, dest_content) = md_file.read()
    dest_matches = list(regex.finditer(dest_pattern, dest_content))
    if len(dest_matches) == 0:
      logging.warning(f"Could not get insertion point for: {index} in file {md_file.file_path}")
      continue
    dest_match = dest_matches[0]
    inserted_html = source_match_map[index].group()
    dest_content = dest_content.replace(dest_match.group(), "%s\n\n%s" % (dest_match.group(), inserted_html))
    md_file.replace_content_metadata(new_content=dest_content, dry_run=dry_run)
    source_content = source_content.replace(source_match_map[index].group(), "")
  source_md.replace_content_metadata(new_content=source_content, dry_run=dry_run)

  pass