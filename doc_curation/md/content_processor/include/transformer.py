import json
import logging
import os

import regex
from bs4 import BeautifulSoup
from doc_curation.md import content_processor, library
from doc_curation.md.content_processor.details import common as details_common
from doc_curation.md.content_processor.include.maker import make_alt_include
from doc_curation.md.content_processor.include.seeker import (
  _ATTR_URL_RE,
  _DETAILS_TAG_RE,
  _DIV_TAG_RE,
  _OPEN_DIV_RE,
  check_tag_balance,
  file_path_from_url,
  resolve_include_file_path,
)
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

def _served_dir(file_path, is_md_raw=False):
  """Map a Hugo ``static/`` or ``content/`` file path to its served URL-equivalent folder path."""
  norm_path = str(file_path)
  if "/static/" in norm_path:
    served = norm_path.replace("/static/", "/", 1)
    return os.path.dirname(served) if (is_md_raw or served.endswith("_index.md")) else served + "/"
  if "/content/" in norm_path:
    served = norm_path.replace("/content/", "/", 1)
    return os.path.dirname(served) if served.endswith("_index.md") else served + "/"
  if norm_path.endswith("_index.md"):
    return os.path.dirname(norm_path)
  return norm_path + "/"


def fix_rel_urls(content, from_path, to_path):
  src_folder = _served_dir(from_path, is_md_raw=str(from_path).endswith(".md") and "/static/" in str(from_path))
  dest_folder = _served_dir(to_path)

  def _relativize(orig_url):
    # Skip if URL has a scheme (http:, mailto:, javascript:, tel:, data: ...) or starts with '#' or '/'
    if regex.match(r'[a-zA-Z][a-zA-Z0-9+.\-]*:', orig_url) or orig_url.startswith(('#', '/')):
      return orig_url
    resolved = os.path.normpath(os.path.join(src_folder, orig_url))
    return os.path.relpath(resolved, dest_folder)

  def replacer(match):
    return f'{match.group(1)}{_relativize(match.group(2))}{match.group(3)}'

  # Fix both image ![](url) and link [](url) references
  pattern = regex.compile(r'(!?\[.*?\]\()([^\)\s]+)(\))')
  return pattern.sub(replacer, content)


_TAG_ATTR_RE = regex.compile(
  r"""\b([a-zA-Z_:][a-zA-Z0-9_.:-]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?"""
)
_SUMMARY_TAG_RE = regex.compile(r"<summary\b[^>]*>(.*?)</summary>", flags=regex.DOTALL | regex.IGNORECASE)
_INNER_HTML_TAG_RE = regex.compile(r"<[^>]+>")


def _extract_open_tag_attrs(open_tok: str) -> dict[str, str]:
  """Parse HTML opening tag attributes into a lowercase-keyed dict."""
  inner = open_tok.strip()
  if inner.startswith("<"):
    m_head = regex.match(r"^<\s*\w+\b", inner)
    if m_head:
      inner = inner[m_head.end():]
  if inner.endswith(">"):
    inner = inner[:-1].rstrip("/")
  attrs: dict[str, str] = {}
  for m in _TAG_ATTR_RE.finditer(inner):
    key = m.group(1).lower()
    val = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else (m.group(4) if m.group(4) is not None else ""))
    attrs[key] = val
  return attrs


def _extract_bs_attrs(tag) -> dict[str, str]:
  """Normalize BeautifulSoup tag attributes into lowercase string values matching ``_extract_open_tag_attrs``."""
  attrs: dict[str, str] = {}
  for k, v in (tag.attrs or {}).items():
    kl = str(k).lower()
    if isinstance(v, list):
      attrs[kl] = " ".join(str(x) for x in v)
    elif v is None:
      attrs[kl] = ""
    else:
      attrs[kl] = str(v)
  return attrs


def filter_details_by_pattern(content: str, details_pattern: str | None) -> str:
  """Keep only ``<details>`` blocks whose trimmed ``<summary>`` matches ``details_pattern`` (matching JS ``handleIncludes.js``)."""
  if not details_pattern or details_pattern.strip() == ".*":
    return content
  try:
    pat = regex.compile(details_pattern, flags=regex.DOTALL)
  except regex.error as exc:
    logging.error(f"Invalid detailsPattern regex {details_pattern!r}: {exc}")
    return content

  def _collect(text: str, out: list[str]) -> None:
    for start, end in details_common.get_top_level_detail_spans(text):
      block = text[start:end]
      m_sum = _SUMMARY_TAG_RE.search(block)
      summary_raw = m_sum.group(1) if m_sum else ""
      summary_text = _INNER_HTML_TAG_RE.sub("", summary_raw).strip()
      if pat.search(summary_text):
        out.append(block)
      elif m_sum:
        close_idx = block.rfind("</details>")
        if close_idx > m_sum.end():
          _collect(block[m_sum.end():close_idx], out)

  matched: list[str] = []
  _collect(content, matched)
  return "\n\n".join(matched)


