"""Harvest curated ``विश्वास-प्रस्तुतिः`` passages AND uncurated ``मूलम्`` passages
(for 14B QLoRA teacher pseudo-labeling) into SLP1 boundary-tagging JSONL files."""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import tomllib
from pathlib import Path
import regex

from doc_curation.sanskrit.hyphenator.lexicon import list_ramanujIya_source_files
from doc_curation.sanskrit.hyphenator.slp1_codec import encode_curated_sentence
from doc_curation.llm.proofreader.dataset.text_normalizer import (
  DETAILS_RE,
  MANIPRAVALA_RE,
  clean_prastuti_target,
  has_meaningful_prose_clause_breaks,
)

_EXTRA_CURATED_ROOTS = [
  "/home/vvasuki/gitland/vishvAsa/vedAH/content",
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content",
  "/home/vvasuki/gitland/vishvAsa/kAvyam/content",
  "/home/vvasuki/gitland/vishvAsa/kalpAntaram/content",
]
_UNCURATED_SEARCH_ROOTS = [
  "/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content",
  "/home/vvasuki/gitland/vishvAsa/advEtam/content",
  "/home/vvasuki/gitland/vishvAsa/kAvyam/content",
  "/home/vvasuki/gitland/vishvAsa/purANam/content",
  "/home/vvasuki/gitland/vishvAsa/vyAkaraNam/content",
  "/home/vvasuki/gitland/vishvAsa/nyAyaH/content",
]


def _load_heldout_reference_keys(hyp_toml_path: str) -> set[str]:
  with open(hyp_toml_path, "rb") as f:
    cfg = tomllib.load(f)
  keys: set[str] = set()
  for c in cfg.get("reference_sentences", {}).get("cases", []):
    norm = regex.sub(r"[\s\-–—]+", "", c["text"])
    if len(norm) >= 20:
      keys.add(norm[:40])
  return keys


def _collect_curated_files() -> list[str]:
  """Use ONLY the curated hyphenated rAmAnujIya corpus (``rAmAnujIya-sources.toml``)
  so unhyphenated Vedic mantra repositories never dilute compound-hyphen supervision."""
  seen = set()
  files: list[str] = []
  for fp in list_ramanujIya_source_files():
    if os.path.isfile(fp) and fp not in seen:
      seen.add(fp)
      files.append(fp)
  return files


def _extract_curated_paragraphs(md_path: str, heldout_keys: set[str]) -> list[str]:
  try:
    text = Path(md_path).read_text(encoding="utf-8")
  except OSError:
    return []
  if "[यान्त्रिकम्]" in text[:600]:
    return []
  blocks = [
    m.group(2) for m in DETAILS_RE.finditer(text)
    if m.group(1).strip().startswith(("विश्वास-प्रस्तुतिः", "विश्वास-टिप्पनी")) and "यान्त्रिक" not in m.group(1)
  ]
  if not blocks and "<details" not in text:
    blocks = [text]
  out: list[str] = []
  for body in blocks:
    cleaned = clean_prastuti_target(body)
    if not cleaned or MANIPRAVALA_RE.search(cleaned):
      continue
    for para in regex.split(r"\n\s*\n+", cleaned):
      p = para.strip()
      if len(p) < 10 or len(p) > 850:
        continue
      # Skip paragraphs that appear unhyphenated (long >=22-char plain Devanāgarī words with zero hyphens in para)
      if "-" not in p and "–" not in p and any(len(w) >= 22 for w in regex.findall(r"[\u0900-\u097f]+", p)):
        continue
      norm_key = regex.sub(r"[\s\-–—]+", "", p)
      if any(hk in norm_key for hk in heldout_keys):
        continue
      out.append(p)
  return out


def _collect_uncurated_for_teacher(max_passages: int, rng: random.Random) -> list[str]:
  """Gather clean uncurated Sanskrit sentences/paragraphs (no ``विश्वास-प्रस्तुतिः``)
  for ``Qwen3-14B + LoRA`` teacher pseudo-labeling on Kaggle GPU."""
  cand_files: list[str] = []
  for root in _UNCURATED_SEARCH_ROOTS:
    if os.path.isdir(root):
      cand_files.extend(
        fp for fp in glob.glob(os.path.join(root, "**", "*.md"), recursive=True)
        if not fp.endswith("_index.md")
      )
  rng.shuffle(cand_files)
  passages: list[str] = []
  seen: set[str] = set()
  for fp in cand_files:
    if len(passages) >= max_passages:
      break
    try:
      txt = Path(fp).read_text(encoding="utf-8")
    except OSError:
      continue
    if "विश्वास-प्रस्तुतिः" in txt or MANIPRAVALA_RE.search(txt):
      continue
    # Pull clean मूलम् blocks or bare Devanāgarī paragraphs
    blocks = [m.group(2) for m in DETAILS_RE.finditer(txt) if m.group(1).strip().startswith("मूलम्")]
    if not blocks:
      blocks = [txt]
    for blk in blocks:
      for para in regex.split(r"\n\s*\n+", blk):
        p = regex.sub(r"\s+", " ", para).strip()
        if not (35 <= len(p) <= 380):
          continue
        if "<" in p or "[" in p or "#" in p or "+" in p:
          continue
        dev_n = len(regex.findall(r"[\u0905-\u0939]", p))
        if dev_n < len(p) * 0.55:
          continue
        # Prefer passages with compound-length words (>= 14 chars) so teacher distillation adds high value
        if not any(len(w) >= 14 for w in p.split()):
          continue
        if p not in seen:
          seen.add(p)
          passages.append(p)
          if len(passages) >= max_passages:
            break
  return passages


