import logging
import os

import regex

from curation_utils import file_helper
from doc_curation.md.file import MdFile


def import_md_recursive(source_dir, file_extension, source_format=None, dry_run=False):
  from pathlib import Path
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  source_paths = sorted(Path(source_dir).glob("**/*." + file_extension))
  if source_format is None:
    source_format = file_extension
  for source_path in source_paths:
    md_path = str(source_path).replace("." + file_extension, ".md")
    md_path = file_helper.clean_file_path(md_path)
    if os.path.exists(md_path):
      logging.info("Skipping %s", md_path)
      continue
    logging.info("Processing %s to %s", source_path, md_path)
    md_file = MdFile(file_path=md_path, frontmatter_type=MdFile.TOML)
    md_file.import_with_pandoc(source_file=source_path, source_format=source_format, dry_run=dry_run)


def make_full_text_md(source_dir, dry_run=False):
  from pathlib import Path
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  md = ""
  title = "पूर्णपाठः"
  rel_url = "../"

  num_md_files = 0

  index_md_path = os.path.join(source_dir, "_index.md")
  if os.path.exists(index_md_path):
    index_md = MdFile(file_path=index_md_path)
    (index_yml, _) = index_md.read_md_file()
    title = "%s (%s)" % (index_yml["title"], title)
    md = "%s\n%s" % (md, """<div class="js_include" url="%s"  newLevelForH1="1" includeTitle="false"> </div>""" % (rel_url).strip())
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
    md = "%s\n%s" % (md, """<div class="js_include" url="%s"  newLevelForH1="1" includeTitle="true"> </div>""" % (rel_url).strip())
  
  if num_md_files > 0:
    full_md_path = os.path.join(source_dir, "full.md")
    full_md = MdFile(file_path=full_md_path)
    full_md.dump_to_file(md=md, metadata={"title": title}, dry_run=dry_run)
  else:
    logging.info("No md files found in %s. Skipping.", source_dir)


def migrate_and_include(files, location_computer, new_url_computer, dry_run=False):
  logging.info("Processing %d files", len(files))
  for f in files:
    new_path = location_computer(str(f))
    logging.info("Moving %s to %s", str(f), new_path)
    md_file = MdFile(file_path=f)
    (metadata, _) = md_file.read_md_file()
    if not dry_run:
      os.makedirs(os.path.dirname(new_path), exist_ok=True)
      os.rename(src=f, dst=new_path)
    md = """<div class="js_include" url="%s"  newLevelForH1="1" includeTitle="true"> </div>""" % new_url_computer(str(f))
    logging.info("Inclusion in old file : %s", md)
    md_file.dump_to_file(metadata=metadata, md=md, dry_run=dry_run)
