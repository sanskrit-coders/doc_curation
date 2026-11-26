"""Fix Latin-titled or accent-split static mantra filenames and frontmatter across Vedic trees."""
from __future__ import annotations

import dataclasses
import logging
import pathlib
import re
import shutil
import subprocess
import tomllib
from typing import Sequence

from doc_curation.md.content_processor.include import transformer
from doc_curation.md.content_processor.include.seeker import resolve_include_file_path
from doc_curation.sanskrit.accent.reconciler import (
  format_suggested_vp_summary,
  parse_padapatha_header,
)
from doc_curation.sanskrit.accent.samhita_splitter import parse_top_level_details
from doc_curation.sanskrit.accent.us_converter import split_frontmatter_verbatim
from doc_curation_projects.veda.dedup.block_parser import format_vp_summary_with_kind
from doc_curation_projects.veda.dedup.cascade import (
  UrlCallerIndex,
  _balanced_tags,
  _rewrite_url_across_callers,
)
from doc_curation_projects.veda.dedup.mulam_merger import DEFAULT_CALLER_ROOTS
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import format_static_title_and_stem
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.tika_merger import format_details_block

_TWO_PART_RE = re.compile(r"^(.*?)/(vishvAsa-prastutiH|sarvASh_TIkAH)/(.+)$")
_VEDA_UNIT_SUBTREE_RE = re.compile(
  r"(?:^|/)(Rk|yajuH|brAhmaNam)/(vishvAsa-prastutiH|sarvASh_TIkAH|sarva-prastutiH)/"
)
_UNIT_DIR_TO_KIND = {"Rk": "rk", "yajuH": "yajuh", "brAhmaNam": "brahmana"}
_MD_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
_SUG_IN_TEXT_RE = re.compile(r"\[\[[^|\]]+\|[^\]]+\]\]")
_URL_ATTR_RE = re.compile(r"""url=(["'])([^"']+)\1""")
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


def _collect_vishvasa_scan_roots(
  all_vishvasa_root: pathlib.Path,
  static_roots: Sequence[pathlib.Path],
) -> list[pathlib.Path]:
  """Collect all ``<repo>/{content,static}`` trees under ``all_vishvasa_root`` plus explicit roots."""
  roots: set[pathlib.Path] = set()
  if all_vishvasa_root.exists():
    for repo_dir in all_vishvasa_root.iterdir():
      if not repo_dir.is_dir() or repo_dir.name.startswith("."):
        continue
      for sub in ("content", "static"):
        cand = repo_dir / sub
        if cand.is_dir():
          roots.add(cand.resolve())
  for sr in static_roots:
    if sr.exists():
      roots.add(sr.resolve())
    cand_c = sr.parent / "content"
    if cand_c.is_dir():
      roots.add(cand_c.resolve())
  return sorted(roots)


def _resolve_ref_target(
  raw_url: str,
  caller_fp: pathlib.Path,
  hugo_base_dir: str,
  url_to_target: dict[str, pathlib.Path] | None = None,
) -> pathlib.Path | None:
  """Resolve an include or Markdown link target to an existing static file path when possible."""
  clean_u = raw_url.split("#", 1)[0].split("?", 1)[0].strip()
  if not clean_u or clean_u.startswith(("http://", "https://", "mailto:")):
    return None
  if url_to_target is not None and clean_u.startswith("/"):
    direct = url_to_target.get(clean_u)
    if direct is not None:
      return direct
    # Strip duplicate slashes if present without invoking filesystem resolution.
    norm_u = "/" + "/".join(p for p in clean_u.split("/") if p)
    return url_to_target.get(norm_u)
  resolved = resolve_include_file_path(
    url=clean_u,
    hugo_base_dir=hugo_base_dir,
    current_file_path=str(caller_fp),
  )
  if resolved:
    p = pathlib.Path(resolved)
    if p.is_file():
      return p.resolve()
  if not clean_u.startswith("/"):
    rel_p = caller_fp.parent / clean_u
    if rel_p.is_file():
      return rel_p.resolve()
  return None


