import logging
import os
import subprocess

from doc_curation.md.file import MdFile

CALIBRE = 'ebook-convert'


def metadata_to_calibre_args(metadata):
  args = []
  for key, value in metadata.items():
    if key.startswith("_"):
      continue
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


def to_pdf(epub_path: str, metadata={}):
  dest_path = epub_path.replace(".epub", ".pdf")
  command = [
    CALIBRE,
    epub_path,
    dest_path,
    '--output-profile', 'generic_eink',
    '--paper-size', 'a5',
    '--pdf-serif-family', 'Nimbus Roman [urw]',
    '--pdf-sans-family', 'Noto Sans Devanagari',
    '--pdf-mono-family', 'Nimbus Mono PS [urw]',
    '--pdf-standard-font', 'sans',
    '--pdf-default-font-size', '14',
    '--pdf-mono-font-size', '14',
    '--pdf-page-margin-left', '36',
    '--pdf-page-margin-right', '36',
    '--pdf-page-margin-top', '24',
    '--pdf-page-margin-bottom', '24',
    '--pdf-page-numbers',
    '--pdf-add-toc',
    '--chapter-mark', 'rule'
  ]

  options = metadata_to_calibre_args(metadata=metadata)
  command.extend(options)

  # Execute the command
  result = subprocess.run(command, check=True, capture_output=True, text=True)

  logging.info("Conversion successful!")
  return dest_path
