"""Structural and fidelity auditor for ``विश्वास-प्रस्तुतिः`` / ``मूलम्`` block files.

Promoted from batch Saṁhitā auditing: validates `<details>`/`<summary>` balance,
``validate_accented_markdown`` and ``find_vp_integrity_issues``, source-to-``मूलम्``
round-trip fidelity, colophon isolation, avagraha & canonical sandhi-skeleton parity,
``्-अ`` splits, short prose clause-wrap lines, and oversized blocks — including files
carrying interleaved commentary/viniyoga layers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import regex

from doc_curation.sanskrit.accent.validator import (
  AccentValidationIssue,
  find_vp_integrity_issues,
  validate_accented_markdown,
)
from .guards import canonical_sandhi_skeleton
from .interleave_helper import _DETAIL_SPAN_RE, parse_markdown_clusters

_SVARA_RE = regex.compile(r"[\u0951-\u0954\u1cd0-\u1cff]")
_NON_LETTER_RE = regex.compile(r"[^अ-हऀ-ॿa-zA-Z]")
_HALANT_HYPH_VOW_RE = regex.compile(r"\S*्[-–][आअइईउऊएऐओऔ]\S*")
_DEFAULT_COLOPHON_PATTERNS = ("इति शुक्लयजुः",)
_DEFAULT_HEADING_PREFIX_RE = regex.compile(r"(?m)^## (?=(?:[^\n]*(?:ध्यायः|दशकः|प्रपाठकः|काण्डम्|अनुवाकः)))")


@dataclass
class VipraMulaAuditReport:
  total_blocks: int = 0
  tag_unbalanced: bool = False
  validator_issues: list[AccentValidationIssue] = field(default_factory=list)
  vp_integrity_issues: list[tuple[int, list[str]]] = field(default_factory=list)
  source_diff: tuple[int, int] | None = None
  colophons_inside_blocks: list[tuple[int, str]] = field(default_factory=list)
  orphan_danda_starts: list[tuple[int, str]] = field(default_factory=list)
  avagraha_diffs: list[tuple[int, int, int, str]] = field(default_factory=list)
  skeleton_diffs: list[tuple[int, str, str]] = field(default_factory=list)
  halant_hyph_vowels: list[tuple[int, str]] = field(default_factory=list)
  short_multiline_vp_lines: list[tuple[int, int, str, str]] = field(default_factory=list)
  giant_blocks: list[tuple[int, int, int, str]] = field(default_factory=list)

  @property
  def ok(self) -> bool:
    return (
      not self.tag_unbalanced
      and not self.validator_issues
      and not self.vp_integrity_issues
      and self.source_diff is None
      and not self.colophons_inside_blocks
      and not self.avagraha_diffs
      and not self.halant_hyph_vowels
    )


def extract_vipra_mula_pairs(md_text: str) -> list[tuple[str, str]]:
  """Extract ``(vp_body, mula_body)`` pairs from clusters even when extra layers intervene."""
  _, clusters, _, mula_bodies = parse_markdown_clusters(md_text)
  pairs: list[tuple[str, str]] = []
  for cl, mu in zip(clusters, mula_bodies):
    vp_raw = cl.get("vp", "")
    m = regex.search(r"<summary>\s*विश्वास-प्रस्तुतिः[^<]*</summary>\s*(.*?)\s*</details>", vp_raw, regex.DOTALL)
    vp_body = m.group(1).strip() if m else ""
    pairs.append((vp_body, mu.strip()))
  return pairs


def check_source_roundtrip(
  rendered_md: str,
  source_md: str,
  *,
  heading_prefix_re: regex.Pattern = _DEFAULT_HEADING_PREFIX_RE,
  strip_source_glosses: bool = True,
) -> tuple[int, int] | None:
  """Verify ``rendered_md`` preserves ``source_md`` characters across bare headings & ``मूलम्``."""
  parts: list[str] = []
  cursor = 0
  for m in _DETAIL_SPAN_RE.finditer(rendered_md or ""):
    parts.append(rendered_md[cursor:m.start()])
    title = m.group("title").strip()
    if title == "मूलम्" or title.startswith("मूलम् "):
      parts.append(m.group("body").strip())
    cursor = m.end()
  parts.append(rendered_md[cursor:])
  reconstructed = heading_prefix_re.sub("", "".join(parts))
  cmp_src = regex.sub(r"\+\+\+\([^)]*\)\+\+\+", "", source_md) if strip_source_glosses else source_md
  a = regex.sub(r"\s+", "", cmp_src)
  b = regex.sub(r"\s+", "", reconstructed)
  return None if a == b else (len(a), len(b))


def audit_vipra_mula_blocks(
  rendered_md: str,
  *,
  source_md: str | None = None,
  colophon_patterns: tuple[str, ...] = _DEFAULT_COLOPHON_PATTERNS,
  max_vp_chars: int = 500,
  max_mula_dandas: int = 6,
) -> VipraMulaAuditReport:
  """Audit a Markdown document produced by ``text_to_vipra_mula_blocks``."""
  rep = VipraMulaAuditReport()
  rep.tag_unbalanced = (
    rendered_md.count("<details") != rendered_md.count("</details>")
    or rendered_md.count("<summary>") != rendered_md.count("</summary>")
  )
  rep.validator_issues = validate_accented_markdown(rendered_md)
  if source_md is not None:
    rep.source_diff = check_source_roundtrip(rendered_md, source_md)

  pairs = extract_vipra_mula_pairs(rendered_md)
  rep.total_blocks = len(pairs)
  for bi, (vp, mu) in enumerate(pairs):
    if vp:
      vp_errs = find_vp_integrity_issues(vp)
      if vp_errs:
        rep.vp_integrity_issues.append((bi, vp_errs))
    if any(pat in mu or pat in vp for pat in colophon_patterns):
      rep.colophons_inside_blocks.append((bi, mu[:120]))
    if mu.lstrip().startswith("॥"):
      rep.orphan_danda_starts.append((bi, mu[:120]))
    danda_count = len(regex.findall(r"[।॥]", mu))
    if len(vp) >= max_vp_chars or danda_count >= max_mula_dandas:
      rep.giant_blocks.append((bi, len(vp), danda_count, mu[:140]))
    vp_clean = _SVARA_RE.sub("", vp)
    mu_clean = _SVARA_RE.sub("", mu)
    if vp and canonical_sandhi_skeleton(vp_clean) != canonical_sandhi_skeleton(mu_clean):
      rep.skeleton_diffs.append((bi, vp[:120], mu[:120]))
    if vp and vp_clean.count("ऽ") != mu_clean.count("ऽ"):
      rep.avagraha_diffs.append((bi, vp_clean.count("ऽ"), mu_clean.count("ऽ"), vp[:140]))
    for hm in _HALANT_HYPH_VOW_RE.finditer(vp):
      rep.halant_hyph_vowels.append((bi, hm.group(0)))
    lines = [ln.strip() for ln in vp.splitlines() if ln.strip()]
    if len(lines) >= 2:
      for li, ln in enumerate(lines):
        lets = len(_NON_LETTER_RE.sub("", ln))
        stripped_ref = regex.sub(r"[०-९0-9()\s]+$", "", ln)
        if (lets <= 10 and not regex.search(r"[।॥]$", stripped_ref)) or lets <= 6:
          rep.short_multiline_vp_lines.append((bi, li, ln, vp[:160]))
  return rep


def audit_vipra_mula_dir(
  dir_path: str | Path,
  *,
  source_dir: str | Path | None = None,
  git_repo: str | Path | None = None,
  git_rel_dir: str | None = None,
  file_pattern: str = "[0-9][0-9].md",
  colophon_patterns: tuple[str, ...] = _DEFAULT_COLOPHON_PATTERNS,
) -> dict[str, object]:
  """Audit every matching Markdown file under ``dir_path`` against optional source/git HEAD."""
  root = Path(dir_path)
  by_file: dict[str, VipraMulaAuditReport] = {}
  total_blocks = 0
  failed_files: list[str] = []
  for p in sorted(root.glob(file_pattern)):
    src: str | None = None
    if source_dir is not None:
      sp = Path(source_dir) / p.name
      if sp.is_file():
        src = sp.read_text(encoding="utf-8")
    elif git_repo is not None and git_rel_dir is not None:
      src = subprocess.check_output(
        ["git", "-C", str(git_repo), "show", f"HEAD:{git_rel_dir}/{p.name}"],
        text=True,
      )
    rep = audit_vipra_mula_blocks(p.read_text(encoding="utf-8"), source_md=src, colophon_patterns=colophon_patterns)
    by_file[p.name] = rep
    total_blocks += rep.total_blocks
    if not rep.ok:
      failed_files.append(p.name)
  return {
    "files": len(by_file),
    "total_blocks": total_blocks,
    "failed_files": failed_files,
    "reports": by_file,
  }