def _scan_static_references(
  scan_roots: Sequence[pathlib.Path],
  target_set: set[pathlib.Path],
  hugo_base_dir: str,
  target_repo_names: Sequence[str],
  url_to_target: dict[str, pathlib.Path] | None = None,
) -> tuple[dict[pathlib.Path, list[tuple[pathlib.Path, str, str]]], dict[pathlib.Path, set[pathlib.Path]]]:
  """Scan all candidate Markdown files once to map every ``target_fp`` to its includes and Markdown links."""
  include_refs: dict[pathlib.Path, list[tuple[pathlib.Path, str, str]]] = {}
  link_refs: dict[pathlib.Path, set[pathlib.Path]] = {}
  if not scan_roots or not target_set:
    return include_refs, link_refs

  repo_name_set = {r for r in target_repo_names if r}
  same_repo_roots = [r for r in scan_roots if r.parent.name in repo_name_set]
  ext_repo_roots = [r for r in scan_roots if r.parent.name not in repo_name_set]

  rg_bin = shutil.which("rg")
  cand_files: list[pathlib.Path] = []
  if rg_bin:
    if same_repo_roots:
      proc = subprocess.run(
        [rg_bin, "-l", r"(?:js_include|\]\()", "-g", "*.md", *[str(r) for r in same_repo_roots]],
        capture_output=True, text=True, check=False,
      )
      if proc.returncode in (0, 1):
        cand_files.extend(pathlib.Path(line) for line in proc.stdout.splitlines() if line.strip())
    if ext_repo_roots and repo_name_set:
      repo_alt = "|".join(re.escape(r) for r in sorted(repo_name_set))
      proc = subprocess.run(
        [rg_bin, "-l", repo_alt, "-g", "*.md", *[str(r) for r in ext_repo_roots]],
        capture_output=True, text=True, check=False,
      )
      if proc.returncode in (0, 1):
        cand_files.extend(pathlib.Path(line) for line in proc.stdout.splitlines() if line.strip())
  if not rg_bin:
    cand_files = [
      fp for r in scan_roots if r.exists() for fp in r.rglob("*.md") if fp.is_file()
    ]

  for fp in sorted(set(cand_files)):
    if not fp.is_file():
      continue
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    if "js_include" in txt:
      for _, _, _, _, _, open_tag in transformer.find_js_include_divs(txt):
        m_u = _URL_ATTR_RE.search(open_tag)
        if not m_u:
          continue
        tgt = _resolve_ref_target(m_u.group(2), fp, hugo_base_dir, url_to_target)
        if tgt is not None and tgt in target_set:
          include_refs.setdefault(tgt, []).append((fp.resolve(), m_u.group(2), open_tag))
    if "](" in txt:
      for m_l in _MD_LINK_RE.finditer(txt):
        tgt = _resolve_ref_target(m_l.group(1), fp, hugo_base_dir, url_to_target)
        if tgt is not None and tgt in target_set:
          link_refs.setdefault(tgt, set()).add(fp.resolve())
  return include_refs, link_refs


def _extract_forwarding_include_url(file_text: str) -> str | None:
  """Return target URL when a static file's entire body is a single forwarding ``js_include``."""
  _, body = split_frontmatter_verbatim(file_text)
  stripped = body.strip()
  if not stripped or "js_include" not in stripped:
    return None
  divs = transformer.find_js_include_divs(stripped)
  if len(divs) == 1 and divs[0][0] == 0 and divs[0][4] == len(stripped):
    m_u = _URL_ATTR_RE.search(divs[0][5])
    if m_u:
      return m_u.group(2)
  return None


def _find_companion_vyat_counts(
  caller_text: str,
  after_pos: int,
  caller_fp: pathlib.Path,
  vp_static_fp: pathlib.Path,
  hugo_base_dir: str,
) -> tuple[int, int] | None:
  """Locate companion ``पद-पाठः (यान्त्रिकः - N/P व्यत्यस्त-स्वराः)`` for an inlined ``[[|]]`` VP block."""
  tail = caller_text[after_pos:]
  # Bound search to the current mantra cluster (before next ## heading or next विश्वास-प्रस्तुतिः / VP include).
  bound = len(tail)
  for rx in (
    r"(?m)^##+\s",
    r"<details(?:\s+open)?><summary>विश्वास-प्रस्तुतिः",
    r'/vishvAsa-prastutiH/',
  ):
    m_b = re.search(rx, tail)
    if m_b and m_b.start() < bound:
      bound = m_b.start()
  cluster_tail = tail[:bound]

  candidate_texts: list[str] = []
  for _, _, ttl, body in parse_top_level_details(cluster_tail):
    if ttl.strip() == "सर्वाष् टीकाः":
      candidate_texts.append(body)
  for _, _, _, _, _, otok in transformer.find_js_include_divs(cluster_tail):
    m_u = _URL_ATTR_RE.search(otok)
    if m_u and "/sarvASh_TIkAH/" in m_u.group(2):
      sarva_p = _resolve_ref_target(m_u.group(2), caller_fp, hugo_base_dir)
      if sarva_p is not None and sarva_p.is_file():
        candidate_texts.append(sarva_p.read_text(encoding="utf-8", errors="ignore"))

  sib_sarva = pathlib.Path(str(vp_static_fp).replace("/vishvAsa-prastutiH/", "/sarvASh_TIkAH/"))
  if sib_sarva != vp_static_fp and sib_sarva.is_file():
    candidate_texts.append(sib_sarva.read_text(encoding="utf-8", errors="ignore"))

  for cand in candidate_texts:
    best_counts: tuple[int, int] | None = None
    for _, _, ttl, _ in parse_top_level_details(cand):
      s = ttl.strip()
      if not s.startswith("पद-पाठः (यान्त्रिकः"):
        continue
      qual, n_v, p_t = parse_padapatha_header(s)
      if n_v > 0 and p_t:
        if qual is None:
          return n_v, p_t
        if best_counts is None:
          best_counts = (n_v, p_t)
    if best_counts is not None:
      return best_counts
  return None


