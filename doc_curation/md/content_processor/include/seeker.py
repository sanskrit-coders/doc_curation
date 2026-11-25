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
      if not os.path.isfile(file_path):
        file_path = regex.sub(r"(/.+?)(/.+)/?", f"{hugo_base_dir}\\1/content\\2/_index.md", url)
  else:
    # relative path: _index.md and raw static .md files resolve from their containing directory.
    if os.path.basename(current_file_path) == "_index.md" or ("/static/" in str(current_file_path) and str(current_file_path).endswith(".md")):
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
    if not os.path.isfile(file_path) and "/content/" in file_path:
      if os.path.isdir(file_path):
        idx_cand = os.path.join(file_path, "_index.md")
        if os.path.isfile(idx_cand):
          return idx_cand
      elif file_path.endswith(".md") and os.path.basename(current_file_path) != "_index.md":
        idx_cand = regex.sub(r"\.md$", "/_index.md", file_path)
        if os.path.isfile(idx_cand):
          return idx_cand
    if os.path.isfile(file_path):
      return file_path
    # logging.debug(f"Could not find: {file_path} in {current_file_path}")
    return None


def resolve_include_file_path(url, hugo_base_dir, current_file_path):
  """Resolve a ``js_include`` ``url`` to an existing Markdown file path (including ``_index.md`` directory targets)."""
  p = file_path_from_url(url=url, hugo_base_dir=hugo_base_dir, current_file_path=current_file_path)
  if p and os.path.isfile(p):
    return str(p)
  for cand in (
    regex.sub("/$", "", url) + "/_index.md",
    url[:-3] if url.endswith(".md") else (url[:-1] if url.endswith(".md/") else regex.sub("/$", "", url) + ".md"),
  ):
    alt_url = cand.replace("/content/", "/").replace("/static/", "/").replace("//", "/")
    p2 = file_path_from_url(url=alt_url, hugo_base_dir=hugo_base_dir, current_file_path=current_file_path)
    if p2 and os.path.isfile(p2):
      return str(p2)
  return None
