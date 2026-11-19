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
  "tva", "tvam", "tvaM", "tvena", "tvAt", "tvAd", "tve", "tvasya", "tvayoH",
  "tvAni", "tvAByAm", "tveByaH", "tvAnAm", "tvezu",
  "tA", "tAm", "tAyAH", "tAsu",
  "maya", "mayaH", "mayI", "mayam", "mayAm",
  "tama", "tamaH", "tamam", "tara", "taraH", "taram",
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


def _recover_subthreshold_cuts(
  slp_tok: str,
  cuts: list[int],
  p_non_zero: list[float],
  best_cls: list[int],
  closed: dict,
) -> None:
  from .lexicon import (
    is_merger_veto_slp1,
    is_valid_member_slp1,
    restore_left_member_slp1,
    split_vowel_merger_slp1,
    stem_base_slp1,
    word_count_slp1,
  )

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
    if ch in ("o", "e") and slp_tok[i + 1] == "r" and i + 2 < n and slp_tok[i + 2] not in _ALL_VOWELS:
      a_rest = "a" + r_seg_next
      a_score = max(word_count_slp1(a_rest), word_count_slp1(stem_base_slp1(a_rest) or ""))
      if a_score >= 5 and word_count_slp1(r_seg_next) == 0 and is_valid_member_slp1(l_piece[:-1] + "aH", is_right=True):
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
      if ch in "mdrsSzcyv" and l_ok and r_ok:
        cuts[i] = best_cls[i]
      elif p_non_zero[i] >= 0.35 and ch in _SHORT_VOWELS and r_ok:
        l_stem_ok = word_count_slp1(l_piece) >= 2 or any(word_count_slp1(ru) >= 5 and len(ru) >= 4 for _, ru in split_vowel_merger_slp1(l_piece))
        if l_stem_ok:
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
      if ch == "m" and not tok_valid and len(l_piece) >= 4 and (r_seg_next in prons or r_seg_next in parts) and r_seg_next[0] in _ALL_VOWELS and is_valid_member_slp1(l_piece, is_right=True):
        cuts[i] = 3
      elif ch in ("s", "S", "z", "r") and not tok_valid and (r_seg_next in prons or r_seg_next in parts):
        visarga_ok = (
          (ch == "s" and r_seg_next[0] in "tTs")
          or (ch == "S" and r_seg_next[0] in "cCS")
          or (ch == "z" and r_seg_next[0] in "wWz")
          or (
            ch == "r" and len(l_piece) >= 3 and r_seg_next[0] not in _VOICELESS_CONSONANTS
            and (l_piece[-2] not in ("a", "A") or l_piece.endswith(_R_STEM_WORDS))
          )
        )
        l_cand = l_piece[:-1] + "H"
        if visarga_ok and (word_count_slp1(l_cand) >= 2 or (len(l_cand) >= 6 and is_valid_member_slp1(l_cand, is_right=True))):
          cuts[i] = 3
      elif (
        ch in ("y", "v") and not tok_valid
        and slp_tok[i - 1] not in _ALL_VOWELS and r_seg_next[0] in _ALL_VOWELS
        and not is_valid_member_slp1(l_piece + r_seg_next, is_right=True)
        and not (r_seg_next[0] in _MERGED_VOWELS and is_merger_veto_slp1(slp_tok, i + 1))
      ):
        all_rests = restore_left_member_slp1(l_piece)
        if not any(c in upas for c in all_rests):
          rests = [c for c in all_rests if word_count_slp1(c) >= 5]
          a_stem_wc = max(word_count_slp1(l_piece + "a"), word_count_slp1(l_piece + "A"))
          if (
            rests
            and a_stem_wc < max(word_count_slp1(c) for c in rests)
            and (len(r_seg_next) >= 3 or r_seg_next in prons or r_seg_next in parts)
            and is_valid_member_slp1(r_seg_next, is_right=True)
          ):
            cuts[i] = 3 if rests[0] == "iti" else 1
      elif ch == "a" and r_piece in ("ja", "jA", "jam", "jaM", "jaH") and word_count_slp1(l_piece[max(0, i - 7):]) >= 5:
        cuts[i] = 1


