"""Phonemic Extended-SLP1 codec, alignment encoder, and BytesTrie-refined decoder
for the distilled local Sanskrit neural hyphenator."""
from __future__ import annotations

import random
import regex
from indic_transliteration import sanscript

from doc_curation.llm.proofreader.guards import (
  canonical_sandhi_skeleton,
  mask_protected_blocks,
  rejoin_merger_violations,
  restore_protected_blocks,
)

SLP1_CHARS = (
  "aAiIuUfFxXeEoOMH"
  "kKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzshL|"
  "Z'~0123456789"
  " -–।॥,;.?!\"()>"
)
# ``indic_transliteration`` used to encode avagraha as ``Z`` in SLP1 and switched to ``'``.
# The neural codec's alphabet (and thus its trained weights) keeps using ``Z``, so translate
# between the installed scheme's character and ``Z`` at the boundaries.
SLP1_AVAGRAHA = sanscript.transliterate("ऽ", sanscript.DEVANAGARI, sanscript.SLP1) or "Z"
_CODEC_AVAGRAHA = "Z"


def to_codec_slp1(text: str, from_scheme: str) -> str:
  """Transliterate *text* into the codec's SLP1 alphabet (avagraha always ``Z``)."""
  slp = sanscript.transliterate(text, from_scheme, sanscript.SLP1)
  if SLP1_AVAGRAHA != _CODEC_AVAGRAHA:
    slp = slp.replace(SLP1_AVAGRAHA, _CODEC_AVAGRAHA)
  return slp


def from_codec_slp1(slp: str, to_scheme: str) -> str:
  """Transliterate codec-SLP1 (avagraha ``Z``) into *to_scheme*."""
  if SLP1_AVAGRAHA != _CODEC_AVAGRAHA:
    slp = slp.replace(_CODEC_AVAGRAHA, SLP1_AVAGRAHA)
  return sanscript.transliterate(slp, sanscript.SLP1, to_scheme)


CHAR_TO_ID: dict[str, int] = {ch: idx + 2 for idx, ch in enumerate(SLP1_CHARS)}
VOCAB_SIZE = len(SLP1_CHARS) + 2

_SHORT_VOWELS = frozenset("aiufx")
_MERGED_VOWELS = frozenset("AIUFXeEoO")
_ALL_VOWELS = _SHORT_VOWELS | _MERGED_VOWELS
_SEMIVOWELS = frozenset("yrlvL")
_NASALS = frozenset("NYRnm")
_SIBILANTS = frozenset("Szsh")
_STOPS = frozenset("kKgGcCjJwWqQtTdDpPbB")
_HALANT_CODA_OK = frozenset("myvrsSzdcjgbRntkpl")
_BOUND_SUFFIXES = frozenset({
  "tva", "tvam", "tvaM", "tvAya", "tvena", "tvAt", "tvAd", "tve", "tvasya", "tvayoH",
  "tvAni", "tvAByAm", "tveByaH", "tvAnAm", "tvezu",
  "tA", "tAm", "tAyE", "tAyAH", "tAsu",
  "maya", "mayaH", "mayI", "mayam", "mayAm",
  "tama", "tamaH", "tamam", "tara", "taraH", "taram",
  "Dvam", "Dve", "DvaH", "sva", "zva", "masi", "taH", "tas", "Imahi", "Asam", "ate", "ati", "anti", "ante",
  "AnAH", "AnA", "AnAm", "Anas",
  "svantam", "svanto", "svantaH", "vantam", "vanto", "vantaH",
  "vatI", "vatIm", "vatIH", "matI", "matIm", "matIH", "tIH",
})
_CLITIC_HYPHEN_VETO = frozenset({"vas", "vaH", "nas", "naH"})
_VALID_TWO_CHAR_SPACE_WORDS = frozenset({"nu", "ko", "so", "sa", "yo", "ya", "vE"})
_UNHYPHENATABLE_RIGHT_PADAS = frozenset({
  "asi", "asmi", "asti", "sTa", "sTu", "astu", "santu", "vettu", "smArjmi",
  "CunDAmi", "pAhi", "Bava", "dehi", "DeHi", "vada", "yaja", "gacCa", "muYca",
})
_TIN_ANTI_VERBS = frozenset({
  "eti", "upEti", "paryeti", "aveti", "samaveti", "prEti", "aByeti", "anveti",
  "atyeti", "vyeti", "sameti", "punareti", "antareti", "apeti", "apyeti",
  "udeti", "pratyeti", "aDyeti", "Ayureti",
})
_COMPOUND_SINGLE_CHAR_RIGHT = frozenset({
  "ja", "jA", "jAH", "jam", "jaM", "da", "dA", "daH", "ga", "gA", "gaH", "vit", "jYa", "jYaM", "jYaH", "pAH", "kft", "BUH",
})
_VOICELESS_CONSONANTS = frozenset("kKcCwWtTpPSzs")
_R_STEM_WORDS = ("punar", "prAtar", "antar", "svar", "ahar")
_ACCENT_RE = regex.compile(r"[\u0951-\u0954\u1cd0-\u1cff]")
_ANNO_RE = regex.compile(r"\+\+\+\(.*?\)\+\+\+", regex.DOTALL)
_DEV_SPAN_RE = regex.compile(r"[\u0900-\u0963\u0966-\u097f\u1cd0-\u1cff\-–—]+")
_IAST_DIACRITIC_RE = regex.compile(r"[āīūṛṝḷḹṅñṭḍṇśṣṃḥĀĪŪṚṜḶḸṄÑṬḌṆŚṢṂḤ]")
_IAST_WORD_RE = regex.compile(r"[A-Za-zāīūṛṝḷḹṅñṭḍṇśṣṃḥĀĪŪṚṜḶḸṄÑṬḌṆŚṢṂḤ'’\-–]+")

NUM_SEP_CLASSES = 5
NUM_CLAUSE_CLASSES = 7

_CLAUSE_SPLIT_MAP: dict[tuple[int, str], tuple[str, str]] = {
  (3, "A"): ("a", "a"), (3, "I"): ("i", "i"), (3, "U"): ("u", "u"),
  (4, "A"): ("a", "A"), (4, "I"): ("i", "I"), (4, "U"): ("u", "U"),
  (5, "e"): ("a", "i"), (5, "o"): ("a", "u"),
  (6, "E"): ("a", "e"), (6, "O"): ("a", "o"),
}


def phon_category(ch: str) -> int:
  if ch in _SHORT_VOWELS:
    return 1
  if ch in _MERGED_VOWELS:
    return 2
  if ch in ("M", "H"):
    return 3
  if ch in _SEMIVOWELS:
    return 4
  if ch in _NASALS:
    return 5
  if ch in _SIBILANTS:
    return 6
  if ch in _STOPS:
    return 7
  if ch in ("Z", "'"):
    return 8
  if ch in " -–।॥,;.?!\"()>":
    return 9
  return 0


