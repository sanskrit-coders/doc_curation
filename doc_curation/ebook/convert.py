import logging
import os
import subprocess

from doc_curation.md.file import MdFile

CALIBRE = 'ebook-convert'


def metadata_to_calibre_args(metadata):
  args = []
  for key, value in metadata.items():
    args.append('--%s' % key)
    args.append(value)
  return args


def to_azw3(epub_path: str, metadata={}):
  logging.info("\nStep 3: Converting EPUB to AZW3...")
  # Construct the command for ebook-convert
  # The command is: ebook-convert "input_path.epub" "output_path.azw3"
  azw3_path = epub_path.replace(".epub", ".azw3")
  command = [CALIBRE, epub_path, azw3_path]
  options = metadata_to_calibre_args(metadata=metadata)
  command.extend(options)

  logging.info(f"Converting {os.path.basename(epub_path)} to AZW3...")

  # Execute the command
  result = subprocess.run(command, check=True, capture_output=True, text=True)

  logging.info("Conversion successful!")
  return azw3_path
