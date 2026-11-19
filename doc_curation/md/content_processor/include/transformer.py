import logging
import os

import regex
from bs4 import BeautifulSoup
from doc_curation.md import content_processor, library
from doc_curation.md.content_processor.include.maker import make_alt_include
from doc_curation.md.content_processor.include.seeker import file_path_from_url
from doc_curation.md.content_processor.section_helper import fix_headers
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement
from doc_curation.scraping.html_scraper import souper


def transform_include_lines(md_file, transformer, dry_run=False):
  [_, content] = md_file.read()
  content = regex.sub(r"<div.+js_include.+url=['\"](.+?)['\"][\s\S]+?</div>", transformer, content)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)

def transform_includes_with_soup(content, metadata, transformer, *args, **kwargs):
  # Stray usage of < can fool the soup parser. Hence the below.
  # This will still pass through md files with non js_inclde tags which can be messed up, like  
  # {{< figure src="images/vaidika-puM-deva-jAlam.jpg" title="" class="thumbnail">}}  
    # but that will be fixed later.
  if "js_include" not in content:
    return content
  
  # Having divs within markdown list items can lead to this function producing the closing tag outside the list item. This can then lead to mangled html, which can then cause page inclusion javascript calls to fail. 
  content = regex.sub(r"(?=\n|^)( *[-*] .+)<div", "$1\n\n<div", content)
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content
  includes = soup.select("div.js_include")
  # logging.debug(f"Processing {metadata['_file_path']}")
  for inc in includes:
    top_level_include = True
    parents = list(inc.parents)
    if len(parents) == 0:
      # Decomposed include?
      continue
    for parent in parents:
      if "js_include" in parent.get("class", []):
        top_level_include = False
        break
    if top_level_include:
      transformer(inc, metadata["_file_path"], *args, **kwargs)
  new_content = content_processor._make_content_from_soup(soup=soup)

  # The below is for hugo shortcuts. Eg.
  # {{< figure src="images/vaidika-puM-deva-jAlam.jpg" title="" class="thumbnail">}}  
  new_content = new_content.replace("{{&lt;", "{{<").replace("&gt;}}", ">}}")

  # Fix quotation symbols in markdown
  new_content = regex.sub(r"(?<=\s)&gt;", ">", new_content)

  html_escapes = list(regex.findall(r"&[lg]t;(?=/?d(iv|etails))", new_content))
  if len(html_escapes) > 0:
    logging.warning(f"Somehow < or > was replaced in " + metadata["_file_path"])
    return content
  return  new_content

def old_include_remover(inc, *args, **kwargs):
  """To be used with transform_include_lines.
  
  :param inc: 
  :return: 
  """
  if "title_to_exclude" in kwargs:
    if not inc.attrs["title"] == kwargs["title_to_exclude"]:
      return inc.decompose()
  elif "url_to_exclude" in kwargs:
    if not regex.fullmatch(kwargs["url_to_exclude"], inc.attrs["url"]):
      return inc.decompose()
  elif not "includetitle" in inc.attrs:
    return inc.decompose()

def fix_rel_urls(content, from_path, to_path):
  def replacer(match):
    orig_url = match.group(2)
    # Skip if URL has a scheme (http:, mailto:, javascript:, tel: ...) or starts with '#'
    if regex.match(r'[a-zA-Z][a-zA-Z0-9+.\-]*:', orig_url) or orig_url.startswith(('#', '/')):
      return match.group(0)
    # Compute fixed relative path from file b to target
    if from_path.endswith("_index.md"):
      src_folder = os.path.dirname(from_path)
    else:
      src_folder = from_path + "/"
    if to_path.endswith("_index.md"):
      dest_folder = os.path.dirname(to_path)
    else:
      dest_folder = to_path + "/"
    resolved = os.path.normpath(os.path.join(src_folder, orig_url))
    rel_new = os.path.relpath(resolved, dest_folder)
    return f'{match.group(1)}{rel_new}{match.group(3)}'

  # Fix both image ![](url) and link [](url) references
  pattern = regex.compile(r'(!?\[.*?\]\()([^\)\s]+)(\))')
  new_content = pattern.sub(replacer, content)
  return new_content

