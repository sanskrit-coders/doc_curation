"""Fix Latin-titled or accent-split static mantra filenames and frontmatter across Vedic trees."""
from __future__ import annotations

import dataclasses
import logging
import pathlib
import re
import tomllib
from typing import Sequence

from doc_curation.md.content_processor.include import transformer
from doc_curation.sanskrit.accent.samhita_splitter import parse_top_level_details
from doc_curation.sanskrit.accent.us_converter import split_frontmatter_verbatim
from doc_curation_projects.veda.dedup.cascade import (
  UrlCallerIndex,
  _balanced_tags,
  _rewrite_url_across_callers,
)
from doc_curation_projects.veda.dedup.mulam_merger import DEFAULT_CALLER_ROOTS
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import format_static_title_and_stem

_TWO_PART_RE = re.compile(r"^(.*?)/(vishvAsa-prastutiH|sarvASh_TIkAH)/(.+)$")
_NUM_STEM_RE = re.compile(r"^(\d+)_(.+)\.md$")
_ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
_DEVA_CHAR_RE = re.compile(r"[\u0900-\u097f]")
_TITLE_LINE_RE = re.compile(r"""(?m)^title\s*([:=])\s*(.+?)\s*$""")


@dataclasses.dataclass
class _StaticUnit:
  static_root: pathlib.Path
  repo_name: str
  vp_fp: pathlib.Path | None = None
  sarva_fp: pathlib.Path | None = None
  other_fp: pathlib.Path | None = None

  def all_files(self) -> list[pathlib.Path]:
    return [p for p in (self.vp_fp, self.sarva_fp, self.other_fp) if p is not None]


def _parse_frontmatter_title(fm: str) -> str:
  """Extract decoded `title` from TOML (`+++`) or YAML (`---`) frontmatter."""
  stripped = fm.strip()
  if stripped.startswith("+++") and stripped.endswith("+++"):
    inner = stripped[3:-3].strip()
    try:
      data = tomllib.loads(inner)
      val = data.get("title", "")
      return str(val).strip() if val is not None else ""
    except tomllib.TOMLDecodeError:
      pass
  m = _TITLE_LINE_RE.search(fm)
  if not m:
    return ""
  raw_val = m.group(2).strip()
  if len(raw_val) >= 2 and raw_val[0] == raw_val[-1] and raw_val[0] in ('"', "'"):
    raw_val = raw_val[1:-1]
  return raw_val.strip()


def _rewrite_frontmatter_title(fm: str, new_title: str) -> str:
  """Set Devanāgarī `title` and `unicode_script` cleanly while preserving delimiter style."""
  escaped = new_title.replace("\\", "\\\\").replace('"', '\\"')
  stripped = fm.strip()
  is_yaml = stripped.startswith("---")
  sep = ":" if is_yaml else "="
  title_line = f'title {sep} "{escaped}"'
  if _TITLE_LINE_RE.search(fm):
    new_fm = _TITLE_LINE_RE.sub(lambda _: title_line, fm, count=1)
  else:
    lines = fm.splitlines()
    if lines:
      lines.insert(1, title_line)
      new_fm = "\n".join(lines) + ("\n" if fm.endswith("\n") else "")
    else:
      delim = "---" if is_yaml else "+++"
      new_fm = f"{delim}\n{title_line}\n{delim}\n"

  if "unicode_script" not in new_fm:
    script_line = f'unicode_script {sep} "devanagari"'
    lines = new_fm.splitlines()
    out_lines: list[str] = []
    inserted = False
    for line in lines:
      out_lines.append(line)
      if not inserted and _TITLE_LINE_RE.match(line.strip()):
        out_lines.append(script_line)
        inserted = True
    if not inserted and len(out_lines) >= 2:
      out_lines.insert(-1, script_line)
    new_fm = "\n".join(out_lines) + ("\n" if new_fm.endswith("\n") else "")
  return new_fm


def _strip_includes_and_tags(text: str) -> str:
  spans = [(a, e) for a, _, _, _, e, _ in transformer.find_js_include_divs(text)]
  cleaned = text
  for a, e in reversed(spans):
    cleaned = cleaned[:a] + "\n" + cleaned[e:]
  return re.sub(r"</?(?:div|details|summary)[^>]*>", " ", cleaned).strip()


