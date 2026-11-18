"""Instant mmap-backed Sanskrit lexicon helpers (`BytesTrie` in `<2 ms`, zero CPU grind).

Uses the compact vocabulary tries (`padas.trie`, `nominal-stems.trie`, `verb-stems.trie`,
`avyayas.trie`, `dcs-stems.trie`) and `misc-vocab.toml` to support:
1. Microsecond dictionary-backed *dīrgha/guṇa/vṛddhi* merger veto in `slp1_codec.py`
   (protecting inline mergers in the distilled local SLP1 neural hyphenator),
2. Samāsa & vowel-merger member decomposition in `doc_curation.sanskrit.accent.samasa`,
3. Corpus source listing from `rAmAnujIya-sources.toml`.

All obsolete non-LLM DP/n-gram/badsplit hyphenator code and `rAmAnujIya*.trie` files are gone.
"""
from __future__ import annotations

import glob
import os
import struct
import tomllib
import marisa_trie

DATA_DIR = os.path.join(
  os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
  "data", "vocabulary", "sanskrit",
)
RA_SOURCES_TOML = os.path.join(DATA_DIR, "rAmAnujIya-sources.toml")
MISC_VOCAB_TOML = os.path.join(DATA_DIR, "misc-vocab.toml")

_SLP_TO_HK_MAP = {
  "K": "kh", "G": "gh", "N": "G", "C": "ch", "J": "jh", "Y": "J",
  "w": "T", "W": "Th", "q": "D", "Q": "Dh", "R": "N",
  "T": "th", "D": "dh", "P": "ph", "B": "bh",
  "S": "z", "z": "S", "f": "R", "F": "RR", "x": "lR", "X": "lRR",
  "E": "ai", "O": "au", "Z": "'",
}

_TRIES: dict[str, marisa_trie.BytesTrie] | None = None
_CLOSED_SLP: frozenset[str] | None = None

_MERGER_EXPS_SLP: dict[str, tuple[tuple[str, str], ...]] = {
  "A": (("a", "a"), ("a", "A"), ("A", "a"), ("A", "A")),
  "I": (("i", "i"), ("i", "I"), ("I", "i"), ("I", "I")),
  "U": (("u", "u"), ("u", "U"), ("U", "u"), ("U", "U")),
  "F": (("f", "f"),),
  "e": (("a", "i"), ("a", "I"), ("A", "i"), ("A", "I")),
  "o": (("a", "u"), ("a", "U"), ("A", "u"), ("A", "U")),
  "E": (("a", "e"), ("a", "E"), ("A", "e"), ("A", "E")),
  "O": (("a", "o"), ("a", "O"), ("A", "o"), ("A", "O")),
}
_INFLECTED_TAILS_SLP = (
  "am", "aM", "aH", "ena", "eRa", "Aya", "At", "Ad", "asya", "e", "O", "AH",
  "An", "EH", "eByaH", "ezu", "AnAm", "ARAm", "A", "Am", "AM", "ayA", "AbhiH",
  "ABiH", "Asu", "iH", "im", "inA", "aye", "eH", "ayaH", "In", "iBiH",
  "InAm", "uH", "um", "unA", "ave", "oH", "avaH", "Un", "uBiH", "UnAm",
  "tA", "tva", "tvam", "tvaM", "tvena", "tvAt", "tvAd",
)


def slp1_to_hk(slp: str) -> str:
  return "".join(_SLP_TO_HK_MAP.get(ch, ch) for ch in slp)


def _get_tries() -> dict[str, marisa_trie.BytesTrie]:
  global _TRIES
  if _TRIES is not None:
    return _TRIES
  loaded: dict[str, marisa_trie.BytesTrie] = {}
  for name in ("padas", "nominal-stems", "verb-stems", "avyayas", "dcs-stems"):
    fp = os.path.join(DATA_DIR, f"{name}.trie")
    if os.path.isfile(fp):
      t = marisa_trie.BytesTrie()
      t.load(fp)
      loaded[name] = t
  _TRIES = loaded
  return loaded


def word_count_slp1(slp_w: str) -> int:
  """Return combined attestation score across vocabulary tries in O(len(word)) time."""
  if not slp_w:
    return 0
  if slp_w in load_closed_slp1():
    return 50
  hk = slp1_to_hk(slp_w)
  total = 0
  for name, tr in _get_tries().items():
    vals = tr.get(hk)
    if vals:
      c = struct.unpack("<H", vals[0][:2])[0] if len(vals[0]) >= 2 else 1
      total += c * (3 if name == "dcs-stems" else 1)
  return total


def list_ramanujIya_source_files() -> list[str]:
  if not os.path.isfile(RA_SOURCES_TOML):
    return []
  with open(RA_SOURCES_TOML, "rb") as f:
    cfg = tomllib.load(f)
  out: list[str] = []
  for entry in cfg.get("source", ()):
    p = entry["path"]
    if os.path.isfile(p) and not p.endswith("_index.md"):
      out.append(p)
    elif os.path.isdir(p):
      out.extend(
        fp for fp in sorted(glob.glob(os.path.join(p, "**", "*.md"), recursive=True))
        if not fp.endswith("_index.md")
      )
  return out