def prefill_include(inc, container_file_path, h1_level_offset=0, hugo_base_dir="/home/vvasuki/gitland/vishvAsa",
                    dynamic_loading=True, hash_title=False):
  """To be used with transform_include_lines.
  
  :param match: 
  :param source_dir: Eg. "vishvAsa-prastutiH"
  :param alt_dirs: Eg: ["commentary-1", "commentary-2"]
  :return: 
  """
  inc["unfilled"] = None
  souper.empty_tag(inc)

  url = inc["url"]

  file_path = file_path_from_url(url=url, hugo_base_dir=hugo_base_dir, current_file_path=container_file_path)
  if file_path is None:
    if url.endswith(".md"):
      new_url = url[:-3]
    elif url.endswith(".md/"):
      new_url = url[:-1]
    else:
      new_url = regex.sub("/$", "", url) + ".md"

    # Neither of the below should appear in a valid url.
    url = new_url.replace("/content/", "/").replace("/static/", "/").replace("//", "/")

    file_path = file_path_from_url(url=new_url, hugo_base_dir=hugo_base_dir, current_file_path=container_file_path)
    if file_path is None:
      logging.warning(f"Could not fix: {url} in {container_file_path}")
      return 
    else:
      logging.info(f"Corrected url to: {new_url} in {container_file_path}")
      url = new_url
      inc["url"] = url
  md_file = MdFile(file_path=file_path)
  (metadata, content) = md_file.read()
  metadata["_file_path"] = file_path
  if h1_level_offset == "b[]" or inc.get("newlevelforh1", 2) == "b[]":
    h1_level = "b[]"
  else:
    h1_level = h1_level_offset + int(inc.get("newlevelforh1", 2))
  if "newlevelforh1" not in inc.attrs:
    logging.warning(f"No newlevelforh1 for {file_path} in {container_file_path}")

  content = fix_headers(content, h1_level)
  # TODO: Handle spreadsheets in includes
  content = fix_rel_urls(content=content, from_path=file_path, to_path=container_file_path)
  if file_path == container_file_path:
    logging.fatal(f"Circular include in {container_file_path}")
    return 
  content = transform_includes_with_soup(content=content, metadata=metadata, h1_level_offset=h1_level, transformer=prefill_include, dynamic_loading=dynamic_loading, hugo_base_dir=hugo_base_dir)

  title = inc.get("title", "")
  if title == "" and inc.get("includetitle", "false").lower() != "false":
    title = metadata.get("title", "UNKNOWN_TITLE")
    if title == "UNKNOWN_TITLE":
      logging.warning(f"Could not get title for {file_path} in {container_file_path}")
  if title != "" and dynamic_loading:
    title +=  " …{Loading}…"

  title = title.strip()
  # title = regex.sub(r"^\+", "", title)

  hash_title = hash_title or os.path.basename(container_file_path) == "full.md"

  if title != "":
    if "collapsed" not in inc["class"] and hash_title:
      if h1_level != "b[]":
        title = f"{'#'*h1_level} {title}"
      else:
        title = f"**{title}**"
      details = BeautifulSoup(f"{title}\n\n{content}", 'html.parser')
    else:
      if h1_level != "b[]":
        title = f"<h{h1_level}>{title}</h{h1_level}>"
      else:
        title = f"{title}"
      details = BeautifulSoup(f"<body><details><summary>{title}</summary>\n\n{content}\n</details></body>", 'html.parser').select_one("details")
      if "collapsed" not in inc["class"]:
        details["open"] = ""
  else:
    details = BeautifulSoup(f"{content}", 'html.parser')

  # Guard against missing / invalid include content.
  if details is None:
    return
  # Skip empty tags to avoid bs4 insert/index issues.
  if getattr(details, "contents", None) == []:
    return
  if dynamic_loading:
    inc.append("\n\n")
    inc.append(details)
    inc.append("\n\n")
  else:
    inc.replace_with(details)

def prefill_includes(dir_path, file_name_filter=None, dry_run=False, *args, **kwargs):
  logging.info(f"Prefilling includes in {dir_path}")
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, metadata: transform_includes_with_soup(x, metadata, transformer=prefill_include, *args, **kwargs), file_name_filter=file_name_filter, dry_run=dry_run)