def text_to_ids_and_cats(slp_str: str) -> tuple[list[int], list[int]]:
  return [CHAR_TO_ID.get(ch, 1) for ch in slp_str], [phon_category(ch) for ch in slp_str]


def strip_accents_tracking(slp_with_accents: str) -> tuple[str, dict[int, str]]:
  clean_chars: list[str] = []
  accents: dict[int, str] = {}
  for ch in slp_with_accents:
    if _ACCENT_RE.fullmatch(ch):
      if clean_chars:
        idx = len(clean_chars) - 1
        accents[idx] = accents.get(idx, "") + ch
    else:
      clean_chars.append(ch)
  return "".join(clean_chars), accents


def encode_curated_sentence(
  curated_text: str,
  rng: random.Random,
  *,
  has_clause_breaks: bool = False,
) -> tuple[str, list[int], list[int]] | None:
  txt = _ANNO_RE.sub("", curated_text)
  txt = regex.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", txt)
  txt = _ACCENT_RE.sub("", txt)
  txt = regex.sub(r"(?<=\S)--(?=\S)", "–", txt)
  txt = regex.sub(r"([ेो])ऽ", r"\1 ऽ", txt)
  if "<" in txt or "[[" in txt or not regex.search(r"[\u0905-\u0939]", txt):
    return None

  slp = to_codec_slp1(txt.strip(), sanscript.DEVANAGARI)
  slp = regex.sub(r"[ \t]*\n[ \t]*", "\n", slp)
  slp = regex.sub(r"[ \t]{2,}", " ", slp)

  raw_chars: list[str] = []
  sep_y: list[int] = []
  clause_y: list[int] = []
  i, n = 0, len(slp)
  while i < n:
    ch = slp[i]
    if ch == "\n" and raw_chars:
      prev = raw_chars[-1]
      nxt = slp[i + 1] if i + 1 < n else ""
      if has_clause_breaks and nxt and rng.random() < 0.75:
        if prev == "H" and nxt in "tTsScCjJwWqQ":
          raw_chars[-1] = "s" if nxt in "tTs" else ("S" if nxt in "cCS" else "z")
          clause_y[-1] = 2
          i += 1
          continue
        matched = False
        for cl_id, (lv, rv, mv) in (
          (3, ("a", "a", "A")), (3, ("i", "i", "I")), (3, ("u", "u", "U")),
          (4, ("a", "A", "A")), (4, ("i", "I", "I")), (4, ("u", "U", "U")),
          (5, ("a", "i", "e")), (5, ("a", "u", "o")),
          (6, ("a", "e", "E")), (6, ("a", "o", "O")),
        ):
          if prev == lv and nxt == rv:
            raw_chars[-1], clause_y[-1], i, matched = mv, cl_id, i + 2, True
            break
        if matched:
          continue
      if has_clause_breaks:
        clause_y[-1] = 1
      if prev != " " and nxt and prev not in _HALANT_CODA_OK:
        raw_chars.append(" ")
        sep_y.append(0)
        clause_y.append(0)
      elif prev in _HALANT_CODA_OK and nxt:
        sep_y[-1] = 3
      i += 1
      continue

    if ch in ("-", "–") and raw_chars:
      sep_y[-1] = 1 if ch == "-" else 2
      i += 1
      continue

    if ch == " " and raw_chars and i + 1 < n:
      prev, nxt = raw_chars[-1], slp[i + 1]
      if prev in ("o", "e") and slp[i + 1:i + 3] == "Zr" and i + 3 < n and slp[i + 3] not in _ALL_VOWELS and rng.random() < 0.45:
        sep_y[-1] = 4
        i += 2
        continue
      if (nxt == "Z" or prev in _HALANT_CODA_OK) and rng.random() < 0.90:
        sep_y[-1] = 3
        i += 1
        continue
      if prev in _ALL_VOWELS and nxt not in _ALL_VOWELS and rng.random() < 0.06:
        sep_y[-1] = 3
        i += 1
        continue

    raw_chars.append(ch)
    sep_y.append(0)
    clause_y.append(0)
    i += 1

  return ("".join(raw_chars), sep_y, clause_y) if len(raw_chars) >= 3 else None


def _is_valid_o_avagraha_cut(slp_tok: str, pos: int, prev_cut: int, next_cut: int) -> bool:
  from .lexicon import is_valid_member_slp1, stem_base_slp1, word_count_slp1

  n = len(slp_tok)
  if pos < prev_cut + 2 or pos + 2 >= next_cut or slp_tok[pos] != "o" or slp_tok[pos + 1] != "r":
    return False
  if slp_tok[pos + 2] in _ALL_VOWELS:
    return False
  l_seg = slp_tok[prev_cut:pos + 1]
  r_seg = slp_tok[pos + 1:next_cut]
  a_rest = "a" + r_seg
  a_score = max(word_count_slp1(a_rest), word_count_slp1(stem_base_slp1(a_rest) or ""))
  l_vis = l_seg[:-1] + "aH"
  has_una_merger = any(
    is_valid_member_slp1(l_seg[:-1] + lv, is_right=False)
    and (word_count_slp1(rv + r_seg) >= 1 or (rv + r_seg).startswith("Urj"))
    for lv, rv in (("a", "u"), ("a", "U"), ("A", "u"), ("A", "U"))
  )
  return a_score >= 5 and word_count_slp1(r_seg) == 0 and word_count_slp1(l_vis) >= 2 and not has_una_merger