def _format_metadata_detail(metadata: dict, detail_name: str) -> str:
  """Render frontmatter metadata inside ``<details>`` matching ``mdInclude.js``."""
  clean_meta = {k: v for k, v in (metadata or {}).items() if not str(k).startswith("_")}
  meta_json = json.dumps(clean_meta, indent=2, ensure_ascii=False, default=str)
  meta_md = regex.sub(r"(\s*[\{\[\]\}])", "", meta_json)
  meta_md = regex.sub(r"(\n +)", r"\1- ", meta_md).strip()
  return f"<details><summary>{detail_name}</summary>\n\n{meta_md}\n</details>"


def _apply_md_frontmatter_options(inc_meta: dict, inc_content: str, attrs: dict[str, str], url: str) -> str:
  """Apply ``mdInclude.js`` frontmatter options (``fieldNames`` and ``metadataDetailName``) for ``.md`` targets."""
  clean_url = (url or "").split("#", 1)[0].split("?", 1)[0]
  if not clean_url.endswith(".md"):
    return inc_content
  out = inc_content
  if "metadatadetailname" in attrs:
    raw_name = (attrs.get("metadatadetailname") or "").strip()
    if raw_name.lower() != "false":
      detail_name = raw_name or "Metadata"
      out = f"{_format_metadata_detail(inc_meta, detail_name)}\n\n{out}"
  field_names = (attrs.get("fieldnames") or "").strip()
  if field_names:
    clean_meta = {k: v for k, v in (inc_meta or {}).items() if not str(k).startswith("_")}
    parts = []
    for raw_field in field_names.split(","):
      fn = raw_field.strip()
      if fn in clean_meta and clean_meta[fn] is not None:
        parts.append(f"{fn} : {clean_meta[fn]}")
      else:
        parts.append("")
    out = "\n\n".join(parts) + "\n\n" + out
  return out


def _effective_h1_level(raw_new_level, h1_level_offset=0, default_level=2):
  """Compute clamped effective H1 level (1..6 or ``"b[]"``), matching JS nested include math."""
  if h1_level_offset == "b[]" or raw_new_level == "b[]":
    return "b[]"
  if raw_new_level is not None and str(raw_new_level).strip().isdigit():
    own = int(str(raw_new_level).strip())
    if own < 1 or own > 6:
      own = 6
  else:
    own = default_level
  if isinstance(h1_level_offset, int) and h1_level_offset > 0:
    return min(6, (own - 1) + h1_level_offset)
  return max(1, min(6, own))


def _resolve_title_from_attrs(attrs: dict[str, str], inc_meta: dict, fallback_title: str = "") -> tuple[str, bool]:
  """Resolve ``(title, is_plain)`` using JS ``includeTitle`` / ``title`` precedence."""
  inc_title_attr = attrs.get("includetitle")
  title_attr = (attrs.get("title") or "").strip()
  add_title = inc_title_attr if inc_title_attr is not None else (title_attr or None)
  if not add_title or str(add_title).strip().lower() == "false":
    return "", False
  resolved = title_attr or str((inc_meta or {}).get("title") or fallback_title).strip()
  is_plain = str(add_title).strip().lower() == "plain"
  return resolved, is_plain


def _relativize_html_attrs(content: str, from_path: str, to_path: str, parent_h1_level=None) -> str:
  """Relativize HTML ``src``, nested ``js_include`` ``url``/``newLevelForH1``, and Markdown links/images."""
  content = fix_rel_urls(content=content, from_path=from_path, to_path=to_path)
  src_folder = _served_dir(from_path, is_md_raw=str(from_path).endswith(".md") and "/static/" in str(from_path))
  dest_folder = _served_dir(to_path)

  def _relativize(orig_url: str) -> str:
    if not orig_url or regex.match(r'[a-zA-Z][a-zA-Z0-9+.\-]*:', orig_url) or orig_url.startswith(('#', '/')):
      return orig_url
    resolved = os.path.normpath(os.path.join(src_folder, orig_url))
    return os.path.relpath(resolved, dest_folder)

  content = regex.sub(
    r"""(<(?:img|source|div)\b[^>]*?\bsrc=["'])([^"']+)(["'])""",
    lambda m: f"{m.group(1)}{_relativize(m.group(2))}{m.group(3)}",
    content,
    flags=regex.IGNORECASE,
  )

  def _fix_nested_inc(match):
    tag = match.group(0)
    if "js_include" not in tag:
      return tag
    tag = regex.sub(
      r"""(\burl=["'])([^"']+)(["'])""",
      lambda um: f"{um.group(1)}{_relativize(um.group(2))}{um.group(3)}",
      tag,
      flags=regex.IGNORECASE,
    )
    if isinstance(parent_h1_level, int) and parent_h1_level > 0:
      def _shift_nl(nm):
        val = nm.group(2).strip()
        if val.isdigit():
          shifted = min(6, (int(val) - 1) + parent_h1_level)
          return f"{nm.group(1)}{shifted}{nm.group(3)}"
        return nm.group(0)
      tag = regex.sub(r"""(\bnewLevelForH1=["'])([^"']+)(["'])""", _shift_nl, tag, flags=regex.IGNORECASE)
    return tag

  return regex.sub(r"<div\b[^>]*>", _fix_nested_inc, content, flags=regex.IGNORECASE)


