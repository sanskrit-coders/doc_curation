from doc_curation.md import library
import os
import regex
import glob
from curation_utils import file_helper


def update_blog_files():
  latest_file_paths = glob.glob("/home/vvasuki/hindu-comm/weblogs/manasataramgini/**/*.md", recursive=True)
  paths_in = glob.glob("/home/vvasuki/vishvAsa/**/MT*/**/*.md", recursive=True)
  file_helper.substitute_with_latest(paths_in=paths_in, latest_file_paths=latest_file_paths, dry_run=False)


if __name__ == '__main__':
  update_blog_files()
  # files = glob.glob("/home/vvasuki/vishvAsa/vedAH/content/yajuH/taittirIyam/brAhmaNam/bhaTTa-bhAskara-bhAShyam/3/1/*/*.md")
  # files = [f for f in files if not f.endswith("_index.md")]
  # location_computer = lambda x: regex.sub("/content/", r"/static/", x)
  # library.migrate(files=files, location_computer=location_computer, dry_run=False)