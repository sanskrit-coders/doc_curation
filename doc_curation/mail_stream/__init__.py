import os
import shutil


def _delete_month(md_path, month_dir_pattern="SUB/xyz.md"):
  month_dir = md_path
  for _ in month_dir_pattern.split("/"):
    month_dir = os.path.dirname(month_dir)
  shutil.rmtree(month_dir)


def delete_last_month(dest_dir_base, month_dir_pattern="SUB/xyz.md"):
  import glob
  files = glob.glob(os.path.join(dest_dir_base, '**/*.md'), recursive=True)
  files = [file for file in files if files != "_index.md"]
  files = sorted(files, reverse=True)
  if len(files) > 0:
    _delete_month(files[0])