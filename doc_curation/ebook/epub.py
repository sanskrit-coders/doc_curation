import logging
import os
import re
import shutil
import tempfile
import zipfile
from typing import Any
from indic_transliteration import sanscript
import regex
import xml.etree.ElementTree as ET

from doc_curation.ebook import calibre_helper

from doc_curation.ebook.pandoc_helper import pandoc_from_md_file
from doc_curation.md.file import MdFile


_OPF_NS = "http://www.idpf.org/2007/opf"
_EPUB_NS = {"opf": _OPF_NS, "dc": "http://purl.org/dc/elements/1.1/"}
ET.register_namespace("opf", _OPF_NS)
ET.register_namespace("dc", "http://purl.org/dc/elements/1.1/")


def merge_chapter_files(epub_path, keep_first_n=1):
  """Join linear spine XHTML chapters into a single flow.

  Calibre's PDF engine emits a full blank page at the end of every chapter
  file when the stylesheet uses multi-column layout (column-count: 2), while
  single-column output flows continuously. Joining removes those blank pages
  at chapter ends.

  The first ``keep_first_n`` linear files (typically the title page) are kept
  as-is; the rest are spliced into the next file. Nav/non-linear spine items
  are untouched; links to merged files are rewritten to the surviving file;
  OPF manifest/spine/guide entries for removed files are pruned.

  :return: (num_joined, num_removed)
  """
  with zipfile.ZipFile(epub_path, "r") as zin:
    names = zin.namelist()
    mimetype = zin.read("mimetype") if "mimetype" in names else None
    blobs = {n: zin.read(n) for n in names}
  container = ET.fromstring(blobs["META-INF/container.xml"])
  opf_path = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile").get("full-path")
  opf_dir = os.path.dirname(opf_path)
  opf = ET.fromstring(blobs[opf_path])

  def href_to_name(href):
    return os.path.normpath(os.path.join(opf_dir, href)).replace("\\", "/")

  manifest = {}
  for item in opf.find("opf:manifest", _EPUB_NS):
    manifest[item.get("id")] = (item.get("href"), item.get("media-type"), item)
  files = []
  for itemref in opf.find("opf:spine", _EPUB_NS):
    idref = itemref.get("idref")
    if itemref.get("linear", "yes") == "no":
      continue
    href, media_type, _el = manifest[idref]
    if "nav" in (_el.get("properties") or "").split():
      continue
    if media_type in ("application/xhtml+xml", "text/html"):
      files.append((idref, href_to_name(href)))
  targets = files[keep_first_n:]
  if len(targets) < 2:
    logging.info(f"No chapters to join in {epub_path}.")
    return (len(targets), 0)

  def body_inner(blob):
    text = blob.decode("utf-8")
    match = re.search(r"<body[^>]*>(.*)</body>", text, flags=re.DOTALL | re.IGNORECASE)
    if not match:
      raise ValueError(f"No <body> in {epub_path}")
    return match.group(1)

  _first_id, first_name = targets[0]
  combined = body_inner(blobs[first_name])
  for _id, name in targets[1:]:
    combined += "\n" + body_inner(blobs[name])
  first_text = blobs[first_name].decode("utf-8")
  first_text = re.sub(r"</body>", combined + "\n</body>", first_text, count=1, flags=re.IGNORECASE)
  blobs[first_name] = first_text.encode("utf-8")

  removed_names = {n for _i, n in targets[1:]}
  removed_ids = {i for i, _n in targets[1:]}
  first_base = os.path.basename(first_name)
  for name, blob in list(blobs.items()):
    if not name.endswith((".xhtml", ".html", ".ncx")):
      continue
    try:
      text = blob.decode("utf-8")
    except UnicodeDecodeError:
      continue
    original = text
    for _i, removed_name in targets[1:]:
      base = os.path.basename(removed_name)
      text = text.replace(f"{base}#", f"{first_base}#").replace(f'"{base}"', f'"{first_base}"').replace(f"'{base}'", f"'{first_base}'")
    if text != original:
      blobs[name] = text.encode("utf-8")

  manifest_el = opf.find("opf:manifest", _EPUB_NS)
  for item in list(manifest_el):
    if item.get("id") in removed_ids:
      manifest_el.remove(item)
  spine_el = opf.find("opf:spine", _EPUB_NS)
  for itemref in list(spine_el):
    if itemref.get("idref") in removed_ids:
      spine_el.remove(itemref)
  guide_el = opf.find("opf:guide", _EPUB_NS)
  if guide_el is not None:
    removed_bases = {os.path.basename(n) for n in removed_names}
    for ref in list(guide_el):
      if os.path.basename(ref.get("href", "").split("#")[0]) in removed_bases:
        guide_el.remove(ref)
  blobs[opf_path] = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(opf, encoding="utf-8")

  for name in [n for n in blobs if n in removed_names]:
    del blobs[name]

  fd, temp_epub = tempfile.mkstemp(suffix=".epub")
  os.close(fd)
  try:
    with zipfile.ZipFile(temp_epub, "w") as zout:
      if mimetype is not None:
        zinfo = zipfile.ZipInfo("mimetype")
        zinfo.compress_type = zipfile.ZIP_STORED
        zout.writestr(zinfo, mimetype)
      for name, blob in blobs.items():
        if name == "mimetype":
          continue
        zout.writestr(name, blob)
    shutil.move(temp_epub, epub_path)
  finally:
    try:
      if os.path.exists(temp_epub):
        os.remove(temp_epub)
    except Exception:
      pass
  logging.info(f"Joined {len(targets)} chapters into {first_name}, removed {len(removed_names)} files in {epub_path}.")
  return (len(targets), len(removed_names))


