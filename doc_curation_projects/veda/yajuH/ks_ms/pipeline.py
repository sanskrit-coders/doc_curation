"""End-to-end MS & KS splitting, padapāṭha generation, validation, and index-fixing pipeline.

Run MS **first** (100% US-accented Caraka Saṁhitā), then ingest the freshly split MS blocks
into ``VedicReferenceIndex`` before running KS so KS's 370 unaccented files benefit from
exact sister-śākhā Caraka parallel mantras and accents!
"""

from __future__ import annotations

import dataclasses
import glob
import logging
import os
import re
import time
from typing import Sequence

from indic_transliteration import sanscript

from doc_curation.md.library import arrangement
from doc_curation.sanskrit.accent.provenance import VedicCorpusCounter
from doc_curation.sanskrit.accent.shatapatha_solver import UnifiedVedicLexicon
from doc_curation_projects.veda.yajuH.ks_ms.padapatha_builder import (
  BuiltBlock,
  build_block_padapatha_full,
  render_anuvaka_markdown,
)
from doc_curation_projects.veda.yajuH.ks_ms.reference_index import VedicReferenceIndex
from doc_curation_projects.veda.yajuH.ks_ms.source_parser import (
  KsAnuvakaSource,
  MsAnuvakaSource,
  parse_ks_anuvaka,
  parse_ms_prapathaka,
)
from doc_curation_projects.veda.yajuH.ks_ms.splitter import (
  split_ks_anuvaka,
  split_ms_anuvaka,
)

DEFAULT_MS_SARVA_ROOT = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/maitrAyaNIyam/saMhitA/sarva-prastutiH"
DEFAULT_KS_SCHROEDER_ROOT = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/kaTha-kapiShTalAH/saMhitA/mUlam/schroeder"
DEFAULT_KS_SARVA_ROOT = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/kaTha-kapiShTalAH/saMhitA/sarva-prastutiH"

_FORBIDDEN_TAG_RE = re.compile(r"\*(?:TA|EK)\*")
_ZERO_COUNT_RE = re.compile(r"\*(?:TS|RV|TB|TK|AV|SB-M|SB-K|VS-M|VS-K|MS|KS)\*-0(?![/\d])")
_BARE_CORPUS_RE = re.compile(r"\*(?:TS|RV|TB|TK|AV|SB-M|SB-K|VS-M|VS-K|MS|KS)\*(?!-\d)")
_ZERO_ABBREV_RE = re.compile(r"[\u0905-\u0939][\u093e-\u094d\u0901-\u0903]*\u0966")
_QMARK_ARROW_RE = re.compile(r"→\s*\*\*\?\*\*")
_BAD_ACCENT_ORDER_RE = re.compile(r"[\u0915-\u0939][\u1cd3\u1cd9][\u093e-\u094d]")
_DOUBLE_ACCENT_RE = re.compile(r"[\u1cd3\u1cd9]{2,}")
_DEVA_BARE_RE = re.compile(r"[\u0905-\u0939\u093e-\u094d]")


@dataclasses.dataclass
class FileStats:
  """Per-output-file processing & verification metrics."""

  out_path: str
  n_blocks: int
  n_rks: int
  n_brahmana: int
  n_with_viniyoga: int
  n_padas: int
  n_sandhi_ok: int
  n_vyat: int
  n_yantra_svara_blocks: int
  n_ocr_repairs: int
  issues: list[str]