def _recover_clitic_and_yv_cut(
  slp_tok: str,
  i: int,
  l_piece: str,
  r_seg_next: str,
  tok_valid: bool,
  upas: frozenset[str],
  prons: frozenset[str],
  parts: frozenset[str],
) -> int:
  from .lexicon import is_merger_veto_slp1, is_valid_member_slp1, restore_left_member_slp1, stem_base_slp1, word_count_slp1

  ch = slp_tok[i]
  if ch == "m" and not tok_valid and len(l_piece) >= 4 and (r_seg_next in prons or r_seg_next in parts) and r_seg_next[0] in _ALL_VOWELS and is_valid_member_slp1(l_piece, is_right=True):
    return 3
  if ch in ("s", "S", "z", "r") and not tok_valid and (r_seg_next in prons or r_seg_next in parts):
    visarga_ok = (
      (ch == "s" and r_seg_next[0] in "tTs")
      or (ch == "S" and r_seg_next[0] in "cCS")
      or (ch == "z" and r_seg_next[0] in "wWz")
      or (ch == "r" and len(l_piece) >= 3 and r_seg_next[0] not in _VOICELESS_CONSONANTS and (l_piece[-2] not in ("a", "A") or l_piece.endswith(_R_STEM_WORDS)))
    )
    l_cand = l_piece[:-1] + "H"
    if visarga_ok and (word_count_slp1(l_cand) >= 2 or (len(l_cand) >= 6 and is_valid_member_slp1(l_cand, is_right=True))):
      return 3
  if (
    ch in ("y", "v") and not tok_valid
    and slp_tok[i - 1] not in _ALL_VOWELS and r_seg_next[0] in _ALL_VOWELS
    and not is_valid_member_slp1(l_piece + r_seg_next, is_right=True)
    and not any(is_valid_member_slp1(c, is_right=True) for c in restore_left_member_slp1(l_piece + r_seg_next))
    and not (r_seg_next[0] in _MERGED_VOWELS and is_merger_veto_slp1(slp_tok, i + 1))
  ):
    l_fem_ok = word_count_slp1(l_piece + "A") >= 1 or stem_base_slp1(l_piece + "A") is not None
    if r_seg_next[0] == "A" and l_fem_ok and _is_valid_right_piece("a" + r_seg_next[1:]):
      return 0
    all_rests = restore_left_member_slp1(l_piece)
    if not any(c in upas for c in all_rests):
      rests = [c for c in all_rests if word_count_slp1(c) >= 5]
      a_stem_wc = max(word_count_slp1(l_piece + "a"), word_count_slp1(l_piece + "A"))
      r_direct_ok = word_count_slp1(r_seg_next) >= 2 or r_seg_next in prons or r_seg_next in parts
      if rests and a_stem_wc < max(word_count_slp1(c) for c in rests) and r_direct_ok and (len(r_seg_next) >= 3 or r_seg_next in prons or r_seg_next in parts):
        return 3 if rests[0] == "iti" else 1
  if ch == "a" and slp_tok[i + 1:] in ("ja", "jA", "jam", "jaM", "jaH") and word_count_slp1(l_piece[max(0, i - 7):]) >= 5:
    return 1
  return 0


def _recover_subthreshold_cuts(
  slp_tok: str,
  cuts: list[int],
  p_non_zero: list[float],
  best_cls: list[int],
  closed: dict,
) -> None:
  from .lexicon import is_valid_member_slp1, restore_left_member_slp1, split_vowel_merger_slp1, word_count_slp1

  n = len(slp_tok)
  upas, prons, parts = closed["upasargas"], closed["pronouns"], closed["particles"]
  tok_valid = is_valid_member_slp1(slp_tok, is_right=True) or (
    slp_tok.endswith("M") and is_valid_member_slp1(slp_tok[:-1] + "m", is_right=True)
  )
  for i in range(1, n - 1):
    if cuts[i] != 0:
      continue
    next_existing = next((k for k in range(i + 1, n - 1) if cuts[k] != 0), n - 1)
    l_piece, r_piece = slp_tok[:i + 1], slp_tok[i + 1:]
    r_seg_next = slp_tok[i + 1:next_existing + 1]
    if not any(v in _ALL_VOWELS for v in l_piece) or not any(v in _ALL_VOWELS for v in r_seg_next):
      continue
    ch = slp_tok[i]
    if not tok_valid and _is_valid_o_avagraha_cut(slp_tok, i, 0, next_existing + 1):
      cuts[i] = 4
      continue
    if (
      l_piece.endswith("tum") and len(l_piece) >= 5 and r_piece[0] in _ALL_VOWELS
      and not tok_valid
      and not slp_tok[i:].startswith(("maya", "mayI", "mayA", "maye", "mAn", "mat"))
      and is_valid_member_slp1(r_seg_next, is_right=True)
    ):
      cuts[i] = 3
      continue
    if p_non_zero[i] >= 0.10:
      l_tails = [l_piece[max(0, len(l_piece) - k):] for k in (len(l_piece), 8, 6, 5)]
      l_ok = any(is_valid_member_slp1(c, is_right=True) for lt in l_tails for c in restore_left_member_slp1(lt))
      r_ok = is_valid_member_slp1(r_seg_next, is_right=True) or any(is_valid_member_slp1(c, is_right=True) for c in restore_left_member_slp1(r_seg_next))
      if ch in "mdrsSzc" and l_ok and r_ok:
        if p_non_zero[i] < 0.50 and word_count_slp1(r_seg_next) < 2 and r_seg_next not in prons and r_seg_next not in parts:
          pass
        else:
          cuts[i] = best_cls[i]
      elif ch in "yv" and l_ok and r_ok:
        cuts[i] = best_cls[i]
      elif p_non_zero[i] >= 0.35 and ch in _SHORT_VOWELS and r_ok:
        if word_count_slp1(l_piece) >= 2 or any(word_count_slp1(ru) >= 5 and len(ru) >= 4 for _, ru in split_vowel_merger_slp1(l_piece)):
          cuts[i] = best_cls[i]
    if (
      ch in ("s", "S", "z") and not tok_valid and len(l_piece) >= 4
      and i + 1 < n - 1 and slp_tok[i + 1] == ch and r_seg_next not in ("su", "zu")
      and not l_piece.endswith(("nis", "dus", "niS", "duS"))
    ):
      l_vis_ok = is_valid_member_slp1(l_piece[:-1] + "H", is_right=True) or any(
        is_valid_member_slp1(lt[:-1] + "H", is_right=True) for lt in (l_piece[-8:], l_piece[-6:]) if len(lt) >= 4
      )
      r_sib_ok = (
        word_count_slp1(r_seg_next) >= 1
        or is_valid_member_slp1(r_seg_next, is_right=True)
        or any(word_count_slp1(r_seg_next[:k]) >= 10 for k in range(4, min(8, len(r_seg_next))))
      )
      if l_vis_ok and r_sib_ok:
        cuts[i] = 3
        continue
    if cuts[i] == 0 and n <= 22:
      cuts[i] = _recover_clitic_and_yv_cut(slp_tok, i, l_piece, r_seg_next, tok_valid, upas, prons, parts)


def _is_valid_left_piece(l_seg: str) -> bool:
  from .lexicon import is_valid_member_slp1, restore_left_member_slp1, split_vowel_merger_slp1, stem_base_slp1, word_count_slp1

  if l_seg.endswith(("tum", "tvA", "tvI")) and len(l_seg) >= 5:
    return True
  if any(is_valid_member_slp1(c, is_right=True) for c in restore_left_member_slp1(l_seg)):
    return True
  if len(l_seg) >= 6:
    tails = [l_seg[max(0, len(l_seg) - k):] for k in (8, 6, 5, 4) if len(l_seg) > k]
    if any(is_valid_member_slp1(c, is_right=True) for lt in tails for c in restore_left_member_slp1(lt)):
      return True
    if l_seg.endswith(("Adi", "Adya", "AdiBiH", "AdInAm", "rUpa", "rUpA", "maya", "BUta")):
      return True
    if split_vowel_merger_slp1(l_seg):
      return True
  return stem_base_slp1(l_seg) is not None or word_count_slp1(l_seg) >= 2