def epub_from_md_file(md_path, epub_path, css_path=None, metadata={}, file_split_level=4, toc_depth=6, appendix=None, scripts=[sanscript.ISO], overwrite=".*"):
  logging.info("=========EPUB 1========")
  def _make_extra_args(file_split_level, toc_depth=6, css_path=css_path):
    pandoc_extra_args = ["--toc", f"--toc-depth={toc_depth}", f"--split-level={file_split_level}"]
    if css_path is not None:
      pandoc_extra_args.extend([f'--css={css_path}'])
    pandoc_extra_args.extend(["--resource-path", os.path.dirname(md_path)])
    return pandoc_extra_args

  pandoc_extra_args = _make_extra_args(file_split_level=file_split_level, toc_depth=toc_depth)
  source_dir = os.path.dirname(md_path)
  md_path_min = epub_path.replace(".epub", "_min.md")

  if not os.path.exists(epub_path) or regex.match(overwrite, "epub"):
    make_script_epubs(epub_path=epub_path, md_path=md_path, metadata=metadata, pandoc_extra_args=pandoc_extra_args, scripts=scripts)

    epub_path_min = epub_path.replace(".epub", "_min.epub")
    pandoc_extra_args = _make_extra_args(file_split_level=1)
    make_script_epubs(epub_path=epub_path_min, md_path=md_path_min, metadata=metadata, pandoc_extra_args=pandoc_extra_args, scripts=scripts)

    # Enable downstream artifacts recreation
    overwrite = ".*"


  if regex.match(overwrite, "pdf"):
    pandoc_extra_args = _make_extra_args(file_split_level=1)
    pandoc_extra_args.remove("--toc")
    epub_path_min_notoc = epub_path.replace(".epub", "_min_notoc.epub")
    make_script_epubs(epub_path=epub_path_min_notoc, md_path=md_path_min, metadata=metadata, pandoc_extra_args=pandoc_extra_args, scripts=scripts)
    if css_path is not None:
      pandoc_extra_args = _make_extra_args(file_split_level=1, css_path=css_path.replace(".css", "_2col.css"))
      epub_path_min_2cols = epub_path.replace(".epub", "_min_notoc_2cols.epub")
      make_script_epubs(epub_path=epub_path_min_2cols, md_path=md_path_min, metadata=metadata, pandoc_extra_args=pandoc_extra_args, scripts=scripts)
      # Calibre's PDF engine emits a full blank page at the end of every
      # chapter file when the stylesheet uses multi-column layout
      # (column-count: 2), while single-column output flows continuously.
      # Join the 2-column chapters into one flow so no blank pages appear
      # at chapter ends. (https://bugs.launchpad.net/calibre/+bug/2142731 follow-up.)
      for script in scripts:
        if script is None:
          _epub_2col = epub_path_min_2cols
        else:
          _epub_2col = os.path.join(os.path.dirname(epub_path_min_2cols), script, os.path.basename(epub_path_min_2cols))
        if os.path.exists(_epub_2col):
          merge_chapter_files(epub_path=_epub_2col)


  make_deprecated = False

  if make_deprecated:  
    if regex.match(overwrite, "kobo"):
      epub_for_kobo(epub_path=epub_path)


    if regex.match(overwrite, "azw"):
      calibre_helper.to_azw3(epub_path=epub_path, metadata=metadata)

  return epub_path