def _prepare_included_content(inc_meta, inc_content, attrs, url, target_fp, container_fp, h1_level, strip_rel_url_shift=False):
  """Apply JS-equivalent ``js_include`` transforms (frontmatter fields/details, ``detailsPattern``, headers, relative URLs)."""
  rendered = _apply_md_frontmatter_options(inc_meta, inc_content, attrs, url)
  rendered = filter_details_by_pattern(rendered, attrs.get("detailspattern"))
  rendered = fix_headers(rendered, h1_level)
  rendered = _relativize_html_attrs(
    rendered,
    from_path=target_fp,
    to_path=str(container_fp),
    parent_h1_level=None if strip_rel_url_shift else h1_level,
  )
  return rendered

def prefill_include(inc, container_file_path, h1_level_offset=0, hugo_base_dir="/home/vvasuki/gitland/vishvAsa",
                    dynamic_loading=True, hash_title=False):
  """Prefill a ``<div class="js_include">`` BeautifulSoup element to match runtime ``js_include`` behavior."""
  inc["unfilled"] = None
  souper.empty_tag(inc)

  attrs = _extract_bs_attrs(inc)
  url = attrs.get("url", "")
  clean_url = url.split("#", 1)[0].split("?", 1)[0]

  file_path = file_path_from_url(url=clean_url, hugo_base_dir=hugo_base_dir, current_file_path=container_file_path)
  if file_path is None:
    if clean_url.endswith(".md"):
      new_url = clean_url[:-3]
    elif clean_url.endswith(".md/"):
      new_url = clean_url[:-1]
    else:
      new_url = regex.sub("/$", "", clean_url) + ".md"

    # Neither of the below should appear in a valid url.
    new_url = new_url.replace("/content/", "/").replace("/static/", "/").replace("//", "/")

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
  if "newlevelforh1" not in attrs:
    logging.warning(f"No newlevelforh1 for {file_path} in {container_file_path}")
  h1_level = _effective_h1_level(attrs.get("newlevelforh1"), h1_level_offset=h1_level_offset, default_level=2)

  if file_path == container_file_path:
    logging.fatal(f"Circular include in {container_file_path}")
    return

  content = _apply_md_frontmatter_options(metadata, content, attrs, url)
  content = filter_details_by_pattern(content, attrs.get("detailspattern"))
  content = fix_headers(content, h1_level)
  content = transform_includes_with_soup(content=content, metadata=metadata, h1_level_offset=h1_level, transformer=prefill_include, dynamic_loading=dynamic_loading, hugo_base_dir=hugo_base_dir)
  # TODO: Handle spreadsheets in includes
  content = _relativize_html_attrs(content=content, from_path=file_path, to_path=container_file_path, parent_h1_level=None)

  title, is_plain = _resolve_title_from_attrs(attrs, metadata, fallback_title="UNKNOWN_TITLE")
  if title == "UNKNOWN_TITLE":
    logging.warning(f"Could not get title for {file_path} in {container_file_path}")
  if title != "" and dynamic_loading:
    title += " …{Loading}…"

  title = title.strip()
  hash_title = hash_title or os.path.basename(container_file_path) == "full.md"
  classes = attrs.get("class", "").split()

  if title != "":
    if "collapsed" not in classes and hash_title:
      if h1_level != "b[]" and not is_plain:
        title = f"{'#' * h1_level} {title}"
      else:
        title = f"**{title}**"
      details = BeautifulSoup(f"{title}\n\n{content}", 'html.parser')
    else:
      if is_plain or h1_level == "b[]":
        summary_html = title
      else:
        summary_html = f"<h{h1_level}>{title}</h{h1_level}>"
      details = BeautifulSoup(f"<body><details><summary>{summary_html}</summary>\n\n{content}\n</details></body>", 'html.parser').select_one("details")
      if "collapsed" not in classes:
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
  only_if_prefilled=False,
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
    attrs = _extract_open_tag_attrs(d[5])
    url = attrs.get("url", "")
    if not url:
      continue
    if url_filter is not None:
      matched = url_filter(url) if callable(url_filter) else bool(regex.search(url_filter, url))
      if not matched:
        continue
    clean_url = url.split("#", 1)[0].split("?", 1)[0]
    file_path = resolve_include_file_path(
      url=clean_url,
      hugo_base_dir=hugo_base_dir,
      current_file_path=container_file_path,
    )
    if not file_path or str(file_path) == str(container_file_path) or not os.path.isfile(file_path):
      continue
    if only_if_prefilled and not content[d[2] : d[3]].strip():
      continue
    target_divs.append((d, url, attrs, str(file_path)))
    covered.append((d[0], d[4]))

  edits = []
  for (_, _, b_start, b_end, _, open_tok), url, attrs, target_fp in target_divs:
    inc_meta, inc_content = MdFile(file_path=target_fp).read()
    cur_body = content[b_start:b_end]
    m_wrap = _LOADING_WRAPPER_RE.match(cur_body)
    if m_wrap and not _has_balanced_details(m_wrap.group(3)):
      m_wrap = None
    m_hash = None if m_wrap else _HASH_LOADING_RE.match(cur_body)
    if m_wrap:
      wrap_head, h_lvl_str, old_inner, wrap_tail = m_wrap.group(1), m_wrap.group(2), m_wrap.group(3), m_wrap.group(4)
      raw_nl = h_lvl_str if h_lvl_str else attrs.get("newlevelforh1")
      h1_level = _effective_h1_level(raw_nl, default_level=2)
      rendered = _prepare_included_content(inc_meta, inc_content, attrs, url, target_fp, container_file_path, h1_level)
      lead_ws = old_inner[: len(old_inner) - len(old_inner.lstrip())] or "\n\n"
      trail_ws = old_inner[len(old_inner.rstrip()) :] or "\n"
      new_body = wrap_head + lead_ws + rendered.strip() + trail_ws + wrap_tail
    elif m_hash:
      wrap_head, hashes, old_inner = m_hash.group(1), m_hash.group(2), m_hash.group(3)
      h1_level = _effective_h1_level(len(hashes), default_level=2)
      rendered = _prepare_included_content(inc_meta, inc_content, attrs, url, target_fp, container_file_path, h1_level)
      lead_ws = old_inner[: len(old_inner) - len(old_inner.lstrip())] or "\n"
      trail_ws = old_inner[len(old_inner.rstrip()) :] or "\n\n"
      new_body = wrap_head + lead_ws + rendered.strip() + trail_ws
    else:
      h1_level = _effective_h1_level(attrs.get("newlevelforh1"), default_level=2)
      rendered = _prepare_included_content(inc_meta, inc_content, attrs, url, target_fp, container_file_path, h1_level)
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


