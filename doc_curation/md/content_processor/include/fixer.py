"""Normalize ``js_include`` title/includeTitle attributes and ``{Loading}`` wrappers."""
from __future__ import annotations

import dataclasses
import logging
import os
from collections.abc import Callable, Collection, Iterable

import regex

from doc_curation.md.content_processor.include.seeker import (
  _iter_markdown_files,
  check_tag_balance,
)
from doc_curation.md.content_processor.include.transformer import (
  _LOADING_WRAPPER_RE,
  _effective_h1_level,
  _has_balanced_details,
  find_js_include_divs,
  surgical_prefill_transitive,
)

DEFAULT_SARVA_TITLE = "सर्वाष् टीकाः"
DEFAULT_VP_TITLE = "विश्वास-प्रस्तुतिः"
DEFAULT_SARVA_SEGMENT = "/sarvASh_TIkAH/"
DEFAULT_VP_SEGMENT = "/vishvAsa-prastutiH/"
DEFAULT_SARVA_TITLE_ALIASES = frozenset({"सर्वाः टीकाः", "सर्वाष्टीकाः", "सर्वाः टीकाः।", "सर्वाष् टीकाः।"})
DEFAULT_VP_TITLE_ALIASES = frozenset({"विश्वासप्रस्तुतिः", "विश्वासः प्रस्तुतिः"})

_DEFAULT_EXCLUDE_DIR_NAMES = (".git", "public", "themes", "resources", "node_modules")
_DEFAULT_EXCLUDE_DIR_PREFIXES = ("build_",)

_OPEN_TAG_ATTR_RE = regex.compile(r"""([A-Za-z_:][A-Za-z0-9_.:-]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?""")
_HEADING_DETAILS_WRAPPER_RE = regex.compile(
  r"^(\s*<details[^>]*><summary>\s*<h(\d+)>([^<]*?)</h\2>\s*</summary>)(.*)(</details>\s*)$",
  regex.S,
)
_LOADING_SUFFIX_RE = regex.compile(r"\s*(?:\.\.\.|…)\{Loading\}(?:\.\.\.|…)\s*$")


@dataclasses.dataclass(frozen=True)
class IncludeTitleChange:
  """One rewritten outer ``js_include`` block."""

  file_path: str
  url: str
  reason: str
  old_title: str | None
  new_title: str | None
  old_includetitle: str | None
  new_includetitle: str | None


@dataclasses.dataclass(frozen=True)
class IncludeTitleFixReport:
  """Aggregate summary returned by :func:`fix_include_titles`."""

  changed_files: tuple[str, ...]
  changes: tuple[IncludeTitleChange, ...]
  propagated_files: tuple[str, ...] = ()
  scanned_files: int = 0


def _parse_open_tag_attrs(open_tag: str) -> list[tuple[str, str | None, str]]:
  inner = open_tag[4:-1].strip()
  attrs: list[tuple[str, str | None, str]] = []
  for m in _OPEN_TAG_ATTR_RE.finditer(inner):
    key = m.group(1)
    if m.group(2) is not None:
      attrs.append((key, m.group(2), '"'))
    elif m.group(3) is not None:
      attrs.append((key, m.group(3), "'"))
    elif m.group(4) is not None:
      attrs.append((key, m.group(4), ""))
    else:
      attrs.append((key, None, ""))
  return attrs


def _format_open_tag(attrs: list[tuple[str, str | None, str]]) -> str:
  parts = ["<div"]
  for key, val, quote in attrs:
    if val is None:
      parts.append(key)
    else:
      q = quote or '"'
      parts.append(f"{key}={q}{val}{q}")
  return " ".join(parts) + ">"


def _get_attr(attrs: list[tuple[str, str | None, str]], name: str) -> str | None:
  lname = name.lower()
  for key, val, _ in attrs:
    if key.lower() == lname:
      return val
  return None


