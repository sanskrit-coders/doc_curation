"""Multi-task SFT dataset builder package for ``doc_curation.llm.proofreader``."""
from __future__ import annotations

import json
import os
import random
import tomllib

from doc_curation.sanskrit.hyphenator import constants as HC
from .interleave_extractor import (
  extract_commentary_interleaver_examples,
  extract_padapatha_examples,
  extract_translation_matcher_examples,
)
from .proofread_extractor import (
  extract_proofreading_examples,
  extract_structural_and_mixed_examples,
)
from .text_normalizer import clean_prastuti_target, unsplit_sanskrit_to_raw

__all__ = [
  "build_sft_datasets",
  "clean_prastuti_target",
  "unsplit_sanskrit_to_raw",
]


def _collect_ra_files() -> tuple[list[str], list[str]]:
  with open(HC._RA_SOURCES_TOML, "rb") as f:
    cfg = tomllib.load(f)
  train_files, eval_files = [], []
  for src in cfg.get("source", ()):
    root, until = src["path"], src.get("until")
    if os.path.isfile(root) and os.path.basename(root) != "_index.md":
      train_files.append(root)
    elif os.path.isdir(root):
      for dp, dns, fns in os.walk(root):
        dns.sort()
        for fn in sorted(fns):
          if fn.endswith(".md") and fn != "_index.md":
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            (eval_files if (until and rel >= until) else train_files).append(full)
  return train_files, eval_files


def _collect_vedic_files(vedic_root: str) -> tuple[list[str], list[str]]:
  vedic_all: list[str] = []
  if os.path.isdir(vedic_root):
    for dp, dns, fns in os.walk(vedic_root):
      dns.sort()
      for fn in sorted(fns):
        if fn.endswith(".md") and fn != "_index.md":
          fp = os.path.join(dp, fn)
          try:
            head = open(fp, encoding="utf-8", errors="ignore").read(12000)
          except OSError:
            continue
          if any(k in head for k in ("पद-पाठः (यान्त्रिकः", "विनियोगः</summary>", "अवतारिका</summary>")):
            vedic_all.append(fp)
  split_pt = max(1, int(len(vedic_all) * 0.85))
  return vedic_all[:split_pt], vedic_all[split_pt:]


def build_sft_datasets(
  out_dir: str,
  *,
  seed: int = 42,
  vedic_root: str = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content",
) -> dict[str, int]:
  """Build ``train.jsonl`` and ``eval.jsonl`` under ``out_dir`` and return counts."""
  os.makedirs(out_dir, exist_ok=True)
  rng = random.Random(seed)
  ra_train, ra_eval = _collect_ra_files()
  vedic_train, vedic_eval = _collect_vedic_files(vedic_root)

  train_recs = (
    extract_proofreading_examples(
      ra_train, rng, max_vp_pairs=320, max_sug_blocks=850, max_clause_on=950, max_clause_off=200
    )
    + extract_structural_and_mixed_examples(ra_train, rng, limit=200)
    + extract_translation_matcher_examples(ra_train + vedic_train[:60], rng, limit=300)
    + extract_commentary_interleaver_examples(vedic_train + ra_train, rng, limit=220)
    + extract_padapatha_examples(vedic_train, rng, limit=160)
  )
  rng.shuffle(train_recs)

  eval_recs = (
    extract_proofreading_examples(
      ra_eval, rng, max_vp_pairs=40, max_sug_blocks=40, max_clause_on=40, max_clause_off=20
    )
    + extract_structural_and_mixed_examples(ra_eval, rng, limit=25)
    + extract_translation_matcher_examples(ra_eval + vedic_eval[:20], rng, limit=30)
    + extract_commentary_interleaver_examples(vedic_eval + ra_eval, rng, limit=25)
    + extract_padapatha_examples(vedic_eval, rng, limit=25)
  )

  for name, recs in (("train.jsonl", train_recs), ("eval.jsonl", eval_recs)):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
      for r in recs:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

  summary: dict[str, int] = {"train_total": len(train_recs), "eval_total": len(eval_recs)}
  for prefix, recs in (("train", train_recs), ("eval", eval_recs)):
    for r in recs:
      k = f"{prefix}_{r['task_type']}"
      summary[k] = summary.get(k, 0) + 1
  with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)
  return summary
