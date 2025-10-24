import math
import os
import shutil
import logging

from doc_curation.md import library
from doc_curation.md.library import arrangement


# # Configure logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def move_files_increment_dir(base_dir, dry_run=True):
  for filename in os.listdir(base_dir):
    if '_' in filename:
      prefix = filename.split('_')[0]  # e.g., '11' or '101'
      if prefix.isdigit():
        digits = prefix
        number = int(digits)
        centad = math.ceil(number/10.0)
        decad = int(digits[-1])
        if decad == 0:
          decad = 10
        dest_path = os.path.join(base_dir, f"{centad:02}", f"{decad:02}_{filename[len(prefix) + 1:]}" )
        old_path = os.path.join(base_dir, filename)

        if dest_path == old_path:
          continue
        logging.info(f"Move {filename} to {dest_path}")
        if not dry_run:
          os.makedirs(os.path.dirname(dest_path), exist_ok=True)
          shutil.move(old_path, dest_path)

  arrangement.fix_index_files(os.path.dirname(base_dir), dry_run=dry_run)