def _extract_vp_for_title(vp_body: str | None, sarva_body: str | None) -> str:
  """Select clean Sanskrit mantra text for title/slug extraction, ignoring avatārikā prose."""
  if vp_body:
    for _, _, ttl, inner in parse_top_level_details(vp_body):
      if ttl.strip().startswith("विश्वास-प्रस्तुतिः"):
        cand = _strip_includes_and_tags(inner)
        if _DEVA_CHAR_RE.search(cand):
          return cand
    # Avoid mixing English avatārikā blocks into standalone combined files.
    stripped = vp_body
    for a, b, ttl, _ in reversed(parse_top_level_details(vp_body)):
      if "अवतारिका" in ttl or ttl.strip() == "सर्वाष् टीकाः":
        stripped = stripped[:a] + "\n" + stripped[b:]
    cand = _strip_includes_and_tags(stripped)
    if _DEVA_CHAR_RE.search(cand):
      return cand
    # Fall back to text inside an included block if the outer VP is a pure wrapper.
    cand_full = re.sub(r"</?(?:div|details|summary)[^>]*>", " ", vp_body).strip()
    if _DEVA_CHAR_RE.search(cand_full):
      return cand_full

  if sarva_body:
    for _, _, ttl, inner in parse_top_level_details(sarva_body):
      if ttl.strip().startswith("मूलम्"):
        cand = _strip_includes_and_tags(inner)
        if _DEVA_CHAR_RE.search(cand):
          return cand
  return ""


def _resolve_non_colliding_names(
  paths: Sequence[pathlib.Path],
  num_prefix: str,
  stem: str,
) -> dict[pathlib.Path, pathlib.Path]:
  """Choose one shared `new_filename` for sibling paths without colliding with existing files."""
  suffix_idx = 1
  while True:
    cand_name = f"{num_prefix}_{stem}.md" if suffix_idx == 1 else f"{num_prefix}_{stem}_{suffix_idx}.md"
    mapping = {fp: fp.with_name(cand_name) for fp in paths}
    if all((dest == src or not dest.exists()) for src, dest in mapping.items()):
      return mapping
    suffix_idx += 1


def _collect_units(static_roots: Sequence[pathlib.Path]) -> list[_StaticUnit]:
  by_key: dict[tuple[pathlib.Path, str, str], _StaticUnit] = {}
  singles: list[_StaticUnit] = []
  for root in static_roots:
    if not root.exists():
      continue
    repo_name = root.parent.name
    for fp in sorted(root.rglob("*.md")):
      if not fp.is_file() or fp.name in ("_index.md", "file_list.md"):
        continue
      rel = fp.relative_to(root).as_posix()
      m = _TWO_PART_RE.match(rel)
      if m:
        prefix, part, subrel = m.groups()
        key = (root, prefix, subrel)
        unit = by_key.setdefault(key, _StaticUnit(static_root=root, repo_name=repo_name))
        if part == "vishvAsa-prastutiH":
          unit.vp_fp = fp
        else:
          unit.sarva_fp = fp
      else:
        singles.append(_StaticUnit(static_root=root, repo_name=repo_name, other_fp=fp))
  return list(by_key.values()) + singles


