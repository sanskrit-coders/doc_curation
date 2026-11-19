"""Corpus-scale orchestration, adjudication verification, and full Phase 4 certification for Śatapatha Brāhmaṇa US accents.

Provides three reusable workflow entry points over ``shatapatha-brAhmaNam/sarva-prastutiH``:
1. :func:`run_solver_corpus_pass`: Runs :func:`solve_sb_file` across content ``.md`` files
   (skipping ``_index.md`` / ``file_list.md`` and pre-``##`` non-mantra intros), emits per-kāṇḍa
   ``kanda_XX_auto_clean.jsonl``, ``kanda_XX_adjudication.jsonl``, and ``corpus_summary.json``,
   and optionally applies ``AUTO_CLEAN`` kaṇḍikās via :func:`apply_sb_kandika_updates`.
2. :func:`verify_and_apply_adjudications`: Reads adjudicated kaṇḍikā JSONL records, independently
   certifies every record (``build_sb_vp_from_padapatha``, ``verify_mantra_sandhi``,
   ``audit_padapatha_against_sb`` with cross-kaṇḍikā ``next_first_mark``, ``validate_accented_markdown``,
   and ``reconcile_markdown_blocks``), applies passing records cleanly via
   :func:`apply_sb_kandika_updates`, and returns structured ``ACCEPTED``/``REJECTED`` diagnostics.
3. :func:`audit_full_sb_corpus`: Phase 4 corpus-wide verifier checking zero leftover ŚB marks
   (outside untouched verbatim pre-existing pratīkas), exact ``पद-पाठः`` placement after each
   contiguous ``मूलम् - *`` run, zero validator issues, zero reconciler diffs, forward-sandhi
   round-trips, and zero unmapped/unflagged/spurious two-source ŚB audit findings.
"""

from __future__ import annotations

import collections
import concurrent.futures
import dataclasses
import json
import os
import re
import time
from pathlib import Path
from typing import AbstractSet, Any, Sequence

from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.accent.reconciler import (
  DETAILS_RE,
  PadapathaItem,
  has_us_accents,
  is_solid_provenance,
  parse_padapatha_items,
  reconcile_markdown_blocks,
  syllables_with_marks,
)
from doc_curation.sanskrit.accent.sandhi_check import verify_mantra_sandhi
from doc_curation.sanskrit.accent.shatapatha import (
  _extract_vp_clusters,
  apply_sb_kandika_updates,
  audit_padapatha_against_sb,
  build_sb_vp_from_padapatha,
  format_padapatha_block,
  normalize_sb_orthography,
)
from doc_curation.sanskrit.accent.shatapatha_solver import (
  KandikaCluster,
  SolveResult,
  UnifiedVedicLexicon,
  export_adjudication_jsonl,
  lookup_corpus_counts,
  parse_sb_markdown_clusters,
  solve_sb_file,
)
from doc_curation.sanskrit.accent.validator import validate_accented_markdown

_SKIP_FILENAMES = frozenset({"_index.md", "file_list.md"})
_SB_MARKS_RE = re.compile(r"[\u1cd8\u1cdf\u0957]")
_PRATIKA_PAREN_RE = re.compile(r"\(\s*[\u0900-\u097f\u1cd0-\u1cff\u0951-\u0957\sऽ]{1,14}\)")
_SUG_SPAN_RE = re.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]")
_INLINE_NOTE_RE = re.compile(r"\+\+\+.*?\+\+\+|\[\[(?:\?+|!+)\]\]", re.S)
_ZERO_CORPUS_COUNT_RE = re.compile(r"\*(?:VS|TS|RV|AV|TB|TA)\*-0(?![0-9])")

_WORKER_LEXICON: UnifiedVedicLexicon | None = None


def _init_solver_worker() -> None:
  global _WORKER_LEXICON
  _WORKER_LEXICON = UnifiedVedicLexicon.load_or_build(force_rebuild=False)


def _solve_one_file_worker(args: tuple[str, str]) -> tuple[str, list[KandikaCluster], list[SolveResult]]:
  md_path, sb_root = args
  assert _WORKER_LEXICON is not None
  txt = Path(md_path).read_text(encoding="utf-8")
  clusters = parse_sb_markdown_clusters(txt)
  results = solve_sb_file(md_path, _WORKER_LEXICON, rel_root=sb_root)
  return md_path, clusters, results


def _normalize_kandas_filter(kandas: Sequence[str | int] | None) -> set[str] | None:
  if kandas is None:
    return None
  norm: set[str] = set()
  for k in kandas:
    s = str(k).strip()
    norm.add(f"{int(s):02d}" if s.isdigit() else s)
  return norm


def _kanda_tag_for_rel(rel_posix: str) -> str:
  parts = rel_posix.split("/")
  if len(parts) >= 2:
    return parts[0]
  return "00"


def discover_sb_content_files(
  sb_root: str | os.PathLike[str],
  *,
  kandas: Sequence[str | int] | None = None,
) -> list[Path]:
  """Return deterministically sorted ŚB content ``.md`` files, skipping ``_index.md`` and ``file_list.md``."""
  root = Path(sb_root)
  k_filter = _normalize_kandas_filter(kandas)
  out: list[Path] = []
  for p in sorted(root.rglob("*.md"), key=lambda x: x.relative_to(root).as_posix()):
    if p.name in _SKIP_FILENAMES:
      continue
    rel_posix = p.relative_to(root).as_posix()
    ktag = _kanda_tag_for_rel(rel_posix)
    if k_filter is not None and ktag not in k_filter:
      continue
    out.append(p)
  return out


def _first_us_mark(vp_text: str) -> str | None:
  """Return the US mark (``'U'``/``'S'``/``''``) of the first Devanagari syllable in ``vp_text``."""
  cleaned = _INLINE_NOTE_RE.sub(" ", vp_text)
  cleaned = _PRATIKA_PAREN_RE.sub(" ", cleaned)
  cleaned = _SUG_SPAN_RE.sub(r"\2", cleaned)
  _, marks = syllables_with_marks(cleaned)
  return marks[0] if marks else None


def _vp_body_to_clean_for_audit(vp_body: str) -> str:
  """Produce an unaccented, annotation-free Devanagari VP string preserving ``ऽ`` and ``-`` for audit/sandhi."""
  s = _INLINE_NOTE_RE.sub(" ", vp_body)
  s = _PRATIKA_PAREN_RE.sub(" ", s)
  s = _SUG_SPAN_RE.sub(r"\1", s)
  s = accent.strip_accents(s)
  s = s.replace("᳟", "").replace("᳭", "").replace("ᳮ", "")
  s = re.sub(r" {2,}", " ", s)
  return s.strip()


def _reason_bucket(reason: str) -> str:
  return reason.split(":", 1)[0].strip()


# ---------------------------------------------------------------------------
# Deterministic ``*CORPUS*-N`` occurrence-count enrichment of padapāṭha provenance
# ---------------------------------------------------------------------------

_CORPUS_RE = r"(?:VS|TS|RV|AV|TB|TA)"
_BARE_TAGS_ONLY_RE = re.compile(rf"\*{_CORPUS_RE}\*(?:-\d+)?(?:\s*/\s*\*{_CORPUS_RE}\*(?:-\d+)?)*")
_INLINE_FORM_TAG_RE = re.compile(rf"^\*({_CORPUS_RE})\*(?:-\d+)?(\s+(?![०-९\d\s]).+)$")