def _set_attr(
  attrs: list[tuple[str, str | None, str]],
  name: str,
  value: str | None,
) -> list[tuple[str, str | None, str]]:
  lname = name.lower()
  found = False
  out: list[tuple[str, str | None, str]] = []
  for key, val, quote in attrs:
    if key.lower() == lname:
      found = True
      if value is not None:
        out.append((name if key.lower() in ("title", "includetitle", "class") else key, value, quote or '"'))
    else:
      out.append((key, val, quote))
  if found or value is None:
    return out
  inserted = False
  ordered: list[tuple[str, str | None, str]] = []
  for item in out:
    if not inserted and item[0].lower() in ("unfilled", "url"):
      ordered.append((name, value, '"'))
      inserted = True
    ordered.append(item)
  if not inserted:
    ordered.append((name, value, '"'))
  return ordered


def _set_collapsed_class(
  attrs: list[tuple[str, str | None, str]],
  collapsed: bool,
) -> list[tuple[str, str | None, str]]:
  cls_val = _get_attr(attrs, "class") or "js_include"
  tokens = cls_val.split()
  if collapsed:
    if "collapsed" not in tokens:
      tokens.append("collapsed")
  else:
    tokens = [t for t in tokens if t != "collapsed"]
  return _set_attr(attrs, "class", " ".join(tokens))


def _outermost_js_include_divs(content: str) -> list[tuple[int, int, int, int, int, str]]:
  all_divs = find_js_include_divs(content)
  outer: list[tuple[int, int, int, int, int, str]] = []
  covered: list[tuple[int, int]] = []
  for div in sorted(all_divs, key=lambda d: (d[0], -(d[4] - d[0]))):
    if any(a <= div[0] and div[4] <= b for a, b in covered):
      continue
    outer.append(div)
    covered.append((div[0], div[4]))
  outer.sort(key=lambda d: d[0])
  return outer


def _match_wrapper_details(
  body: str,
  known_heading_titles: Collection[str] = (),
) -> tuple[str | None, str, str] | None:
  """Return ``(h_level_or_none, summary_title, inner_body)`` for an outer wrapper ``<details>``."""
  m_load = _LOADING_WRAPPER_RE.match(body)
  if m_load and _has_balanced_details(m_load.group(3)):
    head = m_load.group(1)
    m_sum = regex.search(r"<summary>(?:<h\d+>)?(.*?)(?:</h\d+>)?</summary>", head, regex.S)
    raw_sum = _LOADING_SUFFIX_RE.sub("", m_sum.group(1)).strip() if m_sum else ""
    return m_load.group(2), raw_sum, m_load.group(3)

  if known_heading_titles:
    m_hd = _HEADING_DETAILS_WRAPPER_RE.match(body)
    if m_hd and _has_balanced_details(m_hd.group(4)):
      raw_title = _LOADING_SUFFIX_RE.sub("", m_hd.group(3)).strip()
      if raw_title in known_heading_titles:
        return m_hd.group(2), raw_title, m_hd.group(4)
  return None


def _unwrap_outer_details(body: str, known_heading_titles: Collection[str] = ()) -> str:
  matched = _match_wrapper_details(body, known_heading_titles=known_heading_titles)
  if matched is None:
    return body
  inner = matched[2].strip()
  return f"\n{inner}\n" if inner else "\n"