def _normalize_inlined_sarva_tika(rep_html: str) -> str:
  """Ensure inlined ``सर्वाष् टीकाः`` is collapsed and wraps bare mūlam text cleanly in ``<details>``."""
  rep = rep_html.replace("\r\n", "\n").strip()
  dets = parse_top_level_details(rep)
  if len(dets) != 1 or dets[0][2].strip() != "सर्वाष् टीकाः":
    return rep
  inner = dets[0][3].strip()
  inner_dets = parse_top_level_details(inner)
  if not inner_dets:
    if inner:
      inner = format_details_block("मूलम्", inner)
  elif inner_dets[0][0] > 0:
    lead = inner[: inner_dets[0][0]].strip()
    if lead:
      inner = format_details_block("मूलम्", lead) + "\n\n" + inner[inner_dets[0][0] :].lstrip()
  sep = "\n" if inner.startswith("<details") else "\n\n"
  return f"<details><summary>सर्वाष् टीकाः</summary>{sep}{inner}\n</details>"


def _normalize_inlined_sarva_prastuti(rep_html: str, unit_kind: str) -> str:
  """Keep inner blocks unwrapped and qualify inner ``विश्वास-प्रस्तुतिः`` summaries inside expanded ``sarva-prastutiH/``."""
  rep = rep_html.replace("\r\n", "\n").strip()
  out_parts: list[str] = []
  cursor = 0
  for s_pos, e_pos, ttl, body in parse_top_level_details(rep):
    if s_pos > cursor:
      out_parts.append(rep[cursor:s_pos])
    ttl_s = ttl.strip()
    if ttl_s.startswith("विश्वास-प्रस्तुतिः"):
      new_sum = format_vp_summary_with_kind(ttl_s, unit_kind)
      out_parts.append(format_details_block(new_sum, body, is_open=True))
    elif ttl_s == "सर्वाष् टीकाः":
      out_parts.append(_normalize_inlined_sarva_tika(rep[s_pos:e_pos]))
    else:
      out_parts.append(rep[s_pos:e_pos])
    cursor = e_pos
  if cursor < len(rep):
    out_parts.append(rep[cursor:])
  return "".join(out_parts).strip()


def _unlink_and_prune_empty_dirs(fp: pathlib.Path, stop_root: pathlib.Path) -> None:
  """Delete ``fp`` and remove any emptied intermediate directories up to ``stop_root``."""
  if fp.is_file():
    fp.unlink()
  cur = fp.parent
  stop_resolved = stop_root.resolve()
  while cur != stop_resolved and stop_resolved in cur.parents:
    if cur.name in ("vishvAsa-prastutiH", "sarvASh_TIkAH", "sarva-prastutiH", "Rk", "yajuH", "brAhmaNam"):
      break
    try:
      cur.rmdir()
    except OSError:
      break
    cur = cur.parent