def surgical_prefill_transitive(
  dir_paths,
  changed_file_paths,
  *,
  hugo_base_dir="/home/vvasuki/gitland/vishvAsa",
  exclude_path_substrings=(),
  skip_sources_with_empty_includes=True,
  only_if_prefilled=False,
  require_balanced_tags=True,
  max_passes=6,
  dry_run=False,
) -> set[str]:
  """Propagate edits from ``changed_file_paths`` through all transitive ``js_include`` containers in topological waves.

  :param dir_paths: A single directory path or sequence of root directories to scan for ``js_include`` container ``.md`` files.
  :param changed_file_paths: Iterable of modified source Markdown file paths whose changes should propagate upward.
  :param hugo_base_dir: Base parent directory of Hugo repositories (e.g. ``/home/vvasuki/gitland/vishvAsa``).
  :param exclude_path_substrings: Substrings of directory/file paths to skip completely (e.g. ``("shatapatha-brAhmaNam",)``).
  :param skip_sources_with_empty_includes: When ``True``, skip pulling from an intermediate file that still has empty ``js_include`` divs.
  :param require_balanced_tags: When ``True``, refuse any update that unbalances a previously balanced ``<details>`` or ``<div>`` count.
  :param max_passes: Maximum topological propagation waves.
  :param dry_run: When ``True``, compute the set of affected container files without writing to disk.
  :return: Set of container file paths updated across all waves.
  """
  if isinstance(dir_paths, (str, os.PathLike)):
    roots = [os.fspath(dir_paths)]
  else:
    roots = [os.fspath(p) for p in dir_paths]

  abs_url_cache: dict[str, str | None] = {}
  rev_deps: dict[str, set[str]] = {}

  def _resolve_abs(url: str, container_fp: str) -> str | None:
    if url.startswith("/"):
      if url in abs_url_cache:
        return abs_url_cache[url]
      tgt = resolve_include_file_path(url=url, hugo_base_dir=hugo_base_dir, current_file_path=container_fp)
      res = os.path.abspath(tgt) if tgt else None
      abs_url_cache[url] = res
      return res
    tgt = resolve_include_file_path(url=url, hugo_base_dir=hugo_base_dir, current_file_path=container_fp)
    return os.path.abspath(tgt) if tgt else None

  def _index_host_urls(fp: str, txt: str) -> None:
    for m_div in _OPEN_DIV_RE.finditer(txt):
      tok = m_div.group(0)
      if 'class="js_include' in tok or "class='js_include" in tok:
        m_u = _ATTR_URL_RE.search(tok)
        if m_u:
          tgt_abs = _resolve_abs(m_u.group(1), fp)
          if tgt_abs:
            rev_deps.setdefault(tgt_abs, set()).add(fp)

  seen_cands: set[str] = set()
  for root in roots:
    if not os.path.exists(root):
      continue
    for dirpath, dirnames, filenames in os.walk(root):
      dirnames[:] = [
        d for d in dirnames
        if d != ".git" and not (exclude_path_substrings and any(ex in d for ex in exclude_path_substrings))
      ]
      if exclude_path_substrings and any(ex in dirpath for ex in exclude_path_substrings):
        continue
      for fn in sorted(filenames):
        if not fn.endswith(".md"):
          continue
        fp = os.path.abspath(os.path.join(dirpath, fn))
        if fp in seen_cands:
          continue
        if exclude_path_substrings and any(ex in fp for ex in exclude_path_substrings):
          continue
        try:
          with open(fp, encoding="utf-8") as f:
            txt = f.read()
        except UnicodeDecodeError:
          logging.warning(f"Skipping non-UTF-8 file in surgical_prefill_transitive: {fp}")
          continue
        if "js_include" in txt:
          seen_cands.add(fp)
          _index_host_urls(fp, txt)

  unfilled_cache: dict[str, bool] = {}
  in_memory_texts: dict[str, str] = {}

  def _has_empty_nested_include(fp: str) -> bool:
    if fp in unfilled_cache:
      return unfilled_cache[fp]
    txt = in_memory_texts.get(fp)
    if txt is None:
      try:
        with open(fp, encoding="utf-8") as f:
          txt = f.read()
      except UnicodeDecodeError:
        logging.warning(f"Skipping non-UTF-8 include target in surgical_prefill_transitive: {fp}")
        unfilled_cache[fp] = False
        return False
    if "js_include" not in txt:
      unfilled_cache[fp] = False
      return False
    divs = find_js_include_divs(txt)
    res = any(not txt[bs:be].strip() for _, _, bs, be, _, _ in divs)
    unfilled_cache[fp] = res
    return res

  frontier: set[str] = {os.path.abspath(os.fspath(p)) for p in changed_file_paths if p}
  expanded_sources: set[str] = set()
  touched_files: set[str] = set()
  pass_num = 0

  while frontier and pass_num < max_passes:
    pass_num += 1
    expanded_sources.update(frontier)
    wave_candidates = sorted({fp for src in frontier for fp in rev_deps.get(src, ())})
    newly_changed: set[str] = set()
    for fp in wave_candidates:
      orig = in_memory_texts.get(fp)
      if orig is None:
        with open(fp, encoding="utf-8") as f:
          orig = f.read()

      def _url_match(url: str, _fp: str = fp, _front: set[str] = frontier) -> bool:
        tgt_abs = _resolve_abs(url, _fp)
        if not tgt_abs or tgt_abs not in _front:
          return False
        if skip_sources_with_empty_includes and _has_empty_nested_include(tgt_abs):
          return False
        return True

      updated, n_divs = surgical_prefill_content(
        orig,
        fp,
        url_filter=_url_match,
        hugo_base_dir=hugo_base_dir,
        only_if_prefilled=only_if_prefilled,
      )
      if n_divs > 0 and updated != orig:
        if require_balanced_tags:
          orig_ok = (
            orig.count("<details") == orig.count("</details>")
            and orig.count("<div") == orig.count("</div>")
          )
          upd_ok = (
            updated.count("<details") == updated.count("</details>")
            and updated.count("<div") == updated.count("</div>")
          )
          if orig_ok and not upd_ok:
            logging.warning(f"Skipping unbalanced transitive prefill in {fp}")
            continue
        if dry_run:
          in_memory_texts[fp] = updated
        else:
          with open(fp, "w", encoding="utf-8") as f:
            f.write(updated)
        touched_files.add(fp)
        unfilled_cache.pop(fp, None)
        _index_host_urls(fp, updated)
        if fp not in expanded_sources:
          newly_changed.add(fp)
    frontier = newly_changed
  return touched_files

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