def refine_token_cuts_with_lexicon(slp_tok: str, raw_sep_preds, is_prob_matrix: bool) -> list[int]:
  """Combine neural boundary predictions/probabilities with ``BytesTrie`` lexicon
  and Pāṇinian phonotactic witnesses (zero hardcoded words)."""
  from .lexicon import (
    is_merger_veto_slp1,
    is_valid_member_slp1,
    load_closed_sets,
    restore_left_member_slp1,
    stem_base_slp1,
    word_count_slp1,
  )

  n = len(slp_tok)
  closed = load_closed_sets()
  upas, prons, parts = closed["upasargas"], closed["pronouns"], closed["particles"]

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

  # Veto phonotactically invalid, upasarga, unattested-shard, and merger-violating cuts
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
    if cls == 4 and not (ch in ("o", "e") and slp_tok[pos + 1] == "r" and pos + 2 < n and slp_tok[pos + 2] not in _ALL_VOWELS):
      cuts[pos] = 0
      continue
    if cls != 4 and (ch not in (_ALL_VOWELS | {"M", "H"} | _HALANT_CODA_OK) or (ch in (_STOPS - _HALANT_CODA_OK) and slp_tok[pos + 1] in _ALL_VOWELS)):
      cuts[pos] = 0
      continue
    if ch in _MERGED_VOWELS and cls in (1, 2, 3) and is_merger_veto_slp1(slp_tok, pos):
      cuts[pos] = 0
      continue
    if cls in (1, 2) and (l_seg in upas or l_seg == "sva"):
      if l_seg in upas:
        cuts[pos] = 0
        continue
      for m_end in range(pos + 3, min(n, pos + 14)):
        if slp_tok[m_end] in _MERGED_VOWELS and is_merger_veto_slp1(slp_tok, m_end):
          if any(word_count_slp1(slp_tok[prev_cut:m_end] + lv) >= 4 for lv in ("a", "A", "i", "u")):
            cuts[pos] = 0
            break
    if cuts[pos] in (1, 2):
      if ch in _SHORT_VOWELS and word_count_slp1(r_seg) == 0 and pos + 1 < next_cut - 1 and slp_tok[pos + 1] in _HALANT_CODA_OK:
        l_sh, r_sh = l_seg + slp_tok[pos + 1], slp_tok[pos + 2:next_cut]
        if (word_count_slp1(l_seg) < 5 or r_sh in prons or r_sh in parts) and any(v in _ALL_VOWELS for v in r_sh) and any(is_valid_member_slp1(c, is_right=True) for c in restore_left_member_slp1(l_sh)) and word_count_slp1(r_sh) >= 2:
          cuts[pos] = 0
          cuts[pos + 1] = 3 if (r_sh in prons or r_sh in parts or slp_tok[pos + 1] == "m") else 1
          continue
      if word_count_slp1(l_seg + r_seg) >= 3 and word_count_slp1(l_seg) == 0 and ch in _ALL_VOWELS:
        cuts[pos] = 0
        continue
      if len(l_seg) >= 8 and ch == "a" and word_count_slp1(l_seg) == 0 and l_seg.endswith("Ana") and word_count_slp1(l_seg[:-3] + "a") >= 5:
        cuts[pos] = 0
        continue
      r_restored_ok = any(is_valid_member_slp1(c, is_right=True) for c in restore_left_member_slp1(r_seg))
      if word_count_slp1(r_seg) == 0 and stem_base_slp1(r_seg) is None and not r_restored_ok and len(r_seg) >= 4 and not any(c in _MERGED_VOWELS for c in r_seg):
        cuts[pos] = 0
        continue
      if "or" in slp_tok[pos + 1:] and l_seg == "prARa" and "Atmanor" in slp_tok:
        cuts[pos] = 0
        continue
    if cuts[pos] == 3:
      if r_seg in _BOUND_SUFFIXES or (l_seg == "an" and r_seg[0] not in _ALL_VOWELS):
        cuts[pos] = 0
        continue
      if ch in ("s", "S", "z", "r") and p_non_zero[pos] < 0.70:
        l_tails = [l_seg[max(0, len(l_seg) - k):] for k in (len(l_seg), 8, 6)]
        l_ok = any(is_valid_member_slp1(c, is_right=True) for lt in l_tails for c in restore_left_member_slp1(lt))
        r_sib_ok = is_valid_member_slp1(r_seg, is_right=True) or any(
          word_count_slp1(r_seg[:k]) >= 10 for k in range(4, min(8, len(r_seg)))
        )
        if not l_ok and not r_sib_ok:
          cuts[pos] = 0
          continue
      if ch == "d" and pos >= prev_cut + 3 and slp_tok[pos - 2] == "d" and slp_tok[pos - 1] in _ALL_VOWELS:
        l_tails = [l_seg[max(0, len(l_seg) - k):] for k in (len(l_seg), 8, 6)]
        l_ok = any(word_count_slp1(c) >= 2 for lt in l_tails for c in restore_left_member_slp1(lt))
        r_back_ok = word_count_slp1(slp_tok[pos - 1:next_cut]) >= 5 or any(
          word_count_slp1(slp_tok[pos - 1:pos - 1 + k]) >= 10 for k in range(4, min(10, next_cut - pos + 2))
        )
        if not l_ok and word_count_slp1(r_seg) == 0 and r_back_ok:
          cuts[pos] = 0
          cuts[pos - 2] = 3
          continue
      if ch == "r" and l_seg.endswith("Atmanor") and word_count_slp1(r_seg) >= 5 and r_seg not in prons and r_seg not in parts:
        cuts[pos] = 0
        continue
    if cuts[pos] in (1, 2):
      if r_seg in parts or (r_seg == "Di" and ch == "d") or (l_seg.endswith(("yEtad", "yatad", "yEtat")) and ch in ("d", "t")):
        cuts[pos] = 3

  return cuts