def _wrap_or_update_details_wrapper(
  body: str,
  title: str,
  nl_str: str | None,
  collapsed: bool,
  *,
  known_heading_titles: Collection[str] = (),
  wrap_plain_body: bool = True,
) -> str:
  if not body.strip():
    return body
  eff = _effective_h1_level(nl_str, default_level=4)
  fallback_lvl = str(eff) if isinstance(eff, int) else "4"
  open_attr = "" if collapsed else " open"

  matched = _match_wrapper_details(body, known_heading_titles=known_heading_titles)
  if matched is not None:
    h_lvl_orig, _raw_sum, inner = matched
    h_lvl = h_lvl_orig or fallback_lvl
    lead_ws = inner[: len(inner) - len(inner.lstrip())] or "\n\n"
    trail_ws = inner[len(inner.rstrip()) :] or "\n"
    return f"\n<details{open_attr}><summary><h{h_lvl}>{title} …{{Loading}}…</h{h_lvl}></summary>{lead_ws}{inner.strip()}{trail_ws}</details>\n"

  if not wrap_plain_body:
    return body
  inner_s = body.strip()
  sep = "\n" if inner_s.startswith("<details") else "\n\n"
  return f"\n<details{open_attr}><summary><h{fallback_lvl}>{title} …{{Loading}}…</h{fallback_lvl}></summary>{sep}{inner_s}\n</details>\n"


def _fix_nested_vp_div(
  attrs: list[tuple[str, str | None, str]],
  body: str,
  *,
  vp_title: str,
  vp_title_aliases: Collection[str],
  sarva_title: str,
  sarva_title_aliases: Collection[str],
  fix_nested_vp_missing_includetitle: bool,
  fix_nested_vp_includetitle_true: bool,
  unwrap_nested_vp_details: bool,
  update_prefill_wrappers: bool,
) -> tuple[str | None, list[tuple[str, str | None, str]], str]:
  title = _get_attr(attrs, "title")
  it = _get_attr(attrs, "includetitle")
  it_low = it.strip().lower() if it is not None else None
  cls_tokens = (_get_attr(attrs, "class") or "js_include").split()
  vp_heading_titles = {vp_title, *vp_title_aliases, sarva_title, *sarva_title_aliases}

  reason: str | None = None
  new_attrs = list(attrs)
  new_body = body

  if title in vp_heading_titles or title == "":
    new_attrs = _set_attr(new_attrs, "title", None)
    new_attrs = _set_attr(new_attrs, "includetitle", "false")
    new_attrs = _set_collapsed_class(new_attrs, False)
    reason = "NESTED_VP_STRIP_TITLE"
  elif title is None and it is None and fix_nested_vp_missing_includetitle:
    new_attrs = _set_attr(new_attrs, "includetitle", "false")
    new_attrs = _set_collapsed_class(new_attrs, False)
    reason = "NESTED_VP_SET_FALSE"
  elif title is None and it_low == "true" and fix_nested_vp_includetitle_true:
    new_attrs = _set_attr(new_attrs, "includetitle", "false")
    new_attrs = _set_collapsed_class(new_attrs, False)
    reason = "NESTED_VP_IT_TRUE_TO_FALSE"
  elif title is None and it_low == "false":
    changed_cleanup = False
    if it != "false":
      new_attrs = _set_attr(new_attrs, "includetitle", "false")
      changed_cleanup = True
    if "collapsed" in cls_tokens:
      new_attrs = _set_collapsed_class(new_attrs, False)
      changed_cleanup = True
    if update_prefill_wrappers and unwrap_nested_vp_details:
      matched = _match_wrapper_details(body, known_heading_titles=vp_heading_titles)
      if matched is not None and matched[1] in vp_heading_titles:
        unwrapped = _unwrap_outer_details(body, known_heading_titles=vp_heading_titles)
        if unwrapped != body:
          new_body = unwrapped
          changed_cleanup = True
    if changed_cleanup:
      return "NESTED_VP_CLEANUP", new_attrs, new_body
    return None, attrs, body
  else:
    return None, attrs, body

  if update_prefill_wrappers and unwrap_nested_vp_details:
    new_body = _unwrap_outer_details(body, known_heading_titles=vp_heading_titles)
  return reason, new_attrs, new_body