def enrich_provenance_with_corpus_counts(
  lex: UnifiedVedicLexicon,
  pada_us: str,
  just: str,
) -> tuple[str, list[str]]:
  """Rewrite corpus citations in ``just`` to exact ``*CORPUS*-N`` occurrence counts for ``pada_us``.

  - Standalone tags (``*TS*``, ``*RV*``, ``*TS*-3``) are replaced by one counts clause listing every
    corpus attesting the exact US form, ordered by count (ties ``VS > TS > RV > AV > TB > TA``).
    The clause is inserted after the leading sūtra/rule segments (or first, if none) of the first ``;`` clause.
  - Inline form citations (``*TS* सँस्थि॑ते``) keep their form but gain the exact count (no duplicate tag).
  - Verse references (``*VS* १.५``), mixed forms (``*RV*/*TS* …``), dictionaries (``*MW*``, ``*Macdonell*``…),
    and editorial notes stay verbatim; ``पा\\u0966`` is normalized to ``पा॰``.
  - Idempotent. Never emits ``-0``. When a cited corpus cannot be verified for the exact form, the original
    bare tag is kept and reported in the second return value (``"<TAG>"``), so adjudicators can resolve it.

  Returns ``(new_just, unverified_tags)``.
  """
  just = just.replace("पा\u0966", "पा॰")
  counts = lookup_corpus_counts(lex, pada_us)
  unverified: list[str] = []
  used: set[str] = set()
  dropped_bare: list[str] = []
  new_clauses: list[list[str]] = []
  for clause in just.split(";"):
    kept: list[str] = []
    for seg in (s.strip() for s in clause.split(",")):
      if not seg:
        continue
      if _BARE_TAGS_ONLY_RE.fullmatch(seg):
        dropped_bare.append(seg)
        continue
      m_inl = _INLINE_FORM_TAG_RE.match(seg)
      if m_inl and "/" not in seg.split(" ", 1)[0]:
        cname = m_inl.group(1)
        if cname in counts:
          used.add(cname)
          seg = f"*{cname}*-{counts[cname]}{m_inl.group(2)}"
        else:
          unverified.append(cname)
      kept.append(seg)
    new_clauses.append(kept)

  for seg in dropped_bare:
    unverified.extend(c for c in re.findall(rf"\*({_CORPUS_RE})\*", seg) if c not in counts)
  remaining = {c: n for c, n in counts.items() if c not in used}
  counts_clause = ", ".join(f"*{c}*-{n}" for c, n in remaining.items())
  if counts_clause:
    first = new_clauses[0] if new_clauses else []
    if not new_clauses:
      new_clauses.append(first)
    first.append(counts_clause)
  elif dropped_bare:
    # Nothing attested for the exact form: unverifiable bare tags are dropped when the remaining provenance is
    # still solid (sūtra / inline cited form); otherwise they are kept verbatim so solidity is not lost.
    # Either way they are reported, and counts are never invented.
    for seg in dropped_bare:
      unverified.extend(re.findall(rf"\*({_CORPUS_RE})\*", seg))
    rest = "; ".join(", ".join(k) for k in new_clauses if k)
    if not is_solid_provenance(rest):
      first = new_clauses[0] if new_clauses else []
      if not new_clauses:
        new_clauses.append(first)
      first.append(", ".join(dropped_bare))
  new_just = "; ".join(", ".join(k) for k in new_clauses if k)
  return new_just, sorted(set(unverified))


def enrich_items_with_corpus_counts(
  lex: UnifiedVedicLexicon,
  items: Sequence[PadapathaItem],
) -> tuple[list[PadapathaItem], dict[int, list[str]]]:
  """Apply :func:`enrich_provenance_with_corpus_counts` to every item; returns ``(items, {idx: unverified_tags})``."""
  out: list[PadapathaItem] = []
  warn: dict[int, list[str]] = {}
  for i, it in enumerate(items):
    new_prov, unv = enrich_provenance_with_corpus_counts(lex, it.ref if it.ref != "?" else it.ar, it.prov)
    if unv:
      warn[i] = unv
    out.append(
      PadapathaItem(
        ar=it.ar,
        ref=it.ref,
        prov=new_prov,
        vyat=it.vyat,
        solid=is_solid_provenance(new_prov) and it.ref != "?",
      )
    )
  return out, warn


# ---------------------------------------------------------------------------
# 1. Corpus-wide solver runner (Phase 2)
# ---------------------------------------------------------------------------


