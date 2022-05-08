import logging
import os

import regex

from doc_curation.md import library
from doc_curation_projects.iitk import bhagavadgiitaa
from indic_transliteration import sanscript


def to_language_code_or_transliterate(text):
  if text == "english":
    return "(Eng)"
  elif text == "saMskRtam":
    return "(सं)"
  elif text == "hindI":
    return "(हि)"
  return sanscript.transliterate(text, sanscript.OPTITRANS, sanscript.DEVANAGARI)


def title_from_folder_path(folder_path):
  path_parts = folder_path.split("/")
  title_parts = [to_language_code_or_transliterate(path_parts[0])]
  for p in path_parts[1:]:
    title = to_language_code_or_transliterate(p)
    title_parts.append(title)
  return " ".join(title_parts)


def make_content_files(base_dir):
  static_dir_base = base_dir.replace("/content/", "/static/")
  md_files = library.get_md_files_from_path(dir_path=base_dir, file_pattern="**/*.md", file_name_filter=lambda x: regex.match("^\\d\\d_", os.path.basename(x)) is not None)
  for md_file in md_files:
    content = ""
    file_path = md_file.file_path

    for alt_title, folder_path in bhagavadgiitaa.iitk_title_to_folder_path.items():
      if "__________" in folder_path:
        content += "\n\n_________________\n## %s\n" % alt_title
        continue
      title = title_from_folder_path(folder_path=folder_path)
      logging.info("%s %s", title, folder_path)
      
      url = str(file_path).replace(base_dir, "/purANam/mahAbhAratam/06-bhIShma-parva/02-bhagavad-gItA-parva/sarva-prastutiH")
      url = url.replace("sarva-prastutiH", folder_path).replace("//", "/")
      included_file_path = url.replace("/purANam", "/home/vvasuki/vishvAsa/purANam/static")
      if "vishvAsa-prastutiH" in included_file_path:
        classes = []
        h1_level = 2 
      else:
        classes = ["collapsed"]
        h1_level = 3
      if os.path.exists(included_file_path):
        content += "%s\n" % library.get_include(field_names=None, classes=classes, title=title, url=url, h1_level=h1_level)
    
    md_file.replace_content_metadata(new_content=content, dry_run=False)

if __name__ == '__main__':
  base_dir = "/home/vvasuki/vishvAsa/purANam/content/mahAbhAratam/06-bhIShma-parva/02-bhagavad-gItA-parva/sarva-prastutiH"
  make_content_files(base_dir=base_dir)
  # library.fix_index_files(dir_path=base_dir, dry_run=False)