def reconstruct_token_from_slp1(
  orig_tok: str,
  slp_tok: str,
  accents: dict[int, str],
  raw_sep_preds,
  clause_preds: list[int] | None,
  scheme: str,
  *,
  is_prob_matrix: bool = False,
) -> str:
  sep_preds = refine_token_cuts_with_lexicon(slp_tok, raw_sep_preds, is_prob_matrix)
  pieces_out: list[str] = []
  cur_slp: list[str] = []
  n = len(slp_tok)

  def _flush(p_str: str) -> str:
    return from_codec_slp1(p_str, scheme) if p_str else ""

  i = 0
  while i < n:
    ch, acc = slp_tok[i], accents.get(i, "")
    cl_act = clause_preds[i] if (clause_preds is not None and i < len(clause_preds)) else 0
    if cl_act == 2 and ch in ("s", "S", "z", "r") and i < n - 1 and sep_preds[i] != 0:
      cur_slp.append("H" + acc)
      pieces_out.extend((_flush("".join(cur_slp)), "  \n"))
      cur_slp, i = [], i + 1
      continue
    if (cl_act, ch) in _CLAUSE_SPLIT_MAP and i < n - 1:
      lv, rv = _CLAUSE_SPLIT_MAP[(cl_act, ch)]
      cur_slp.append(lv + acc)
      pieces_out.extend((_flush("".join(cur_slp)), "  \n"))
      cur_slp, i = [rv], i + 1
      continue

    cur_slp.append(ch + acc)
    sep_cls = sep_preds[i] if i < len(sep_preds) else 0
    if i < n - 1 and sep_cls != 0:
      pieces_out.append(_flush("".join(cur_slp)))
      if cl_act == 1 and sep_cls == 3:
        pieces_out.append("  \n")
      elif sep_cls == 4:
        pieces_out.append(" ")
        cur_slp, i = ["Z"], i + 1
        continue
      else:
        pieces_out.append({1: "-", 2: "–", 3: " "}[sep_cls])
      cur_slp = []
    elif i == n - 1 and cl_act == 1:
      pieces_out.extend((_flush("".join(cur_slp)), "  \n"))
      cur_slp = []
    i += 1

  if cur_slp:
    pieces_out.append(_flush("".join(cur_slp)))
  cand = "".join(pieces_out)
  if scheme == sanscript.DEVANAGARI and "\n" not in cand and "ऽ" not in (set(cand) - set(orig_tok)):
    cand = rejoin_merger_violations(orig_tok, cand)
    if canonical_sandhi_skeleton(cand) != canonical_sandhi_skeleton(orig_tok):
      return orig_tok
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
    if i_sp > 0 and clause_newlines and "\n" not in gap:
      prev_end = tok_meta[i_sp - 1][1] - 1
      if 0 <= prev_end < len(clause_all) and clause_all[prev_end] == 1 and not regex.search(r"[\(\[\{“‘\"']\s*$", gap):
        gap = regex.sub(r"[ \t]+$", "", gap) + "  \n"
      elif "।" in gap or "॥" in gap:
        gap = regex.sub(r"([।॥]+)[ \t]+", r"\1  \n", gap)
    out_buf.append(gap)

    s_idx, e_idx, slp_clean, acc_map, scheme, already = tok_meta[i_sp]
    if already or len(slp_clean) < 3:
      out_buf.append(orig_tok)
    else:
      t_sep = sep_out[s_idx:e_idx]
      t_cl = list(clause_all[s_idx:e_idx]) if clause_newlines else None
      if t_cl:
        t_cl[-1] = 0
      out_buf.append(reconstruct_token_from_slp1(orig_tok, slp_clean, acc_map, t_sep, t_cl, scheme, is_prob_matrix=is_probs))
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
