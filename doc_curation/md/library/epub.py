import logging
import os
import pathlib
import subprocess
import regex
import sys

from doc_curation.md.file import MdFile
from doc_curation.md.library import combination
from doc_curation.md.library.combination import make_full_text_md


def prep_content(content):
  content = regex.sub(r"\+\+\+(\(.+?\))\+\+\+", r'<span class="inline_comment">\1</span>', content)
  content = regex.sub(r" *\.\.\.\{Loading\}\.\.\.", fr"", content)
  return content


def make_epub(source_dir, out_path=None, css_path=None, recursion_depth=None, metadata=None):
  if out_path is None:
    out_path = source_dir
  if recursion_depth is not None:
    for subdir in os.listdir(source_dir):
      subdir_path = os.path.join(source_dir, subdir)
      if os.path.isdir(subdir_path):
        if recursion_depth > 0:
          make_epub(source_dir=subdir_path, out_path=os.path.join(out_path, subdir), css_path=css_path, metadata=metadata, recursion_depth=recursion_depth - 1)


  epub_name = os.path.basename(source_dir)
  if epub_name in ["sarva-prastutiH", "mUlam"]:
    epub_name = os.path.basename(os.path.basename(source_dir))
  epub_path = os.path.join(out_path, f"{epub_name}.epub")

  
  
  
  # The name of the temporary file we will generate.
  MASTER_FILE = pathlib.Path("temp_master_book.md")
  
  # 1. Find all Markdown files recursively
  logging.info(f"🔍 Searching for Markdown files in '{source_dir}'...")
  if not source_dir.is_dir():
    logging.info(f"❌ Error: Source directory not found at '{source_dir}'")
    sys.exit(1)

  # md_files = sorted(
  #   list(source_dir.rglob("*.md")),
  #   key=combination.natural_sort_key
  # )
  # 
  # if not md_files:
  #   logging.info("❌ Error: No Markdown files found.")
  #   sys.exit(1)
  # 
  # # TODO: Make copy of md files to a temp dir.
  # # Alter the copies with prep_content
  # logging.info(f"✅ Found {len(md_files)} files. Sorted order:")
  # for f in md_files:
  #   logging.info(f"  - {f}")
  # 
  # # 2. Generate the master Markdown file
  # logging.info(f"\n📝 Generating master file '{MASTER_FILE}'...")
  # current_part_dir = None
  # try:
  #   with open(MASTER_FILE, "w", encoding="utf-8") as outfile:
  #     for md_file in md_files:
  #       # Check if we have entered a new top-level directory (a "Part")
  #       part_dir = md_file.parent
  #       if part_dir != current_part_dir:
  #         current_part_dir = part_dir
  #         part_title = clean_name(part_dir.name)
  #         outfile.write(f"\n# {part_title}\n\n")
  #         logging.info(f"  - Adding Part: {part_title}")
  # 
  #       # Add the chapter/section title from the filename
  #       chapter_title = clean_name(md_file.stem)
  #       outfile.write(f"## {chapter_title}\n\n")
  # 
  #       # Add the file's content
  #       content = md_file.read_text(encoding="utf-8")
  #       outfile.write(content)
  #       outfile.write("\n\n")
  # 
  #   logging.info("✅ Master file generated successfully.")
  # 
  #   # 3. Build the Pandoc command
  #   pandoc_cmd = [
  #     "pandoc",
  #     str(MASTER_FILE),
  #     "--metadata-file", str(METADATA_FILE),
  #     "--epub-stylesheet", str(CSS_FILE),
  #     "--table-of-contents",
  #     "--toc-depth=2",  # TOC will include # and ## headers
  #     "--epub-chapter-level=1", # Split EPUB pages at Level 1 headers
  #     "--standalone",
  #     "--to", "epub3",
  #     "-o", str(OUTPUT_EPUB),
  #   ]
  # 
  #   # 4. Execute the Pandoc command
  #   logging.info("\n📚 Running Pandoc to build EPUB...")
  #   logging.info("   " + " ".join(pandoc_cmd))
  # 
  #   # We use check=True to raise an exception if Pandoc fails
  #   subprocess.run(pandoc_cmd, check=True)
  # 
  #   logging.info(f"\n🎉 Success! EPUB created at '{OUTPUT_EPUB}'")
  # 
  # except FileNotFoundError:
  #   logging.info("❌ Error: 'pandoc' command not found.")
  #   logging.info("   Please ensure Pandoc is installed and in your system's PATH.")
  #   sys.exit(1)
  # except subprocess.CalledProcessError as e:
  #   logging.info(f"❌ Error: Pandoc failed with exit code {e.returncode}.")
  #   sys.exit(1)
  # finally:
  #   # 5. Clean up the temporary file
  #   if MASTER_FILE.exists():
  #     logging.info(f"\n🗑️ Cleaning up temporary file '{MASTER_FILE}'.")
  #     MASTER_FILE.unlink()


def epub_from_full_md(source_dir, epub_path, css_path=None, metadata=None): 
  """Beware - a giant html file performs poorly on many devices."""
  full_md_path = os.path.join(source_dir, "full.md")
  if not os.path.exists(full_md_path):
    full_md_path = make_full_text_md(source_dir=source_dir)
    if full_md_path is None:
      return
  md_file = MdFile(file_path=full_md_path)
  md_file.export_with_pandoc(dest_path=epub_path, css_path=css_path, metadata=metadata)

  # Clean up full.md files under source_dir
  for dirpath, dirnames, filenames in os.walk(source_dir):
    if "full.md" in filenames:
      os.remove(os.path.join(dirpath, "full.md"))


def epub_for_kobo(epub_path: str, out_path):
  kepub_path = epub_path.replace(".epub", ".kepub.epub")
  # --- Step 2: Use kepubify to convert the EPUB to a KEPUB ---
  logging.info("\nStep 2: Converting EPUB to KEPUB with kepubify...")
  # The command to run. Ensure 'kepubify' is in your system's PATH.
  kepubify_command = ['/home/vvasuki/go/bin/kepubify', epub_path, '-o', out_path]

  import subprocess
  result = subprocess.run(kepubify_command, capture_output=True, text=True)

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
  if len(tome_match) > 0:
    tome = tome_match.group(2)
    out_path = os.path.join(out_path, tome)
    metadata["title"] = MdFile(os.path.join(tome_match.group(1), tome_match.group(2), "_index.md")).get_title()
  return metadata, out_path