def build_distillation_dataset(
  out_dir: str,
  *,
  max_train_examples: int = 38000,
  max_eval_examples: int = 1500,
  max_teacher_passages: int = 900,
  seed: int = 42,
) -> dict:
  rng = random.Random(seed)
  out = Path(out_dir)
  out.mkdir(parents=True, exist_ok=True)

  hyp_toml = str(
    Path(__file__).resolve().parents[1] / "data" / "vocabulary" / "hyphenations.toml"
  )
  heldout_keys = _load_heldout_reference_keys(hyp_toml)

  all_files = _collect_curated_files()
  rng.shuffle(all_files)
  n_eval_files = max(15, int(len(all_files) * 0.06))
  eval_files = set(all_files[:n_eval_files])

  train_recs: list[dict] = []
  eval_recs: list[dict] = []

  for fp in all_files:
    is_eval = fp in eval_files
    paras = _extract_curated_paragraphs(fp, heldout_keys)
    for p in paras:
      has_cl = has_meaningful_prose_clause_breaks(p)
      # Augment rich compounds / lost-avagraha / endash paragraphs in train
      n_aug = 1 if is_eval else (4 if ("ऽर्" in p or " ऽर्" in p) else (2 if ("–" in p or "-" in p or has_cl) else 1))
      for _ in range(n_aug):
        enc = encode_curated_sentence(p, rng, has_clause_breaks=has_cl)
        if enc is None or len(enc[0]) > 510:
          continue
        rec = {"slp": enc[0], "sep": enc[1], "clause": enc[2], "has_clause": int(has_cl)}
        if is_eval:
          if len(eval_recs) < max_eval_examples:
            eval_recs.append(rec)
        else:
          train_recs.append(rec)

      # Also sample isolated 1–3 word snippets from training paragraphs so single-word
      # inputs (`hyphene("मध्वरिः")`, `hyphene("रामोर्थः")`, `hyphene("जगत्कारणम्")`) match
      # full-sentence accuracy without length/punctuation bias!
      if not is_eval:
        words = [w.strip("।॥,;.?!()\"") for w in regex.split(r"\s+", p) if w.strip("।॥,;.?!()\"")]
        for idx_w, w in enumerate(words):
          is_interesting = ("-" in w or "–" in w or "ऽ" in w or len(w) >= 8)
          if is_interesting and rng.random() < 0.35:
            span_w = " ".join(words[idx_w:min(len(words), idx_w + rng.choice((1, 1, 2)))])
            enc_w = encode_curated_sentence(span_w, rng, has_clause_breaks=False)
            if enc_w is not None and 4 <= len(enc_w[0]) <= 120:
              train_recs.append({"slp": enc_w[0], "sep": enc_w[1], "clause": enc_w[2], "has_clause": 0})

  rng.shuffle(train_recs)
  if len(train_recs) > max_train_examples:
    train_recs = train_recs[:max_train_examples]

  teacher_passages = _collect_uncurated_for_teacher(max_teacher_passages, rng)

  with open(out / "train_slp1.jsonl", "w", encoding="utf-8") as f:
    for r in train_recs:
      f.write(json.dumps(r, ensure_ascii=False) + "\n")
  with open(out / "eval_slp1.jsonl", "w", encoding="utf-8") as f:
    for r in eval_recs:
      f.write(json.dumps(r, ensure_ascii=False) + "\n")
  with open(out / "uncurated_for_teacher.jsonl", "w", encoding="utf-8") as f:
    for p in teacher_passages:
      f.write(json.dumps({"text": p}, ensure_ascii=False) + "\n")

  import shutil
  shutil.copy2(hyp_toml, out / "hyphenations.toml")

  manifest = {
    "curated_files_scanned": len(all_files),
    "train_slp1_examples": len(train_recs),
    "eval_slp1_examples": len(eval_recs),
    "uncurated_teacher_passages": len(teacher_passages),
  }
  (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
  return manifest


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--out-dir", required=True)
  ap.add_argument("--max-train", type=int, default=38000)
  ap.add_argument("--max-teacher", type=int, default=900)
  args = ap.parse_args()
  stats = build_distillation_dataset(
    args.out_dir, max_train_examples=args.max_train, max_teacher_passages=args.max_teacher
  )
  print(json.dumps(stats, indent=2))


if __name__ == "__main__":
  main()