_DIV_TAG_RE = regex.compile(r"<div\b[^>]*>|</div>", regex.S)
_DETAILS_TAG_RE = regex.compile(r"<details\b[^>]*>|</details>", regex.S)
_LOADING_WRAPPER_RE = regex.compile(
  r"^(\s*<details[^>]*><summary>(?:<h(\d+)>)?(?:(?!</summary>).)*?(?:\.\.\.|…)\{Loading\}(?:\.\.\.|…)(?:(?!</summary>).)*?(?:</h\d+>)?\s*</summary>)(.*)(</details>\s*)$",
  regex.S,
)
_HASH_LOADING_RE = regex.compile(
  r"^(\s*(#+)\s+[^\n]*?(?:\.\.\.|…)\{Loading\}(?:\.\.\.|…)\s*\n)(.*)$",
  regex.S,
)


def _has_balanced_details(text):
  """Return True iff every ``<details>``/``</details>`` inside ``text`` nests cleanly and closes back to depth 0."""
  depth = 0
  for m in _DETAILS_TAG_RE.finditer(text):
    if m.group(0).startswith("<details"):
      depth += 1
    else:
      depth -= 1
      if depth < 0:
        return False
  return depth == 0


def find_js_include_divs(content):
  """Return balanced ``(s_open, e_open, body_start, body_end, e_close, open_tag)`` tuples for all ``js_include`` divs."""
  stack = []
  results = []
  for m in _DIV_TAG_RE.finditer(content):
    tok = m.group(0)
    if tok.startswith("<div"):
      is_js = 'class="js_include' in tok or "class='js_include" in tok
      stack.append((m.start(), m.end(), tok, is_js))
    elif stack:
      s_open, e_open, open_tok, is_js = stack.pop()
      if is_js:
        results.append((s_open, e_open, e_open, m.start(), m.end(), open_tok))
  return results