def validate_rendered_markdown(md_text: str) -> list[str]:
  """Verify structural, tag-balance, accent-order, and provenance invariants on a rendered file."""
  issues: list[str] = []

  # 1. Exact `<details>` / `</details>` nesting balance
  depth = 0
  for m in re.finditer(r"<details(?:\s+open)?>|</details>", md_text):
    if m.group(0).startswith("</"):
      depth -= 1
      if depth < 0:
        issues.append(f"unbalanced </details> at offset {m.start()}")
        break
    else:
      depth += 1
  if depth != 0:
    issues.append(f"unclosed <details> tags (final depth={depth})")

  # 2. Check padapāṭha bullet lines for forbidden patterns
  for ln_i, ln in enumerate(md_text.splitlines(), 1):
    if ln.startswith("- "):
      if _FORBIDDEN_TAG_RE.search(ln):
        issues.append(f"L{ln_i}: forbidden *TA*/*EK* tag: {ln[:80]}")
      if _ZERO_COUNT_RE.search(ln):
        issues.append(f"L{ln_i}: forbidden *-0 count: {ln[:80]}")
      if _BARE_CORPUS_RE.search(ln):
        issues.append(f"L{ln_i}: bare uncounted corpus tag: {ln[:80]}")
      if _QMARK_ARROW_RE.search(ln):
        issues.append(f"L{ln_i}: forbidden → **?**: {ln[:80]}")
      if _ZERO_ABBREV_RE.search(ln):
        issues.append(f"L{ln_i}: digit-zero abbreviation (पा०): {ln[:80]}")
    # Check VP lines for broken accent placement (skip Schroeder raw मूलम् / टिप्पणी)
    if _BAD_ACCENT_ORDER_RE.search(ln):
      issues.append(f"L{ln_i}: malformed consonant+accent+matra order: {ln[:80]}")

  # 3. Verify no `<details><summary>मूलम्</summary>` or `<details open><summary>विश्वास-प्रस्तुतिः` starts with
  #    a matra/virāma/accent (catches any cut-index drift!)
  _BAD_START = frozenset("ािीुूृॄॢॣेैोौ्ंःँ᳓᳙॒॑")
  for m_blk in re.finditer(
    r"<details(?:\s+open)?><summary>(मूलम्|विश्वास-प्रस्तुतिः[^<]*)</summary>\s*(.*?)\s*</details>",
    md_text,
    re.S,
  ):
    b_txt = m_blk.group(2).strip()
    if b_txt and b_txt[0] in _BAD_START:
      issues.append(f"bad block start in {m_blk.group(1)}: {b_txt[:40]!r}")

  return issues


def _bare_deva_len(text: str) -> int:
  return len(_DEVA_BARE_RE.findall(text))


def _check_lossless_coverage(src_text: str, blocks: Sequence[BuiltBlock]) -> str | None:
  """Verify concatenated ``मूलम्`` blocks preserve the source Devanagari text without dropping chunks."""
  # Strip trailing anuvāka numerals and `ओम्` header markers from source comparison
  src_clean = re.sub(r"[।॥]+\s*[०-९0-9]+\s*[।॥]*", "", src_text)
  n_src = _bare_deva_len(src_clean)
  if n_src < 10:
    return None
  n_out = sum(_bare_deva_len(b.mula_body) for b in blocks)
  ratio = n_out / max(n_src, 1)
  if ratio < 0.92 or ratio > 1.12:
    return f"lossless coverage drift: out={n_out} vs src={n_src} (ratio={ratio:.3f})"
  return None


def _process_ms_anuvaka(
  anu: MsAnuvakaSource,
  out_path: str,
  ref_index: VedicReferenceIndex,
  lex: UnifiedVedicLexicon,
  counter: VedicCorpusCounter,
  cursors: dict[str, int],
  *,
  dry_run: bool = False,
) -> FileStats:
  split_blocks = split_ms_anuvaka(anu, ref_index, cursors=cursors)
  built = [build_block_padapatha_full(b, lex, counter, corpus="MS") for b in split_blocks]
  md_text = render_anuvaka_markdown(anu.title_dev, built)
  issues = validate_rendered_markdown(md_text)
  cov_issue = _check_lossless_coverage(" ".join(anu.raw_lines), built)
  if cov_issue:
    issues.append(cov_issue)

  if not dry_run:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
      fh.write(md_text)

  return FileStats(
    out_path=out_path,
    n_blocks=len(built),
    n_rks=sum(1 for b in built if b.split_block.is_rk),
    n_brahmana=sum(1 for b in built if b.split_block.is_brahmana),
    n_with_viniyoga=sum(1 for b in built if b.split_block.viniyogas),
    n_padas=sum(len(b.padas_bare) for b in built),
    n_sandhi_ok=sum(1 for b in built if b.sandhi_ok),
    n_vyat=sum(b.n_vyat for b in built),
    n_yantra_svara_blocks=sum(1 for b in built if not b.mula_had_accents),
    n_ocr_repairs=0,
    issues=issues,
  )


