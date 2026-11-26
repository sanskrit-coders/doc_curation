import argparse
import dataclasses
import logging
import os
from urllib.parse import urljoin

import regex

_DIV_TAG_RE = regex.compile(r"<div\b[^>]*>|</div>", regex.S)
_DETAILS_TAG_RE = regex.compile(r"<details\b[^>]*>|</details>", regex.S)
_OPEN_DIV_RE = regex.compile(r"<div\b[^>]*>", regex.S)
_TAG_BALANCE_RE = regex.compile(r"<(/?)(details|div)\b[^>]*>", regex.S)
_ATTR_URL_RE = regex.compile(r"""\burl=["']([^"']+)["']""", regex.IGNORECASE)
_EXTERNAL_URL_RE = regex.compile(r"^(?:https?:|mailto:|javascript:|#)", regex.IGNORECASE)
_JS_INCLUDE_CLASS_RE = regex.compile(r"""\bclass=["'][^"']*\bjs_include\b""", regex.IGNORECASE)


@dataclasses.dataclass(frozen=True)
class BrokenInclude:
  """A ``js_include`` directive whose ``url`` does not resolve to an existing file."""

  file_path: str
  line_number: int
  url: str
  reason: str = "missing_target"


@dataclasses.dataclass(frozen=True)
class TagBalanceIssue:
  """Unbalanced ``<details>`` or ``<div>`` tags in a Markdown file."""

  file_path: str
  details_delta: int
  div_delta: int
  underflow: bool = False


@dataclasses.dataclass(frozen=True)
class IncludeAuditReport:
  """Summary of broken ``js_include`` URLs and tag balance across scanned trees."""

  broken_includes: tuple[BrokenInclude, ...]
  unbalanced_files: tuple[TagBalanceIssue, ...]
  scanned_files: int


def _strip_url_query_fragment(url: str) -> str:
  return url.split("#", 1)[0].split("?", 1)[0]


def _is_ignored_include_url(url: str) -> bool:
  return not url or bool(_EXTERNAL_URL_RE.match(url.strip()))


def file_path_from_url(url, hugo_base_dir, current_file_path=None):
  """Resolve a local Hugo include ``url`` to a file path matching Hugo ``static/`` vs ``content/`` rules."""
  if _is_ignored_include_url(url):
    return None
  clean_url = _strip_url_query_fragment(url)
  file_path = None
  if clean_url.startswith("/"):
    parts = clean_url.lstrip("/").split("/", 1)
    if len(parts) < 2 or not parts[0] or not parts[1].strip("/"):
      return None
    site, raw_rel = parts[0], parts[1].rstrip("/")
    rel = os.path.normpath(raw_rel)
    if rel in (".", "") or rel.startswith(".."):
      return None
    if clean_url.endswith(".md"):
      file_path = os.path.join(hugo_base_dir, site, "static", rel)
    else:
      file_path = os.path.join(hugo_base_dir, site, "content", rel + ".md")
      if not os.path.isfile(file_path):
        file_path = os.path.join(hugo_base_dir, site, "content", rel, "_index.md")
  else:
    if current_file_path is None:
      return None
    # relative path: _index.md and raw static .md files resolve from their containing directory.
    if os.path.basename(current_file_path) == "_index.md" or ("/static/" in str(current_file_path) and str(current_file_path).endswith(".md")):
      file_path = urljoin(str(current_file_path), clean_url)
    else:
      file_path = urljoin(str(current_file_path) + "/", clean_url)
    if file_path.endswith(".md"):
      if "/content/" in file_path:
        file_path = file_path.replace("/content/", "/static/")
    else:
      file_path = regex.sub("(?<=[^/])/*(?=$)", ".md", file_path)
  if file_path is not None:
    file_path = os.path.normpath(regex.sub("//+", "/", file_path))
    if not os.path.isfile(file_path) and "/content/" in file_path:
      if os.path.isdir(file_path):
        idx_cand = os.path.join(file_path, "_index.md")
        if os.path.isfile(idx_cand):
          return idx_cand
      elif file_path.endswith(".md") and os.path.basename(str(current_file_path)) != "_index.md":
        idx_cand = regex.sub(r"\.md$", "/_index.md", file_path)
        if os.path.isfile(idx_cand):
          return idx_cand
    if os.path.isfile(file_path):
      return file_path
    return None