def make_script_epubs(epub_path, md_path, metadata: dict[Any, Any], pandoc_extra_args: list[str], scripts: list[Any]):
  pandoc_from_md_file(md_path=md_path, dest_path=epub_path, metadata=metadata, pandoc_extra_args=pandoc_extra_args)
  _fix_details_in_epub(epub_path=epub_path)
  for script in scripts:
    script_dir = os.path.join(os.path.dirname(epub_path), script)
    md_path = os.path.join(script_dir, os.path.basename(md_path))
    epub_path = os.path.join(script_dir, os.path.basename(epub_path))
    os.makedirs(script_dir, exist_ok=True)
    pandoc_from_md_file(md_path=md_path, dest_path=epub_path, metadata=metadata, pandoc_extra_args=pandoc_extra_args)
    _fix_details_in_epub(epub_path=epub_path)
    

def make_epubs_recursively(source_dir, out_path, recursion_depth=None, dry_run=False, cleanup=True, *args, **kwargs):
  if out_path is None:
    out_path = source_dir
  if recursion_depth is not None:
    for subdir in os.listdir(source_dir):
      subdir_path = os.path.join(source_dir, subdir)
      if os.path.isdir(subdir_path):
        if recursion_depth > 0:
          make_epubs_recursively(source_dir=subdir_path, out_path=os.path.join(out_path, subdir), recursion_depth=recursion_depth - 1, dry_run=dry_run, cleanup=False, *args, **kwargs)


  make_all(source_dir=source_dir, out_path=out_path, cleanup=cleanup, *args, **kwargs)


def epub_for_kobo(epub_path: str):

  logging.info("\nStep 2: Converting EPUB to KEPUB with kepubify...")
  kepubify_command = ['/home/vvasuki/go/bin/kepubify', epub_path, "-o", os.path.dirname(epub_path)]

  import subprocess
  result = subprocess.run(kepubify_command, capture_output=True, text=True)

  kepub_path = epub_path.replace(".epub", ".kepub.epub")
  if result.returncode == 0:
    logging.info(f"Successfully created '{kepub_path}'!")
  else:
    logging.error("Error during kepubify conversion:")
    logging.error(result.stderr)


def _fix_details_in_epub(epub_path: str):
  """
  Post-process an EPUB to convert <details ... open> into <details ... open="open">.
  Ensures 'mimetype' stays first and uncompressed as per EPUB spec.
  """
  import re
  import zipfile
  import tempfile
  import shutil

  if not os.path.isfile(epub_path):
    logging.warning(f"EPUB not found for post-process: {epub_path}")
    return

  # Read original EPUB
  with zipfile.ZipFile(epub_path, "r") as zin:
    # Extract 'mimetype' to preserve as-is (must be first and uncompressed)
    mimetype_data = None
    try:
      mimetype_data = zin.read("mimetype")
    except KeyError:
      pass  # Not strictly required to exist, but typical; we'll just proceed.

    # Create temp output EPUB
    fd, temp_epub = tempfile.mkstemp(suffix=".epub")
    os.close(fd)
    try:
      with zipfile.ZipFile(temp_epub, "w") as zout:
        # Write mimetype first, uncompressed if present
        if mimetype_data is not None:
          zinfo = zipfile.ZipInfo("mimetype")
          zinfo.compress_type = zipfile.ZIP_STORED
          zout.writestr(zinfo, mimetype_data)

        # Process all other files
        for item in zin.infolist():
          if item.filename == "mimetype":
            continue
          data = zin.read(item.filename)

          # Modify only XHTML/HTML files
          if item.filename.lower().endswith((".xhtml", ".html", ".htm")):
            try:
              text = data.decode("utf-8")
            except UnicodeDecodeError:
              # Try common fallback; if it fails, leave as-is
              try:
                text = data.decode("utf-16")
              except UnicodeDecodeError:
                zout.writestr(item, data)
                continue

            # Replace bare boolean open with explicit value, without touching open=
            pattern = re.compile(r'(<details\b[^>]*?)\sopen(?!\s*=)(?=(\s|/?>))', flags=re.IGNORECASE)
            fixed = pattern.sub(r'\1 open="open"', text)

            # Also handle stray cases like "<details open>" exactly
            fixed = re.sub(r'<details\s+open\s*>', '<details open="open">', fixed, flags=re.IGNORECASE)

            data = fixed.encode("utf-8")

          # Preserve compression for the rest (deflated)
          zout.writestr(item, data)

      # Replace original EPUB
      shutil.move(temp_epub, epub_path)
      logging.info(f"Normalized <details open> in EPUB: {epub_path}")
    finally:
      try:
        if os.path.exists(temp_epub):
          os.remove(temp_epub)
      except Exception:
        pass
