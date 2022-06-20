import logging
import os
from collections import defaultdict

import regex
from tqdm import tqdm

from doc_curation.md.file import MdFile
from doc_curation.md.library import get_md_files_from_path
from indic_transliteration import sanscript


def combine_select_files_in_dir(md_file, source_fname_list, dry_run=False):
  dir_path = os.path.dirname(md_file.file_path)
  source_mds = [MdFile(file_path=os.path.join(dir_path, x)) for x in source_fname_list if x in os.listdir(dir_path)]
  md_file.append_content_from_mds(source_mds=source_mds, dry_run=dry_run)
  if not dry_run:
    for source_md in source_mds:
      os.remove(source_md.file_path)


def combine_files_in_dir(md_file, dry_run=False):
  dir_path = os.path.dirname(md_file.file_path)
  source_mds = [MdFile(file_path=os.path.join(dir_path, x)) for x in sorted(os.listdir(dir_path)) if os.path.isfile(os.path.join(dir_path, x)) and x.endswith(".md") and x != os.path.basename(md_file.file_path) ]
  md_file.append_content_from_mds(source_mds=source_mds, dry_run=dry_run)
  if not dry_run:
    for source_md in source_mds:
      os.remove(source_md.file_path)


def combine_to_details(source_paths_or_content, dest_path, source_path_to_title=None, mode="overwrite", default_script=sanscript.DEVANAGARI, dravidian_titles=False, dry_run=False):
  final_content_map = defaultdict(lambda : "")
  final_metadata_map = defaultdict(lambda: {})
  ready_content = None
  for source_path in source_paths_or_content:
    logging.info(f"Scanning {source_path}")
    if source_path.startswith("CONTENT:"):
      ready_content = source_path.replace("CONTENT:", "")
      continue
    index_md_path = os.path.join(source_path, "_index.md")
    if os.path.exists(index_md_path):
      md_file = MdFile(file_path=index_md_path)
      (metadata, content) = md_file.read()
      title = metadata["title"]
      if title.startswith("+"):
        title = title[1:]
    elif source_path_to_title is not None and source_path in source_path_to_title:
      title = source_path_to_title[source_path]
    else:
      title = os.path.basename(source_path)
      title = sanscript.transliterate(title, _from=sanscript.OPTITRANS, _to=default_script, maybe_use_dravidian_variant=dravidian_titles)
    
    md_files = get_md_files_from_path(dir_path=source_path)
    for md_file in tqdm(md_files):
      subpath = md_file.file_path.replace(source_path, "")
      if subpath.startswith("/"):
        subpath = subpath[1:]
      (metadata, content) = md_file.read()
      from doc_curation.md.content_processor import details_helper
      if content.strip() != "":
        if ready_content is not None:
          final_content_map[subpath] += f"\n{ready_content}\n"
        detail = details_helper.Detail(type=title, content=content)
        final_content_map[subpath] += f"\n{detail.to_html()}\n"
      for key, value in metadata.items():
        final_metadata = final_metadata_map[subpath]
        if key not in final_metadata:
          final_metadata[key] = value
    ready_content = None
      
  for subpath in tqdm(sorted(final_metadata_map.keys())):
    # logging.info(f"Dumping {source_path}")
    md_file = MdFile(file_path=os.path.join(dest_path, subpath))
    metadata = final_metadata_map[subpath]
    content = final_content_map[subpath]
    if os.path.exists(md_file.file_path):
      (metadata_init, content_init) = md_file.read()
      if mode == "prepend":
        metadata.update(metadata_init)
        content = f"{content}\n\n{content_init}"
    md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)


def make_full_text_md(source_dir, dry_run=False):
  """Create a text - by include-directives - which includes all md files within the directory."""
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  content = ""
  title = "पूर्णपाठः"
  rel_url = "../"

  num_md_files = 0

  index_md_path = os.path.join(source_dir, "_index.md")
  if os.path.exists(index_md_path):
    index_md = MdFile(file_path=index_md_path)
    (index_yml, _) = index_md.read()
    title = "%s (%s)" % (index_yml["title"], title)
    content = "%s\n%s" % (content, """<div class="js_include" url="%s"  newLevelForH1="1" includeTitle="false"> </div>""" % (rel_url).strip())
    num_md_files = num_md_files + 1


  for subfile in sorted(os.listdir(source_dir)):
    subfile_path = os.path.join(source_dir, subfile)
    if os.path.isdir(subfile_path):
      if subfile not in ["images"]:
        make_full_text_md(source_dir=subfile_path)
        sub_md_file_path = os.path.join(subfile, "full.md")
      else:
        continue
    else:
      if subfile in ("full.md", "_index.md") or not str(subfile).endswith(".md"):
        continue
      sub_md_file_path = subfile

    num_md_files = num_md_files + 1
    rel_url = os.path.join("..", regex.sub("\.md", "/", sub_md_file_path))
    content = "%s\n%s" % (content, """<div class="js_include" url="%s"  newLevelForH1="1" includeTitle="true"> </div>""" % (rel_url).strip())
  
  if num_md_files > 0:
    full_md_path = os.path.join(source_dir, "full.md")
    full_md = MdFile(file_path=full_md_path)
    full_md.dump_to_file(content=content, metadata={"title": title}, dry_run=dry_run)
  else:
    logging.info("No md files found in %s. Skipping.", source_dir)