def _is_valid_right_piece(r_seg: str) -> bool:
  from .lexicon import is_valid_member_slp1, restore_left_member_slp1, split_vowel_merger_slp1, word_count_slp1

  r_norm = ("a" + r_seg[1:]) if r_seg.startswith(_CODEC_AVAGRAHA) else r_seg
  if is_valid_member_slp1(r_norm, is_right=True):
    return True
  restored = restore_left_member_slp1(r_norm)
  if any(is_valid_member_slp1(c, is_right=True) or split_vowel_merger_slp1(c) for c in restored):
    return True
  if r_norm.endswith("y") and len(r_norm) >= 4 and (split_vowel_merger_slp1(r_norm[:-1] + "i") or split_vowel_merger_slp1(r_norm[:-1] + "I")):
    return True
  if r_norm.endswith("v") and len(r_norm) >= 4 and (split_vowel_merger_slp1(r_norm[:-1] + "u") or split_vowel_merger_slp1(r_norm[:-1] + "U")):
    return True
  if split_vowel_merger_slp1(r_norm):
    return True
  if len(r_norm) >= 8:
    if any(c in _MERGED_VOWELS for c in r_norm) and any(word_count_slp1(r_norm[:k]) >= 4 for k in range(3, min(10, len(r_norm)))):
      return True
    if any(is_valid_member_slp1(r_norm[:k], is_right=False) and is_valid_member_slp1(r_norm[k:], is_right=True) for k in range(3, len(r_norm) - 2)):
      return True
  return False


def _is_valid_space_coda(ch: str, next_ch: str) -> bool:
  if ch == "S":
    return next_ch in ("c", "C", "S")
  if ch == "z":
    return next_ch in ("w", "W", "z")
  if ch == "s":
    return next_ch in ("t", "T", "s")
  if ch == "m":
    return next_ch in _ALL_VOWELS or next_ch == "m"
  return True


def _should_veto_yv_cut(slp_tok: str, pos: int, next_cut: int, l_seg: str, r_seg: str, upas, parts, prons) -> bool:
  from .lexicon import is_valid_member_slp1, is_merger_veto_slp1, restore_left_member_slp1, stem_base_slp1, word_count_slp1

  l_rests = restore_left_member_slp1(l_seg)
  l_closed = any(c in upas or c in parts or c in prons for c in l_rests)
  if not l_closed and any(is_valid_member_slp1(c, is_right=True) for c in restore_left_member_slp1(l_seg + r_seg)):
    return True
  if pos + 1 < len(slp_tok) and slp_tok[pos + 1] in _MERGED_VOWELS:
    l_strong = l_closed or any(word_count_slp1(c) >= 10 for c in l_rests)
    l_fem_ok = not l_closed and (word_count_slp1(l_seg + "A") >= 1 or stem_base_slp1(l_seg + "A") is not None)
    return (is_merger_veto_slp1(slp_tok, pos + 1) and not l_strong) or (
      slp_tok[pos + 1] == "A"
      and _is_valid_right_piece("a" + slp_tok[pos + 2:next_cut])
      and (not l_strong or (l_fem_ok and word_count_slp1(r_seg) < 10))
    )
  return False


def _fix_shifted_hyphen_cut(slp_tok: str, cuts: list[int], pos: int, prev_cut: int, l_seg: str, r_seg: str) -> None:
  from .lexicon import is_valid_member_slp1, stem_base_slp1, word_count_slp1

  ch = slp_tok[pos]
  if ch == "u" and len(l_seg) >= 8 and word_count_slp1(l_seg) == 0 and l_seg[-3:-1] in ("cC", "CC") and word_count_slp1("S" + ch + r_seg) >= 2:
    cuts[pos], cuts[pos - 2] = 0, 3
    return
  if ch != "a" or pos < prev_cut + 2:
    return
  if slp_tok[pos - 1] == "k" and word_count_slp1(l_seg) == 0 and stem_base_slp1(l_seg) is None and len(l_seg) >= 6 and l_seg[-3] in _STOPS and word_count_slp1("k" + ch + r_seg) >= 2:
    cuts[pos], cuts[pos - 2] = 0, 3
    return
  l_back, r_back = l_seg[:-1], ch + r_seg
  if l_seg == "antara" and r_seg.startswith("jAyamAn"):
    cuts[pos], cuts[pos - 1] = 0, 3
  elif slp_tok[pos - 1] == "r" and not _is_valid_left_piece(l_seg) and is_valid_member_slp1(r_back, is_right=True):
    cuts[pos], cuts[pos - 1] = 0, 3
  elif (
    slp_tok[pos - 1] == "m"
    and slp_tok[pos - 2] in _ALL_VOWELS
    and word_count_slp1(l_seg) == 0
    and stem_base_slp1(l_seg) is None
    and (word_count_slp1(l_back[:-1]) >= 2 or any(is_valid_member_slp1(l_back[-k:-1], is_right=True) for k in (5, 6) if len(l_back) > k) or l_back.endswith("Cukram"))
    and is_valid_member_slp1(r_back, is_right=True)
    and not (len(l_seg) >= 5 and l_seg.endswith(("krama", "rama")) and not l_seg.endswith("Cukrama"))
  ):
    cuts[pos], cuts[pos - 1] = 0, 3


def _prune_pre_cuts(slp_tok: str, cuts: list[int]) -> None:
  n = len(slp_tok)
  pre_pos = [i for i in range(n - 1) if cuts[i] != 0]
  last_kept = 0
  for idx_k, pos in enumerate(pre_pos):
    cls = cuts[pos]
    prev_cut = last_kept
    next_cut = pre_pos[idx_k + 1] + 1 if idx_k + 1 < len(pre_pos) else n
    l_seg, r_seg = slp_tok[prev_cut:pos + 1], slp_tok[pos + 1:next_cut]
    ch = slp_tok[pos]
    if not any(v in _ALL_VOWELS for v in l_seg) or not any(v in _ALL_VOWELS for v in r_seg):
      cuts[pos] = 0
    elif cls == 3 and not _is_valid_space_coda(ch, slp_tok[pos + 1]):
      cuts[pos] = 0
    elif cls == 3 and not _is_valid_left_piece(l_seg):
      cuts[pos] = 0
    elif cls in (1, 2) and ch in _ALL_VOWELS and len(l_seg) <= 7 and not _is_valid_left_piece(l_seg):
      cuts[pos] = 0
    if cuts[pos] != 0:
      last_kept = pos + 1


