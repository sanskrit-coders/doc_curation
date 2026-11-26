"""Reusable batch runner and CLI for backfilling Vedic corpus counts into ``पद-पाठः (यान्त्रिकः)`` blocks.

Wraps :func:`doc_curation.sanskrit.accent.provenance.backfill_corpora_in_padapatha_markdown` with:
- single-pass directory traversal across one or more target roots (respecting ``skip_js_includes``),
- pre-write structural invariants (balanced ``<details>`` tags, optional self-citation guard,
  no newly introduced bare ``*CORPUS*`` or ``*-0`` tags),
- optional transitive ``js_include`` prefill propagation via
  :func:`doc_curation.md.content_processor.include.transformer.surgical_prefill_transitive`.

Example CLI invocation::

  ~/gitland/python_venv/bin/python -m doc_curation.sanskrit.accent.backfill \\
    --dir /home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/maitrAyaNIyam/saMhitA/sarva-prastutiH \\
    --corpora KS --forbid-self MS
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import os
import re
from typing import Sequence

from doc_curation.md.content_processor.include import transformer as include_transformer
from doc_curation.sanskrit.accent.provenance import (
  CORPUS_TAGS,
  VedicCorpusCounter,
  backfill_corpora_in_padapatha_markdown,
)
from doc_curation.sanskrit.accent.reconciler import LEAF_DETAILS_RE, find_js_include_spans
from doc_curation.sanskrit.accent.validator import validate_padapatha_block

_PROVENANCE_ERROR_KINDS = frozenset({
  "uncounted_corpus_tag",
  "zero_corpus_count",
  "forbidden_corpus_tag",
  "zero_abbrev_sign",
})


@dataclasses.dataclass
class BackfillStats:
  """Summary metrics for a batch corpus backfill run."""

  scanned: int = 0
  modified: int = 0
  lines_changed: int = 0
  self_cite_hits: int = 0
  bad_tag_hits: int = 0
  unbalanced_hits: int = 0
  provenance_error_hits: int = 0
  modified_files: list[str] = dataclasses.field(default_factory=list)
  refreshed_containers: list[str] = dataclasses.field(default_factory=list)
  warnings: list[str] = dataclasses.field(default_factory=list)


def _iter_markdown_files(root_dirs: Sequence[str]) -> list[str]:
  files: list[str] = []
  seen: set[str] = set()
  for root in root_dirs:
    abs_root = os.path.abspath(root)
    if os.path.isfile(abs_root) and abs_root.endswith(".md"):
      if abs_root not in seen:
        seen.add(abs_root)
        files.append(abs_root)
      continue
    for fp in sorted(glob.glob(os.path.join(abs_root, "**", "*.md"), recursive=True)):
      if not os.path.isfile(fp) or os.path.basename(fp) in ("_index.md", "file_list.md"):
        continue
      if fp not in seen:
        seen.add(fp)
        files.append(fp)
  return files


def backfill_corpora_in_directories(
  root_dirs: Sequence[str],
  corpora: Sequence[str],
  *,
  counter: VedicCorpusCounter | None = None,
  forbid_self_corpus: str | None = None,
  skip_js_includes: bool = True,
  prefill_roots: Sequence[str] = (),
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
  validate_modified: bool = True,
  dry_run: bool = False,
) -> BackfillStats:
  """Backfill ``corpora`` counts in mechanical ``पद-पाठः`` blocks under ``root_dirs``.

  Refuses to write any file whose ``<details>`` open/close balance changes or where a
  forbidden self-citation (``forbid_self_corpus``) would be introduced.
  When ``prefill_roots`` is non-empty and ``dry_run`` is ``False``, propagates updates
  across prefilled transitive ``js_include`` containers via ``surgical_prefill_transitive``.
  """
  if not corpora:
    raise ValueError("corpora must be non-empty")
  unknown = [c for c in corpora if c not in CORPUS_TAGS]
  if unknown:
    raise ValueError(f"Unknown corpus tag(s): {unknown}")
  if forbid_self_corpus and forbid_self_corpus in corpora:
    raise ValueError(f"Cannot backfill forbidden self-corpus {forbid_self_corpus!r}")

  vc = counter if counter is not None else VedicCorpusCounter.load_or_build()
  corpora_pat = "|".join(re.escape(c) for c in corpora)
  bare_target_re = re.compile(rf"\*(?:{corpora_pat})\*(?!-\d)")
  zero_target_re = re.compile(rf"\*(?:{corpora_pat})\*-0(?!/\d)")
  target_tag_tokens = tuple(f"*{c}*" for c in corpora)

  stats = BackfillStats()
  for fp in _iter_markdown_files(root_dirs):
    txt = open(fp, encoding="utf-8").read()
    if "पद-पाठः (यान्त्रिकः" not in txt:
      continue
    stats.scanned += 1
    updated = backfill_corpora_in_padapatha_markdown(
      txt, vc, corpora=corpora, skip_js_includes=skip_js_includes
    )
    if updated == txt:
      continue

    if updated.count("<details") != txt.count("<details") or updated.count("</details>") != txt.count("</details>"):
      stats.unbalanced_hits += 1
      stats.warnings.append(f"UNBALANCED {fp}")
      continue

    old_lines = txt.splitlines()
    new_lines = updated.splitlines()
    changed_pairs = [(a, b) for a, b in zip(old_lines, new_lines) if a != b]
    file_self_hit = False
    for old_l, new_l in changed_pairs:
      if forbid_self_corpus and f"*{forbid_self_corpus}*" in new_l and f"*{forbid_self_corpus}*" not in old_l:
        stats.self_cite_hits += 1
        file_self_hit = True
        stats.warnings.append(f"SELF({forbid_self_corpus}) {fp}: {new_l}")
      if (bare_target_re.search(new_l) and not bare_target_re.search(old_l)) or (
        zero_target_re.search(new_l) and not zero_target_re.search(old_l)
      ):
        stats.bad_tag_hits += 1
        stats.warnings.append(f"BADTAG {fp}: {new_l}")

    if file_self_hit:
      continue

    if validate_modified:
      inc = find_js_include_spans(updated) if skip_js_includes else []
      for m in LEAF_DETAILS_RE.finditer(updated):
        if inc and any(a <= m.start() < b for a, b in inc):
          continue
        hdr = m.group(1).strip()
        if hdr.startswith("पद-पाठः (यान्त्रिकः"):
          for err in validate_padapatha_block(hdr, m.group(2)):
            if err.kind in _PROVENANCE_ERROR_KINDS and any(tok in err.line for tok in target_tag_tokens):
              stats.provenance_error_hits += 1
              if len(stats.warnings) < 50:
                stats.warnings.append(f"PROV {fp}: {err.kind} | {err.line}")

    stats.lines_changed += len(changed_pairs)
    stats.modified += 1
    stats.modified_files.append(fp)
    if not dry_run:
      with open(fp, "w", encoding="utf-8") as fh:
        fh.write(updated)

  if prefill_roots and stats.modified_files and not dry_run:
    refreshed = include_transformer.surgical_prefill_transitive(
      list(prefill_roots),
      stats.modified_files,
      hugo_base_dir=hugo_base_dir,
      only_if_prefilled=True,
      require_balanced_tags=True,
    )
    stats.refreshed_containers = sorted(refreshed)

  return stats


def _build_arg_parser() -> argparse.ArgumentParser:
  p = argparse.ArgumentParser(
    description="Backfill Vedic corpus counts into mechanical पद-पाठः blocks and optionally refresh transitive js_include prefills."
  )
  p.add_argument("--dir", dest="dirs", action="append", required=True, help="Directory (or .md file) to backfill (repeatable).")
  p.add_argument("--corpora", nargs="+", required=True, help="Corpus tags to insert/update (e.g. KS MS).")
  p.add_argument("--forbid-self", default=None, help="Corpus tag forbidden from being introduced (e.g. MS when backfilling MS).")
  p.add_argument("--prefill-root", dest="prefill_roots", action="append", default=[], help="Container root(s) for surgical_prefill_transitive (repeatable).")
  p.add_argument("--hugo-base-dir", default="/home/vvasuki/gitland/vishvAsa", help="Hugo base directory for resolving root-relative js_include URLs.")
  p.add_argument("--include-js-includes", action="store_true", help="Also edit blocks inside js_include wrappers (default skips them).")
  p.add_argument("--no-validate", action="store_true", help="Skip per-block validator checks after backfill.")
  p.add_argument("--dry-run", action="store_true", help="Compute changes without writing files.")
  return p


def main(argv: Sequence[str] | None = None) -> int:
  args = _build_arg_parser().parse_args(argv)
  stats = backfill_corpora_in_directories(
    args.dirs,
    args.corpora,
    forbid_self_corpus=args.forbid_self,
    skip_js_includes=not args.include_js_includes,
    prefill_roots=args.prefill_roots,
    hugo_base_dir=args.hugo_base_dir,
    validate_modified=not args.no_validate,
    dry_run=args.dry_run,
  )
  print(
    f"scanned={stats.scanned} modified={stats.modified} lines={stats.lines_changed} "
    f"refreshed={len(stats.refreshed_containers)} self={stats.self_cite_hits} "
    f"badtag={stats.bad_tag_hits} unbal={stats.unbalanced_hits} prov_err={stats.provenance_error_hits}"
  )
  for w in stats.warnings[:20]:
    print("WARN:", w)
  return 0 if (stats.self_cite_hits == 0 and stats.bad_tag_hits == 0 and stats.unbalanced_hits == 0) else 1


if __name__ == "__main__":
  raise SystemExit(main())
