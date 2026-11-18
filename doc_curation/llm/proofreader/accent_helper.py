"""RAG-grounded Vedic ``पद-पाठः (यान्त्रिकः)`` helper for the ``/accenting`` skill.

Avoids memorizing huge accent dictionaries inside LoRA weights by looking up
candidate word accents from local Babylon dictionaries (``rv-padasvara-dev``,
``kyv-ts-padasvara``, ``av-padasvara``, ``mw-cologne``) in Python, decomposing
compounds and sandhi seams via ``doc_curation.sanskrit.accent.samasa`` (backed
by ``doc_curation.sanskrit.hyphenator``), computing the baseline
``accent.to_US_accents(mUlam)`` projection, asking the fine-tuned LLM to resolve
contextual pada splits & Pāṇinian vākya/samāsa-svara, and validating with
``doc_curation.sanskrit.accent.{sandhi_check, validator, reconciler}``.
"""
from __future__ import annotations

import os
import regex
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.accent.samasa import decompose_samasa_for_padasvara
from .prompts import PADAPATHA_ACCENT_SYSTEM_PROMPT

DEFAULT_DICT_ROOT = os.path.expanduser("~/gitland/sanskrit/raw_etexts/koshaH/indic-dict")

_PADASVARA_REL_PATHS = (
  ("RV", "kAvya/rv-padasvara-dev/rv-padasvara-dev.babylon"),
  ("TS", "kAvya/kyv-ts-padasvara/kyv-ts-padasvara.babylon"),
  ("AV", "kAvya/av-padasvara/av-padasvara.babylon"),
  ("MW", "sanskrit/sa-head/en-entries/mw-cologne/mw-cologne.babylon"),
)

_DICT_INDEX_CACHE: dict[str, dict[str, list[str]]] = {}


def _load_babylon_index(path: str, max_body_chars: int = 80) -> dict[str, list[str]]:
  """Build and cache a compact in-memory ``{bare_headword: [variant_snippet, ...]}`` index.

  For ``*padasvara*.babylon`` files, extracts the leading ``<sasvara> (<freq>)`` line
  (already sorted by descending attestation frequency in the Babylon file).
  """
  if path in _DICT_INDEX_CACHE:
    return _DICT_INDEX_CACHE[path]
  idx: dict[str, list[str]] = {}
  if not os.path.isfile(path):
    _DICT_INDEX_CACHE[path] = idx
    return idx
  is_padasvara = "padasvara" in os.path.basename(path)
  with open(path, encoding="utf-8", errors="ignore") as f:
    raw = f.read()
  for entry in raw.split("\n\n"):
    if entry.startswith("#"):
      continue
    head, _, body = entry.partition("\n")
    if not head or not body or head.startswith("#"):
      continue
    if "mw-cologne" in path and "॑" not in body and "\u1cd3" not in body:
      continue
    if is_padasvara:
      # First <br>-delimited segment has "<sasvara_word> (<freq>)"
      snippet = regex.sub(r"<[^>]+>", "", body.split("<br>")[0]).strip()[:max_body_chars]
    else:
      snippet = regex.sub(r"<[^>]+>", " ", body).strip()[:max_body_chars]
    for h in head.split("|"):
      h_clean = accent.strip_accents(h.rstrip("+").strip())
      if h_clean and len(idx.get(h_clean, ())) < 4:
        existing = idx.setdefault(h_clean, [])
        if snippet not in existing:
          existing.append(snippet)
  _DICT_INDEX_CACHE[path] = idx
  return idx


def _lookup_query(q: str, dict_root: str) -> str | None:
  tag_snippets = []
  for label, rel in _PADASVARA_REL_PATHS:
    dpath = os.path.join(dict_root, rel)
    found = _load_babylon_index(dpath).get(q)
    if found:
      limit = 3 if label != "MW" else 1
      tag_snippets.append(f"*{label}*: {', '.join(found[:limit])}")
  if tag_snippets:
    return f"- {q}: " + " | ".join(tag_snippets)
  return None


def retrieve_accent_candidates(
  mula_text: str,
  *,
  dict_root: str = DEFAULT_DICT_ROOT,
) -> list[str]:
  """Look up candidate lexical accents for whole tokens and samāsa/sandhi members."""
  bare = accent.strip_accents(mula_text)
  tokens = [
    t for t in regex.findall(r"[\u0900-\u0963\u0971-\u097f\-ऽ]+", bare) if len(t) >= 2
  ]
  seen_queries: set[str] = set()
  hits: list[str] = []

  for tok in tokens:
    clean_tok = tok.replace("-", "").replace("ऽ", "")
    # Priority 1: whole token & anusvāra/halant normalization
    whole_cands = [clean_tok]
    if clean_tok.endswith("म्") or clean_tok.endswith("ं"):
      whole_cands.append(clean_tok[:-2] if clean_tok.endswith("म्") else clean_tok[:-1])

    # Priority 2: hyphenator-backed samāsa & sandhi member decomposition
    member_cands = decompose_samasa_for_padasvara(tok)

    for q in whole_cands + member_cands:
      if q in seen_queries or len(q) < 2:
        continue
      seen_queries.add(q)
      hit = _lookup_query(q, dict_root)
      if hit:
        hits.append(hit)
      if len(hits) >= 40:
        return hits
  return hits


def format_padapatha_user_prompt(
  mula_text: str,
  *,
  commentary_text: str = "",
  translation_text: str = "",
  lexicon_hits: list[str] | None = None,
) -> str:
  """Construct the context-grounded user prompt for ``पद-पाठः (यान्त्रिकः)`` generation."""
  us_proj = accent.to_US_accents(mula_text.strip(), pauses=r"[।॥,;]+")
  parts = [
    f"मूलम्:\n{mula_text.strip()}",
    f"US-ACCENT PROJECTION OF मूलम्:\n{us_proj}",
  ]
  if translation_text and translation_text.strip():
    parts.append(f"TRANSLATION:\n{translation_text.strip()}")
  if commentary_text and commentary_text.strip():
    parts.append(f"COMMENTARY:\n{commentary_text.strip()[:2000]}")
  if lexicon_hits:
    parts.append("RETRIEVED LEXICON CANDIDATES:\n" + "\n".join(lexicon_hits[:40]))
  return "\n\n".join(parts)