def _handle_hyphen_cut(
  slp_tok: str,
  cuts: list[int],
  pos: int,
  prev_cut: int,
  next_cut: int,
  l_seg: str,
  r_seg: str,
  tok_valid: bool,
  prons: frozenset[str],
  parts: frozenset[str],
) -> None:
  from .lexicon import is_valid_member_slp1, restore_left_member_slp1, stem_base_slp1, word_count_slp1

  ch = slp_tok[pos]
  if ch in _SHORT_VOWELS and word_count_slp1(r_seg) == 0 and pos + 1 < next_cut - 1 and slp_tok[pos + 1] in _HALANT_CODA_OK:
    l_sh, r_sh = l_seg + slp_tok[pos + 1], slp_tok[pos + 2:next_cut]
    if (word_count_slp1(l_seg) < 5 or r_sh in prons or r_sh in parts) and any(v in _ALL_VOWELS for v in r_sh) and any(is_valid_member_slp1(c, is_right=True) for c in restore_left_member_slp1(l_sh)) and (word_count_slp1(r_sh) >= 2 or (not is_valid_member_slp1(r_seg, is_right=True) and is_valid_member_slp1(r_sh, is_right=True))):
      cuts[pos] = 0
      cuts[pos + 1] = 3 if (r_sh in prons or r_sh in parts or slp_tok[pos + 1] == "m") else 1
      return
  if (
    ch in ("a", "A")
    and pos >= prev_cut + 2
    and slp_tok[pos - 1] == "m"
    and slp_tok[pos - 2] in _ALL_VOWELS
    and (word_count_slp1(r_seg) < 5 or word_count_slp1(l_seg) == 0)
  ):
    l_prev, r_prev = slp_tok[prev_cut:pos], slp_tok[pos:next_cut]
    l_prev_tails = (l_prev, l_prev[-8:], l_prev[-6:], l_prev[-5:])
    if any(is_valid_member_slp1(lt, is_right=True) for lt in l_prev_tails if len(lt) >= 4) and _is_valid_right_piece(r_prev):
      cuts[pos] = 0
      cuts[pos - 1] = 3
      return
  if ch in ("a", "A") and pos >= prev_cut + 3 and slp_tok[pos - 1] == "r" and word_count_slp1(l_seg) == 0:
    l_prev, r_prev = slp_tok[prev_cut:pos], slp_tok[pos:next_cut]
    if slp_tok[pos - 2] not in ("a", "A") or any(l_prev.endswith(rw) for rw in _R_STEM_WORDS):
      l_prev_tails = (l_prev, l_prev[-8:], l_prev[-6:], l_prev[-5:])
      if any(word_count_slp1(c) >= 1 for lt in l_prev_tails if len(lt) >= 3 for c in restore_left_member_slp1(lt)) and _is_valid_right_piece(r_prev):
        cuts[pos] = 0
        cuts[pos - 1] = 3
        return
  if r_seg.startswith(("sva", "svA", "sve", "svo", "svO")) and any(word_count_slp1(l_seg[k:] + "sva") >= 2 for k in range(max(0, len(l_seg) - 8), max(0, len(l_seg) - 1))):
    cuts[pos] = 0
    return
  if r_seg in _BOUND_SUFFIXES or r_seg in _CLITIC_HYPHEN_VETO or l_seg == "anA" or (l_seg == "an" and r_seg[0] not in _ALL_VOWELS):
    cuts[pos] = 0
    return
  if ch == "a" and r_seg.startswith(("vas", "vaH")) and any(word_count_slp1(l_seg[k:-1] + "u") >= 2 for k in range(max(0, len(l_seg) - 10), max(0, len(l_seg) - 1))):
    cuts[pos] = 0
    return
  if len(l_seg) <= 2 and l_seg not in ("go", "BU"):
    cuts[pos] = 0
    return
  if len(r_seg) <= 3 and r_seg not in _COMPOUND_SINGLE_CHAR_RIGHT and (
    any(is_valid_member_slp1(c, is_right=True) for c in restore_left_member_slp1(l_seg + r_seg))
    or word_count_slp1(r_seg) < 20
    or (len(l_seg) <= 8 and word_count_slp1(l_seg) == 0)
  ):
    cuts[pos] = 0
    return
  if tok_valid and len(l_seg) <= 3 and l_seg not in ("go", "BU", "nO", "strI"):
    cuts[pos] = 0
    return
  if ch in _ALL_VOWELS and len(l_seg) <= 8 and not _is_valid_left_piece(l_seg):
    cuts[pos] = 0
    return
  if len(l_seg) >= 8 and ch == "a" and word_count_slp1(l_seg) == 0 and l_seg.endswith("Ana") and word_count_slp1(l_seg[:-3] + "a") >= 5:
    cuts[pos] = 0
    return
  if not _is_valid_right_piece(r_seg) and not (r_seg in _COMPOUND_SINGLE_CHAR_RIGHT and len(l_seg) >= 4 and _is_valid_left_piece(l_seg)):
    cuts[pos] = 0
    return
  if ch in _SHORT_VOWELS:
    for k in range(max(0, len(l_seg) - 8), max(0, len(l_seg) - 3)):
      lt = l_seg[k:]
      joined_cand = lt + r_seg
      joined_wc = max(word_count_slp1(joined_cand), word_count_slp1(stem_base_slp1(joined_cand) or ""))
      if joined_wc >= 2 and joined_wc > max(20, word_count_slp1(lt) * 3) if word_count_slp1(lt) > 0 else joined_wc >= 2:
        cuts[pos] = 0
        return
  if "or" in slp_tok[pos + 1:] and l_seg == "prARa" and "Atmanor" in slp_tok:
    cuts[pos] = 0