def _fix_host_vp_div(
  attrs: list[tuple[str, str | None, str]],
  body: str,
  *,
  vp_title: str,
  vp_title_aliases: Collection[str],
  sarva_title: str,
  sarva_title_aliases: Collection[str],
  fix_missing_vp_title: bool,
  update_prefill_wrappers: bool,
) -> tuple[str | None, list[tuple[str, str | None, str]], str]:
  title = _get_attr(attrs, "title")
  it = _get_attr(attrs, "includetitle")
  it_low = it.strip().lower() if it is not None else None
  nl = _get_attr(attrs, "newlevelforh1")
  wrong_titles = {sarva_title, *sarva_title_aliases, *vp_title_aliases}

  if title in wrong_titles:
    new_attrs = _set_attr(attrs, "title", vp_title)
    new_attrs = _set_attr(new_attrs, "includetitle", None)
    new_attrs = _set_collapsed_class(new_attrs, False)
    new_body = (
      _wrap_or_update_details_wrapper(
        body, vp_title, nl, collapsed=False, known_heading_titles=wrong_titles
      )
      if update_prefill_wrappers
      else body
    )
    return "HOST_VP_FIX_TITLE", new_attrs, new_body

  if title == "":
    new_attrs = _set_attr(attrs, "title", None)
    if it is None:
      new_attrs = _set_attr(new_attrs, "includetitle", "false")
    elif it != it_low and it_low in ("true", "false", "plain"):
      new_attrs = _set_attr(new_attrs, "includetitle", it_low)
    return "HOST_VP_EMPTY_TITLE", new_attrs, body

  if title is None and it is None and fix_missing_vp_title:
    new_attrs = _set_attr(attrs, "title", vp_title)
    new_attrs = _set_collapsed_class(new_attrs, False)
    new_body = (
      _wrap_or_update_details_wrapper(
        body, vp_title, nl, collapsed=False, known_heading_titles=wrong_titles
      )
      if update_prefill_wrappers
      else body
    )
    return "HOST_VP_ADD_TITLE", new_attrs, new_body

  if it is not None and it_low in ("true", "false", "plain") and it != it_low:
    return "HOST_VP_LOWER_IT", _set_attr(attrs, "includetitle", it_low), body

  if title == vp_title and it is None and update_prefill_wrappers:
    matched = _match_wrapper_details(body, known_heading_titles=wrong_titles)
    if matched is not None and matched[1] in wrong_titles:
      new_body = _wrap_or_update_details_wrapper(
        body, vp_title, nl, collapsed=False, known_heading_titles=wrong_titles
      )
      if new_body != body:
        return "HOST_VP_FIX_WRAPPER", list(attrs), new_body

  return None, attrs, body