def surgical_prefill_content(
  content,
  container_file_path,
  *,
  url_filter=None,
  hugo_base_dir="/home/vvasuki/gitland/vishvAsa",
):
  """Refresh ``js_include`` prefills via exact string slicing without BeautifulSoup re-serialization.

  Preserves ``<div ...>`` attributes, ``<details ...><summary>...{Loading}...</summary>`` wrapper headers,
  and all surrounding Markdown/HTML byte-for-byte. When an outer ``js_include`` div is skipped by ``url_filter``,
  descends into its nested ``js_include`` children so matching inner includes still get refreshed.

  Returns ``(updated_content, num_divs_updated)``.
  """
  if "js_include" not in content:
    return content, 0

  all_divs = find_js_include_divs(content)
  target_divs = []
  covered = []
  for d in sorted(all_divs, key=lambda x: (x[0], -(x[4] - x[0]))):
    if any(a <= d[0] and d[4] <= b for a, b in covered):
      continue
    m_url = regex.search(r"""url=["']([^"']+)["']""", d[5])
    if not m_url:
      continue
    url = m_url.group(1)
    if url_filter is not None:
      matched = url_filter(url) if callable(url_filter) else bool(regex.search(url_filter, url))
      if not matched:
        continue
    file_path = file_path_from_url(url=url, hugo_base_dir=hugo_base_dir, current_file_path=container_file_path)
    if file_path is None:
      alt_url = url[:-3] if url.endswith(".md") else (url[:-1] if url.endswith(".md/") else regex.sub("/$", "", url) + ".md")
      alt_url = alt_url.replace("/content/", "/").replace("/static/", "/").replace("//", "/")
      file_path = file_path_from_url(url=alt_url, hugo_base_dir=hugo_base_dir, current_file_path=container_file_path)
    if not file_path or str(file_path) == str(container_file_path) or not os.path.exists(file_path):
      continue
    target_divs.append((d, str(file_path)))
    covered.append((d[0], d[4]))

  edits = []
  for (_, _, b_start, b_end, _, open_tok), target_fp in target_divs:
    _, inc_content = MdFile(file_path=target_fp).read()
    cur_body = content[b_start:b_end]
    m_wrap = _LOADING_WRAPPER_RE.match(cur_body)
    if m_wrap and not _has_balanced_details(m_wrap.group(3)):
      m_wrap = None
    m_hash = None if m_wrap else _HASH_LOADING_RE.match(cur_body)
    if m_wrap:
      wrap_head, h_lvl_str, old_inner, wrap_tail = m_wrap.group(1), m_wrap.group(2), m_wrap.group(3), m_wrap.group(4)
      if h_lvl_str:
        h1_level = int(h_lvl_str)
      else:
        m_nl = regex.search(r"""newlevelforh1=["']([^"']+)["']""", open_tok)
        h1_level = int(m_nl.group(1)) if (m_nl and m_nl.group(1).isdigit()) else 2
      rendered = fix_headers(inc_content, h1_level)
      rendered = fix_rel_urls(content=rendered, from_path=target_fp, to_path=str(container_file_path))
      lead_ws = old_inner[: len(old_inner) - len(old_inner.lstrip())] or "\n\n"
      trail_ws = old_inner[len(old_inner.rstrip()) :] or "\n"
      new_body = wrap_head + lead_ws + rendered.strip() + trail_ws + wrap_tail
    elif m_hash:
      wrap_head, hashes, old_inner = m_hash.group(1), m_hash.group(2), m_hash.group(3)
      h1_level = len(hashes)
      rendered = fix_headers(inc_content, h1_level)
      rendered = fix_rel_urls(content=rendered, from_path=target_fp, to_path=str(container_file_path))
      lead_ws = old_inner[: len(old_inner) - len(old_inner.lstrip())] or "\n"
      trail_ws = old_inner[len(old_inner.rstrip()) :] or "\n\n"
      new_body = wrap_head + lead_ws + rendered.strip() + trail_ws
    else:
      m_nl = regex.search(r"""newlevelforh1=["']([^"']+)["']""", open_tok)
      h1_level = int(m_nl.group(1)) if (m_nl and m_nl.group(1).isdigit()) else 2
      rendered = fix_headers(inc_content, h1_level)
      rendered = fix_rel_urls(content=rendered, from_path=target_fp, to_path=str(container_file_path))
      new_body = "\n" + rendered.strip() + "\n"

    if new_body != cur_body:
      edits.append((b_start, b_end, new_body))

  if not edits:
    return content, 0

  out = content
  for s, e, rep in sorted(edits, key=lambda x: x[0], reverse=True):
    out = out[:s] + rep + out[e:]
  return out, len(edits)


def surgical_prefill_includes(
  dir_path,
  *,
  url_filter=None,
  file_name_filter=None,
  hugo_base_dir="/home/vvasuki/gitland/vishvAsa",
  dry_run=False,
):
  """Surgically refresh ``js_include`` prefills across ``dir_path`` while preserving ``{Loading}`` wrappers."""
  logging.info(f"Surgically prefilling includes in {dir_path}")
  library.apply_function(
    fn=MdFile.transform,
    dir_path=dir_path,
    content_transformer=lambda x, metadata: surgical_prefill_content(
      x,
      metadata["_file_path"],
      url_filter=url_filter,
      hugo_base_dir=hugo_base_dir,
    )[0],
    file_name_filter=file_name_filter,
    dry_run=dry_run,
  )

def include_to_details(inc, container_file_path, title, url_pattern=None, prefill=False, hugo_base_dir="/home/vvasuki/gitland/vishvAsa", *args, **kwargs):
  """To be used with transform_includes_with_soup: convert a prefilled include into a plain details block.

  The include div is dropped and the (already prefilled) details tag within it is retained, with its summary text replaced by `title`.
  Use this when the included content is to be inlined in the host file and the source file deleted, eg. a `vishvAsa-prastutiH` include becoming a `विश्वास-प्रस्तुतिः` details block.
  """
  url = inc.get("url", "")
  if url_pattern is not None and not regex.search(url_pattern, url):
    return
  if prefill:
    prefill_include(inc, container_file_path, hugo_base_dir=hugo_base_dir)
  details = inc.select_one("details")
  if details is None:
    # Titleless includes (eg. includetitle="false") are prefilled without a details wrapper; wrap their bare content.
    body = inc.decode_contents()
  else:
    summary = details.select_one("summary")
    if summary is None:
      logging.warning(f"No summary in details extracted from include {url} in {container_file_path}")
      return
    body = details.decode_contents()
    if summary_str := str(summary):
      if summary_str not in body:
        logging.warning(f"Could not separate summary from body for include {url} in {container_file_path}")
        return
      body = body.split(summary_str, 1)[1]
  body = body.strip()
  details_new = BeautifulSoup(f"<details open><summary>{title}</summary>\n\n{body}\n</details>", "html.parser").select_one("details")
  inc.replace_with(details_new)

