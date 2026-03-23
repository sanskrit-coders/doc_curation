import logging
import os

import doc_curation.md.library
import regex

import doc_curation.md.content_processor.include_helper
import doc_curation.md.library.arrangement
from doc_curation.md import library
from doc_curation.md.content_processor import include_helper

from doc_curation.md.library import arrangement
from doc_curation_projects.sites.iitk import bhagavadgiitaa
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
  md_files = doc_curation.md.library.get_md_files_from_path(dir_path=base_dir, file_pattern="**/*.md")
  comment_groups = ["saMskRtam/vishvAsa-prastutiH", "saMskRtam/mUlam", "saMskRtam/rAmAnujaH/sarvASh_TIkAH", "saMskRtam/shankaraH/sarvASh_TIkAH", "saMskRtam/madhvaH/sarvASh_TIkAH", "saMskRtam/abhinava-guptaH/sarvASh_TIkAH", "saMskRtam/vallabhaH/sarvASh_TIkAH", "saMskRtam/shrIdhara-svAmI", "english/sarvASh_TIkAH", "hindI/sarvASh_TIkAH"]
  for md_file in md_files:
    content = ""
    file_path = md_file.file_path

    for comment_group in comment_groups:

      url = str(file_path).replace(base_dir, "/mahAbhAratam/vyAsaH/shlokashaH/06-bhIShma-parva/03-bhagavad-gItA-parva/sarva-prastutiH")
      url = url.replace("sarva-prastutiH", comment_group).replace("//", "/")
      included_file_path = url.replace("/mahAbhAratam", "/home/vvasuki/gitland/vishvAsa/mahAbhAratam/static")
      classes = []
      title = None
      if "vishvAsa-prastutiH" in included_file_path:
        h1_level = 2 
        title = "विश्वास-प्रस्तुतिः"
      elif "mUlam" in included_file_path:
        classes = ["collapsed"]
        title = "मूलम्"
        
        
      if os.path.exists(included_file_path):
        content += "%s\n" % include_helper.Include(field_names=None, classes=classes, title=title, url=url, h1_level=h1_level).to_html_str()
    content = regex.sub(r"(?<=\n)____+\n##[^\n]+\s+(?=____+|$)", "", content)
    md_file.replace_content_metadata(new_content=content, dry_run=False)
  include_helper.prefill_includes(dir_path=base_dir)



if __name__ == '__main__':
  base_dir = "/home/vvasuki/gitland/vishvAsa/mahAbhAratam/content/vyAsaH/shlokashaH/bhagavad-gItA-parva/sarva-prastutiH"
  make_content_files(base_dir=base_dir)
  # arrangement.fix_index_files(dir_path=base_dir, dry_run=False)