def resolve_hugo_include_file_path(url, hugo_base_dir, current_file_path=None):
  """Strictly resolve a ``js_include`` ``url`` using Hugo runtime rules (``.md`` -> ``static/``, else ``content/``)."""
  p = file_path_from_url(url=url, hugo_base_dir=hugo_base_dir, current_file_path=current_file_path)
  return str(p) if p and os.path.isfile(p) else None


def resolve_include_file_path(url, hugo_base_dir, current_file_path=None):
  """Resolve a ``js_include`` ``url`` to an existing Markdown file path (with permissive ``.md`` fallback)."""
  p = resolve_hugo_include_file_path(url=url, hugo_base_dir=hugo_base_dir, current_file_path=current_file_path)
  if p:
    return p
  clean_url = _strip_url_query_fragment(url)
  for cand in (
    clean_url,
    regex.sub("/$", "", clean_url) + "/_index.md",
    clean_url[:-3] if clean_url.endswith(".md") else (clean_url[:-1] if clean_url.endswith(".md/") else regex.sub("/$", "", clean_url) + ".md"),
  ):
    alt_url = cand.replace("/content/", "/").replace("/static/", "/").replace("//", "/")
    p2 = file_path_from_url(url=alt_url, hugo_base_dir=hugo_base_dir, current_file_path=current_file_path)
    if p2 and os.path.isfile(p2):
      return str(p2)
  return None


def diagnose_include_url(url, hugo_base_dir, current_file_path=None) -> str | None:
  """Return ``None`` if ``url`` resolves strictly for Hugo, else a machine-readable failure reason."""
  if _is_ignored_include_url(url):
    return None
  if resolve_hugo_include_file_path(url=url, hugo_base_dir=hugo_base_dir, current_file_path=current_file_path):
    return None
  clean_url = _strip_url_query_fragment(url)
  permissive = resolve_include_file_path(url=url, hugo_base_dir=hugo_base_dir, current_file_path=current_file_path)
  if permissive:
    if clean_url.endswith(".md") and "/content/" in permissive:
      return "dot_md_points_to_content"
    if not clean_url.endswith(".md") and "/static/" in permissive:
      return "non_md_points_to_static"
    if "/content/" in clean_url or "/static/" in clean_url:
      return "redundant_content_or_static_prefix"
  return "missing_target"


def check_tag_balance(content: str, file_path: str = "") -> TagBalanceIssue | None:
  """Return a :class:`TagBalanceIssue` when ``<details>`` or ``<div>`` tags are unbalanced."""
  det = 0
  div = 0
  underflow = False
  for m in _TAG_BALANCE_RE.finditer(content):
    is_close = m.group(1) == "/"
    if m.group(2) == "details":
      det += -1 if is_close else 1
      if det < 0:
        underflow = True
    else:
      div += -1 if is_close else 1
      if div < 0:
        underflow = True
  if underflow or det != 0 or div != 0:
    return TagBalanceIssue(file_path=file_path, details_delta=det, div_delta=div, underflow=underflow)
  return None


def audit_includes_in_content(
  content: str,
  container_file_path: str,
  hugo_base_dir: str,
  *,
  url_prefix: str | None = None,
  strict: bool = True,
) -> list[BrokenInclude]:
  """Find all broken ``js_include`` URLs inside ``content``."""
  if "js_include" not in content:
    return []
  broken: list[BrokenInclude] = []
  resolver = resolve_hugo_include_file_path if strict else resolve_include_file_path
  for m in _OPEN_DIV_RE.finditer(content):
    tok = m.group(0)
    if not _JS_INCLUDE_CLASS_RE.search(tok):
      continue
    m_url = _ATTR_URL_RE.search(tok)
    if not m_url:
      continue
    url = m_url.group(1)
    if _is_ignored_include_url(url):
      continue
    if url_prefix is not None and not url.startswith(url_prefix):
      continue
    if resolver(url=url, hugo_base_dir=hugo_base_dir, current_file_path=container_file_path) is None:
      line_no = content.count("\n", 0, m.start()) + 1
      reason = diagnose_include_url(url=url, hugo_base_dir=hugo_base_dir, current_file_path=container_file_path) or "missing_target"
      broken.append(BrokenInclude(file_path=container_file_path, line_number=line_no, url=url, reason=reason))
  return broken