def process_ms_corpus(
  ms_root: str = DEFAULT_MS_SARVA_ROOT,
  *,
  prapathaka_filter: Sequence[str] | None = None,
  ref_index: VedicReferenceIndex | None = None,
  lex: UnifiedVedicLexicon | None = None,
  counter: VedicCorpusCounter | None = None,
  dry_run: bool = False,
  remove_old_prapathakas: bool = False,
  fix_indexes: bool = False,
) -> list[FileStats]:
  """Split all MS prapāṭhakas into per-anuvāka wrapped files with viniyogas & padapāṭhas."""
  ref_index = ref_index or VedicReferenceIndex.load_or_build()
  lex = lex or UnifiedVedicLexicon.load_or_build(include_sb_m=True)
  counter = counter or VedicCorpusCounter.load_or_build()

  prap_files = sorted(
    f
    for f in glob.glob(os.path.join(ms_root, "*", "*.md"))
    if os.path.basename(f) != "_index.md"
  )
  if prapathaka_filter:
    flt = set(prapathaka_filter)
    prap_files = [
      f for f in prap_files if os.path.relpath(f, ms_root).replace("\\", "/") in flt
      or os.path.splitext(os.path.relpath(f, ms_root).replace("\\", "/"))[0] in flt
    ]

  all_stats: list[FileStats] = []
  # Maintain sequential ritual-order cursors across consecutive anuvākas within a kāṇḍa!
  for pf in prap_files:
    anus = parse_ms_prapathaka(pf)
    cursors: dict[str, int] = {}
    prap_dir = os.path.splitext(pf)[0]  # e.g. .../1/01
    for anu in anus:
      out_path = os.path.join(prap_dir, f"{anu.anuvaka_num:02d}.md")
      st = _process_ms_anuvaka(
        anu, out_path, ref_index, lex, counter, cursors, dry_run=dry_run
      )
      all_stats.append(st)
    if remove_old_prapathakas and not dry_run and anus:
      os.remove(pf)

  if fix_indexes and not dry_run:
    arrangement.fix_index_files(
      dir_path=ms_root, transliteration_target=sanscript.DEVANAGARI, dry_run=False
    )
  return all_stats


def _process_ks_file(
  src_path: str,
  schroeder_root: str,
  out_root: str,
  ref_index: VedicReferenceIndex,
  lex: UnifiedVedicLexicon,
  counter: VedicCorpusCounter,
  cursors: dict[str, int],
  *,
  dry_run: bool = False,
) -> FileStats:
  anu: KsAnuvakaSource = parse_ks_anuvaka(src_path, schroeder_root, lex=lex)
  split_blocks = split_ks_anuvaka(anu, ref_index, lex=lex, cursors=cursors)

  # Map each block's inline footnote IDs to their Schroeder definitions (deduplicated across blocks!)
  emitted_fns: set[str] = set()
  built: list[BuiltBlock] = []
  for blk in split_blocks:
    b_notes: list[str] = []
    for fid in blk.footnote_ids:
      if fid not in emitted_fns and fid in anu.footnote_defs:
        emitted_fns.add(fid)
        b_notes.append(f"- **[{fid}]** {anu.footnote_defs[fid]}")
    built.append(
      build_block_padapatha_full(
        blk, lex, counter, corpus="KS", schroeder_notes=b_notes
      )
    )

  # Attach any unattached footnotes + unnumbered Schroeder notes + `cf.` notes onto anuvāka tail
  tail_notes: list[str] = []
  for fid, fdef in anu.footnote_defs.items():
    if fid not in emitted_fns:
      tail_notes.append(f"- **[{fid}]** {fdef}")
  tail_notes.extend(anu.unnumbered_notes)
  if anu.cf_notes:
    tail_notes.append("**समानान्तराणि:** " + "; ".join(anu.cf_notes))

  md_text = render_anuvaka_markdown(anu.title, built, anuvaka_schroeder_notes=tail_notes)
  issues = validate_rendered_markdown(md_text)
  cov_issue = _check_lossless_coverage(" ".join(p.raw_mula for p in anu.pieces), built)
  if cov_issue:
    issues.append(cov_issue)

  out_path = os.path.join(out_root, anu.rel_path)
  if not dry_run:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
      fh.write(md_text)

  n_repairs = sum(len(p.ocr_repairs) for p in anu.pieces)
  return FileStats(
    out_path=out_path,
    n_blocks=len(built),
    n_rks=sum(1 for b in built if b.split_block.is_rk),
    n_brahmana=sum(1 for b in built if b.split_block.is_brahmana),
    n_with_viniyoga=sum(1 for b in built if b.split_block.viniyogas),
    n_padas=sum(len(b.padas_bare) for b in built),
    n_sandhi_ok=sum(1 for b in built if b.sandhi_ok),
    n_vyat=sum(b.n_vyat for b in built),
    n_yantra_svara_blocks=sum(1 for b in built if not b.mula_had_accents),
    n_ocr_repairs=n_repairs,
    issues=issues,
  )