def _add_rel_path_to_jsonl(jsonl_path: Path, root: Path) -> None:
  """Add a ``rel_path`` field (relative to ``root``) to every record of an exported adjudication JSONL."""
  lines = [ln for ln in jsonl_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
  out: list[str] = []
  for ln in lines:
    rec = json.loads(ln)
    src = rec.get("file") or rec.get("rel_path")
    if src:
      try:
        rec["rel_path"] = Path(src).relative_to(root).as_posix() if Path(src).is_absolute() else Path(src).as_posix()
      except ValueError:
        rec["rel_path"] = Path(src).name
      rec.setdefault("file", str(src))
    out.append(json.dumps(rec, ensure_ascii=False))
  jsonl_path.write_text("".join(o + "\n" for o in out), encoding="utf-8")


def run_solver_corpus_pass(
  sb_root: str | os.PathLike[str],
  out_dir: str | os.PathLike[str],
  *,
  kandas: Sequence[str | int] | None = None,
  apply_auto_clean: bool = False,
  max_workers: int = 1,
  lexicon: UnifiedVedicLexicon | None = None,
  export_all_to_adjudication: bool = False,
) -> dict[str, Any]:
  """Run :func:`solve_sb_file` across ŚB content files, export per-kāṇḍa JSONLs, and optionally apply ``AUTO_CLEAN``.

  Writes under ``out_dir``:
  - ``kanda_<XX>_auto_clean.jsonl``: certified ``AUTO_CLEAN`` kaṇḍikā records (directly consumable by
    :func:`verify_and_apply_adjudications`).
  - ``kanda_<XX>_adjudication.jsonl``: ``NEEDS_ADJUDICATION`` queue exported by :func:`export_adjudication_jsonl`.
  - ``corpus_summary.json``: aggregate and per-kāṇḍa counts, failure reason breakdowns, timing, and apply results.

  Parameters:
  - ``sb_root``: root directory (e.g. ``.../shatapatha-brAhmaNam/sarva-prastutiH``).
  - ``out_dir``: output directory for JSONLs and summary JSON.
  - ``kandas``: optional subset of kāṇḍas (e.g. ``["01", "02"]`` or ``[1, 2]``).
  - ``apply_auto_clean``: when ``True``, applies ``AUTO_CLEAN`` kaṇḍikās via
    :func:`apply_sb_kandika_updates(..., preserve_existing_us=True, strict=True)`.
  - ``max_workers``: defaults to ``1`` to stay polite on local CPU; capped at ``os.cpu_count()``.
  - ``lexicon``: optional pre-loaded :class:`UnifiedVedicLexicon` (used when ``max_workers <= 1``).
  - ``export_all_to_adjudication``: when ``True``, ``AUTO_CLEAN`` drafts are ALSO written to
    ``kanda_<XX>_adjudication.jsonl`` (reason ``auto_clean_draft``) so Phase 3 covers every non-skipped kaṇḍikā.
    Adjudication records always carry both ``file`` (absolute) and ``rel_path``.
  """
  t0 = time.monotonic()
  root = Path(sb_root)
  out_path = Path(out_dir)
  out_path.mkdir(parents=True, exist_ok=True)

  files = discover_sb_content_files(root, kandas=kandas)
  solved_files: list[tuple[str, list[KandikaCluster], list[SolveResult]]] = []

  eff_workers = max(1, min(int(max_workers), os.cpu_count() or 2))
  if eff_workers <= 1 or len(files) <= 1:
    lex = lexicon or UnifiedVedicLexicon.load_or_build(force_rebuild=False)
    for md_path in files:
      txt = md_path.read_text(encoding="utf-8")
      clusters = parse_sb_markdown_clusters(txt)
      results = solve_sb_file(str(md_path), lex, rel_root=str(root))
      solved_files.append((str(md_path), clusters, results))
  else:
    # Ensure on-disk lexicon pickle exists before spawning worker processes.
    if lexicon is None:
      UnifiedVedicLexicon.load_or_build(force_rebuild=False)
    work_items = [(str(p), str(root)) for p in files]
    with concurrent.futures.ProcessPoolExecutor(
      max_workers=eff_workers,
      initializer=_init_solver_worker,
    ) as pool:
      for item in pool.map(_solve_one_file_worker, work_items):
        solved_files.append(item)

  by_kanda: dict[str, list[tuple[str, list[KandikaCluster], list[SolveResult]]]] = collections.defaultdict(list)
  for md_path_s, clusters, results in solved_files:
    rel_posix = Path(md_path_s).relative_to(root).as_posix()
    by_kanda[_kanda_tag_for_rel(rel_posix)].append((md_path_s, clusters, results))

  total_kandikas = 0
  total_auto = 0
  total_adj = 0
  total_skipped = 0
  total_preserved = 0
  preserved_existing_us_ids: list[str] = []
  total_reasons: collections.Counter[str] = collections.Counter()
  files_applied: list[str] = []
  apply_errors: list[dict[str, str]] = []
  per_kanda_summary: dict[str, dict[str, Any]] = {}

  for ktag in sorted(by_kanda.keys()):
    k_entries = by_kanda[ktag]
    k_total = 0
    k_auto = 0
    k_adj = 0
    k_skip = 0
    k_pres = 0
    k_reasons: collections.Counter[str] = collections.Counter()

    auto_jsonl_path = out_path / f"kanda_{ktag}_auto_clean.jsonl"
    adj_jsonl_path = out_path / f"kanda_{ktag}_adjudication.jsonl"

    with auto_jsonl_path.open("w", encoding="utf-8") as f_auto:
      for md_path_s, clusters, results in k_entries:
        rel_posix = Path(md_path_s).relative_to(root).as_posix()
        kandika_map: dict[tuple[str, int], tuple[str | None, list[PadapathaItem]]] = {}
        for cl, res in zip(clusters, results):
          k_total += 1
          if res.preserve_vp:
            k_pres += 1
            preserved_existing_us_ids.append(
              f"{rel_posix}::{cl.heading}" + (f"#{cl.sub_idx}" if cl.sub_idx > 0 else "")
            )
          if res.status == "AUTO_CLEAN":
            k_auto += 1
            rec = {
              "id": res.kandika_id,
              "rel_path": rel_posix,
              "heading": cl.heading,
              "sub_idx": cl.sub_idx,
              "preserve_vp": res.preserve_vp,
              "vp_clean": None if res.preserve_vp else res.vp_clean,
              "vp_summary": res.vp_summary,
              "vp_accented": res.vp_accented,
              "items": [
                {
                  "pada": it.ref,
                  "just": it.prov,
                  "vyat_from": it.ar if it.vyat else None,
                }
                for it in res.items
              ],
              "sandhi_ok": list(res.sandhi_ok),
            }
            f_auto.write(json.dumps(rec, ensure_ascii=False) + "\n")
            kandika_map[(cl.heading, cl.sub_idx)] = (None if res.preserve_vp else res.vp_clean, res.items)
          elif res.status == "NEEDS_ADJUDICATION":
            k_adj += 1
            for r in res.reasons:
              b = _reason_bucket(r)
              k_reasons[b] += 1
              total_reasons[b] += 1
          else:
            k_skip += 1

        if apply_auto_clean and kandika_map:
          try:
            apply_sb_kandika_updates(
              md_path_s,
              kandika_map,
              preserve_existing_us=True,
              dry_run=False,
              strict=True,
            )
            files_applied.append(rel_posix)
          except Exception as exc:  # noqa: BLE001
            apply_errors.append({"rel_path": rel_posix, "error": str(exc)})

    export_entries = k_entries
    if export_all_to_adjudication:
      # Every non-skipped kaṇḍikā (including AUTO_CLEAN drafts) goes to Phase 3: no unreviewed auto-application.
      export_entries = [
        (
          md_s,
          cls_,
          [
            dataclasses.replace(r, reasons=list(r.reasons) or ["auto_clean_draft"])
            if r.status == "AUTO_CLEAN"
            else r
            for r in res_
          ],
        )
        for md_s, cls_, res_ in k_entries
      ]
    adj_written = export_adjudication_jsonl(
      export_entries,
      str(adj_jsonl_path),
      include_auto_clean=export_all_to_adjudication,
      rel_root=str(root),
    )
    assert adj_written == (k_adj + k_auto if export_all_to_adjudication else k_adj)
    _add_rel_path_to_jsonl(adj_jsonl_path, root)

    total_kandikas += k_total
    total_auto += k_auto
    total_adj += k_adj
    total_skipped += k_skip
    total_preserved += k_pres

    per_kanda_summary[ktag] = {
      "files": len(k_entries),
      "total": k_total,
      "auto_clean": k_auto,
      "needs_adjudication": k_adj,
      "skipped": k_skip,
      "preserved_existing_us": k_pres,
      "auto_clean_pct": round(100.0 * k_auto / k_total, 2) if k_total else 0.0,
      "reason_counts": dict(k_reasons.most_common()),
      "auto_clean_jsonl": str(auto_jsonl_path),
      "adjudication_jsonl": str(adj_jsonl_path),
    }

  elapsed = round(time.monotonic() - t0, 3)
  summary: dict[str, Any] = {
    "sb_root": str(root),
    "out_dir": str(out_path),
    "files": len(files),
    "total_kandikas": total_kandikas,
    "auto_clean": total_auto,
    "needs_adjudication": total_adj,
    "skipped": total_skipped,
    "preserved_existing_us": total_preserved,
    "preserved_existing_us_ids": preserved_existing_us_ids,
    "auto_clean_pct": round(100.0 * total_auto / total_kandikas, 2) if total_kandikas else 0.0,
    "elapsed_sec": elapsed,
    "ms_per_kandika": round(1000.0 * elapsed / total_kandikas, 2) if total_kandikas else 0.0,
    "apply_auto_clean": apply_auto_clean,
    "files_applied": files_applied,
    "apply_errors": apply_errors,
    "reason_counts": dict(total_reasons.most_common()),
    "per_kanda": per_kanda_summary,
  }
  (out_path / "corpus_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  return summary


# ---------------------------------------------------------------------------
# 2. Adjudication verifier & applier (Phase 3)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AdjudicationRecordResult:
  """Per-kaṇḍikā verification outcome from :func:`verify_and_apply_adjudications`."""

  kandika_id: str
  rel_path: str
  heading: str
  sub_idx: int
  status: str  # 'ACCEPTED' | 'REJECTED'
  applied: bool
  preserved_vp: bool
  errors: list[str]
  disagree_syllables: list[dict[str, Any]] = dataclasses.field(default_factory=list)
  validation_issues: list[str] = dataclasses.field(default_factory=list)
  reconcile_logs: list[str] = dataclasses.field(default_factory=list)
  unverified_corpus_tags: list[str] = dataclasses.field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class AdjudicationBatchReport:
  """Structured summary returned by :func:`verify_and_apply_adjudications`."""

  adj_jsonl_path: str
  dry_run: bool
  total_records: int
  accepted: int
  rejected: int
  files_written: list[str]
  records: list[AdjudicationRecordResult]

  def to_dict(self) -> dict[str, Any]:
    return {
      "adj_jsonl_path": self.adj_jsonl_path,
      "dry_run": self.dry_run,
      "total_records": self.total_records,
      "accepted": self.accepted,
      "rejected": self.rejected,
      "files_written": list(self.files_written),
      "records": [r.to_dict() for r in self.records],
    }


def _parse_adjudication_items(raw_items: Any) -> tuple[list[PadapathaItem], list[str]]:
  """Convert structured ``[{"pada", "just", "vyat_from"}]`` (or bullet line) specs into :class:`PadapathaItem`s."""
  if not isinstance(raw_items, list) or not raw_items:
    return [], ["items must be a non-empty list"]
  items: list[PadapathaItem] = []
  errs: list[str] = []
  for idx, entry in enumerate(raw_items):
    if isinstance(entry, str):
      parsed = parse_padapatha_items(entry.replace("पा\u0966", "पा॰"))
      if not parsed:
        errs.append(f"item[{idx}]: unparseable bullet {entry!r}")
        continue
      it = parsed[0]
      if not it.prov:
        errs.append(f"item[{idx}] ({it.ref}): missing provenance")
      if it.vyat and not it.solid:
        errs.append(f"item[{idx}] ({it.ar} → {it.ref}): vyatyasta item lacks solid provenance ({it.prov!r})")
      if it.vyat and it.ar == it.ref:
        errs.append(f"item[{idx}] ({it.ref}): no-op vyatyasta arrow")
      items.append(it)
      continue
    if not isinstance(entry, dict):
      errs.append(f"item[{idx}]: expected dict or str, got {type(entry).__name__}")
      continue
    pada = str(entry.get("pada") or "").strip()
    just = str(entry.get("just") or "").strip().replace("पा\u0966", "पा॰")
    vyat_raw = entry.get("vyat_from")
    vyat_from = str(vyat_raw).strip() if vyat_raw is not None else ""
    if not pada:
      errs.append(f"item[{idx}]: empty 'pada'")
      continue
    if not just:
      errs.append(f"item[{idx}] ({pada}): empty 'just' provenance")
    vyat = bool(vyat_from)
    ar = vyat_from if vyat else pada
    solid = is_solid_provenance(just) and pada != "?"
    if vyat:
      if ar == pada:
        errs.append(f"item[{idx}] ({pada}): vyat_from equals pada")
      if len(syllables_with_marks(ar)[0]) != len(syllables_with_marks(pada)[0]):
        errs.append(f"item[{idx}] ({ar} → {pada}): syllable count mismatch between vyat_from and pada")
      if not solid:
        errs.append(f"item[{idx}] ({ar} → {pada}): vyatyasta item lacks solid provenance ({just!r})")
    items.append(PadapathaItem(ar=ar, ref=pada, prov=just, vyat=vyat, solid=solid))
  return items, errs


def _resolve_rel_path(sb_root: Path, rec: dict[str, Any]) -> tuple[str | None, Path | None, str | None]:
  raw = rec.get("rel_path") or rec.get("file")
  if not raw or not isinstance(raw, str):
    return None, None, "missing 'rel_path'"
  raw_p = Path(raw)
  root_resolved = sb_root.resolve()
  if raw_p.is_absolute():
    try:
      rel = raw_p.resolve().relative_to(root_resolved)
      cand = root_resolved / rel
    except ValueError:
      return raw, None, f"path {raw!r} is outside sb_root {str(sb_root)!r}"
  else:
    cand = (root_resolved / raw_p).resolve()
    try:
      rel = cand.relative_to(root_resolved)
    except ValueError:
      return raw, None, f"path traversal outside sb_root: {raw!r}"
  if not cand.is_file():
    return rel.as_posix(), None, f"target file not found: {rel.as_posix()}"
  return rel.as_posix(), cand, None


@dataclasses.dataclass(frozen=True)
class _FileClusterSlot:
  heading: str
  sub_idx: int
  vp_summary: str
  vp_body: str
  is_already_us: bool
  weber: str
  shri: str
  has_pp: bool
  pp_body: str
  pp_raw: str = ""


def _parse_file_slots(md_text: str) -> list[_FileClusterSlot]:
  slots: list[_FileClusterSlot] = []
  for part in re.split(r"(?m)(?=^##\s+)", md_text):
    m_hdr = re.match(r"^##\s+([^\n]+)", part)
    if not m_hdr:
      continue
    norm_hdr = re.sub(r"\s+", " ", m_hdr.group(1).strip())
    for cl in _extract_vp_clusters(part):
      vp_sum = cl.vp_match.group(1).strip()
      vp_body = cl.vp_match.group(2).strip()
      pp_body = cl.existing_pp_match.group(2).strip() if cl.existing_pp_match is not None else ""
      pp_raw = cl.existing_pp_match.group(0) if cl.existing_pp_match is not None else ""
      slots.append(
        _FileClusterSlot(
          heading=norm_hdr,
          sub_idx=cl.subidx,
          vp_summary=vp_sum,
          vp_body=vp_body,
          is_already_us=has_us_accents(vp_body),
          weber=cl.weber_text,
          shri=cl.shri_text,
          has_pp=cl.existing_pp_match is not None,
          pp_body=pp_body,
          pp_raw=pp_raw,
        )
      )
  return slots


def _build_cluster_validation_snippet(
  slot: _FileClusterSlot,
  *,
  vp_summary: str,
  vp_body: str,
  pp_block: str,
) -> str:
  parts = [
    f"## {slot.heading}\n",
    f"<details open><summary>{vp_summary}</summary>\n\n{vp_body}\n</details>",
  ]
  if slot.shri:
    parts.append(f"<details><summary>मूलम् - श्रीधरादि</summary>\n\n{slot.shri}\n</details>")
  if slot.weber:
    parts.append(f"<details><summary>मूलम् - Weber</summary>\n\n{slot.weber}\n</details>")
  parts.append(pp_block)
  return "\n\n".join(parts) + "\n"


def verify_and_apply_adjudications(
  sb_root: str | os.PathLike[str],
  adj_jsonl_path: str | os.PathLike[str],
  *,
  dry_run: bool = False,
  enrich_counts: bool = True,
  lexicon: UnifiedVedicLexicon | None = None,
) -> AdjudicationBatchReport:
  """Independently verify adjudicated kaṇḍikā JSONL records, apply passing files, and return structured diagnostics.

  Each JSONL line specifies::

    {
      "rel_path": "01/01/2.md",
      "heading": "०१",
      "sub_idx": 0,
      "vp_clean": "...",  # or null when existing VP is already US-accented
      "items": [{"pada": "...", "just": "...", "vyat_from": null}, ...]
    }

  Every record is independently verified against:
  1. Item schema, provenance, and vyatyasta solidity checks.
  2. ``verify_mantra_sandhi`` on VP (and Weber/Śrīdharādi fallback only for verbatim pre-existing US VPs).
  3. ``build_sb_vp_from_padapatha`` (0 unmapped syllables, 0 leftover ŚB marks).
  4. ``audit_padapatha_against_sb`` with cross-kaṇḍikā ``next_first_mark`` (0 unmapped, 0 unflagged, 0 spurious).
  5. Per-kaṇḍikā ``validate_accented_markdown`` (auto-enforcing separated upasarga+tiṅanta) &
     ``reconcile_markdown_blocks`` (0 diffs on non-preserved VP).
  6. File-level :func:`apply_sb_kandika_updates(..., preserve_existing_us=True, strict=True)` guaranteeing
     verbatim preservation of all non-managed blocks and already-US VP blocks before writing.
  """
  root = Path(sb_root)
  jsonl_path = Path(adj_jsonl_path)

  raw_lines = [ln.strip() for ln in jsonl_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
  results_by_order: list[AdjudicationRecordResult | None] = [None] * len(raw_lines)

  # Group valid JSON lines by target file while tracking duplicates and parse errors immediately.
  by_file: dict[str, tuple[Path, list[tuple[int, dict[str, Any]]]]] = {}
  seen_keys: set[tuple[str, str, int]] = set()

  for row_i, ln in enumerate(raw_lines):
    try:
      rec = json.loads(ln)
    except json.JSONDecodeError as exc:
      results_by_order[row_i] = AdjudicationRecordResult(
        kandika_id=f"line:{row_i + 1}",
        rel_path="",
        heading="",
        sub_idx=0,
        status="REJECTED",
        applied=False,
        preserved_vp=False,
        errors=[f"invalid JSON on line {row_i + 1}: {exc}"],
      )
      continue
    if not isinstance(rec, dict):
      results_by_order[row_i] = AdjudicationRecordResult(
        kandika_id=f"line:{row_i + 1}",
        rel_path="",
        heading="",
        sub_idx=0,
        status="REJECTED",
        applied=False,
        preserved_vp=False,
        errors=[f"line {row_i + 1}: expected JSON object"],
      )
      continue

    rel_posix, abs_path, path_err = _resolve_rel_path(root, rec)
    heading = re.sub(r"\s+", " ", str(rec.get("heading") or "").strip())
    try:
      sub_idx = int(rec.get("sub_idx", 0))
    except (TypeError, ValueError):
      sub_idx = -1
    kid = f"{rel_posix or '?'}::{heading}" + (f"#{sub_idx}" if sub_idx > 0 else "")

    if path_err or abs_path is None or rel_posix is None:
      results_by_order[row_i] = AdjudicationRecordResult(
        kandika_id=kid,
        rel_path=rel_posix or "",
        heading=heading,
        sub_idx=sub_idx,
        status="REJECTED",
        applied=False,
        preserved_vp=False,
        errors=[path_err or "invalid rel_path"],
      )
      continue
    if not heading or sub_idx < 0:
      results_by_order[row_i] = AdjudicationRecordResult(
        kandika_id=kid,
        rel_path=rel_posix,
        heading=heading,
        sub_idx=sub_idx,
        status="REJECTED",
        applied=False,
        preserved_vp=False,
        errors=["missing 'heading' or negative 'sub_idx'"],
      )
      continue

    dup_key = (rel_posix, heading, sub_idx)
    if dup_key in seen_keys:
      results_by_order[row_i] = AdjudicationRecordResult(
        kandika_id=kid,
        rel_path=rel_posix,
        heading=heading,
        sub_idx=sub_idx,
        status="REJECTED",
        applied=False,
        preserved_vp=False,
        errors=[f"duplicate_kandika_in_batch: {kid}"],
      )
      continue
    seen_keys.add(dup_key)

    if rel_posix not in by_file:
      by_file[rel_posix] = (abs_path, [])
    by_file[rel_posix][1].append((row_i, rec))

  files_written: list[str] = []

  for rel_posix, (abs_path, row_recs) in by_file.items():
    md_text = abs_path.read_text(encoding="utf-8")
    slots = _parse_file_slots(md_text)
    slot_lookup: dict[tuple[str, int], int] = {(sl.heading, sl.sub_idx): i for i, sl in enumerate(slots)}
    # Also support unambiguous leading-numeral lookup (e.g. "०१" -> "०१ अर्कस्यार्कत्वम्")
    lead_counts: collections.Counter[str] = collections.Counter(sl.heading.split()[0] for sl in slots if sl.sub_idx == 0)
    lead_lookup: dict[tuple[str, int], int] = {}
    for i, sl in enumerate(slots):
      lead = sl.heading.split()[0]
      if lead != sl.heading and lead_counts[lead] == 1:
        lead_lookup[(lead, sl.sub_idx)] = i

    # Pre-parse incoming records and precompute first US marks across the file for cross-kaṇḍikā boundary auditing.
    slot_first_marks: list[str | None] = [
      (_first_us_mark(sl.vp_body) if sl.is_already_us else None) for sl in slots
    ]

    parsed_entries: list[dict[str, Any]] = []
    for row_i, rec in row_recs:
      heading = re.sub(r"\s+", " ", str(rec["heading"]).strip())
      sub_idx = int(rec.get("sub_idx", 0))
      kid = f"{rel_posix}::{heading}" + (f"#{sub_idx}" if sub_idx > 0 else "")

      slot_idx = slot_lookup.get((heading, sub_idx))
      if slot_idx is None:
        slot_idx = lead_lookup.get((heading, sub_idx))
      if slot_idx is None:
        results_by_order[row_i] = AdjudicationRecordResult(
          kandika_id=kid,
          rel_path=rel_posix,
          heading=heading,
          sub_idx=sub_idx,
          status="REJECTED",
          applied=False,
          preserved_vp=False,
          errors=[f"cluster ({heading!r}, {sub_idx}) not found in {rel_posix}"],
        )
        continue

      slot = slots[slot_idx]
      items, item_errs = _parse_adjudication_items(rec.get("items"))
      unverified_by_idx: dict[int, list[str]] = {}
      if enrich_counts and items and not item_errs:
        if lexicon is None:
          lexicon = UnifiedVedicLexicon.load_or_build(force_rebuild=False)
        items, unverified_by_idx = enrich_items_with_corpus_counts(lexicon, items)
      vp_clean_raw = rec.get("vp_clean")
      vp_clean = str(vp_clean_raw).strip() if vp_clean_raw is not None and str(vp_clean_raw).strip() else None
      preserve_vp = slot.is_already_us

      if not preserve_vp and vp_clean is None:
        item_errs.append("vp_clean is required for non-US kaṇḍikā")
      elif vp_clean is not None and _SB_MARKS_RE.search(vp_clean):
        item_errs.append("vp_clean contains leftover ŚB accent marks (᳘/᳟/ॗ)")

      vp_eval = vp_clean if vp_clean is not None else _vp_body_to_clean_for_audit(slot.vp_body)

      vp_sum = slot.vp_summary
      vp_acc = slot.vp_body
      unmapped: list[tuple[str, int]] = []
      if not item_errs and items and vp_eval:
        try:
          vp_sum, vp_acc, unmapped = build_sb_vp_from_padapatha(
            vp_eval,
            items,
            weber_text=slot.weber,
            shri_text=slot.shri,
            orig_summary=slot.vp_summary,
          )
          if not preserve_vp:
            fm = _first_us_mark(vp_acc)
            if fm is not None:
              slot_first_marks[slot_idx] = fm
        except Exception as exc:  # noqa: BLE001
          item_errs.append(f"build_sb_vp_from_padapatha failed: {exc}")

      parsed_entries.append({
        "row_i": row_i,
        "kid": kid,
        "slot_idx": slot_idx,
        "slot": slot,
        "items": items,
        "item_errs": item_errs,
        "vp_clean": vp_clean,
        "vp_eval": vp_eval,
        "preserve_vp": preserve_vp,
        "vp_sum": vp_sum,
        "vp_acc": vp_acc,
        "unmapped": unmapped,
        "unverified": sorted({t for v in unverified_by_idx.values() for t in v}),
      })

    # Verify each parsed record independently with cross-kaṇḍikā next_first_mark.
    kandika_map: dict[tuple[str, int], tuple[str | None, list[PadapathaItem]]] = {}
    accepted_entries: list[dict[str, Any]] = []

    for ent in parsed_entries:
      row_i = ent["row_i"]
      slot: _FileClusterSlot = ent["slot"]
      slot_idx: int = ent["slot_idx"]
      items: list[PadapathaItem] = ent["items"]
      errors: list[str] = list(ent["item_errs"])
      disagree_syls_out: list[dict[str, Any]] = []
      val_strs: list[str] = []
      rec_logs_out: list[str] = []

      if not errors:
        # 1. Unmapped syllables + leftover ŚB marks on built VP
        if ent["unmapped"]:
          errors.append(f"unmapped_vp_syllables: {ent['unmapped'][:6]}")
        if not ent["preserve_vp"] and _SB_MARKS_RE.search(ent["vp_acc"]):
          errors.append("leftover_sb_marks_in_vp")

        # 2. Forward-sandhi round-trip verification
        padas_ref = [it.ref for it in items]
        ok_vp, fail_i, win_vp, pref_vp = verify_mantra_sandhi(padas_ref, ent["vp_eval"])
        if not ok_vp:
          if ent["preserve_vp"] and ent["vp_clean"] is None:
            ok_w = verify_mantra_sandhi(padas_ref, slot.weber)[0] if slot.weber else False
            ok_s = verify_mantra_sandhi(padas_ref, slot.shri)[0] if slot.shri else False
            if not (ok_w or ok_s):
              bad_p = padas_ref[fail_i] if 0 <= fail_i < len(padas_ref) else "END"
              errors.append(f"sandhi_vp_fail: idx={fail_i} pada={bad_p!r} win={win_vp!r} pref={pref_vp!r}")
          else:
            bad_p = padas_ref[fail_i] if 0 <= fail_i < len(padas_ref) else "END"
            errors.append(f"sandhi_vp_fail: idx={fail_i} pada={bad_p!r} win={win_vp!r} pref={pref_vp!r}")

        # 3. Two-source ŚB audit with cross-kaṇḍikā boundary mark
        nxt_first = slot_first_marks[slot_idx + 1] if slot_idx + 1 < len(slots) else None
        rep = audit_padapatha_against_sb(
          ent["vp_eval"],
          items,
          slot.weber,
          slot.shri,
          next_first_mark=nxt_first,
        )
        if rep.unmapped_vp_syllables:
          errors.append(f"audit_unmapped: {rep.unmapped_vp_syllables[:6]}")
        if rep.unflagged_vyatyasta_padas:
          unflag_names = [f"{i}:{items[i].ref}" for i in rep.unflagged_vyatyasta_padas if i < len(items)]
          errors.append(f"unflagged_vyatyasta_padas: {unflag_names}")
        if rep.possibly_spurious_vyatyasta_padas:
          spur_names = [f"{i}:{items[i].ref}" for i in rep.possibly_spurious_vyatyasta_padas if i < len(items)]
          errors.append(f"spurious_vyatyasta_padas: {spur_names}")
        for s in rep.syllables:
          if s.status in ("both_disagree", "unaligned"):
            disagree_syls_out.append({
              "syl_idx": s.vp_syl_idx,
              "token": s.token,
              "us": s.us_mark,
              "exp_w": s.exp_weber,
              "exp_s": s.exp_shri,
              "act_w": s.act_weber,
              "act_s": s.act_shri,
              "padas": [items[pi].ref for pi in s.pada_indices if pi < len(items)],
            })

        # 4. Per-cluster validator + reconciler check
        pp_block = format_padapatha_block(items)
        snippet_vp_sum = slot.vp_summary if ent["preserve_vp"] else ent["vp_sum"]
        snippet_vp_body = slot.vp_body if ent["preserve_vp"] else ent["vp_acc"]
        snippet = _build_cluster_validation_snippet(
          slot,
          vp_summary=snippet_vp_sum,
          vp_body=snippet_vp_body,
          pp_block=pp_block,
        )
        v_issues = validate_accented_markdown(snippet)
        if v_issues:
          val_strs = [f"{iss.kind}: {iss.message} ({iss.line})" if iss.line else f"{iss.kind}: {iss.message}" for iss in v_issues]
          errors.append(f"validation_issues: {len(v_issues)}")
        if not ent["preserve_vp"]:
          rec_out, rec_logs = reconcile_markdown_blocks(snippet)
          if rec_logs or rec_out != snippet:
            rec_logs_out = rec_logs or ["reconciler modified snippet without logs"]
            errors.append(f"reconcile_diffs: {len(rec_logs_out)}")

      if errors:
        results_by_order[row_i] = AdjudicationRecordResult(
          kandika_id=ent["kid"],
          rel_path=rel_posix,
          heading=slot.heading,
          sub_idx=slot.sub_idx,
          status="REJECTED",
          applied=False,
          preserved_vp=ent["preserve_vp"],
          errors=errors,
          disagree_syllables=disagree_syls_out,
          validation_issues=val_strs,
          reconcile_logs=rec_logs_out,
        )
      else:
        kandika_map[(slot.heading, slot.sub_idx)] = (
          None if ent["preserve_vp"] else ent["vp_clean"],
          items,
        )
        accepted_entries.append(ent)

    if not kandika_map:
      continue

    # Apply all individually accepted records for this file atomically via apply_sb_kandika_updates(..., strict=True).
    try:
      upd_rep = apply_sb_kandika_updates(
        abs_path,
        kandika_map,
        preserve_existing_us=True,
        dry_run=dry_run,
        strict=True,
      )
      if upd_rep.wrote:
        files_written.append(rel_posix)
      for ent in accepted_entries:
        slot = ent["slot"]
        results_by_order[ent["row_i"]] = AdjudicationRecordResult(
          kandika_id=ent["kid"],
          rel_path=rel_posix,
          heading=slot.heading,
          sub_idx=slot.sub_idx,
          status="ACCEPTED",
          applied=upd_rep.wrote,
          preserved_vp=ent["preserve_vp"],
          errors=[],
          unverified_corpus_tags=ent["unverified"],
        )
    except Exception as exc:  # noqa: BLE001
      for ent in accepted_entries:
        slot = ent["slot"]
        results_by_order[ent["row_i"]] = AdjudicationRecordResult(
          kandika_id=ent["kid"],
          rel_path=rel_posix,
          heading=slot.heading,
          sub_idx=slot.sub_idx,
          status="REJECTED",
          applied=False,
          preserved_vp=ent["preserve_vp"],
          errors=[f"file_apply_failed: {exc}"],
        )

  final_records = [r for r in results_by_order if r is not None]
  n_acc = sum(1 for r in final_records if r.status == "ACCEPTED")
  n_rej = sum(1 for r in final_records if r.status == "REJECTED")
  return AdjudicationBatchReport(
    adj_jsonl_path=str(jsonl_path),
    dry_run=dry_run,
    total_records=len(final_records),
    accepted=n_acc,
    rejected=n_rej,
    files_written=files_written,
    records=final_records,
  )


# ---------------------------------------------------------------------------
# 3. Full Phase 4 corpus certification verifier
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SbKandikaAuditFailure:
  """One Phase 4 audit failure detected in a Śatapatha Brāhmaṇa Markdown file."""

  kandika_id: str
  rel_path: str
  heading: str
  sub_idx: int
  kind: str
  detail: str


@dataclasses.dataclass(frozen=True)
class SbCorpusAuditReport:
  """Complete Phase 4 certification report returned by :func:`audit_full_sb_corpus`."""

  sb_root: str
  files_scanned: int
  total_kandikas: int
  converted_kandikas: int
  unconverted_kandikas: int
  preserved_pratika_sb_marks: list[str]
  failures: list[SbKandikaAuditFailure]
  per_kanda: dict[str, dict[str, int]]
  preserved_us_notes: list[str] = dataclasses.field(default_factory=list)

  @property
  def passed(self) -> bool:
    return self.unconverted_kandikas == 0 and len(self.failures) == 0

  def to_dict(self) -> dict[str, Any]:
    return {
      "sb_root": self.sb_root,
      "passed": self.passed,
      "files_scanned": self.files_scanned,
      "total_kandikas": self.total_kandikas,
      "converted_kandikas": self.converted_kandikas,
      "unconverted_kandikas": self.unconverted_kandikas,
      "preserved_pratika_sb_marks": list(self.preserved_pratika_sb_marks),
      "preserved_us_notes": list(self.preserved_us_notes),
      "failure_count": len(self.failures),
      "failures": [dataclasses.asdict(f) for f in self.failures],
      "per_kanda": self.per_kanda,
    }


def audit_full_sb_corpus(
  sb_root: str | os.PathLike[str],
  *,
  kandas: Sequence[str | int] | None = None,
  files: Sequence[str | os.PathLike[str]] | None = None,
  preserved_kandika_ids: AbstractSet[str] | None = None,
) -> SbCorpusAuditReport:
  """Verify ŚB content files end-to-end against all Phase 4 certification criteria.

  Checks across every content ``.md`` file (skipping ``_index.md`` / ``file_list.md`` and pre-``##`` intros):
  (a) Zero leftover ŚB marks (``᳘``/``᳟``/``ॗ``) in US-accented ``विश्वास-प्रस्तुतिः`` blocks
      (recording untouched verbatim pre-existing pratīkas such as ``03/08/4.md::०६`` ``(र्मे᳘)`` separately).
  (b) Every US-accented kaṇḍikā has ``पद-पाठः (यान्त्रिकः...)`` placed immediately after its contiguous
      ``मूलम् - *`` run (and no misplaced stray ``पद-पाठः`` blocks).
  (c) ``validate_accented_markdown(text)`` returns 0 issues (auto-enforcing separated upasarga+tiṅanta
      and canonical ``पा॰`` abbreviation sign ``U+0970``).
  (d) Per-cluster ``reconcile_markdown_blocks`` returns 0 diffs (reporting verbatim pre-existing human US
      blocks listed in ``preserved_kandika_ids`` separately in ``preserved_us_notes``).
  (e) ``verify_mantra_sandhi`` passes on every converted VP with ``पद-पाठः`` (allowing ``Weber``/``Śrīdharādi``
      fallback only for verbatim ``preserved_kandika_ids`` containing editorial markup).
  (f) ``audit_padapatha_against_sb`` (with cross-kaṇḍikā ``next_first_mark``) has 0 unmapped syllables,
      0 unflagged *vyatyasta* padas, and 0 spurious *vyatyasta* padas, plus strict ``(N/P व्यत्यस्त-स्वराः)``
      VP summary matching and zero ``पा\\u0966`` / ``*CORPUS*-0`` occurrences.
  """
  root = Path(sb_root)
  if files is not None:
    target_files = [Path(f) for f in files]
  else:
    target_files = discover_sb_content_files(root, kandas=kandas)

  preserved_ids = frozenset(preserved_kandika_ids) if preserved_kandika_ids else frozenset()
  total_k = 0
  conv_k = 0
  unconv_k = 0
  pratika_notes: list[str] = []
  preserved_notes: list[str] = []
  failures: list[SbKandikaAuditFailure] = []
  per_kanda: dict[str, dict[str, int]] = {}

  for md_path in target_files:
    try:
      rel_posix = md_path.relative_to(root).as_posix()
    except ValueError:
      rel_posix = md_path.name
    ktag = _kanda_tag_for_rel(rel_posix)
    ks = per_kanda.setdefault(
      ktag,
      {"files": 0, "total": 0, "converted": 0, "unconverted": 0, "failures": 0},
    )
    ks["files"] += 1

    txt = md_path.read_text(encoding="utf-8")
    file_fail_start = len(failures)

    # (c) File-level validate_accented_markdown
    for iss in validate_accented_markdown(txt):
      failures.append(
        SbKandikaAuditFailure(
          kandika_id=rel_posix,
          rel_path=rel_posix,
          heading="",
          sub_idx=0,
          kind=f"validate:{iss.kind}",
          detail=f"{iss.message} | {iss.line}" if iss.line else iss.message,
        )
      )

    # Collect all section clusters in file order and check misplaced padapāṭha blocks per section.
    slots: list[_FileClusterSlot] = []
    for part in re.split(r"(?m)(?=^##\s+)", txt):
      m_hdr = re.match(r"^##\s+([^\n]+)", part)
      if not m_hdr:
        continue
      norm_hdr = re.sub(r"\s+", " ", m_hdr.group(1).strip())
      clusters = _extract_vp_clusters(part)
      all_pp_in_sec = [
        m for m in DETAILS_RE.finditer(part) if m.group(1).strip().startswith("पद-पाठः (यान्त्रिकः")
      ]
      matched_pp_spans = {
        (cl.existing_pp_match.start(), cl.existing_pp_match.end())
        for cl in clusters
        if cl.existing_pp_match is not None
      }
      if len(all_pp_in_sec) != len(matched_pp_spans):
        failures.append(
          SbKandikaAuditFailure(
            kandika_id=f"{rel_posix}::{norm_hdr}",
            rel_path=rel_posix,
            heading=norm_hdr,
            sub_idx=0,
            kind="misplaced_padapatha",
            detail=(
              f"section has {len(all_pp_in_sec)} पद-पाठः block(s), but only {len(matched_pp_spans)} "
              "placed immediately after contiguous मूलम् - *"
            ),
          )
        )
      for cl in clusters:
        vp_body = cl.vp_match.group(2).strip()
        slots.append(
          _FileClusterSlot(
            heading=norm_hdr,
            sub_idx=cl.subidx,
            vp_summary=cl.vp_match.group(1).strip(),
            vp_body=vp_body,
            is_already_us=has_us_accents(vp_body),
            weber=cl.weber_text,
            shri=cl.shri_text,
            has_pp=cl.existing_pp_match is not None,
            pp_body=cl.existing_pp_match.group(2).strip() if cl.existing_pp_match is not None else "",
            pp_raw=cl.existing_pp_match.group(0) if cl.existing_pp_match is not None else "",
          )
        )

    first_marks: list[str | None] = [
      (_first_us_mark(sl.vp_body) if sl.is_already_us else None) for sl in slots
    ]

    for idx, sl in enumerate(slots):
      total_k += 1
      ks["total"] += 1
      kid = f"{rel_posix}::{sl.heading}" + (f"#{sl.sub_idx}" if sl.sub_idx > 0 else "")
      is_preserved = kid in preserved_ids

      if not sl.is_already_us:
        unconv_k += 1
        ks["unconverted"] += 1
        continue

      conv_k += 1
      ks["converted"] += 1

      # (a) Check for leftover ŚB marks in converted विश्वास-प्रस्तुतिः
      if _SB_MARKS_RE.search(sl.vp_body):
        without_pratika = _PRATIKA_PAREN_RE.sub("", sl.vp_body)
        if _SB_MARKS_RE.search(without_pratika):
          failures.append(
            SbKandikaAuditFailure(
              kandika_id=kid,
              rel_path=rel_posix,
              heading=sl.heading,
              sub_idx=sl.sub_idx,
              kind="leftover_sb_marks",
              detail="US-accented विश्वास-प्रस्तुतिः still contains ŚB accent marks (᳘/᳟/ॗ) outside pratīka",
            )
          )
        else:
          pratikas = [m.group(0) for m in _PRATIKA_PAREN_RE.finditer(sl.vp_body) if _SB_MARKS_RE.search(m.group(0))]
          pratika_notes.append(f"{kid}: {pratikas}")

      # (b) Every US-accented kaṇḍikā must have पद-पाठः right after contiguous मूलम् - *
      if not sl.has_pp:
        failures.append(
          SbKandikaAuditFailure(
            kandika_id=kid,
            rel_path=rel_posix,
            heading=sl.heading,
            sub_idx=sl.sub_idx,
            kind="missing_padapatha",
            detail="US-accented kaṇḍikā missing पद-पाठः (यान्त्रिकः...) immediately after contiguous मूलम् - *",
          )
        )
        continue

      # Ensure 0 occurrences of digit-zero abbreviation पा\u0966 or zero corpus count *CORPUS*-0
      if "पा\u0966" in sl.vp_body or "पा\u0966" in sl.pp_body:
        failures.append(
          SbKandikaAuditFailure(
            kandika_id=kid,
            rel_path=rel_posix,
            heading=sl.heading,
            sub_idx=sl.sub_idx,
            kind="zero_abbrev_sign",
            detail="Found digit-zero पा\\u0966 instead of Devanagari abbreviation sign पा॰ (U+0970)",
          )
        )
      if _ZERO_CORPUS_COUNT_RE.search(sl.pp_body):
        failures.append(
          SbKandikaAuditFailure(
            kandika_id=kid,
            rel_path=rel_posix,
            heading=sl.heading,
            sub_idx=sl.sub_idx,
            kind="zero_corpus_count",
            detail="Found invalid *CORPUS*-0 occurrence count in पद-पाठः",
          )
        )

      items = parse_padapatha_items(sl.pp_body)
      if not items:
        failures.append(
          SbKandikaAuditFailure(
            kandika_id=kid,
            rel_path=rel_posix,
            heading=sl.heading,
            sub_idx=sl.sub_idx,
            kind="empty_padapatha",
            detail="पद-पाठः block contains 0 parsed items",
          )
        )
        continue

      # (d) Per-cluster reconcile_markdown_blocks
      snippet = _build_cluster_validation_snippet(
        sl,
        vp_summary=sl.vp_summary,
        vp_body=sl.vp_body,
        pp_block=sl.pp_raw or format_padapatha_block(items),
      )
      rec_out, rec_logs = reconcile_markdown_blocks(snippet)
      if rec_logs or rec_out != snippet:
        eff_logs = rec_logs or ["reconciler modified cluster without logs"]
        if is_preserved:
          preserved_notes.append(f"{kid}: reconcile_diff ({len(eff_logs)}): {eff_logs[0]}")
        else:
          for lg in eff_logs:
            failures.append(
              SbKandikaAuditFailure(
                kandika_id=kid,
                rel_path=rel_posix,
                heading=sl.heading,
                sub_idx=sl.sub_idx,
                kind="reconcile_diff",
                detail=lg,
              )
            )

      vp_for_audit = _vp_body_to_clean_for_audit(sl.vp_body)
      padas_ref = [it.ref for it in items]

      # (e) Forward-sandhi round-trip on VP (with Weber/Śrīdharādi fallback only for verbatim preserved human VPs)
      ok_vp, fail_i, win_vp, pref_vp = verify_mantra_sandhi(padas_ref, vp_for_audit)
      if not ok_vp:
        if is_preserved:
          ok_w = verify_mantra_sandhi(padas_ref, sl.weber)[0] if sl.weber else False
          ok_s = verify_mantra_sandhi(padas_ref, sl.shri)[0] if sl.shri else False
          if ok_w or ok_s:
            preserved_notes.append(f"{kid}: preserved editorial VP differs from padapāṭha (sandhi verified on mula)")
          else:
            bad_p = padas_ref[fail_i] if 0 <= fail_i < len(padas_ref) else "END"
            failures.append(
              SbKandikaAuditFailure(
                kandika_id=kid,
                rel_path=rel_posix,
                heading=sl.heading,
                sub_idx=sl.sub_idx,
                kind="sandhi_vp_fail",
                detail=f"idx={fail_i} pada={bad_p!r} win={win_vp!r} pref={pref_vp!r}",
              )
            )
        else:
          bad_p = padas_ref[fail_i] if 0 <= fail_i < len(padas_ref) else "END"
          failures.append(
            SbKandikaAuditFailure(
              kandika_id=kid,
              rel_path=rel_posix,
              heading=sl.heading,
              sub_idx=sl.sub_idx,
              kind="sandhi_vp_fail",
              detail=f"idx={fail_i} pada={bad_p!r} win={win_vp!r} pref={pref_vp!r}",
            )
          )

      # Strict VP summary `(N/P व्यत्यस्त-स्वराः)` check (catching bogus 0/P, wrong N/P, and missing N/P on newly converted VPs)
      m_vp_vyat = re.search(r"\((\d+)/(\d+)\s*व्यत्यस्त-स्वराः\)", sl.vp_summary)
      n_vyat_pp = sum(1 for it in items if it.vyat)
      if n_vyat_pp == 0 and m_vp_vyat:
        failures.append(
          SbKandikaAuditFailure(
            kandika_id=kid,
            rel_path=rel_posix,
            heading=sl.heading,
            sub_idx=sl.sub_idx,
            kind="vp_summary_vyatyasta_mismatch",
            detail=f"VP summary {sl.vp_summary!r} carries count when actual vyatyasta count is 0",
          )
        )
      elif n_vyat_pp > 0:
        if m_vp_vyat:
          if int(m_vp_vyat.group(1)) != n_vyat_pp or int(m_vp_vyat.group(2)) != len(items):
            failures.append(
              SbKandikaAuditFailure(
                kandika_id=kid,
                rel_path=rel_posix,
                heading=sl.heading,
                sub_idx=sl.sub_idx,
                kind="vp_summary_vyatyasta_mismatch",
                detail=f"VP summary {sl.vp_summary!r} != actual {n_vyat_pp}/{len(items)}",
              )
            )
        elif not is_preserved:
          failures.append(
            SbKandikaAuditFailure(
              kandika_id=kid,
              rel_path=rel_posix,
              heading=sl.heading,
              sub_idx=sl.sub_idx,
              kind="vp_summary_vyatyasta_mismatch",
              detail=f"VP summary {sl.vp_summary!r} missing ({n_vyat_pp}/{len(items)} व्यत्यस्त-स्वराः)",
            )
          )

      # (f) Two-source ŚB audit with cross-kaṇḍikā next_first_mark
      nxt_first = first_marks[idx + 1] if idx + 1 < len(slots) else None
      rep = audit_padapatha_against_sb(
        vp_for_audit,
        items,
        sl.weber,
        sl.shri,
        next_first_mark=nxt_first,
      )
      if is_preserved and rep.unmapped_vp_syllables and (sl.weber or sl.shri):
        fallback_vp = normalize_sb_orthography(sl.weber or sl.shri)
        rep = audit_padapatha_against_sb(
          fallback_vp,
          items,
          sl.weber,
          sl.shri,
          next_first_mark=nxt_first,
        )
        preserved_notes.append(f"{kid}: audited padapāṭha via normalized mula fallback for preserved editorial VP")
      if rep.unmapped_vp_syllables:
        failures.append(
          SbKandikaAuditFailure(
            kandika_id=kid,
            rel_path=rel_posix,
            heading=sl.heading,
            sub_idx=sl.sub_idx,
            kind="audit_unmapped",
            detail=f"{rep.unmapped_vp_syllables[:6]}",
          )
        )
      if rep.unflagged_vyatyasta_padas:
        unflag_names = [f"{i}:{items[i].ref}" for i in rep.unflagged_vyatyasta_padas if i < len(items)]
        failures.append(
          SbKandikaAuditFailure(
            kandika_id=kid,
            rel_path=rel_posix,
            heading=sl.heading,
            sub_idx=sl.sub_idx,
            kind="audit_unflagged_vyatyasta",
            detail=f"{unflag_names}",
          )
        )
      if rep.possibly_spurious_vyatyasta_padas:
        spur_names = [f"{i}:{items[i].ref}" for i in rep.possibly_spurious_vyatyasta_padas if i < len(items)]
        failures.append(
          SbKandikaAuditFailure(
            kandika_id=kid,
            rel_path=rel_posix,
            heading=sl.heading,
            sub_idx=sl.sub_idx,
            kind="audit_spurious_vyatyasta",
            detail=f"{spur_names}",
          )
        )

    ks["failures"] += len(failures) - file_fail_start

  return SbCorpusAuditReport(
    sb_root=str(root),
    files_scanned=len(target_files),
    total_kandikas=total_k,
    converted_kandikas=conv_k,
    unconverted_kandikas=unconv_k,
    preserved_pratika_sb_marks=pratika_notes,
    failures=failures,
    per_kanda=per_kanda,
    preserved_us_notes=preserved_notes,
  )


def _cli(argv: Sequence[str] | None = None) -> int:
  """CLI: ``python -m doc_curation.sanskrit.accent.shatapatha_batch {solve,apply,audit} ...`` (JSON on stdout)."""
  import argparse
  import sys

  ap = argparse.ArgumentParser(prog="shatapatha_batch", description=__doc__.splitlines()[0])
  sub = ap.add_subparsers(dest="cmd", required=True)

  p_solve = sub.add_parser("solve", help="run_solver_corpus_pass")
  p_solve.add_argument("sb_root")
  p_solve.add_argument("out_dir")
  p_solve.add_argument("--kandas", nargs="*", default=None)
  p_solve.add_argument("--apply-auto-clean", action="store_true")
  p_solve.add_argument("--max-workers", type=int, default=1)
  p_solve.add_argument(
    "--export-all", action="store_true", help="write AUTO_CLEAN drafts to the adjudication queue too (Phase 3 covers all)"
  )

  p_apply = sub.add_parser("apply", help="verify_and_apply_adjudications")
  p_apply.add_argument("sb_root")
  p_apply.add_argument("adj_jsonl")
  p_apply.add_argument("--dry-run", action="store_true")
  p_apply.add_argument("--no-enrich-counts", action="store_true")

  p_audit = sub.add_parser("audit", help="audit_full_sb_corpus")
  p_audit.add_argument("sb_root")
  p_audit.add_argument("--kandas", nargs="*", default=None)
  p_audit.add_argument("--files", nargs="*", default=None)
  p_audit.add_argument("--preserved-ids", default=None, help="corpus_summary.json (preserved_existing_us_ids) or newline list")

  a = ap.parse_args(argv)
  if a.cmd == "solve":
    out = run_solver_corpus_pass(
      a.sb_root,
      a.out_dir,
      kandas=a.kandas,
      apply_auto_clean=a.apply_auto_clean,
      max_workers=a.max_workers,
      export_all_to_adjudication=a.export_all,
    )
    json.dump({k: v for k, v in out.items() if k != "per_kanda"}, sys.stdout, ensure_ascii=False, indent=2)
    rc = 0
  elif a.cmd == "apply":
    rep = verify_and_apply_adjudications(
      a.sb_root, a.adj_jsonl, dry_run=a.dry_run, enrich_counts=not a.no_enrich_counts
    )
    json.dump(rep.to_dict(), sys.stdout, ensure_ascii=False, indent=2)
    rc = 0 if rep.rejected == 0 else 1
  else:
    pres: set[str] | None = None
    if a.preserved_ids:
      raw = Path(a.preserved_ids).read_text(encoding="utf-8")
      try:
        pres = set(json.loads(raw).get("preserved_existing_us_ids", []))
      except (json.JSONDecodeError, AttributeError):
        pres = {ln.strip() for ln in raw.splitlines() if ln.strip()}
    rep = audit_full_sb_corpus(a.sb_root, kandas=a.kandas, files=a.files, preserved_kandika_ids=pres)
    json.dump(rep.to_dict(), sys.stdout, ensure_ascii=False, indent=2)
    rc = 0 if rep.passed else 1
  sys.stdout.write("\n")
  return rc


if __name__ == "__main__":
  raise SystemExit(_cli())