def load_closed_slp1() -> frozenset[str]:
  global _CLOSED_SLP
  if _CLOSED_SLP is not None:
    return _CLOSED_SLP
  from indic_transliteration import sanscript
  items: set[str] = {"a", "an", "su", "dus", "dur", "duz", "duS", "na", "ca", "vA", "eva", "iti", "api", "hi", "tu"}
  if os.path.isfile(MISC_VOCAB_TOML):
    with open(MISC_VOCAB_TOML, "rb") as f:
      cfg = tomllib.load(f)
    for k in ("upasargas", "pronouns"):
      for hk_w in cfg.get(k, ()):
        items.add(sanscript.transliterate(hk_w, sanscript.HK, sanscript.SLP1))
  _CLOSED_SLP = frozenset(items)
  return _CLOSED_SLP


def stem_base_slp1(slp_w: str) -> str | None:
  for tail in _INFLECTED_TAILS_SLP:
    if slp_w.endswith(tail) and len(slp_w) >= len(tail) + 2:
      pre = slp_w[:-len(tail)]
      for fin in ("a", "A", "i", "I", "u", "U", ""):
        cand = pre + fin
        if len(cand) >= 2 and word_count_slp1(cand) >= 2:
          return cand
  return None


def is_valid_member_slp1(slp_w: str, *, is_right: bool = False) -> bool:
  if not slp_w or len(slp_w) < 2:
    return False
  if slp_w in load_closed_slp1() or word_count_slp1(slp_w) >= 2:
    return True
  return bool(is_right and stem_base_slp1(slp_w) is not None)


def restore_left_member_slp1(slp_left: str) -> list[str]:
  cands: list[str] = []
  if slp_left.endswith("y") and len(slp_left) >= 2:
    cands.extend((slp_left[:-1] + "i", slp_left[:-1] + "I"))
  elif slp_left.endswith("v") and len(slp_left) >= 2:
    cands.extend((slp_left[:-1] + "u", slp_left[:-1] + "U"))
  elif slp_left.endswith(("r", "s", "S", "z")) and len(slp_left) >= 3:
    cands.append(slp_left[:-1] + "H")
  elif slp_left.endswith("o") and len(slp_left) >= 3:
    cands.append(slp_left[:-1] + "aH")
  elif slp_left.endswith(("d", "j", "c", "l")) and len(slp_left) >= 3:
    cands.append(slp_left[:-1] + "t")
  elif slp_left.endswith("g") and len(slp_left) >= 3:
    cands.append(slp_left[:-1] + "k")
  out = [c for c in cands if is_valid_member_slp1(c, is_right=True)]
  if word_count_slp1(slp_left) >= 1:
    out.append(slp_left)
  return list(dict.fromkeys(out or [slp_left]))


def split_vowel_merger_slp1(slp_w: str) -> list[tuple[str, str]]:
  if len(slp_w) < 5:
    return []
  scored: list[tuple[int, str, str]] = []
  for p in range(1, len(slp_w) - 1):
    exps = _MERGER_EXPS_SLP.get(slp_w[p])
    if not exps:
      continue
    l_pre, r_rest = slp_w[:p], slp_w[p + 1:]
    for lv, rv in exps:
      lu, ru = l_pre + lv, rv + r_rest
      if is_valid_member_slp1(lu, is_right=False) and is_valid_member_slp1(ru, is_right=True):
        sc = min(word_count_slp1(lu), 50) + min(word_count_slp1(ru), 50)
        scored.append((sc, lu, ru))
  scored.sort(key=lambda t: (-t[0], len(t[1])))
  seen: set[tuple[str, str]] = set()
  out: list[tuple[str, str]] = []
  for _, lu, ru in scored:
    if (lu, ru) not in seen:
      seen.add((lu, ru))
      out.append((lu, ru))
  return out[:2]


def is_merger_veto_slp1(slp_tok: str, pos: int) -> bool:
  if pos < 1 or pos >= len(slp_tok) - 1:
    return False
  exps = _MERGER_EXPS_SLP.get(slp_tok[pos])
  if not exps:
    return False
  left_full, right_raw, l_pre = slp_tok[:pos + 1], slp_tok[pos + 1:], slp_tok[:pos]
  for lv, rv in exps:
    lu, ru = l_pre + lv, rv + right_raw
    if is_valid_member_slp1(lu, is_right=False) and is_valid_member_slp1(ru, is_right=True):
      if word_count_slp1(left_full) >= 6 and is_valid_member_slp1(right_raw, is_right=True) and word_count_slp1(lu) < 10:
        continue
      return True
  return False