def _fix_sarva_div(
  attrs: list[tuple[str, str | None, str]],
  body: str,
  clean_url: str,
  *,
  sarva_title: str,
  sarva_title_aliases: Collection[str],
  vp_title: str,
  vp_title_aliases: Collection[str],
  extra_wrong_sarva_titles: Collection[str],
  fix_sarva_includetitle_true: bool,
  fix_sarva_includetitle_false: bool,
  fix_missing_sarva_title: bool,
  overwrite_custom_sarva_titles: bool,
  collapse_sarva_leaves: bool,
  ensure_sarva_collapsed: bool,
  update_prefill_wrappers: bool,
) -> tuple[str | None, list[tuple[str, str | None, str]], str]:
  title = _get_attr(attrs, "title")
  it = _get_attr(attrs, "includetitle")
  it_low = it.strip().lower() if it is not None else None
  dp = (_get_attr(attrs, "detailspattern") or "").strip()
  has_custom_filter = bool(dp and dp != ".*")
  nl = _get_attr(attrs, "newlevelforh1")
  cls_tokens = (_get_attr(attrs, "class") or "js_include").split()
  is_idx = clean_url.rstrip("/").endswith("/_index.md") or clean_url.endswith("/")
  want_collapsed = False if is_idx else collapse_sarva_leaves
  wrong_titles = {vp_title, *vp_title_aliases, *sarva_title_aliases, *extra_wrong_sarva_titles, ""}

  if has_custom_filter:
    if title in sarva_title_aliases:
      new_attrs = _set_attr(attrs, "title", sarva_title)
      new_body = (
        _wrap_or_update_details_wrapper(
          body,
          sarva_title,
          nl,
          collapsed=("collapsed" in cls_tokens),
          known_heading_titles=sarva_title_aliases,
        )
        if update_prefill_wrappers
        else body
      )
      return "SARVA_ALIAS_TITLE", new_attrs, new_body
    return None, attrs, body

  reason: str | None = None
  if title in sarva_title_aliases:
    reason = "SARVA_ALIAS_TITLE"
  elif title in wrong_titles:
    reason = "SARVA_WRONG_TITLE"
  elif title is None and it is None and fix_missing_sarva_title:
    reason = "SARVA_MISSING_TITLE"
  elif it_low in ("true", "plain") and fix_sarva_includetitle_true:
    reason = "SARVA_BAD_IT"
  elif title is None and it_low == "false" and fix_sarva_includetitle_false:
    reason = "SARVA_IT_FALSE"
  elif title is not None and title != sarva_title and overwrite_custom_sarva_titles:
    reason = "SARVA_CUSTOM_OVERWRITE"

  if reason is not None:
    target_collapsed = want_collapsed or ("collapsed" in cls_tokens and not is_idx)
    new_attrs = _set_attr(attrs, "title", sarva_title)
    new_attrs = _set_attr(new_attrs, "includetitle", None)
    new_attrs = _set_collapsed_class(new_attrs, target_collapsed)
    new_body = (
      _wrap_or_update_details_wrapper(
        body,
        sarva_title,
        nl,
        collapsed=target_collapsed,
        known_heading_titles=wrong_titles | {sarva_title},
      )
      if update_prefill_wrappers
      else body
    )
    return reason, new_attrs, new_body

  if title == sarva_title and it is None:
    if ensure_sarva_collapsed and ("collapsed" in cls_tokens) != want_collapsed:
      new_attrs = _set_collapsed_class(attrs, want_collapsed)
      new_body = (
        _wrap_or_update_details_wrapper(
          body,
          sarva_title,
          nl,
          collapsed=want_collapsed,
          known_heading_titles=wrong_titles | {sarva_title},
          wrap_plain_body=False,
        )
        if update_prefill_wrappers
        else body
      )
      return "SARVA_COLLAPSED_SYNC", new_attrs, new_body
    if update_prefill_wrappers:
      matched = _match_wrapper_details(body, known_heading_titles=wrong_titles)
      if matched is not None and matched[1] in wrong_titles:
        cur_collapsed = "collapsed" in cls_tokens
        new_body = _wrap_or_update_details_wrapper(
          body,
          sarva_title,
          nl,
          collapsed=cur_collapsed,
          known_heading_titles=wrong_titles,
          wrap_plain_body=False,
        )
        if new_body != body:
          return "SARVA_FIX_WRAPPER", list(attrs), new_body

  return None, attrs, body