_MD_LINK_URL_RE = regex.compile(r"""\]\(([^)\s]+)\)""")


def _clean_loading_title(raw_title: str) -> str:
  cleaned = regex.sub(r"</?h\d+>", "", raw_title)
  cleaned = regex.sub(r"\s*(?:\.\.\.|…)\{Loading\}(?:\.\.\.|…)\s*", "", cleaned)
  return cleaned.strip()


def _extract_existing_wrapper(cur_body: str):
  """Return ``(inner_body, summary_title, h1_level, is_open_or_none)`` from a prefilled ``js_include`` body."""
  m_wrap = _LOADING_WRAPPER_RE.match(cur_body)
  if m_wrap and not _has_balanced_details(m_wrap.group(3)):
    m_wrap = None
  if m_wrap:
    wrap_head, h_lvl_str, old_inner = m_wrap.group(1), m_wrap.group(2), m_wrap.group(3)
    m_sum = regex.search(r"<summary>(.*?)</summary>", wrap_head, regex.S)
    summary_title = _clean_loading_title(m_sum.group(1)) if m_sum else ""
    h1_level = int(h_lvl_str) if h_lvl_str else None
    is_open = bool(regex.search(r"<details\b[^>]*\bopen\b", wrap_head))
    return old_inner.strip(), summary_title, h1_level, is_open
  m_hash = _HASH_LOADING_RE.match(cur_body)
  if m_hash:
    wrap_head, hashes, old_inner = m_hash.group(1), m_hash.group(2), m_hash.group(3)
    raw_title = regex.sub(r"^\s*#+\s*", "", wrap_head).strip()
    return old_inner.strip(), _clean_loading_title(raw_title), len(hashes), True
  return cur_body.strip(), "", None, None


