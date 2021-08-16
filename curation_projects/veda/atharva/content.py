import glob
import os

import regex

from doc_curation.md import library
from doc_curation.md.library import get_include

dest_dir_suuktas = "/home/vvasuki/vishvAsa/vedAH/content/atharva/shaunakam/rUDha-saMhitA/sarva-prastutiH"
dest_dir_static = dest_dir_suuktas.replace("/content/", "/static/").replace("sarva-prastutiH", "")
dest_dir_suukta_info = os.path.join(dest_dir_static, "info_vh")
dest_dir_Rks = os.path.join(dest_dir_static, "mUlam")


def set_content(dry_run=False):
  md_files = library.get_md_files_from_path(dir_path=dest_dir_suuktas, file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d\\d", os.path.basename(x))) > 0)
  for md_file in md_files:
    [metadata, _] = md_file.read_md_file()
    path_parts = regex.match(".+(\d\d/\d\d\d_.+?)\.md", str(md_file.file_path))
    if path_parts is None:
      continue
    suukta_id = path_parts.group(1)
    rk_file_names = sorted([x for x in os.listdir(os.path.join(dest_dir_Rks, suukta_id)) if x != "_index.md"])
    content = ""

    file_path = os.path.join(dest_dir_static, "info_vh", suukta_id + ".md")
    if os.path.exists(file_path):
      url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
      content += "%s\n" % library.get_include(field_names=None, classes=None, title="अनुक्रमणी (VH)", url=url)

    file_path = os.path.join(dest_dir_static, "griffith", suukta_id + "/_index.md")
    if os.path.exists(file_path):
      url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
      content += "%s\n" % library.get_include(field_names=None, classes=None, title="Griffith", url=url)

    for rk_file_name in rk_file_names:
      file_path = os.path.join(dest_dir_static, "vishvAsa-prastutiH", suukta_id, rk_file_name)
      url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
      content += "%s\n" % library.get_include(field_names=None, classes=None, title="विश्वास-प्रस्तुतिः", url=url)

      file_path = os.path.join(dest_dir_static, "mUlam", suukta_id, rk_file_name)
      url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
      content += "%s\n" % library.get_include(field_names=None, classes=["collapsed"], title="मूलम्", url=url, h1_level=3)

      file_path = os.path.join(dest_dir_static, "griffith", suukta_id, rk_file_name)
      if os.path.exists(file_path):
        url = regex.sub(".+?/vedAH/", "/vedAH/", file_path).replace("/static/", "/")
        content += "%s\n" % library.get_include(field_names=None, classes=None, title="Griffith", url=url)

        content += "\n\n"

    md_file.replace_content(new_content=content, dry_run=dry_run)
  library.fix_index_files(dir_path=dest_dir_suuktas)


def set_suukta_info_to_match(dest_dir, dry_run=False):
  md_files = library.get_md_files_from_path(dir_path=dest_dir_suukta_info, file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d\\d", os.path.basename(x))) > 0)
  for md_file in md_files:
    [metadata, content] = md_file.read_md_file()
    path_parts = regex.match(".+(\d\d/\d\d\d)", str(md_file.file_path))
    if path_parts is None:
      continue
    suukta_id = path_parts.group(1)
    dest_md_file = MdFile(file_path=os.path.join(dest_dir, "%s/_index.md" % suukta_id))
    dest_md_file.dump_to_file(metadata=metadata, content="", dry_run=dry_run)
    dest_md_file.set_filename_from_title(transliteration_source=sanscript.DEVANAGARI, dry_run=dry_run, skip_dirs=False)


if __name__ == '__main__':
  # dump_text(base_dir="/home/vvasuki/sanskrit/raw_etexts/vedaH/atharva/shaunaka/saMhitA_VH")
  set_content()
  # set_suukta_info_to_match(dest_dir=os.path.join(dest_dir_static, "vishvAsa-prastutiH"))
  # library.fix_index_files(dest_dir_suuktas)
  pass