def fix_include_titles_in_content(
  content: str,
  file_path: str = "",
  *,
  sarva_title: str = DEFAULT_SARVA_TITLE,
  vp_title: str = DEFAULT_VP_TITLE,
  sarva_segment: str = DEFAULT_SARVA_SEGMENT,
  vp_segment: str = DEFAULT_VP_SEGMENT,
  sarva_title_aliases: Collection[str] = DEFAULT_SARVA_TITLE_ALIASES,
  vp_title_aliases: Collection[str] = DEFAULT_VP_TITLE_ALIASES,
  extra_wrong_sarva_titles: Collection[str] = (),
  fix_sarva_includetitle_true: bool = True,
  fix_sarva_includetitle_false: bool = False,
  fix_missing_sarva_title: bool = True,
  overwrite_custom_sarva_titles: bool = False,
  collapse_sarva_leaves: bool = True,
  ensure_sarva_collapsed: bool = False,
  fix_missing_vp_title: bool = False,
  fix_nested_vp_missing_includetitle: bool = True,
  fix_nested_vp_includetitle_true: bool = False,
  unwrap_nested_vp_details: bool = True,
  update_prefill_wrappers: bool = True,
  url_filter: Callable[[str], bool] | str | None = None,
  require_balanced_tags: bool = True,
) -> tuple[str, list[IncludeTitleChange]]:
  """Normalize ``title``/``includeTitle``/``collapsed`` attrs & outer ``{Loading}`` wrappers in ``content``."""
  if "js_include" not in content:
    return content, []

  outer_divs = _outermost_js_include_divs(content)
  if not outer_divs:
    return content, []

  norm_path = str(file_path).replace("\\", "/")
  in_vp_file = bool(vp_segment and vp_segment in norm_path)
  in_sarva_file = bool(sarva_segment and sarva_segment in norm_path)

  edits: list[tuple[int, int, str]] = []
  changes: list[IncludeTitleChange] = []

  for a_start, _e_open, b_start, b_end, e_end, open_tok in outer_divs:
    attrs = _parse_open_tag_attrs(open_tok)
    url = _get_attr(attrs, "url") or ""
    if not url:
      continue
    if url_filter is not None:
      matched = url_filter(url) if callable(url_filter) else bool(regex.search(url_filter, url))
      if not matched:
        continue

    clean_url = url.split("#", 1)[0].split("?", 1)[0]
    body = content[b_start:b_end]
    reason: str | None = None
    new_attrs = attrs
    new_body = body

    if vp_segment and vp_segment in clean_url:
      if in_vp_file:
        reason, new_attrs, new_body = _fix_nested_vp_div(
          attrs,
          body,
          vp_title=vp_title,
          vp_title_aliases=vp_title_aliases,
          sarva_title=sarva_title,
          sarva_title_aliases=sarva_title_aliases,
          fix_nested_vp_missing_includetitle=fix_nested_vp_missing_includetitle,
          fix_nested_vp_includetitle_true=fix_nested_vp_includetitle_true,
          unwrap_nested_vp_details=unwrap_nested_vp_details,
          update_prefill_wrappers=update_prefill_wrappers,
        )
      else:
        reason, new_attrs, new_body = _fix_host_vp_div(
          attrs,
          body,
          vp_title=vp_title,
          vp_title_aliases=vp_title_aliases,
          sarva_title=sarva_title,
          sarva_title_aliases=sarva_title_aliases,
          fix_missing_vp_title=fix_missing_vp_title,
          update_prefill_wrappers=update_prefill_wrappers,
        )
    elif sarva_segment and sarva_segment in clean_url and not in_sarva_file:
      reason, new_attrs, new_body = _fix_sarva_div(
        attrs,
        body,
        clean_url,
        sarva_title=sarva_title,
        sarva_title_aliases=sarva_title_aliases,
        vp_title=vp_title,
        vp_title_aliases=vp_title_aliases,
        extra_wrong_sarva_titles=extra_wrong_sarva_titles,
        fix_sarva_includetitle_true=fix_sarva_includetitle_true,
        fix_sarva_includetitle_false=fix_sarva_includetitle_false,
        fix_missing_sarva_title=fix_missing_sarva_title,
        overwrite_custom_sarva_titles=overwrite_custom_sarva_titles,
        collapse_sarva_leaves=collapse_sarva_leaves,
        ensure_sarva_collapsed=ensure_sarva_collapsed,
        update_prefill_wrappers=update_prefill_wrappers,
      )

    if reason is None:
      continue

    new_open = _format_open_tag(new_attrs)
    new_block = new_open + new_body + "</div>"
    old_block = content[a_start:e_end]
    if new_block == old_block:
      continue
    if require_balanced_tags and check_tag_balance(old_block, file_path) is None and check_tag_balance(new_block, file_path) is not None:
      logging.warning(f"Skipping unbalanced include title edit ({reason}) in {file_path} for {url}")
      continue

    edits.append((a_start, e_end, new_block))
    changes.append(
      IncludeTitleChange(
        file_path=file_path,
        url=url,
        reason=reason,
        old_title=_get_attr(attrs, "title"),
        new_title=_get_attr(new_attrs, "title"),
        old_includetitle=_get_attr(attrs, "includetitle"),
        new_includetitle=_get_attr(new_attrs, "includetitle"),
      )
    )

  if not edits:
    return content, []

  out = content
  for start_pos, end_pos, replacement in sorted(edits, key=lambda x: x[0], reverse=True):
    out = out[:start_pos] + replacement + out[end_pos:]
  if require_balanced_tags and check_tag_balance(content, file_path) is None and check_tag_balance(out, file_path) is not None:
    logging.warning(f"Skipping file edit that unbalanced tags in {file_path}")
    return content, []
  return out, changes


