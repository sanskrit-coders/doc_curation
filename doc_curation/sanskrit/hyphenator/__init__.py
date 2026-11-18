"""Distilled local SLP1 Sanskrit hyphenator (replacing the legacy trie hyphenator).

Public entry points:
- ``hyphene(text, show_progress=False, *, clause_newlines=False)``
  (aliased as ``hyphen``, ``hyphenate``, ``hyphenate_text``)
- ``hyphenate_word(word)``
"""
from __future__ import annotations

import regex
from indic_transliteration import sanscript

from .lexicon import (
  DATA_DIR,
  RA_SOURCES_TOML,
  is_merger_veto_slp1,
  is_valid_member_slp1,
  list_ramanujIya_source_files,
  restore_left_member_slp1,
  word_count_slp1,
)
from .neural_slp1 import (
  DEFAULT_LOCAL_HYPHENATOR_DIR,
  is_neural_hyphenator_available,
  neural_hyphene,
  predict_slp1_tags,
  resolve_onnx_model_path,
)


def _fallback_lexicon_split_word(word: str) -> str:
  """Minimal fallback used ONLY if ``hyphenator_slp1.onnx`` is not yet on disk."""
  if not word or len(word) < 4 or any(s in word for s in ("-", "–", "—")):
    return word
  slp = sanscript.transliterate(word, sanscript.DEVANAGARI, sanscript.SLP1)
  if word_count_slp1(slp) >= 8:
    return word
  for cut in range(3, len(slp) - 1):
    l_s, r_s = slp[:cut], slp[cut:]
    if l_s[-1] in "AIUFXeEoO" and is_merger_veto_slp1(slp, cut - 1):
      continue
    if not is_valid_member_slp1(r_s, is_right=True):
      continue
    if l_s[-1] in "myvrsSzdcjgt" and any(word_count_slp1(c) >= 4 for c in restore_left_member_slp1(l_s)):
      if l_s[-1] in "yv" and r_s[0] not in "aAiIuUfFeEoO":
        continue
      sep = " " if l_s[-1] == "m" or r_s in ("ca", "eva", "iti", "api", "tu", "hi") else "-"
      return sanscript.transliterate(l_s, sanscript.SLP1, sanscript.DEVANAGARI) + sep + sanscript.transliterate(r_s, sanscript.SLP1, sanscript.DEVANAGARI)
    if l_s[-1] in "aAiIuU" and r_s[0] not in "aAiIuUfFeEoO" and word_count_slp1(l_s) >= 4:
      return sanscript.transliterate(l_s, sanscript.SLP1, sanscript.DEVANAGARI) + "-" + sanscript.transliterate(r_s, sanscript.SLP1, sanscript.DEVANAGARI)
  return word


def hyphenate_word(word: str) -> str:
  """Hyphenate a single Devanāgarī word (idempotent)."""
  if not word or len(word) < 2:
    return word
  if is_neural_hyphenator_available():
    return neural_hyphene(word, clause_newlines=False)
  return _fallback_lexicon_split_word(word)


def hyphene(text: str, show_progress: bool = False, *, clause_newlines: bool = False) -> str:
  """Hyphenate Sanskrit / mixed Markdown text using the distilled local SLP1 ONNX model."""
  del show_progress
  if not text:
    return text
  if is_neural_hyphenator_available():
    return neural_hyphene(text, clause_newlines=clause_newlines)
  masks: dict[str, str] = {}

  def _m(m):
    k = f"§§A{len(masks)}§§"
    masks[k] = m.group(0)
    return k

  masked = regex.sub(r"\+\+\+\(.*?\)\+\+\+", _m, text, flags=regex.DOTALL)
  out = regex.sub(r"[\u0900-\u0963\u0966-\u097f\-–—]+", lambda m: _fallback_lexicon_split_word(m.group(0)), masked)
  for k, v in masks.items():
    out = out.replace(k, v)
  return out


hyphen = hyphene
hyphenate = hyphene
hyphenate_text = hyphene

__all__ = [
  "DATA_DIR",
  "DEFAULT_LOCAL_HYPHENATOR_DIR",
  "RA_SOURCES_TOML",
  "hyphen",
  "hyphenate",
  "hyphenate_text",
  "hyphenate_word",
  "hyphene",
  "is_neural_hyphenator_available",
  "list_ramanujIya_source_files",
  "neural_hyphene",
  "predict_slp1_tags",
  "resolve_onnx_model_path",
]