def deinclude_content(
  content,
  container_file_path,
  *,
  url_filter=None,
  prefill=True,
  title=None,
  preserve_open_state=True,
  hugo_base_dir="/home/vvasuki/gitland/vishvAsa",
):
  """Inline matching ``js_include`` divs directly into ``content`` via balanced string slicing.

  Preserves surrounding Markdown, Hugo shortcodes, and unmatched ``js_include`` divs byte-for-byte.
  For each matched ``js_include`` div:

  - When ``prefill=True``, reads fresh content from the resolved included file (refreshing nested
    ``js_include`` blocks, adjusting heading levels, and fixing relative URLs). Otherwise extracts
    the already-prefilled body while stripping any outer ``{Loading}`` ``<details>`` or heading wrapper.
  - Strips the outer ``<div class="js_include" ...> ... </div>``, ``{Loading}`` markers, and
    ``<hN>...</hN>`` tags inside ``<summary>``.
  - Preserves open vs. collapsed state (``<details open>`` vs. ``<details>``) when
    ``preserve_open_state=True``; otherwise emits ``<details open>``.
  - ``title`` may be ``None`` (derive from ``title="..."`` attribute, cleaned summary, or included
    file frontmatter; titleless ``includetitle="false"`` includes inline bare content), a ``str``,
    or a callable ``title(url, open_tag, default_title) -> str | None``.

  Returns ``(updated_content, deincluded_file_paths)``.
  """
  if "js_include" not in content:
    return content, []

  all_divs = find_js_include_divs(content)
  target_divs = []
  covered = []
  for d in sorted(all_divs, key=lambda x: (x[0], -(x[4] - x[0]))):
    if any(a <= d[0] and d[4] <= b for a, b in covered):
      continue
    open_tok = d[5]
    attrs = _extract_open_tag_attrs(open_tok)
    url = attrs.get("url", "")
    if not url:
      continue
    if url_filter is not None:
      matched = url_filter(url) if callable(url_filter) else bool(regex.search(url_filter, url))
      if not matched:
        continue
    clean_url = url.split("#", 1)[0].split("?", 1)[0]
    file_path = resolve_include_file_path(
      url=clean_url,
      hugo_base_dir=hugo_base_dir,
      current_file_path=container_file_path,
    )
    if prefill and (not file_path or str(file_path) == str(container_file_path) or not os.path.isfile(file_path)):
      logging.warning(f"Skipping deinclude of unresolved/self url={url} in {container_file_path}")
      continue
    target_divs.append((d, url, attrs, str(file_path) if file_path else None))
    covered.append((d[0], d[4]))

  if not target_divs:
    return content, []

  edits = []
  deincluded_paths = []
  for (s_open, _, b_start, b_end, e_close, open_tok), url, attrs, target_fp in target_divs:
    cur_body = content[b_start:b_end]
    existing_inner, existing_summary, existing_h1, existing_open = _extract_existing_wrapper(cur_body)

    has_class_attr = "class" in attrs
    classes = attrs.get("class", "").split()
    is_collapsed = "collapsed" in classes
    raw_nl = existing_h1 if existing_h1 is not None else attrs.get("newlevelforh1")
    h1_level = _effective_h1_level(raw_nl, default_level=2)

    inc_meta = {}
    if prefill:
      inc_meta, inc_content = MdFile(file_path=target_fp).read()
      if "js_include" in inc_content:
        inc_content, _ = surgical_prefill_content(
          inc_content,
          target_fp,
          hugo_base_dir=hugo_base_dir,
        )
      rendered = _prepare_included_content(inc_meta, inc_content, attrs, url, target_fp, container_file_path, h1_level)
      inner_body = rendered.strip()
    else:
      inner_body = filter_details_by_pattern(existing_inner, attrs.get("detailspattern"))

    default_title, _ = _resolve_title_from_attrs(attrs, inc_meta, fallback_title=existing_summary)

    if callable(title):
      final_title = title(url, open_tok, default_title) or ""
    elif title is not None:
      final_title = title
    else:
      final_title = default_title

    if final_title:
      if preserve_open_state:
        is_open = (not is_collapsed) if has_class_attr else (existing_open if existing_open is not None else True)
      else:
        is_open = True
      open_attr = " open" if is_open else ""
      sep = "\n" if inner_body.startswith("<details") else "\n\n"
      replacement = f"<details{open_attr}><summary>{final_title}</summary>{sep}{inner_body}\n</details>"
    else:
      replacement = inner_body

    edits.append((s_open, e_close, replacement))
    if target_fp:
      deincluded_paths.append(os.path.abspath(target_fp))

  out = content
  for s, e, rep in sorted(edits, key=lambda x: x[0], reverse=True):
    out = out[:s] + rep + out[e:]
  return out, deincluded_paths


