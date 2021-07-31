import os
import shutil


def delete_last_month(dest_dir_base):
  import glob
  files = glob.glob(os.path.join(dest_dir_base, '**/*.md'), recursive=True)
  files = [file for file in files if files != "_index.md"]
  files = sorted(files, reverse=True)
  if len(files) > 0:
    shutil.rmtree(os.path.dirname(os.path.dirname(files[0])))