def _handle_space_cut(
  slp_tok: str,
  cuts: list[int],
  p_non_zero: list[float],
  pos: int,
  prev_cut: int,
  next_cut: int,
  l_seg: str,
  r_seg: str,
  prons: frozenset[str],
  parts: frozenset[str],
) -> None:
  from .lexicon import is_valid_member_slp1, restore_left_member_slp1, stem_base_slp1, word_count_slp1

  ch = slp_tok[pos]
  if not _is_valid_space_coda(ch, slp_tok[pos + 1]):
    cuts[pos] = 0
    return
  if r_seg in _BOUND_SUFFIXES or l_seg == "anA" or (l_seg == "an" and r_seg[0] not in _ALL_VOWELS):
    cuts[pos] = 0
    return
  if len(l_seg) == 2 and ch in _SHORT_VOWELS and slp_tok[pos + 1] not in _ALL_VOWELS and (
    is_valid_member_slp1(slp_tok, is_right=True)
    or (l_seg == "ha" and (prev_cut == 0 or any(is_valid_member_slp1(l_seg + r_seg[:k], is_right=True) for k in range(2, min(8, len(r_seg) + 1)))))
  ):
    cuts[pos] = 0
    return
  if len(l_seg) <= 2 and word_count_slp1(l_seg + r_seg) >= 10 and r_seg not in ("ca", "vA", "hi") and l_seg + r_seg not in ("saca", "nahi", "yadi"):
    cuts[pos] = 0
    return
  if ch == "m" and r_seg.startswith("As") and any(is_valid_member_slp1(c, is_right=True) for c in restore_left_member_slp1(l_seg + "As")):
    cuts[pos] = 0
    return
  if ch == slp_tok[pos + 1] and ch not in ("s", "S", "z") and not is_valid_member_slp1(r_seg, is_right=True):
    cuts[pos] = 0
    return
  if ch == "m" and word_count_slp1(r_seg) == 0 and word_count_slp1(l_seg) == 0:
    has_prefix_stem = any(word_count_slp1(l_seg[k:-1]) > 20 for k in range(max(0, len(l_seg) - 8), max(0, len(l_seg) - 2)))
    if not stem_base_slp1(l_seg) or has_prefix_stem:
      cuts[pos] = 0
      return
  if ch == "m" and word_count_slp1(r_seg) == 0 and len(l_seg) >= 4 and word_count_slp1(l_seg[:-1]) > max(20, word_count_slp1(l_seg) * 5) and any(is_valid_member_slp1(c, is_right=True) for c in restore_left_member_slp1("m" + r_seg)):
    cuts[pos] = 0
    return
  if r_seg == "Aya" and l_seg.endswith("m") and stem_base_slp1(l_seg + r_seg) is not None:
    cuts[pos] = 0
    return
  if word_count_slp1(l_seg) == 0 and not any(word_count_slp1(c) >= 1 for c in restore_left_member_slp1(l_seg)) and len(r_seg) <= 3 and word_count_slp1(l_seg[-2:] + r_seg) >= 10:
    cuts[pos] = 0
    return
  if r_seg not in parts and r_seg not in prons and (
    (len(r_seg) <= 2 and r_seg not in _VALID_TWO_CHAR_SPACE_WORDS)
    or (len(r_seg) <= 3 and (word_count_slp1(l_seg + r_seg) >= 2 or stem_base_slp1(l_seg + r_seg) is not None or r_seg == "ntu"))
  ):
    cuts[pos] = 0
    return
  if not _is_valid_left_piece(l_seg) or not _is_valid_right_piece(r_seg):
    cuts[pos] = 0
    return
  if ch in ("s", "S", "z", "r") and p_non_zero[pos] < 0.70:
    l_tails = [l_seg[max(0, len(l_seg) - k):] for k in (len(l_seg), 8, 6, 5, 4)]
    l_ok = any(is_valid_member_slp1(c, is_right=True) for lt in l_tails for c in restore_left_member_slp1(lt))
    r_sib_ok = is_valid_member_slp1(r_seg, is_right=True) or any(
      word_count_slp1(r_seg[:k]) >= 10 for k in range(4, min(8, len(r_seg)))
    )
    if not l_ok and not r_sib_ok:
      cuts[pos] = 0
      return
  if ch == "d" and pos >= prev_cut + 3 and slp_tok[pos - 2] == "d" and slp_tok[pos - 1] in _ALL_VOWELS:
    l_tails = [l_seg[max(0, len(l_seg) - k):] for k in (len(l_seg), 8, 6)]
    l_ok = any(word_count_slp1(c) >= 2 for lt in l_tails for c in restore_left_member_slp1(lt))
    r_back_ok = word_count_slp1(slp_tok[pos - 1:next_cut]) >= 5 or any(
      word_count_slp1(slp_tok[pos - 1:pos - 1 + k]) >= 10 for k in range(4, min(10, next_cut - pos + 2))
    )
    if not l_ok and word_count_slp1(r_seg) == 0 and r_back_ok:
      cuts[pos] = 0
      cuts[pos - 2] = 3
      return
  if ch == "r" and len(l_seg) >= 2 and l_seg[-2] in ("a", "A") and not any(l_seg.endswith(rw) for rw in _R_STEM_WORDS):
    cuts[pos] = 0
    return
  if ch in ("a", "A") and pos >= prev_cut + 3 and slp_tok[pos - 1] in ("y", "v"):
    l_prev, r_prev = slp_tok[prev_cut:pos], slp_tok[pos:next_cut]
    if any(word_count_slp1(c) >= 20 for c in restore_left_member_slp1(l_prev)):
      r_prev_sc = max(word_count_slp1(r_prev), word_count_slp1(stem_base_slp1(r_prev) or ""))
      r_cur_sc = max(word_count_slp1(r_seg), word_count_slp1(stem_base_slp1(r_seg) or ""))
      if r_prev_sc > r_cur_sc * 2:
        cuts[pos] = 0
        cuts[pos - 1] = 3
        return
  if ch == "d" and word_count_slp1(l_seg) == 0 and pos >= prev_cut + 2 and slp_tok[pos - 1] in ("a", "A"):
    l_tails = [l_seg[max(0, len(l_seg) - k):] for k in (len(l_seg), 8, 6)]
    if not any(word_count_slp1(c) >= 20 for lt in l_tails for c in restore_left_member_slp1(lt)) and word_count_slp1(r_seg[:5]) < 10 and any(word_count_slp1(slp_tok[pos - 1:pos - 1 + k]) >= 50 for k in range(4, min(10, next_cut - pos + 2))):
      cuts[pos] = 0
      return
  if ch == "r" and l_seg.endswith("Atmanor") and word_count_slp1(r_seg) >= 5 and r_seg not in prons and r_seg not in parts:
    cuts[pos] = 0