def _find_referenced_paths(
  candidate_paths: set[str],
  reference_check_roots,
  in_memory_texts: dict[str, str],
  hugo_base_dir: str,
) -> set[str]:
  """Return subset of ``candidate_paths`` still referenced by files under ``reference_check_roots``."""
  if not candidate_paths or not reference_check_roots:
    return set()
  if isinstance(reference_check_roots, (str, os.PathLike)):
    roots = [os.fspath(reference_check_roots)]
  else:
    roots = [os.fspath(p) for p in reference_check_roots]

  skip_dir_names = {".git", "public", "resources", "node_modules"}
  # Build quick token list to avoid scanning unrelated files
  tokens = set()
  for p in candidate_paths:
    bn = os.path.basename(p)
    if bn == "_index.md":
      tokens.add(os.path.basename(os.path.dirname(p)))
    else:
      tokens.add(bn[:-3] if bn.endswith(".md") else bn)

  all_files: list[str] = []
  seen: set[str] = set()
  for root in roots:
    if os.path.isfile(root):
      ap = os.path.abspath(root)
      if ap not in seen:
        seen.add(ap)
        all_files.append(ap)
      continue
    if not os.path.exists(root):
      continue
    for dirpath, dirnames, filenames in os.walk(root):
      dirnames[:] = [d for d in dirnames if d not in skip_dir_names and not d.startswith("build_")]
      for fn in filenames:
        if not fn.endswith(".md"):
          continue
        ap = os.path.abspath(os.path.join(dirpath, fn))
        if ap not in seen:
          seen.add(ap)
          all_files.append(ap)

  def _url_stem(u: str) -> str:
    u_clean = u.split("#", 1)[0].split("?", 1)[0].rstrip("/")
    bn = os.path.basename(u_clean)
    return bn[:-3] if bn.endswith(".md") else bn

  def _refs_in_file(fp: str) -> set[str]:
    txt = in_memory_texts.get(fp)
    if txt is None:
      try:
        with open(fp, encoding="utf-8") as f:
          txt = f.read()
      except OSError:
        return set()
    has_inc = "js_include" in txt
    has_link = "](" in txt
    if not has_inc and not has_link:
      return set()
    hits = set()
    if has_inc:
      for _, _, _, _, _, open_tok in find_js_include_divs(txt):
        m_u = _ATTR_URL_RE.search(open_tok)
        if not m_u:
          continue
        u = m_u.group(1)
        if _url_stem(u) not in tokens:
          continue
        tgt = resolve_include_file_path(url=u, hugo_base_dir=hugo_base_dir, current_file_path=fp)
        if tgt:
          tgt_abs = os.path.abspath(tgt)
          if tgt_abs in candidate_paths:
            hits.add(tgt_abs)
    if has_link:
      for m_l in _MD_LINK_URL_RE.finditer(txt):
        u = m_l.group(1)
        if _url_stem(u) not in tokens:
          continue
        tgt = resolve_include_file_path(url=u, hugo_base_dir=hugo_base_dir, current_file_path=fp)
        if tgt:
          tgt_abs = os.path.abspath(tgt)
          if tgt_abs in candidate_paths:
            hits.add(tgt_abs)
    return hits

  retained: set[str] = set()
  # Check all non-candidate files first
  for fp in all_files:
    if fp in candidate_paths:
      continue
    retained.update(_refs_in_file(fp))

  # Fixed point: if a retained candidate file itself references another candidate, retain that too
  checked_retained: set[str] = set()
  while retained - checked_retained:
    batch = list(retained - checked_retained)
    for fp in batch:
      checked_retained.add(fp)
      retained.update(_refs_in_file(fp))

  return retained


