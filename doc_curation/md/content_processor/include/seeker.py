import os
from urllib.parse import urljoin

import regex


def file_path_from_url(url, hugo_base_dir, current_file_path):
  if url.startswith("http"):
    return
  file_path = None
  if url.startswith("/"):
    if url.endswith(".md"):
      file_path = regex.sub(r"(/.+?)(/.+)", f"{hugo_base_dir}\\1/static\\2", url)
    else:
      file_path = regex.sub(r"(/.+?)(/.+)/?", f"{hugo_base_dir}\\1/content\\2.md", url).replace("/.md", ".md")
      file_path = regex.sub("//+", "/", file_path)
      if not os.path.exists(file_path):
        file_path = regex.sub(r"(/.+?)(/.+)/?", f"{hugo_base_dir}\\1/content\\2/_index.md", url)
  else:
    # relative path
    if os.path.basename(current_file_path) == "_index.md":
      file_path = urljoin(current_file_path, url)
    else:
      file_path = urljoin(current_file_path + "/", url)
    if file_path.endswith(".md"):
      if "/content/" in file_path:
        file_path = file_path.replace("/content/", "/static/")
    else:
      file_path = regex.sub("(?<=[^/])/*(?=$)", ".md", file_path)
  if file_path is not None:
    file_path = regex.sub("//+", "/", file_path)
    if not os.path.exists(file_path) and "/content/" in file_path and os.path.basename(current_file_path) != "_index.md":
      file_path = regex.sub(r".md", f"/_index.md", file_path)
    if os.path.exists(file_path):
      return file_path
    # logging.debug(f"Could not find: {file_path} in {current_file_path}")
    return None
