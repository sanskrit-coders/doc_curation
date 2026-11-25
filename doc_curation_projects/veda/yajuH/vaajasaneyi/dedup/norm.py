"""Text normalization and VS-K <-> VS-M chapter alignment constants for deduplication."""
from __future__ import annotations

import pathlib
import re

from doc_curation.sanskrit.accent.samhita_splitter import strip_vedic_accents

VSM_RK_DIR = pathlib.Path(
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/vAjasaneyam/mAdhyandinam/saMhitA/Rk"
)
VSM_YAJUH_DIR = pathlib.Path(
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/vAjasaneyam/mAdhyandinam/saMhitA/yajuH/sarva-prastutiH"
)
VSM_SARVA_DIR = pathlib.Path(
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/saMhitA/sarva-prastutiH"
)
VSK_SARVA_DIR = pathlib.Path(
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/kANvam/saMhitA/sarva-prastutiH"
)

STATIC_URL_RK_VP = "/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/Rk/vishvAsa-prastutiH"
STATIC_URL_RK_TK = "/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/Rk/sarvASh_TIkAH"
STATIC_URL_YAJUH = "/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/yajuH/sarva-prastutiH"

_VOWEL_JOIN_MAP: dict[str, str] = {
  "अ": "", "आ": "ा", "इ": "ि", "ई": "ी", "उ": "ु", "ऊ": "ू",
  "ऋ": "ृ", "ॠ": "ॄ", "ऌ": "ॢ", "ए": "े", "ऐ": "ै", "ओ": "ो", "औ": "ौ",
}
_INDEP_VOWELS = "अआइईउऊऋॠऌएऐओऔ"

_REPHA_DOUBLING_FOLDS: tuple[tuple[str, str], ...] = (
  ("र्द्ध", "र्ध"), ("र्त्थ", "र्थ"), ("र्म्म", "र्म"), ("र्य्य", "र्य"),
  ("र्व्व", "र्व"), ("र्त्त", "र्त"), ("र्च्च", "र्च"), ("र्ज्ज", "र्ज"),
  ("र्न्न", "र्न"), ("र्ग्घ", "र्घ"), ("र्ब्भ", "र्भ"),
)

# Empirically calibrated VS-K adhyāya -> expected VS-M adhyāya(s) for tie-breaking.
VSK_TO_VSM_CHAPTER: dict[int, tuple[int, ...]] = {
  1: (1,), 2: (2,), 3: (3,), 4: (4,), 5: (5,), 6: (6,), 7: (7,), 8: (8,), 9: (8, 9),
  10: (9,), 11: (10,), 12: (11,), 13: (12,), 14: (13,), 15: (14,), 16: (15,),
  17: (16,), 18: (17,), 19: (17, 18), 20: (18, 19), 21: (19,), 22: (20,),
  23: (21,), 24: (22,), 25: (23,), 26: (24,), 27: (25,), 28: (26,), 29: (27,),
  30: (28,), 31: (29,), 32: (33, 32), 33: (34, 33), 34: (30, 31),
  35: (31, 32, 35), 36: (36,), 37: (37,), 38: (38,), 39: (39,), 40: (40,),
}


def strip_trailing_refs(text: str) -> str:
  """Strip trailing kaṇḍikā/anuvāka numbers and punctuation without stripping pluta digits attached to words."""
  # Require trailing numbers to be preceded by space, paren, or danda so word-attached `हवि᳓ष्माँ२` stays intact.
  out = text.strip()
  prev = None
  while out != prev:
    prev = out
    out = re.sub(
      r"(?:(?<=[।॥\s\)])\(\s*[०-९\d]+\s*\)|[।॥]+\s*[०-९\d]+\s*[।॥]*|(?<=[।॥\s])[०-९\d]+\s*[।॥]*|^\s*[०-९\d]+\s*[।॥]*)$",
      "",
      out,
    ).rstrip()
    out = re.sub(r"[।॥\s]+$", "", out)
  return out


def normalize_phonetic(
  text: str,
  *,
  include_accents: bool = False,
  fold_orthography: bool = True,
) -> str:
  """Normalize Vedic text for pāṭha comparison ignoring numbers, spacing, hyphens, and avagraha spelling."""
  cleaned = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]", "", text, flags=re.S)
  cleaned = strip_trailing_refs(cleaned)
  if not include_accents:
    cleaned = strip_vedic_accents(cleaned)
  # Remove markup, punctuation, whitespace, hyphens (preserve ऽ temporarily and internal pluta २/३).
  cleaned = re.sub(r"[\*\.,\!\?\|\-—–\s\(\)।॥]+", "", cleaned)
  # VS-M writes `ऽअ`/`ऽआ`, while VS-K writes `ऽ` after `े`/`ो`; equalize both to vowel or hiatus-free.
  cleaned = re.sub(rf"([ेो]़?[᳓᳙\u0951\u0952]?)ऽ(?![{_INDEP_VOWELS}])", r"\1अ", cleaned)
  cleaned = cleaned.replace("ऽ", "")
  cleaned = re.sub(rf"्([{_INDEP_VOWELS}])", lambda m: _VOWEL_JOIN_MAP[m.group(1)], cleaned)
  if fold_orthography:
    for src, dst in _REPHA_DOUBLING_FOLDS:
      cleaned = cleaned.replace(src, dst)
  if include_accents:
    cleaned = re.sub(r"[᳓\u0951]", "U", cleaned)
    cleaned = re.sub(r"[᳙\u0952]", "S", cleaned)
  return cleaned


def is_no_patha_bheda(vp_a: str, vp_b: str) -> bool:
  """Return True iff two US-accented passages match cleanly in both reading and US accents."""
  return normalize_phonetic(vp_a, include_accents=True, fold_orthography=True) == normalize_phonetic(
    vp_b, include_accents=True, fold_orthography=True
  )


def chapter_distance(vsk_ch: int, vsm_ch: int) -> int:
  """Return minimum adhyāya distance from a VS-K chapter using calibrated recension alignment."""
  targets = VSK_TO_VSM_CHAPTER.get(vsk_ch, (vsk_ch,))
  return min(abs(t - vsm_ch) for t in targets)