def refine_token_cuts_with_lexicon(slp_tok: str, raw_sep_preds, is_prob_matrix: bool) -> list[int]:
  """Combine neural boundary predictions/probabilities with ``BytesTrie`` lexicon
  and Pāṇinian phonotactic witnesses (zero hardcoded words)."""
  from .lexicon import is_merger_veto_slp1, is_valid_member_slp1, load_closed_sets, restore_left_member_slp1, stem_base_slp1, word_count_slp1

  n = len(slp_tok)
  closed = load_closed_sets()
  upas, prons, parts = closed["upasargas"], closed["pronouns"], closed["particles"]
  tok_valid = word_count_slp1(slp_tok) >= 2 or (slp_tok.endswith("M") and word_count_slp1(slp_tok[:-1] + "m") >= 2)

  if is_prob_matrix:
    cuts = [int(raw_sep_preds[i].argmax()) for i in range(n)]
    p_non_zero = [float(1.0 - raw_sep_preds[i, 0]) for i in range(n)]
    best_cls = [int(raw_sep_preds[i, 1:].argmax() + 1) for i in range(n)]
  else:
    cuts = list(raw_sep_preds[:n])
    p_non_zero = [1.0 if c > 0 else 0.0 for c in cuts]
    best_cls = list(cuts)
  cuts[-1] = 0
  _recover_subthreshold_cuts(slp_tok, cuts, p_non_zero, best_cls, closed)
  _prune_pre_cuts(slp_tok, cuts)

  for _ in range(2):
    active_pos = [i for i in range(n - 1) if cuts[i] != 0]
    for idx_k, pos in enumerate(active_pos):
      cls = cuts[pos]
      prev_cut = active_pos[idx_k - 1] + 1 if idx_k > 0 else 0
      next_cut = active_pos[idx_k + 1] + 1 if idx_k + 1 < len(active_pos) else n
      l_seg, r_seg = slp_tok[prev_cut:pos + 1], slp_tok[pos + 1:next_cut]
      ch = slp_tok[pos]

      if not any(v in _ALL_VOWELS for v in l_seg) or not any(v in _ALL_VOWELS for v in r_seg):
        cuts[pos] = 0
        continue
      if cls == 4:
        if not _is_valid_o_avagraha_cut(slp_tok, pos, prev_cut, next_cut):
          cuts[pos] = 0
        continue
      if ch not in (_ALL_VOWELS | {"M", "H"} | _HALANT_CODA_OK) or (ch in (_STOPS - _HALANT_CODA_OK) and slp_tok[pos + 1] in _ALL_VOWELS):
        cuts[pos] = 0
        continue
      if ch in _MERGED_VOWELS and cls in (1, 2, 3) and is_merger_veto_slp1(slp_tok, pos):
        cuts[pos] = 0
        continue
      if ch in ("y", "v") and cls in (1, 2, 3) and _should_veto_yv_cut(slp_tok, pos, next_cut, l_seg, r_seg, upas, parts, prons):
        cuts[pos] = 0
        continue
      if cls in (1, 2) and l_seg in upas:
        cuts[pos] = 0
        continue
      if cls in (1, 2) and l_seg == "sva":
        if any(
          slp_tok[m_end] in _MERGED_VOWELS
          and is_merger_veto_slp1(slp_tok, m_end)
          and any(word_count_slp1(slp_tok[prev_cut:m_end] + lv) >= 4 for lv in ("a", "A", "i", "u"))
          for m_end in range(pos + 3, min(n, pos + 14))
        ):
          cuts[pos] = 0
          continue
      if cuts[pos] in (1, 2):
        _handle_hyphen_cut(slp_tok, cuts, pos, prev_cut, next_cut, l_seg, r_seg, tok_valid, prons, parts)
        if cuts[pos] in (1, 2):
          _fix_shifted_hyphen_cut(slp_tok, cuts, pos, prev_cut, l_seg, r_seg)
      if cuts[pos] == 3:
        _handle_space_cut(slp_tok, cuts, p_non_zero, pos, prev_cut, next_cut, l_seg, r_seg, prons, parts)

  active_pos = [i for i in range(n - 1) if cuts[i] != 0]
  for idx_k, pos in enumerate(active_pos):
    if cuts[pos] in (1, 2):
      prev_cut = active_pos[idx_k - 1] + 1 if idx_k > 0 else 0
      next_cut = active_pos[idx_k + 1] + 1 if idx_k + 1 < len(active_pos) else n
      l_seg, r_seg = slp_tok[prev_cut:pos + 1], slp_tok[pos + 1:next_cut]
      ch = slp_tok[pos]
      if (
        r_seg in parts
        or r_seg in prons
        or r_seg in _UNHYPHENATABLE_RIGHT_PADAS
        or l_seg in ("tvam", "tad", "yad", "aham", "vayam", "idam", "etad", "videt", "asi")
        or (r_seg == "Di" and ch == "d")
        or (l_seg.endswith(("yEtad", "yatad", "yEtat")) and ch in ("d", "t"))
        or (l_seg.endswith(("or", "er")) and len(l_seg) >= 5 and not l_seg.endswith(("gor", "hor", "dor")))
      ):
        cuts[pos] = 3

  return cuts


def _dev_letter_count(text: str) -> int:
  return len(regex.findall(r"[\u0905-\u0939a-zA-Z]", text))


def _can_apply_clause_vowel_split(slp_tok: str, pos: int, lv: str, rv: str, sep_preds: list[int]) -> bool:
  from .lexicon import load_closed_sets, word_count_slp1

  n = len(slp_tok)
  if pos < 2 or pos >= n - 2:
    return False
  if slp_tok[pos] in ("e", "o") and slp_tok[pos + 1] == "r" and (pos + 2 >= n or slp_tok[pos + 2] not in _ALL_VOWELS):
    return False
  if slp_tok in _TIN_ANTI_VERBS or any(slp_tok.endswith(v) for v in _TIN_ANTI_VERBS):
    return False
  prev_cut = max((k + 1 for k in range(pos) if sep_preds[k] != 0), default=0)
  next_cut = next((k + 1 for k in range(pos + 1, n - 1) if sep_preds[k] != 0), n)
  l_cand = slp_tok[prev_cut:pos] + lv
  r_cand = rv + slp_tok[pos + 1:next_cut]
  parts = load_closed_sets()["particles"]
  if (len(r_cand) < 3 and r_cand not in parts) or r_cand.endswith("r"):
    return False
  if not _is_valid_left_piece(l_cand):
    return False
  if r_cand in parts:
    return True
  return _is_valid_right_piece(r_cand) and (word_count_slp1(r_cand) >= 2 or len(r_cand) >= 5)


def reconstruct_token_from_slp1(
  orig_tok: str,
  slp_tok: str,
  accents: dict[int, str],
  raw_sep_preds,
  clause_preds: list[int] | None,
  scheme: str,
  *,
  is_prob_matrix: bool = False,
  line_prefix_letters: int = 0,
  line_suffix_letters: int = 0,
) -> str:
  sep_preds = refine_token_cuts_with_lexicon(slp_tok, raw_sep_preds, is_prob_matrix)
  pieces_out: list[str] = []
  cur_slp: list[str] = []
  n = len(slp_tok)
  cur_line_letters = line_prefix_letters

  def _flush(p_str: str) -> str:
    return from_codec_slp1(p_str, scheme) if p_str else ""

  def _can_newline_at(left_dev: str, rem_slp: str) -> bool:
    return (
      cur_line_letters + _dev_letter_count(left_dev) >= 18
      and _dev_letter_count(_flush(rem_slp)) + line_suffix_letters >= 14
    )

  i = 0
  while i < n:
    ch, acc = slp_tok[i], accents.get(i, "")
    cl_act = clause_preds[i] if (clause_preds is not None and i < len(clause_preds)) else 0
    if cl_act == 2 and ch in ("s", "S", "z", "r") and 2 <= i < n - 1 and sep_preds[i] == 3:
      left_dev = _flush("".join(cur_slp) + "H" + acc)
      if _can_newline_at(left_dev, slp_tok[i + 1:]):
        pieces_out.extend((left_dev, "  \n"))
        cur_line_letters, cur_slp, i = 0, [], i + 1
        continue
    if (cl_act, ch) in _CLAUSE_SPLIT_MAP and _can_apply_clause_vowel_split(slp_tok, i, *_CLAUSE_SPLIT_MAP[(cl_act, ch)], sep_preds):
      lv, rv = _CLAUSE_SPLIT_MAP[(cl_act, ch)]
      left_dev = _flush("".join(cur_slp) + lv + acc)
      if _can_newline_at(left_dev, rv + slp_tok[i + 1:]):
        pieces_out.extend((left_dev, "  \n"))
        cur_line_letters, cur_slp, i = 0, [rv], i + 1
        continue

    cur_slp.append(ch + acc)
    sep_cls = sep_preds[i] if i < len(sep_preds) else 0
    if i < n - 1 and sep_cls != 0:
      flushed = _flush("".join(cur_slp))
      pieces_out.append(flushed)
      if (
        cl_act == 1
        and sep_cls == 3
        and ch not in ("c", "j", "w", "q", "g", "d")
        and len(cur_slp) >= 4
        and (n - i - 1) >= 5
        and _dev_letter_count(flushed.rsplit(None, 1)[-1] if flushed.strip() else "") >= 2
        and _can_newline_at(flushed, slp_tok[i + 1:])
      ):
        pieces_out.append("  \n")
        cur_line_letters = 0
      elif sep_cls == 4:
        pieces_out.append(" ")
        cur_line_letters += _dev_letter_count(flushed)
        cur_slp, i = ["Z"], i + 1
        continue
      else:
        pieces_out.append({1: "-", 2: "–", 3: " ", 4: " "}[sep_cls])
        cur_line_letters += _dev_letter_count(flushed)
      cur_slp = []
    elif i == n - 1 and cl_act == 1 and cur_line_letters + _dev_letter_count(_flush("".join(cur_slp))) >= 18 and line_suffix_letters >= 14:
      pieces_out.extend((_flush("".join(cur_slp)), "  \n"))
      cur_line_letters, cur_slp = 0, []
    i += 1

  if cur_slp:
    pieces_out.append(_flush("".join(cur_slp)))
  cand = "".join(pieces_out)
  if scheme == sanscript.DEVANAGARI:
    if "\n" not in cand and "ऽ" not in (set(cand) - set(orig_tok)):
      cand = rejoin_merger_violations(orig_tok, cand)
      if canonical_sandhi_skeleton(cand) != canonical_sandhi_skeleton(orig_tok):
        return orig_tok
    elif "\n" in cand:
      cand = "\n".join(rejoin_merger_violations(orig_tok, ln) for ln in cand.split("\n"))
  return cand


