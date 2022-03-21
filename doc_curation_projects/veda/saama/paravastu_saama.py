from doc_curation.md import library
import os
import regex
import glob

if __name__ == '__main__':
  files = glob.glob("/home/vvasuki/vvasuki-git/saMskAra/content/mantraH/**/paravastu-saama/*.md")
  files = [f for f in files if not f.endswith("_index.md")]
  location_computer = lambda x: regex.sub("(.+?/)saMskAra/.+?/([^/]+?)/paravastu.saama/(.+\.md)", r"\g<1>vedAH/content/sAma/paravastu-saama/devaH/\g<2>/\g<3>", x)
  new_url_computer = lambda x: regex.sub("(.+?/)saMskAra/.+?/([^/]+?)/paravastu.saama/(.+?)\.md", r"/vedAH/sAma/paravastu-saama/devaH/\g<2>/\g<3>/", x)
  library.migrate_and_include(files=files, location_computer=location_computer, new_url_computer=new_url_computer, dry_run=False)