def _render_single_inlined_div(
  static_fp: pathlib.Path,
  caller_fp: pathlib.Path,
  caller_text: str,
  div_span: tuple[int, int, int, int, int, str],
  subtree: str,
  unit_kind: str,
  hugo_base_dir: str,
) -> str:
  """Render the replacement Markdown for one matched ``js_include`` span inside ``caller_text``."""
  s_open, _, b_start, b_end, e_close, open_tag = div_span
  snippet = caller_text[s_open:e_close]

  if subtree == "vishvAsa-prastutiH":
    old_sum = ""
    m_title = re.search(r"""title=(["'])([^"']*)\1""", open_tag)
    if m_title:
      old_sum = m_title.group(2).strip()
    prefill_dets = parse_top_level_details(caller_text[b_start:b_end].strip())
    if prefill_dets and prefill_dets[0][2].strip().startswith("विश्वास-प्रस्तुतिः"):
      pref_sum = re.sub(r"\s*(?:\.\.\.|…)\{Loading\}(?:\.\.\.|…)\s*$", "", prefill_dets[0][2].strip()).strip()
      if "(" in pref_sum and "(" not in old_sum:
        old_sum = pref_sum
    base_vp_sum = old_sum if old_sum.startswith("विश्वास-प्रस्तुतिः") else "विश्वास-प्रस्तुतिः"
    deinc, _ = transformer.deinclude_content(
      snippet,
      str(caller_fp),
      prefill=True,
      title="__VP_PLACEHOLDER__",
      preserve_open_state=False,
      hugo_base_dir=hugo_base_dir,
    )
    deinc = deinc.replace("\r\n", "\n").strip()
    if _SUG_IN_TEXT_RE.search(deinc) and not re.search(r"\(\d+/\d+\s*व्यत्यस्त-स्वराः\)", base_vp_sum):
      counts = _find_companion_vyat_counts(caller_text, e_close, caller_fp, static_fp, hugo_base_dir)
      if counts is not None:
        base_vp_sum = format_suggested_vp_summary(base_vp_sum, counts[0], counts[1])
    final_sum = format_vp_summary_with_kind(base_vp_sum, unit_kind)
    return deinc.replace("<summary>__VP_PLACEHOLDER__</summary>", f"<summary>{final_sum}</summary>", 1)
  if subtree == "sarvASh_TIkAH":
    deinc, _ = transformer.deinclude_content(
      snippet,
      str(caller_fp),
      prefill=True,
      title="सर्वाष् टीकाः",
      preserve_open_state=True,
      hugo_base_dir=hugo_base_dir,
    )
    normalized = _normalize_inlined_sarva_tika(deinc)
    from doc_curation_projects.veda.dedup import commentary_merger

    m_url = re.search(r'\burl="([^"]+)"', snippet)
    if m_url:
      normalized = commentary_merger.qualify_cross_corpus_sarva_tika(
        normalized,
        src_url=m_url.group(1),
        caller_fp=caller_fp,
      )
    return normalized
  deinc, _ = transformer.deinclude_content(
    snippet,
    str(caller_fp),
    prefill=True,
    title="",
    preserve_open_state=True,
    hugo_base_dir=hugo_base_dir,
  )
  return _normalize_inlined_sarva_prastuti(deinc, unit_kind)