def _iter_markdown_files(dir_paths, exclude_dir_names, exclude_dir_prefixes):
  if isinstance(dir_paths, (str, os.PathLike)):
    roots = [os.fspath(dir_paths)]
  else:
    roots = [os.fspath(p) for p in dir_paths]
  seen: set[str] = set()
  for root in roots:
    if os.path.isfile(root):
      ap = os.path.abspath(root)
      if ap not in seen:
        seen.add(ap)
        yield ap
      continue
    if not os.path.exists(root):
      continue
    for dirpath, dirnames, filenames in os.walk(root):
      dirnames[:] = sorted(
        d for d in dirnames
        if d not in exclude_dir_names and not any(d.startswith(pfx) for pfx in exclude_dir_prefixes)
      )
      for fn in sorted(filenames):
        if not fn.endswith(".md"):
          continue
        ap = os.path.abspath(os.path.join(dirpath, fn))
        # Guard against rare directories named ``*.md``.
        if ap in seen or not os.path.isfile(ap):
          continue
        seen.add(ap)
        yield ap


def audit_includes(
  dir_paths,
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
  *,
  url_prefix: str | None = None,
  strict: bool = True,
  check_tags: bool = True,
  exclude_dir_names=(".git", "public", "themes", "resources", "node_modules"),
  exclude_dir_prefixes=("build_",),
) -> IncludeAuditReport:
  """Audit ``js_include`` URLs and optional ``<details>``/``<div>`` tag balance across ``dir_paths``."""
  broken: list[BrokenInclude] = []
  unbalanced: list[TagBalanceIssue] = []
  scanned = 0
  exclude_names_set = set(exclude_dir_names)
  for fp in _iter_markdown_files(dir_paths, exclude_names_set, exclude_dir_prefixes):
    scanned += 1
    try:
      with open(fp, encoding="utf-8") as f:
        text = f.read()
    except UnicodeDecodeError:
      logging.warning(f"Skipping non-UTF-8 file in audit_includes: {fp}")
      continue
    broken.extend(
      audit_includes_in_content(
        text,
        fp,
        hugo_base_dir,
        url_prefix=url_prefix,
        strict=strict,
      )
    )
    if check_tags:
      issue = check_tag_balance(text, file_path=fp)
      if issue is not None:
        unbalanced.append(issue)
  return IncludeAuditReport(
    broken_includes=tuple(broken),
    unbalanced_files=tuple(unbalanced),
    scanned_files=scanned,
  )


def main(argv=None) -> int:
  parser = argparse.ArgumentParser(description="Audit Hugo js_include URLs and <details>/<div> balance.")
  parser.add_argument("paths", nargs="+", help="Root directories or Markdown files to scan.")
  parser.add_argument("--hugo-base-dir", default="/home/vvasuki/gitland/vishvAsa", help="Parent directory of Hugo site repos.")
  parser.add_argument("--url-prefix", default=None, help="Optional URL prefix filter (e.g. /vedAH).")
  parser.add_argument("--permissive", action="store_true", help="Allow legacy .md/non-.md cross-tree fallback.")
  parser.add_argument("--no-tag-check", action="store_true", help="Skip <details>/<div> balance check.")
  args = parser.parse_args(argv)
  report = audit_includes(
    args.paths,
    hugo_base_dir=args.hugo_base_dir,
    url_prefix=args.url_prefix,
    strict=not args.permissive,
    check_tags=not args.no_tag_check,
  )
  print(f"Scanned {report.scanned_files} Markdown files.")
  print(f"Broken includes: {len(report.broken_includes)}")
  for item in report.broken_includes:
    print(f"  [{item.reason}] {item.file_path}:{item.line_number} -> {item.url}")
  if not args.no_tag_check:
    print(f"Unbalanced files: {len(report.unbalanced_files)}")
    for item in report.unbalanced_files:
      print(f"  details_delta={item.details_delta}, div_delta={item.div_delta}, underflow={item.underflow}: {item.file_path}")
  return 1 if report.broken_includes else 0


if __name__ == "__main__":
  raise SystemExit(main())