def process_ks_corpus(
  schroeder_root: str = DEFAULT_KS_SCHROEDER_ROOT,
  out_root: str = DEFAULT_KS_SARVA_ROOT,
  *,
  rel_filter: Sequence[str] | None = None,
  ref_index: VedicReferenceIndex | None = None,
  lex: UnifiedVedicLexicon | None = None,
  counter: VedicCorpusCounter | None = None,
  include_ms_witness: bool = True,
  ms_sarva_root: str = DEFAULT_MS_SARVA_ROOT,
  dry_run: bool = False,
  fix_indexes: bool = False,
) -> list[FileStats]:
  """Process all 653 KS Schroeder anuvāka files into ``sarva-prastutiH/``."""
  ref_index = ref_index or VedicReferenceIndex.load_or_build()
  if include_ms_witness:
    ref_index.add_ms_sarva_mantras(ms_sarva_root)
  lex = lex or UnifiedVedicLexicon.load_or_build(include_sb_m=True)
  counter = counter or VedicCorpusCounter.load_or_build()

  ks_files = sorted(
    f
    for f in glob.glob(os.path.join(schroeder_root, "*", "*", "*.md"))
    if os.path.basename(f) != "_index.md" and "/0_prAstAvikam/" not in f.replace("\\", "/")
  )
  if rel_filter:
    flt = set(rel_filter)
    ks_files = [
      f
      for f in ks_files
      if os.path.relpath(f, schroeder_root).replace("\\", "/") in flt
      or any(os.path.relpath(f, schroeder_root).replace("\\", "/").startswith(p) for p in flt)
    ]

  all_stats: list[FileStats] = []
  last_sth = ""
  cursors: dict[str, int] = {}
  for fp in ks_files:
    rel = os.path.relpath(fp, schroeder_root).replace("\\", "/")
    sth = "/".join(rel.split("/")[:2])
    if sth != last_sth:
      cursors = {}
      last_sth = sth
    st = _process_ks_file(
      fp, schroeder_root, out_root, ref_index, lex, counter, cursors, dry_run=dry_run
    )
    all_stats.append(st)

  if fix_indexes and not dry_run:
    arrangement.fix_index_files(
      dir_path=out_root, transliteration_target=sanscript.DEVANAGARI, dry_run=False
    )
  return all_stats


def summarize_stats(label: str, stats: Sequence[FileStats]) -> str:
  n_files = len(stats)
  n_blks = sum(s.n_blocks for s in stats)
  n_rks = sum(s.n_rks for s in stats)
  n_br = sum(s.n_brahmana for s in stats)
  n_vin = sum(s.n_with_viniyoga for s in stats)
  n_padas = sum(s.n_padas for s in stats)
  n_ok = sum(s.n_sandhi_ok for s in stats)
  n_vyat = sum(s.n_vyat for s in stats)
  n_ys = sum(s.n_yantra_svara_blocks for s in stats)
  n_ocr = sum(s.n_ocr_repairs for s in stats)
  n_iss_files = sum(1 for s in stats if s.issues)
  tot_iss = sum(len(s.issues) for s in stats)
  pct_ok = (100.0 * n_ok / n_blks) if n_blks else 100.0
  return (
    f"[{label}] files={n_files} blocks={n_blks} (yajuṣ={n_blks - n_rks - n_br}, ṛk={n_rks}, brāhmaṇa={n_br}) "
    f"viniyoga_blocks={n_vin} padas={n_padas} sandhi_ok={n_ok}/{n_blks} ({pct_ok:.1f}%) "
    f"vyat_padas={n_vyat} yantra_svara_blocks={n_ys} ocr_repairs={n_ocr} "
    f"issue_files={n_iss_files} (total_issues={tot_iss})"
  )
