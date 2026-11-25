"""Frontmatter- and ``js_include``-aware Vedic accent conversion to US (``᳓`` / ``᳙``) notation."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable, Sequence

from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.accent.reconciler import find_js_include_spans
from doc_curation.sanskrit.accent.samhita_splitter import (
  CLASSICAL_VEDIC_ACCENTS,
  dependent_to_us_preserving,
)

DEFAULT_US_PAUSES = r"[।॥\n,;]+"
DEFAULT_SKIP_PATTERN = r"\+\+\+\((.+?)\)\+\+\+"

_FRONTMATTER_RE = re.compile(
  r"\A\ufeff?(?:\+\+\+[ \t]*\r?\n(?:.*?\r?\n)?\+\+\+|---[ \t]*\r?\n(?:.*?\r?\n)?---)[ \t]*(?:\r?\n|$)",
  flags=re.DOTALL,
)

# Protected inline/block chunks outside top-level js_include divs: fenced code,
# raw script/style blocks, inline code, HTML tags, blank-line boundaries, and Markdown headings.
_PROTECTED_OR_BREAK_RE = re.compile(
  r"(?s:^[ \t]*(?:```|~~~)[^\n]*\r?\n.*?^[ \t]*(?:```|~~~)[ \t]*$)"
  r"|(?is:<script\b[^>]*>.*?</script>)"
  r"|(?is:<style\b[^>]*>.*?</style>)"
  r"|`[^`\r\n]+`"
  r"|<[^>]+>"
  r"|\r?\n(?:[ \t]*\r?\n)+"
  r"|^[ \t]*#{1,6}[ \t]+[^\r\n]*",
  flags=re.MULTILINE,
)

_WHITESPACE_WRAP_RE = re.compile(r"^(\s*)(.*?)(\s*)$", flags=re.DOTALL)
_HEADING_PREFIX_RE = re.compile(r"^([ \t]*#{1,6}[ \t]+)(.*)$")


def split_frontmatter_verbatim(markdown_text: str) -> tuple[str, str]:
  """Split leading Hugo TOML (``+++``) or YAML (``---``) frontmatter without altering its bytes."""
  match = _FRONTMATTER_RE.match(markdown_text)
  if not match:
    return "", markdown_text
  return match.group(1 if match.lastindex else 0), markdown_text[match.end():]


def _has_classical_accents(text: str) -> bool:
  return any(mark in text for mark in CLASSICAL_VEDIC_ACCENTS)


def _convert_core_text(
  text: str,
  *,
  pauses: str,
  skip_pattern: str,
  preserve_existing_us: bool,
) -> str:
  if not _has_classical_accents(text):
    return text
  match = _WHITESPACE_WRAP_RE.match(text)
  assert match is not None
  lead, core, trail = match.groups()
  if not core or not _has_classical_accents(core):
    return text
  if preserve_existing_us:
    converted = dependent_to_us_preserving(core, pauses=pauses, skip_pattern=skip_pattern)
  else:
    converted = accent.to_US_accents(core, pauses=pauses, skip_pattern=skip_pattern)
  return f"{lead}{converted}{trail}"


def _convert_plain_chunk(
  chunk: str,
  *,
  pauses: str,
  skip_pattern: str,
  preserve_existing_us: bool,
  newlines_are_pauses: bool,
) -> str:
  if not _has_classical_accents(chunk):
    return chunk
  if not newlines_are_pauses:
    return _convert_core_text(
      chunk,
      pauses=pauses,
      skip_pattern=skip_pattern,
      preserve_existing_us=preserve_existing_us,
    )

  out_lines: list[str] = []
  for line in chunk.splitlines(keepends=True):
    line_body = line.rstrip("\r\n")
    line_end = line[len(line_body):]
    converted = _convert_core_text(
      line_body,
      pauses=pauses,
      skip_pattern=skip_pattern,
      preserve_existing_us=preserve_existing_us,
    )
    out_lines.append(f"{converted}{line_end}")
  return "".join(out_lines)


def _convert_non_include_segment(
  segment: str,
  *,
  pauses: str,
  skip_pattern: str,
  preserve_existing_us: bool,
  newlines_are_pauses: bool,
) -> str:
  if not _has_classical_accents(segment):
    return segment

  parts = _PROTECTED_OR_BREAK_RE.split(segment)
  tokens = _PROTECTED_OR_BREAK_RE.findall(segment)
  out: list[str] = []
  for idx, plain in enumerate(parts):
    if plain:
      out.append(
        _convert_plain_chunk(
          plain,
          pauses=pauses,
          skip_pattern=skip_pattern,
          preserve_existing_us=preserve_existing_us,
          newlines_are_pauses=newlines_are_pauses,
        )
      )
    if idx < len(tokens):
      tok = tokens[idx]
      heading_match = _HEADING_PREFIX_RE.match(tok)
      if heading_match:
        prefix, rest = heading_match.groups()
        converted = _convert_core_text(
          rest,
          pauses=pauses,
          skip_pattern=skip_pattern,
          preserve_existing_us=preserve_existing_us,
        )
        tok = f"{prefix}{converted}"
      out.append(tok)
  return "".join(out)


def to_us_accents_markdown(
  markdown_text: str,
  *,
  pauses: str = DEFAULT_US_PAUSES,
  preserve_existing_us: bool = False,
  skip_pattern: str = DEFAULT_SKIP_PATTERN,
) -> str:
  """Convert dependent Vedic accents in Markdown to US notation while preserving frontmatter and ``js_include`` divs."""
  frontmatter, body = split_frontmatter_verbatim(markdown_text)
  if not _has_classical_accents(body):
    return markdown_text

  newlines_are_pauses = bool(re.compile(pauses).search("\n"))
  include_spans = find_js_include_spans(body)
  if not include_spans:
    converted_body = _convert_non_include_segment(
      body,
      pauses=pauses,
      skip_pattern=skip_pattern,
      preserve_existing_us=preserve_existing_us,
      newlines_are_pauses=newlines_are_pauses,
    )
    return f"{frontmatter}{converted_body}"

  out: list[str] = [frontmatter]
  cursor = 0
  for start, end in include_spans:
    if start > cursor:
      out.append(
        _convert_non_include_segment(
          body[cursor:start],
          pauses=pauses,
          skip_pattern=skip_pattern,
          preserve_existing_us=preserve_existing_us,
          newlines_are_pauses=newlines_are_pauses,
        )
      )
    out.append(body[start:end])
    cursor = end
  if cursor < len(body):
    out.append(
      _convert_non_include_segment(
        body[cursor:],
        pauses=pauses,
        skip_pattern=skip_pattern,
        preserve_existing_us=preserve_existing_us,
        newlines_are_pauses=newlines_are_pauses,
      )
    )
  return "".join(out)


def convert_file_to_us_accents(
  file_path: str | Path,
  *,
  pauses: str = DEFAULT_US_PAUSES,
  preserve_existing_us: bool = False,
  skip_pattern: str = DEFAULT_SKIP_PATTERN,
  dry_run: bool = False,
) -> bool:
  """Convert a single Markdown file in place to US accent notation; return whether its content changed."""
  path = Path(file_path)
  original = path.read_text(encoding="utf-8")
  converted = to_us_accents_markdown(
    original,
    pauses=pauses,
    preserve_existing_us=preserve_existing_us,
    skip_pattern=skip_pattern,
  )
  if converted == original:
    return False
  if not dry_run:
    path.write_text(converted, encoding="utf-8")
  return True


def convert_tree_to_us_accents(
  dir_path: str | Path,
  *,
  pauses: str = DEFAULT_US_PAUSES,
  preserve_existing_us: bool = False,
  skip_pattern: str = DEFAULT_SKIP_PATTERN,
  file_pattern: str = "**/*.md",
  file_name_filter: Callable[[str], bool] | None = None,
  refresh_host_dirs: Sequence[str | Path] = (),
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
  exclude_path_substrings: Sequence[str] = (),
  dry_run: bool = False,
) -> dict[str, list[str]]:
  """Bulk-convert Markdown files under ``dir_path`` to US notation and optionally refresh transitive ``js_include`` hosts.

  When ``dry_run=True``, ``changed_files`` is populated without writing files; host refreshes
  only execute when ``dry_run=False`` so updated source contents are present on disk.
  """
  from doc_curation.md.library import apply_function

  results = apply_function(
    convert_file_to_us_accents,
    dir_path=str(dir_path),
    file_pattern=file_pattern,
    file_name_filter=file_name_filter,
    pauses=pauses,
    preserve_existing_us=preserve_existing_us,
    skip_pattern=skip_pattern,
    dry_run=dry_run,
  )
  changed_files = sorted(str(path) for path, changed in results.items() if changed)
  logging.info("Converted %d file(s) under %s to US accents", len(changed_files), dir_path)

  updated_hosts: list[str] = []
  if changed_files and refresh_host_dirs and not dry_run:
    from doc_curation.md.content_processor.include.transformer import surgical_prefill_transitive

    updated = surgical_prefill_transitive(
      [str(p) for p in refresh_host_dirs],
      set(changed_files),
      hugo_base_dir=hugo_base_dir,
      exclude_path_substrings=tuple(exclude_path_substrings),
      dry_run=dry_run,
    )
    updated_hosts = sorted(updated)
  return {"changed_files": changed_files, "updated_hosts": updated_hosts}