def inline_single_caller_veda_static(
  static_roots: Sequence[pathlib.Path] = (pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static"),),
  all_vishvasa_root: pathlib.Path | None = None,
  *,
  include_sutra: bool = False,
  prune_zero_caller: bool = True,
  hugo_base_dir: str | pathlib.Path = "/home/vvasuki/gitland/vishvAsa",
  dry_run: bool = False,
) -> dict:
  """Inline all single-caller non-sūtra Vedic static files and delete unreferenced dead static files.

  Qualifies every inlined ``विश्वास-प्रस्तुतिः`` block with ``- ऋक्`` / ``- यजुः`` / ``- ब्राह्मणम्``
  before any trailing ``(यन्त्र-स्वरः)`` or ``(N/P व्यत्यस्त-स्वराः)`` tag, rewrites forwarding
  ``vishvAsa-prastutiH/`` wrappers directly to their shared target, ensures inlined
  ``सर्वाष् टीकाः`` blocks are collapsed, and updates ``caller_roots`` cleanly.
  """
  hugo_base = pathlib.Path(hugo_base_dir).resolve()
  scan_base = all_vishvasa_root.resolve() if all_vishvasa_root is not None else hugo_base
  hugo_base_str = str(hugo_base)

  targets: dict[pathlib.Path, tuple[pathlib.Path, str, str, str]] = {}
  url_to_target: dict[str, pathlib.Path] = {}
  repo_names: set[str] = set()
  for sr in static_roots:
    if not sr.exists():
      continue
    sr_res = sr.resolve()
    rname = sr_res.parent.name
    repo_names.add(rname)
    for fp in sorted(sr_res.rglob("*.md")):
      if not fp.is_file() or fp.name in ("_index.md", "file_list.md"):
        continue
      rel = fp.relative_to(sr_res).as_posix()
      if not include_sutra and ("/sUtram/" in f"/{rel}" or rel.startswith("sUtram/")):
        continue
      m_sub = _VEDA_UNIT_SUBTREE_RE.search(f"/{rel}")
      if not m_sub:
        continue
      unit_kind = _UNIT_DIR_TO_KIND[m_sub.group(1)]
      subtree = m_sub.group(2)
      fp_res = fp.resolve()
      targets[fp_res] = (sr_res, rel, unit_kind, subtree)
      url_to_target[f"/{rname}/{rel}"] = fp_res

  scan_roots = _collect_vishvasa_scan_roots(scan_base, static_roots)
  target_set = set(targets.keys())
  include_refs, link_refs = _scan_static_references(
    scan_roots, target_set, hugo_base_str, sorted(repo_names), url_to_target=url_to_target,
  )

  stats: dict = {
    "scanned_targets": len(targets),
    "forwarded": 0,
    "inlined": 0,
    "pruned_zero_caller": 0,
    "by_subtree_kind": {},
    "updated_callers": set(),
    "deleted_files": [],
    "errors": [],
  }

  # Phase 1: unwrap forwarding single-caller wrappers (e.g. VS-M 17/70 -> shared 12/02).
  for fp in sorted(list(targets.keys())):
    if fp not in targets or link_refs.get(fp):
      continue
    refs = include_refs.get(fp, [])
    if len(refs) != 1:
      continue
    _, _, unit_kind, subtree = targets[fp]
    if subtree != "vishvAsa-prastutiH":
      continue
    fwd_url = _extract_forwarding_include_url(fp.read_text(encoding="utf-8", errors="ignore"))
    if not fwd_url:
      continue
    caller_fp, raw_url, _ = refs[0]
    caller_text = caller_fp.read_text(encoding="utf-8")
    url_rx = re.compile(rf"""url=(["']){re.escape(raw_url)}\1""")
    new_text = url_rx.sub(f'url="{fwd_url}"', caller_text, count=1)
    if new_text == caller_text or not _balanced_tags(new_text):
      continue
    if not dry_run:
      pref_txt, n_pref = transformer.surgical_prefill_content(
        new_text, str(caller_fp), hugo_base_dir=hugo_base_str, only_if_prefilled=True,
      )
      if n_pref and _balanced_tags(pref_txt):
        new_text = pref_txt
      caller_fp.write_text(new_text, encoding="utf-8")
      _unlink_and_prune_empty_dirs(fp, targets[fp][0])
    fwd_tgt = _resolve_ref_target(fwd_url, caller_fp, hugo_base_str, url_to_target)
    if fwd_tgt is not None:
      include_refs[fwd_tgt] = [r for r in include_refs.get(fwd_tgt, []) if r[0] != fp] + [(caller_fp, fwd_url, "")]
    include_refs.pop(fp, None)
    targets.pop(fp, None)
    stats["forwarded"] += 1
    stats["updated_callers"].add(str(caller_fp))
    stats["deleted_files"].append(str(fp))

  # Phase 2 & 3: batch-inline 1-caller targets per caller file, and prune 0-caller static files.
  changed_pass = True
  while changed_pass:
    changed_pass = False
    batch_by_caller: dict[pathlib.Path, dict[str, tuple[pathlib.Path, str, str]]] = {}
    for fp in sorted(list(targets.keys())):
      if link_refs.get(fp):
        continue
      refs = include_refs.get(fp, [])
      _, _, unit_kind, subtree = targets[fp]
      if len(refs) == 0:
        if prune_zero_caller:
          nested_divs = transformer.find_js_include_divs(fp.read_text(encoding="utf-8", errors="ignore")) if fp.is_file() else []
          for _, _, _, _, _, otok in nested_divs:
            m_u = _URL_ATTR_RE.search(otok)
            if m_u:
              ntgt = _resolve_ref_target(m_u.group(2), fp, hugo_base_str, url_to_target)
              if ntgt in include_refs:
                include_refs[ntgt] = [r for r in include_refs[ntgt] if r[0] != fp]
          if not dry_run and fp.is_file():
            _unlink_and_prune_empty_dirs(fp, targets[fp][0])
          targets.pop(fp, None)
          stats["pruned_zero_caller"] += 1
          stats["deleted_files"].append(str(fp))
          changed_pass = True
        continue
      if len(refs) == 1:
        caller_fp, raw_url, _ = refs[0]
        batch_by_caller.setdefault(caller_fp, {})[raw_url] = (fp, subtree, unit_kind)

    for caller_fp in sorted(batch_by_caller.keys()):
      url_map = batch_by_caller[caller_fp]
      if not caller_fp.is_file():
        continue
      caller_text = caller_fp.read_text(encoding="utf-8")
      divs_all = transformer.find_js_include_divs(caller_text)
      seen_urls: dict[str, list[tuple[int, int, int, int, int, str]]] = {}
      for d in divs_all:
        m_u = _URL_ATTR_RE.search(d[5])
        if m_u and m_u.group(2) in url_map:
          seen_urls.setdefault(m_u.group(2), []).append(d)

      edits: list[tuple[int, int, str, pathlib.Path, str, str]] = []
      for raw_url, d_list in seen_urls.items():
        if len(d_list) != 1:
          continue
        fp, subtree, unit_kind = url_map[raw_url]
        rep = _render_single_inlined_div(
          fp, caller_fp, caller_text, d_list[0], subtree, unit_kind, hugo_base_str,
        )
        edits.append((d_list[0][0], d_list[0][4], rep, fp, subtree, unit_kind))

      if not edits:
        continue
      edits.sort(key=lambda x: x[0], reverse=True)
      new_parts = caller_text
      for s_open, e_close, rep, _, _, _ in edits:
        prefix = new_parts[:s_open]
        suffix = new_parts[e_close:]
        r_adj = rep
        if prefix and not prefix.endswith("\n"):
          r_adj = "\n" + r_adj
        if suffix and not suffix.startswith("\n"):
          r_adj = r_adj + "\n"
        new_parts = prefix + r_adj + suffix

      if not _balanced_tags(new_parts):
        raise ValueError(f"Unbalanced tags after batch inlining into {caller_fp}")
      if not dry_run:
        caller_fp.write_text(new_parts, encoding="utf-8")

      for _, _, _, fp, subtree, unit_kind in edits:
        nested_divs = transformer.find_js_include_divs(fp.read_text(encoding="utf-8", errors="ignore")) if fp.is_file() else []
        for _, _, _, _, _, otok in nested_divs:
          m_u = _URL_ATTR_RE.search(otok)
          if m_u:
            ntgt = _resolve_ref_target(m_u.group(2), fp, hugo_base_str, url_to_target)
            if ntgt in include_refs:
              include_refs[ntgt] = [
                (caller_fp, m_u.group(2), otok) if r[0] == fp else r for r in include_refs[ntgt]
              ]
        if not dry_run and fp.is_file():
          _unlink_and_prune_empty_dirs(fp, targets[fp][0])
        include_refs.pop(fp, None)
        targets.pop(fp, None)
        key = f"{subtree}:{unit_kind}"
        stats["by_subtree_kind"][key] = stats["by_subtree_kind"].get(key, 0) + 1
        stats["inlined"] += 1
        stats["updated_callers"].add(str(caller_fp))
        stats["deleted_files"].append(str(fp))
        changed_pass = True

  if not dry_run and stats["updated_callers"]:
    caller_list = sorted(stats["updated_callers"])
    same_repo_roots = [r for r in scan_roots if r.parent.name in repo_names]
    rg_bin = shutil.which("rg")
    ext_roots: list[pathlib.Path] = []
    if rg_bin and repo_names:
      other_roots = [str(r) for r in scan_roots if r.parent.name not in repo_names]
      if other_roots:
        repo_alt = "|".join(re.escape(r) for r in sorted(repo_names))
        proc = subprocess.run([rg_bin, "-l", repo_alt, "-g", "*.md", *other_roots], capture_output=True, text=True, check=False)
        if proc.returncode in (0, 1):
          ext_roots = sorted({pathlib.Path(line).parent for line in proc.stdout.splitlines() if line.strip()})
    else:
      ext_roots = [r for r in scan_roots if r.parent.name not in repo_names]
    transformer.surgical_prefill_transitive(
      [*same_repo_roots, *ext_roots],
      caller_list,
      hugo_base_dir=hugo_base_str,
      skip_sources_with_empty_includes=False,
      only_if_prefilled=True,
      dry_run=False,
    )

  stats["updated_callers"] = sorted(stats["updated_callers"])
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
