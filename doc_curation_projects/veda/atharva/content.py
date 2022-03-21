import glob
import logging
import os

import regex

from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.md.library import get_include
from indic_transliteration import sanscript

dest_dir_suuktas = "/home/vvasuki/vishvAsa/vedAH/content/atharva/shaunakam/rUDha-saMhitA/sarva-prastutiH"
dest_dir_static = dest_dir_suuktas.replace("/content/", "/static/").replace("sarva-prastutiH", "")
dest_dir_suukta_info = os.path.join(dest_dir_static, "info_vh")
dest_dir_Rks = os.path.join(dest_dir_static, "mUlam")




def set_book_content(dry_run=False):
  md_files = library.get_md_files_from_path(dir_path=dest_dir_suuktas, file_pattern="**/_index.md", file_name_filter=lambda x: regex.match("\\d\\d", os.path.basename(os.path.dirname(x))))
  for md_file in md_files:
    path_parts = regex.match(".+/(\d\d)/_index\.md", str(md_file.file_path))
    if path_parts is None:
      continue
    book_id = path_parts.group(1)
    content = ""


    file_path = os.path.join(dest_dir_static, "whitney/notes", book_id + "/_index.md")
    if os.path.exists(file_path):
      url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
      content += "%s\n" % library.get_include(field_names=None, classes=None, title="अनुक्रमणी (Whitney)", url=url,
                                              h1_level=2)

    md_file.replace_content_metadata(new_content=content, dry_run=dry_run)
  library.fix_index_files(dir_path=dest_dir_suuktas)


def set_suukta_content(dry_run=False):
  md_files = library.get_md_files_from_path(dir_path=dest_dir_suuktas, file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d\\d", os.path.basename(x))) > 0)
  for md_file in md_files:
    [metadata, _] = md_file.read()
    path_parts = regex.match(".+(\d\d/\d\d\d.*)\.md", str(md_file.file_path))
    if path_parts is None:
      continue
    suukta_id = path_parts.group(1)
    rk_file_names = sorted([x for x in os.listdir(os.path.join(dest_dir_Rks, suukta_id)) if x != "_index.md"])
    content = get_suukta_meta_content(suukta_id)

    for rk_file_name in rk_file_names:
      content += get_rk_content(rk_file_name, suukta_id)

    md_file.replace_content_metadata(new_content=content, dry_run=dry_run)
  library.fix_index_files(dir_path=dest_dir_suuktas)


def get_suukta_meta_content(suukta_id):
  content = "## अधिसूक्तम्\n\n"
  file_path = os.path.join(dest_dir_static, "info_vh", suukta_id + ".md")
  if os.path.exists(file_path):
    url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
    content += "%s\n" % library.get_include(field_names=None, classes=None, title="अनुक्रमणी (VH)", url=url, h1_level=3)

  file_path = os.path.join(dest_dir_static, "whitney/anukramaNikA", suukta_id + ".md")
  if os.path.exists(file_path):
    url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
    content += "%s\n" % library.get_include(field_names=None, classes=None, title="अनुक्रमणी (Whitney)", url=url,
                                            h1_level=3)

  file_path = os.path.join(dest_dir_static, "whitney/notes", suukta_id + "/_index.md")
  if os.path.exists(file_path):
    url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
    content += "%s\n" % library.get_include(field_names=None, classes=None, title="अनुक्रमणी (Whitney)", url=url,
                                            h1_level=3)

  file_path = os.path.join(dest_dir_static, "griffith", suukta_id + "/_index.md")
  if os.path.exists(file_path):
    url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
    content += "%s\n\n\n" % library.get_include(field_names=None, classes=None, title="Griffith", url=url,
                                                h1_level=3)
  return content


def get_rk_content(rk_file_name, suukta_id):
  content = ""
  file_path = os.path.join(dest_dir_static, "vishvAsa-prastutiH", suukta_id, rk_file_name)
  md_file_rk = MdFile(file_path=file_path)
  (metadata, _) = md_file_rk.read()
  content += "## %s\n" % metadata["title"]
  url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
  content += "%s\n" % library.get_include(field_names=None, classes=None, title="विश्वास-प्रस्तुतिः", url=url,
                                          h1_level=3)
  file_path = os.path.join(dest_dir_static, "mUlam", suukta_id, rk_file_name)
  url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
  content += "%s\n" % library.get_include(field_names=None, classes=["collapsed"], title="मूलम्", url=url, h1_level=4)
  file_path = os.path.join(dest_dir_static, "whitney/notes", suukta_id, rk_file_name)
  if os.path.exists(file_path):
    url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
    content += "%s\n" % library.get_include(field_names=None, classes=None, title="Whitney", url=url, h1_level=3)
  file_path = os.path.join(dest_dir_static, "griffith", suukta_id, rk_file_name)
  if os.path.exists(file_path):
    url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
    content += "%s\n" % library.get_include(field_names=None, classes=None, title="Griffith", url=url, h1_level=3)

    content += "\n\n"
  return content


def set_suukta_info_to_match(dest_dir, dry_run=False):
  md_files = library.get_md_files_from_path(dir_path=dest_dir_suukta_info, file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d\\d", os.path.basename(x))) > 0)
  for md_file in md_files:
    [metadata, content] = md_file.read()
    path_parts = regex.match(".+(\d\d/\d\d\d)", str(md_file.file_path))
    if path_parts is None:
      continue
    suukta_id = path_parts.group(1)
    dest_md_file = MdFile(file_path=os.path.join(dest_dir, "%s/_index.md" % suukta_id))
    dest_md_file.dump_to_file(metadata=metadata, content="", dry_run=dry_run)
    dest_md_file.set_filename_from_title(source_script=sanscript.DEVANAGARI, dry_run=dry_run, skip_dirs=False)


def rename_suukta_files(dest_dir, dry_run=False):
  md_files = library.get_md_files_from_path(dir_path=dest_dir_suukta_info, file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d\\d", os.path.basename(x))) > 0)
  for md_file in md_files:
    path_parts = regex.match(".+(\d\d)/(\d\d\d)", str(md_file.file_path))
    if path_parts is None:
      continue
    kaanda_id = path_parts.group(1)
    suukta_id = path_parts.group(2)
    if not os.path.exists(os.path.join(dest_dir, kaanda_id)):
      continue
    suukta_file_names = [x for x in os.listdir(os.path.join(dest_dir, kaanda_id)) if x.startswith(suukta_id)]
    if len(suukta_file_names) != 1:
      logging.warning("%s/%s %s", kaanda_id, suukta_id, suukta_file_names)
      continue
    suukta_path = os.path.join(dest_dir, kaanda_id, suukta_file_names[0])
    target_base_name = os.path.basename(md_file.file_path)
    if not suukta_path.endswith(".md"):
      target_base_name = target_base_name.replace(".md", "")
    suukta_path_needed = os.path.join(dest_dir, kaanda_id, target_base_name)
    if os.path.exists(suukta_path) and suukta_path != suukta_path_needed:
      logging.info("Moving %s to %s", suukta_path, suukta_path_needed)
      if not dry_run:
        os.rename(suukta_path, suukta_path_needed)


if __name__ == '__main__':
  # dump_text(base_dir="/home/vvasuki/sanskrit/raw_etexts/vedaH/atharva/shaunaka/saMhitA_VH")
  set_suukta_content()
  set_book_content()
  # rename_suukta_files(dest_dir=os.path.join(dest_dir_static, "whitney/notes"), dry_run=False)
  # library.fix_index_files(dest_dir_suuktas)
  pass