def includes_to_details(dir_path, title, url_pattern, prefill=False, file_name_filter=None, *args, **kwargs):
  """Replace includes matching `url_pattern` with plain details blocks titled `title`.

  `prefill` refreshes the included content from its source file before converting; otherwise run prefill_includes first.
  """
  def content_transformer(content, metadata, *args, **kwargs):
    return transform_includes_with_soup(content=content, metadata=metadata, transformer=include_to_details, title=title, url_pattern=url_pattern, prefill=prefill, **kwargs)

  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=content_transformer, file_name_filter=file_name_filter, *args, **kwargs)

def deincludify(dir_path, *args, **kwargs):
  # prefill_includes(dir_path=dir_path, *args, **kwargs)
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["</?div.+", r" *[\.…]+\{Loading\}[\.…]+"], replacement="")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"\n\n+"], replacement="\n\n")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"<summary><h\d>"], replacement="<summary>")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"</h\d></summary>"], replacement="</summary>")

  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r" open><summary>[^<]+"], replacement=" open><summary>विश्वास-प्रस्तुतिः")

def alt_include_adder(inc, current_file_path, source_dir, alt_dirs, hugo_base_dir="/home/vvasuki/gitland/vishvAsa"):
  """To be used with transform_include_lines.
  
  :param match: 
  :param source_dir: Eg. "vishvAsa-prastutiH"
  :param alt_dirs: Eg: ["commentary-1", "commentary-2"]
  :return: 
  """
  url = inc["url"]
  file_path = file_path_from_url(url=url, hugo_base_dir=hugo_base_dir, current_file_path=current_file_path)
  h1_level = inc["newlevelforh1"]
  h1_level = int(h1_level) + 1
  for x in alt_dirs:
    if x in ["mUlam"] and regex.fullmatch(".+vedAH_yajuH.+(Rk|ekAgni).+", file_path):
      continue
    new_include = make_alt_include(url=url, source_dir=source_dir, file_path=file_path, h1_level=h1_level, target_dir=x)
    inc.insert_after("\n\n", new_include, "\n\n")

def include_basename_fixer(inc, ref_dir):
  """To be used with transform_include_lines.
  
  :param match: 
  :param ref_dir: 
  :return: 
  """
  sub_path_to_reference = arrangement.get_sub_path_to_reference_map(ref_dir=ref_dir)
  url = inc["url"]
  sub_path_id = arrangement.get_sub_path_id(regex.sub(".+?/%s(/.+)" % os.path.basename(ref_dir), "\\1", url))
  base_url = regex.sub("(.+?/%s)/.+" % os.path.basename(ref_dir), "\\1", url)
  new_sub_path = regex.sub(".+?/%s(/.+)" % os.path.basename(ref_dir), "\\1", str(sub_path_to_reference[sub_path_id].file_path))
  new_url = os.path.abspath(base_url + new_sub_path)
  inc["url"] = new_url

def include_core_with_commentaries(dir_path, alt_dirs, file_pattern="**/*.md", source_dir="vishvAsa-prastutiH"):
  def include_fixer(inc, file_path, *args, **kwargs):
    return alt_include_adder(inc=inc, current_file_path=file_path, source_dir=source_dir, alt_dirs=alt_dirs)

  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, file_pattern=file_pattern, content_transformer=lambda x, y: transform_includes_with_soup(x, y,transformer=old_include_remover))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, file_pattern=file_pattern, content_transformer=lambda x, y: transform_includes_with_soup(x, y,transformer=include_fixer))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, file_pattern=file_pattern, content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)