def deinclude(
  dir_path,
  *,
  url_filter=None,
  file_name_filter=None,
  file_pattern="**/*.md",
  prefill=True,
  title=None,
  preserve_open_state=True,
  delete_included_files=True,
  reference_check_roots=None,
  require_balanced_tags=True,
  hugo_base_dir="/home/vvasuki/gitland/vishvAsa",
  dry_run=False,
) -> dict[str, set[str]]:
  """Inline matching ``js_include`` divs across ``dir_path`` and optionally delete the included source files.

  When ``delete_included_files=True`` and ``reference_check_roots`` is provided (a path or sequence of root
  directories), any included file still referenced elsewhere under ``reference_check_roots`` is kept instead
  of deleted and reported under ``"retained_referenced_files"``.

  Returns ``{"updated_files": set[str], "deleted_files": set[str], "retained_referenced_files": set[str]}``.
  """
  logging.info(f"De-including in {dir_path} (dry_run={dry_run}, delete_included_files={delete_included_files})")
  md_files = library.get_md_files_from_path(
    dir_path=dir_path,
    file_pattern=file_pattern,
    file_name_filter=file_name_filter,
  )

  updated_files: set[str] = set()
  in_memory_texts: dict[str, str] = {}
  candidate_deletes: set[str] = set()

  for md_file in md_files:
    fp = os.path.abspath(md_file.file_path)
    with open(fp, encoding="utf-8") as f:
      orig = f.read()
    if "js_include" not in orig:
      continue
    updated, deincluded_paths = deinclude_content(
      orig,
      fp,
      url_filter=url_filter,
      prefill=prefill,
      title=title,
      preserve_open_state=preserve_open_state,
      hugo_base_dir=hugo_base_dir,
    )
    if updated == orig:
      continue
    if require_balanced_tags:
      orig_ok = (
        orig.count("<details") == orig.count("</details>")
        and orig.count("<div") == orig.count("</div>")
      )
      upd_ok = (
        updated.count("<details") == updated.count("</details>")
        and updated.count("<div") == updated.count("</div>")
      )
      if orig_ok and not upd_ok:
        logging.warning(f"Skipping unbalanced deinclude in {fp}")
        continue
    in_memory_texts[fp] = updated
    updated_files.add(fp)
    candidate_deletes.update(deincluded_paths)
    if not dry_run:
      with open(fp, "w", encoding="utf-8") as f:
        f.write(updated)

  retained_referenced_files: set[str] = set()
  deleted_files: set[str] = set()
  if delete_included_files and candidate_deletes:
    if reference_check_roots is not None:
      retained_referenced_files = _find_referenced_paths(
        candidate_paths=candidate_deletes,
        reference_check_roots=reference_check_roots,
        in_memory_texts=in_memory_texts,
        hugo_base_dir=hugo_base_dir,
      )
    to_delete = sorted(p for p in (candidate_deletes - retained_referenced_files) if os.path.isfile(p))
    for p in to_delete:
      deleted_files.add(p)
      if not dry_run:
        os.remove(p)
    for p in sorted(retained_referenced_files):
      logging.warning(f"Retaining still-referenced included file: {p}")

  return {
    "updated_files": updated_files,
    "deleted_files": deleted_files,
    "retained_referenced_files": retained_referenced_files,
  }

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