def apply_slp1_predictions_to_paragraph(
  para: str,
  predict_fn,
  *,
  clause_newlines: bool = False,
) -> str:
  anno_masks: dict[str, str] = {}

  def _mask_anno(m):
    k = f"§§ANNO{len(anno_masks)}§§"
    anno_masks[k] = m.group(0)
    return k

  work = _ANNO_RE.sub(_mask_anno, para)
  spans: list[tuple[int, int, str, str, bool]] = []
  for m in _DEV_SPAN_RE.finditer(work):
    tok = m.group(0)
    if regex.search(r"[\u0905-\u0939]", tok):
      spans.append((m.start(), m.end(), tok, sanscript.DEVANAGARI, any(s in tok for s in ("-", "–", "—"))))
  if not spans and _IAST_DIACRITIC_RE.search(work):
    for m in _IAST_WORD_RE.finditer(work):
      tok = m.group(0)
      if _IAST_DIACRITIC_RE.search(tok):
        spans.append((m.start(), m.end(), tok, sanscript.IAST, any(s in tok for s in ("-", "–"))))
  if not spans:
    return para

  slp_parts, tok_meta, cursor_slp = [], [], 0
  for idx, (_, _, tok, scheme, already) in enumerate(spans):
    if idx > 0:
      slp_parts.append(" ")
      cursor_slp += 1
    slp_clean, acc_map = strip_accents_tracking(to_codec_slp1(tok, scheme))
    slp_parts.append(slp_clean)
    tok_meta.append((cursor_slp, cursor_slp + len(slp_clean), slp_clean, acc_map, scheme, already))
    cursor_slp += len(slp_clean)

  sep_out, clause_all = predict_fn("".join(slp_parts))
  is_probs = hasattr(sep_out, "ndim") and sep_out.ndim == 2

  out_buf, last_end = [], 0
  for i_sp, (st_char, en_char, orig_tok, _, _) in enumerate(spans):
    gap = work[last_end:st_char]
    next_stop = regex.search(r"[।॥\n]", work[st_char:])
    tail_from_tok = work[st_char:st_char + next_stop.start()] if next_stop else work[st_char:]
    cur_line = "".join(out_buf).rsplit("\n", 1)[-1]
    if i_sp > 0 and clause_newlines and "\n" not in gap:
      prev_end = tok_meta[i_sp - 1][1] - 1
      if "।" in gap or "॥" in gap:
        gap = regex.sub(r"([।॥]+)[ \t]+", r"\1  \n", gap)
      elif 0 <= prev_end < len(clause_all) and clause_all[prev_end] == 1 and not regex.search(r"[\(\[\{“‘\"']\s*$", gap):
        left_letters = _dev_letter_count(cur_line)
        right_letters = _dev_letter_count(tail_from_tok)
        last_word = cur_line.rsplit(None, 1)[-1] if cur_line.strip() else ""
        if left_letters >= 18 and right_letters >= 14 and len(tok_meta[i_sp - 1][2]) >= 4 and _dev_letter_count(last_word) >= 2:
          gap = regex.sub(r"[ \t]+$", "", gap) + "  \n"
    out_buf.append(gap)
    line_pref = _dev_letter_count(("".join(out_buf)).rsplit("\n", 1)[-1])
    after_stop = regex.search(r"[।॥\n]", work[en_char:])
    after_span = work[en_char:en_char + after_stop.start()] if after_stop else work[en_char:]
    line_suff = _dev_letter_count(after_span)

    s_idx, e_idx, slp_clean, acc_map, scheme, already = tok_meta[i_sp]
    if already or len(slp_clean) < 3:
      out_buf.append(orig_tok)
    else:
      t_sep = sep_out[s_idx:e_idx]
      t_cl = list(clause_all[s_idx:e_idx]) if clause_newlines else None
      if t_cl:
        t_cl[-1] = 0
      out_buf.append(reconstruct_token_from_slp1(
        orig_tok,
        slp_clean,
        acc_map,
        t_sep,
        t_cl,
        scheme,
        is_prob_matrix=is_probs,
        line_prefix_letters=line_pref,
        line_suffix_letters=line_suff,
      ))
    last_end = en_char

  out_buf.append(work[last_end:])
  res = "".join(out_buf)
  for k, v in anno_masks.items():
    res = res.replace(k, v)
  return res


def apply_slp1_predictions_to_text(text: str, predict_fn, *, clause_newlines: bool = False) -> str:
  if not text:
    return text
  masked, masks = mask_protected_blocks(text)
  sep_re = r"(\n\s*\n+)" if clause_newlines else r"(\n)"
  parts = regex.split(sep_re, masked)
  out_parts = [
    apply_slp1_predictions_to_paragraph(p, predict_fn, clause_newlines=clause_newlines)
    if idx % 2 == 0 and p.strip()
    else p
    for idx, p in enumerate(parts)
  ]
  return restore_protected_blocks("".join(out_parts), masks)