def fix_static_titles_and_accent_filenames(
  static_roots: Sequence[pathlib.Path],
  caller_roots: Sequence[pathlib.Path] = DEFAULT_CALLER_ROOTS,
  *,
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
  dry_run: bool = False,
) -> dict:
  """Normalize Latin-titled static files to Devanāgarī titles and accent-ignoring slugs."""
  units = _collect_units(static_roots)
  url_index = UrlCallerIndex(caller_roots)

  stats = {
    "checked_units": len(units),
    "titles_fixed": 0,
    "files_renamed": 0,
    "callers_updated": 0,
    "skipped_no_deva": 0,
    "renames": [],
    "title_changes": [],
  }
  touched_callers: set[pathlib.Path] = set()

  for unit in units:
    files = unit.all_files()
    parsed: dict[pathlib.Path, tuple[str, str, str]] = {}
    has_latin_title = False
    for fp in files:
      txt = fp.read_text(encoding="utf-8", errors="ignore")
      fm, body = split_frontmatter_verbatim(txt)
      title = _parse_frontmatter_title(fm)
      parsed[fp] = (fm, body, title)
      if title and _ASCII_LETTER_RE.search(title):
        has_latin_title = True

    if not has_latin_title:
      continue

    primary_fp = unit.vp_fp or unit.other_fp or unit.sarva_fp
    assert primary_fp is not None
    vp_body = parsed[unit.vp_fp][1] if unit.vp_fp else (parsed[unit.other_fp][1] if unit.other_fp else None)
    sarva_body = parsed[unit.sarva_fp][1] if unit.sarva_fp else None
    vp_source = _extract_vp_for_title(vp_body, sarva_body)
    if not vp_source:
      stats["skipped_no_deva"] += 1
      continue

    m_fn = _NUM_STEM_RE.match(primary_fp.name)
    num_prefix = m_fn.group(1) if m_fn else ""
    fn_stem = m_fn.group(2) if m_fn else primary_fp.stem
    new_title, new_stem = format_static_title_and_stem(vp_source, num_prefix=num_prefix)

    # Rename generated files whose old slug matched their Latin title (e.g. accent-split `pra_ti_tvA`).
    should_rename = bool(
      m_fn is not None
      and new_stem != fn_stem
      and any(parsed[fp][2] == fn_stem for fp in files)
    )

    dest_map = _resolve_non_colliding_names(files, num_prefix, new_stem) if should_rename else {fp: fp for fp in files}

    for fp in files:
      fm, body, old_title = parsed[fp]
      dest_fp = dest_map[fp]
      old_url = f"/{unit.repo_name}/{fp.relative_to(unit.static_root).as_posix()}"
      new_url = f"/{unit.repo_name}/{dest_fp.relative_to(unit.static_root).as_posix()}"

      title_needs_fix = bool(old_title and _ASCII_LETTER_RE.search(old_title))
      if title_needs_fix:
        # Re-read fresh text from disk so earlier caller rewrites inside this file are preserved.
        cur_txt = fp.read_text(encoding="utf-8", errors="ignore")
        cur_fm, cur_body = split_frontmatter_verbatim(cur_txt)
        new_fm = _rewrite_frontmatter_title(cur_fm, new_title)
        new_text = f"{new_fm.rstrip()}\n\n{cur_body.lstrip()}" if new_fm else cur_body
        if not _balanced_tags(new_text):
          raise ValueError(f"Unbalanced tags after title update in {fp}")
        stats["titles_fixed"] += 1
        stats["title_changes"].append((old_url, old_title, new_title))
        if not dry_run:
          fp.write_text(new_text, encoding="utf-8")

      # Record callers referencing this static target before possible rename.
      touched_callers.update(url_index.files_for(old_url))

      if dest_fp != fp:
        stats["files_renamed"] += 1
        stats["renames"].append((old_url, new_url))
        if not dry_run:
          fp.rename(dest_fp)
          if fp in touched_callers:
            touched_callers.discard(fp)
            touched_callers.add(dest_fp)
          for caller_set in url_index.by_url.values():
            if fp in caller_set:
              caller_set.discard(fp)
              caller_set.add(dest_fp)
        ch = _rewrite_url_across_callers(old_url, new_url, None, caller_roots, dry_run=dry_run, url_index=url_index)
        for p_str in ch:
          touched_callers.add(pathlib.Path(p_str))

  stats["callers_updated"] = len(touched_callers)
  if not dry_run and touched_callers:
    changed_list: list[str] = []
    for c_fp in sorted(touched_callers):
      if not c_fp.is_file():
        continue
      txt = c_fp.read_text(encoding="utf-8", errors="ignore")
      if "js_include" not in txt:
        continue
      new_txt, n = transformer.surgical_prefill_content(txt, str(c_fp), hugo_base_dir=hugo_base_dir, only_if_prefilled=True)
      if n and new_txt != txt and _balanced_tags(new_txt):
        c_fp.write_text(new_txt, encoding="utf-8")
      changed_list.append(str(c_fp))
    transformer.surgical_prefill_transitive(
      caller_roots, changed_list, hugo_base_dir=hugo_base_dir,
      skip_sources_with_empty_includes=False, only_if_prefilled=True, dry_run=False,
    )

  return stats


if __name__ == "__main__":
  import argparse

  logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
  parser = argparse.ArgumentParser(description="Fix Latin titles and accent-split filenames in Vedic static trees.")
  parser.add_argument(
    "static_roots",
    nargs="*",
    default=[
      "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static",
      "/home/vvasuki/gitland/vishvAsa/vedAH/static",
    ],
  )
  parser.add_argument("--dry-run", action="store_true")
  args = parser.parse_args()
  res = fix_static_titles_and_accent_filenames(
    [pathlib.Path(p) for p in args.static_roots],
    dry_run=args.dry_run,
  )
  print({k: v for k, v in res.items() if k not in ("renames", "title_changes")})
  for pair in res["renames"][:20]:
    print("RENAME:", pair[0], "->", pair[1])
  for chg in res["title_changes"][:20]:
    print("TITLE:", chg[0], repr(chg[1]), "->", repr(chg[2]))
