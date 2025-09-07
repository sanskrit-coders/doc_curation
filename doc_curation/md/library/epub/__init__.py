import logging
import os
import pathlib
import subprocess

import regex
import json

import doc_curation.md.library.arrangement
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement
from doc_curation.md.library.combination import make_full_text_md
from doc_curation.md.library.pandoc_helper import pandoc_from_md_file


def prep_content(content):
  content = regex.sub(r"\+\+\+(\(.+?\))\+\+\+", r'<span class="inline_comment">\1</span>', content)
  content = regex.sub(r" *\.\.\.\{Loading\}\.\.\.", fr"", content)
  # TODO: Details to footnotes optionally
  return content


def epub_from_md_file(md_file, out_path, css_path=None, metadata={}, file_split_level=4, toc_depth=6):
  pandoc_extra_args = ["--toc", f"--toc-depth={toc_depth}", f"--epub-chapter-level={file_split_level}"]
  if css_path is not None:
    pandoc_extra_args.extend([f'--css={css_path}'])

  if not out_path.endswith(".epub"):
    source_dir = os.path.dirname(md_file.file_path)
    epub_name = os.path.basename(source_dir)
    if epub_name in ["sarva-prastutiH", "mUlam"]:
      source_dir = os.path.dirname(source_dir)
      epub_name = os.path.basename(source_dir)
    out_path = os.path.join(out_path, f"{epub_name}.epub")
    metadata["title"] = get_epub_title(dir_path=source_dir)

  pandoc_from_md_file(md_file=md_file, dest_path=out_path, metadata=metadata, pandoc_extra_args=pandoc_extra_args, content_maker=prep_content)
  return out_path


def make_epubs_recursively(source_dir, out_path, recursion_depth=None, dry_run=False, *args, **kwargs):
  if out_path is None:
    out_path = source_dir
  if recursion_depth is not None:
    for subdir in os.listdir(source_dir):
      subdir_path = os.path.join(source_dir, subdir)
      if os.path.isdir(subdir_path):
        if recursion_depth > 0:
          make_epubs_recursively(source_dir=subdir_path, out_path=os.path.join(out_path, subdir), recursion_depth=recursion_depth - 1, dry_run=dry_run, *args, **kwargs)


  epub_from_full_md(source_dir=source_dir, out_path=out_path, *args, **kwargs)



def epub_from_full_md(source_dir, out_path, css_path=None, metadata={}, file_split_level=4, toc_depth=6): 
  full_md_path = os.path.join(source_dir, "full.md")
  if not os.path.exists(full_md_path):
    full_md_path = make_full_text_md(source_dir=source_dir, detail_to_footnotes=True)
    if full_md_path is None:
      return



  md_file = MdFile(file_path=full_md_path)
  epub_path = epub_from_md_file(md_file=md_file, out_path=out_path, metadata=metadata, file_split_level=file_split_level, toc_depth=toc_depth, css_path=css_path)
  epub_for_kobo(epub_path=epub_path)
  
  # Clean up full.md files under source_dir
  # for dirpath, dirnames, filenames in os.walk(source_dir):
  #   if "full.md" in filenames:
  #     os.remove(os.path.join(dirpath, "full.md"))


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


def get_epub_metadata_path(author, dir_path, out_path=f"/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/vv_ebook_pub/"):
  out_path = os.path.join(out_path, author)
  tome_match = regex.match("(.+)/(.+?)/sarva-prastutiH|mUlam/", dir_path)
  metadata = {}
  if author is not None:
    metadata["author"] = author
  if tome_match is not None:
    tome = tome_match.group(2)
    out_path = os.path.join(out_path, tome)
  return metadata, out_path


def get_epub_title(dir_path):
  tome_match = regex.match("(.+)/(.+?)/sarva-prastutiH|mUlam/", dir_path)
  if tome_match is not None:
    ref_dir = os.path.join(tome_match.group(1), tome_match.group(2))
    title = MdFile(os.path.join(ref_dir, "_index.md")).get_title(omit_chapter_id=False)
    if not regex.match("sarva-prastutiH|mUlam", dir_path):
      title = MdFile(os.path.join(dir_path, "_index.md")).get_title(omit_chapter_id=False, ref_dir_for_ancestral_title=ref_dir)
  else:
    title = MdFile(os.path.join(dir_path, "_index.md")).get_title(omit_chapter_id=False)
  return title