def fix_include_titles(
  dir_paths: str | os.PathLike[str] | Iterable[str | os.PathLike[str]],
  *,
  dry_run: bool = False,
  file_name_filter: Callable[[str], bool] | str | None = None,
  propagate_transitive: bool = False,
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
  transitive_roots: Iterable[str | os.PathLike[str]] | None = None,
  exclude_dir_names=_DEFAULT_EXCLUDE_DIR_NAMES,
  exclude_dir_prefixes=_DEFAULT_EXCLUDE_DIR_PREFIXES,
  **kwargs,
) -> IncludeTitleFixReport:
  """Normalize ``js_include`` titles/wrappers across Markdown files in ``dir_paths``.

  Forwarded ``**kwargs`` customize :func:`fix_include_titles_in_content`. When
  ``propagate_transitive=True`` and ``dry_run=False``, refreshes host files that
  prefill any edited ``js_include`` target via :func:`surgical_prefill_transitive`.
  """
  if hasattr(dir_paths, "file_path"):
    dir_paths = dir_paths.file_path

  changed_files: list[str] = []
  all_changes: list[IncludeTitleChange] = []
  scanned = 0

  for fp in _iter_markdown_files(dir_paths, exclude_dir_names, exclude_dir_prefixes):
    if file_name_filter is not None:
      matched = file_name_filter(fp) if callable(file_name_filter) else bool(regex.search(file_name_filter, fp))
      if not matched:
        continue
    scanned += 1
    try:
      with open(fp, encoding="utf-8") as f:
        orig = f.read()
    except UnicodeDecodeError:
      logging.warning(f"Skipping non-UTF-8 file in fix_include_titles: {fp}")
      continue
    if "js_include" not in orig:
      continue

    updated, file_changes = fix_include_titles_in_content(orig, file_path=fp, **kwargs)
    if not file_changes or updated == orig:
      continue
    if not dry_run:
      with open(fp, "w", encoding="utf-8") as f:
        f.write(updated)
    changed_files.append(fp)
    all_changes.extend(file_changes)

  propagated: list[str] = []
  if propagate_transitive and changed_files and not dry_run:
    roots = (
      [os.fspath(p) for p in transitive_roots]
      if transitive_roots is not None
      else ([os.fspath(dir_paths)] if isinstance(dir_paths, (str, os.PathLike)) else [os.fspath(p) for p in dir_paths])
    )
    prop_set = surgical_prefill_transitive(
      dir_paths=roots,
      changed_file_paths=changed_files,
      hugo_base_dir=hugo_base_dir,
      dry_run=False,
    )
    propagated = sorted(prop_set)

  return IncludeTitleFixReport(
    changed_files=tuple(changed_files),
    changes=tuple(all_changes),
    propagated_files=tuple(propagated),
    scanned_files=scanned,
  )
