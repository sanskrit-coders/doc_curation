from doc_curation.md import library
import os
import regex
import glob

if __name__ == '__main__':
  files = glob.glob("/home/vvasuki/vvasuki-git/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/haradatta-TIkA/*/*.md")
  files = [f for f in files if not f.endswith("_index.md")]
  location_computer = lambda x: regex.sub("/content/", r"/static/", x)
  library.migrate(files=files, location_computer=location_computer, dry_run=False)