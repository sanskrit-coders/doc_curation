"""Mechanical US-accented ``पद-पाठः (यान्त्रिकः)`` builder for Taittirīya Saṁhitā/Brāhmaṇa/Kāṭhaka Markdown files.

Projects authoritative ground-truth US accents (``᳓`` / ``᳙``) directly from each
block's classical Taittirīya ``<details><summary>मूलम्</summary>`` (falling back to
``विश्वास-प्रस्तुतिः`` only for all-udātta phrases lacking classical ``॒``/``॑`` or blocks
without ``मूलम्``) onto sandhi-split, compound-hyphenated padas produced by
:mod:`doc_curation.sanskrit.accent.shatapatha_solver` and verified by
:func:`doc_curation.sanskrit.accent.sandhi_check.verify_mantra_sandhi`.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import logging
import os
import re
from pathlib import Path
from typing import Iterable, Sequence

from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.accent.reconciler import (
  DETAILS_RE,
  US_SVARITA,
  US_UDATTA,
  _map_pp_to_vp_syllables,
  find_js_include_spans,
  has_us_accents,
)
from doc_curation.sanskrit.accent.sandhi_check import verify_mantra_sandhi
from doc_curation.sanskrit.accent.shatapatha_solver import (
  UnifiedVedicLexicon,
  _DEVANAGARI_RE,
  _clean_pada_orthography,
  _deva_to_slp,
  _fast_apply_us_marks,
  _fast_extract_vp_pieces,
  _fast_flatten_pp_and_starts,
  _fast_scan_deva_syllables,
  _fast_syllables_with_marks,
  _hyphenate_compound_pada,
  _is_dual_accent_word,
  _normalize_lookup_key,
  _slp_to_deva,
  _strip_leading_upasargas_tinanta,
  split_chunk_to_padas_dp,
  split_vp_to_padas_with_clauses,
)

_SKIP_FILENAMES = frozenset({"_index.md", "file_list.md"})
_TAITTIRIYA_TTR_RE = re.compile(
  r"(क्ष|नक्ष|पु|रा|हो|स्तो|गो|सू|वस्|शस्|मन्|प|अ|च)([\u0951\u0952\u1cd3\u1cd9]*)त्त्र"
)

_ENCLITIC_ALWAYS_UNACCENTED: frozenset[str] = frozenset({
  "च", "वा", "उ", "ह", "स्म", "इव", "मे", "ते", "त्वा", "नः", "वः", "सीम्", "ईम्",
})
_ANVADESHA_ENCLITICS: frozenset[str] = frozenset({
  "एनम्", "एनाम्", "एनत्", "एनौ", "एने", "एनान्", "एनाः", "एनानि", "एनेन", "एनया", "एनयोः",
  "अस्य", "अस्याः", "अस्मै", "अस्यै", "अस्मात्", "अस्मिन्", "अस्याम्", "अनेन", "अनया", "अयोः",
  "एभिः", "एभ्यः", "एषाम्", "एषु", "आभिः", "आभ्यः", "आसाम्", "आसु",
})
_UPASARGAS_BARE: frozenset[str] = frozenset({
  "प्र", "परा", "अप", "सम्", "अनु", "अव", "निस्", "निः", "निर्", "दुस्", "दुः", "दुर्",
  "वि", "आ", "नि", "अधि", "अपि", "अति", "सु", "उत्", "अभि", "प्रति", "परि", "उप", "अच्छ", "अच्छा",
})
_MULA_FOOTNOTE_DEF_RE = re.compile(r"(?m)^\[\^[^\]]+\]:.*$")
_SANDHI_BREAK_CONSONANT_RE = re.compile(
  r"(?:द्(?=ध|भ|व|र|य|ग|द|ब|न|म)|त्(?=त|थ|प|फ|क|ख|स|श|ष)|च्(?=च|छ)|ज्(?=ज|झ)|ल्(?=ल)|न्(?=त|थ|द|ध|न|म|स|श|ष)|ङ्(?=क|ख|ग|घ|न|म)|ञ्(?=च|छ|ज|झ|श)|म्(?=प|फ|ब|भ|म|य|र|ल|व|स|श|ष|ह))"
)
_PREF_BREAK_LIST: tuple[str, ...] = (
  "प्र", "अभि", "प्रति", "परि", "अधि", "अति", "अनु", "अव", "अप", "उप", "सम्", "उत्", "निः", "वि", "नि", "सु",
)

_WORKER_LEX: UnifiedVedicLexicon | None = None


@dataclasses.dataclass(frozen=True)
class BlockPadapathaResult:
  """Result of building a mechanical padapāṭha for one ``(VP, मूलम्)`` block."""

  padas_us: list[str]
  padas_bare: list[str]
  sandhi_ok: bool
  sandhi_detail: str
  multi_udatta_padas: list[str]
  unmapped_syllables: int
  used_vp_fallback: bool = False


def clean_mula_text(raw_mula: str) -> str:
  """Remove markdown/footnote/numbering noise from a ``मूलम्`` or ``विश्वास-प्रस्तुतिः`` block."""
  s = _MULA_FOOTNOTE_DEF_RE.sub("", raw_mula)
  s = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]", " ", s, flags=re.S)
  s = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\1", s)
  s = re.sub(r"<[^>]+>", " ", s)
  s = re.sub(r"[*\"'><…\u200c\u200d]", "", s)
  # Strip numeric section markers like `॥ 28 ॥`, `॥२८॥`, `। 1 ।`, or trailing bare digits
  s = re.sub(r"॥\s*[०-९0-9]+\s*॥", " ॥ ", s)
  s = re.sub(r"।\s*[०-९0-9]+\s*।", " । ", s)
  s = re.sub(r"[०-९0-9]+", " ", s)
  s = re.sub(r"[ \t]+", " ", s)
  return s.strip()


def normalize_taittiriya_orthography(text: str) -> str:
  """Normalize Taittirīya saṁhitā orthography while preserving exact syllable count & accents."""
  s = text
  # Jihvāmūlīya & Upadhmānīya -> visarga (keep any following accent mark intact)
  s = s.replace("ᳵ", "ः").replace("ᳶ", "ः").replace("ꣳ", "ं")
  # Taittirīya nasalized glides for final -म् before homorganic glide (`सं॒ज्ञानव्ँ॑ वि॒ज्ञानं॑`, `पत्नीसय्ंयाज`, `क्षय्यल्ँ᳓ लोक᳓म्`)
  # Match BOTH candrabindu (`ँ`) and anusvāra (`ं`), and BOTH classical (`\u0951\u0952`) and US (`\u1cd3\u1cd9`) accent marks!
  s = re.sub(r"([वयल])्[ँं]([\u0951\u0952\u1cd3\u1cd9]*)", r"ं\2", s)
  # Spaced पा॰ ८.३.७ nasal + sibilant (`आतपँ॒ स्तप॑न्` -> `आतपं॒स्तप॑न्`)
  s = re.sub(r"ँ([\u0951\u0952\u1cd3\u1cd9]*)\s+(?=स्[तथ]|श्[चछ]|ष्[टठ])", r"ं\1", s)
  # Remaining candrabindu -> anusvāra (preserve syllable count; non-syllabic)
  s = s.replace("ँ", "ं")
  # Degeminate Taittirīya orthographic doublings (`र्द्ध` -> `र्ध`, `क्ष॒त्त्र` -> `क्ष॒त्र`, `पु॒त्त्र` -> `पु॒त्र`, etc.)
  s = re.sub(r"र्([क-ह])्\1", r"र्\1", s)
  s = _TAITTIRIYA_TTR_RE.sub(r"\1\2त्र", s)
  # Known Taittirīya print whitespace typos inside a single compound (`सं वत्सर` -> `संवत्सर`)
  s = re.sub(r"(?<![\u0900-\u097f])सं([\u0951\u0952\u1cd3\u1cd9]*)\s+वत्सर", r"सं\1वत्सर", s)
  s = re.sub(r"\s+", " ", s).strip()
  return s


def _detect_post_udatta_classical_svarita_indices(mula_clean_classical: str) -> set[int]:
  """Return syllable indices in ``mula_clean_classical`` that carry classical ``॑`` right after an udātta."""
  if "\u0951" not in mula_clean_classical and "\u0952" not in mula_clean_classical:
    return set()
  # Normalize Taittirīya orthography identically (without stripping ॒/॑) so syllable indices match 1:1
  norm_cl = normalize_taittiriya_orthography(mula_clean_classical)
  us_ver = accent.to_US_accents(norm_cl, pauses=r"[।॥,;]+")
  _, us_mks = _fast_syllables_with_marks(us_ver)
  cl_syls = _fast_scan_deva_syllables(norm_cl)
  if len(cl_syls) != len(us_mks):
    return set()
  out: set[int] = set()
  for idx in range(1, len(cl_syls)):
    if "\u0951" in cl_syls[idx][0] and us_mks[idx] == "" and us_mks[idx - 1] == "U":
      out.add(idx)
  return out


def _mula_to_us_ground_truth(
  mula_raw: str | None,
  vp_raw: str | None,
) -> tuple[str, set[int], bool]:
  """Return ``(normalized_us_samhita, post_udatta_svarita_syl_indices, used_vp_fallback)``."""
  if mula_raw:
    cleaned = clean_mula_text(mula_raw)
    if "\u0951" in cleaned or "\u0952" in cleaned:
      norm_cl = normalize_taittiriya_orthography(cleaned)
      us_txt = accent.to_US_accents(norm_cl, pauses=r"[।॥,;]+")
      post_u_sv = _detect_post_udatta_classical_svarita_indices(cleaned)
      return us_txt, post_u_sv, False
    if has_us_accents(cleaned):
      return normalize_taittiriya_orthography(cleaned), set(), False
  if vp_raw:
    cleaned_vp = clean_mula_text(vp_raw)
    return normalize_taittiriya_orthography(cleaned_vp), set(), True
  return "", set(), True


def _split_chunk_with_avagraha_and_hints(
  tok: str,
  lex: UnifiedVedicLexicon,
  *,
  next_tok: str = "",
  is_end: bool = False,
) -> list[str]:
  """Fallback splitter for long/unsplit chunks containing internal ``ऽ`` or consonant sandhi."""
  # 1. If token contains internal avagraha `ऽ` (`देवतयाऽङ्गिरस्वद्ध्रुवा`, `साम्नाऽर्थोऽस्ति`), split on `ऽ`!
  if "ऽ" in tok and not tok.startswith("ऽ"):
    parts = [p for p in tok.split("ऽ") if p]
    if len(parts) >= 2:
      out: list[str] = []
      for idx, p in enumerate(parts):
        sub_next = ("ऽ" + parts[idx + 1]) if idx + 1 < len(parts) else next_tok
        sub_end = is_end and (idx == len(parts) - 1)
        sub_padas = split_chunk_to_padas_dp(
          p,
          lex,
          next_tok_deva=sub_next,
          is_end_of_clause=sub_end,
          leading_avagraha=(idx > 0),
        )
        out.extend(sub_padas)
      if len(out) >= 2:
        return out
  return [tok]


def _try_split_multi_accent_pada(
  pada_bare: str,
  marks: Sequence[str],
  lex: UnifiedVedicLexicon,
) -> list[str] | None:
  """Try to split an unsplit multi-accent token at consonant/vowel sandhi seams between accents."""
  acc_positions = [i for i, m in enumerate(marks) if m]
  if len(acc_positions) < 2:
    return None
  clean = pada_bare.replace("-", "")
  if _is_dual_accent_word(_normalize_lookup_key(clean)):
    return None

  # First try avagraha split if present
  if "ऽ" in clean and not clean.startswith("ऽ"):
    res = _split_chunk_with_avagraha_and_hints(clean, lex)
    if len(res) >= 2:
      return res

  # Try splitting at internal consonant sandhi seams where each side is >= 2 syllables and at least one side is in lex
  slp = _deva_to_slp(clean)
  if not slp or len(slp) < 6:
    return None

  best: tuple[float, list[str]] | None = None
  # Candidate split indices in SLP1 with optional final consonant normalization
  for i in range(3, len(slp) - 2):
    left_raw = slp[:i]
    right_raw = slp[i:]
    if right_raw[0] in "aAiIuUfFxXeEoO":
      continue
    left_cands: list[tuple[str, float]] = [(left_raw, 0.2)]
    if left_raw.endswith("d"):
      left_cands.append((left_raw[:-1] + "t", 0.0))
    elif left_raw.endswith(("M", "n", "N", "Y")):
      left_cands.append((left_raw[:-1] + "m", 0.05))
      if left_raw[-1] in ("n", "Y"):
        left_cands.append((left_raw[:-1] + "n", 0.08))
    elif left_raw.endswith(("nt", "wt")) and right_raw.startswith("s"):
      left_cands.append((left_raw[:-1], 0.05))
    elif left_raw.endswith(("s", "S", "z", "r")):
      left_cands.append((left_raw[:-1] + "H", 0.05))
    elif left_raw.endswith("o"):
      left_cands.append((left_raw[:-1] + "aH", 0.05))
    elif left_raw.endswith(("c", "j", "l")):
      left_cands.append((left_raw[:-1] + "t", 0.1))

    for l_slp, pen in left_cands:
      l_deva = _clean_pada_orthography(_slp_to_deva(l_slp))
      r_deva = _clean_pada_orthography(_slp_to_deva(right_raw))
      # Try recursive DP on both halves if right half is long
      l_sc = lex.word_score_slp(l_slp)
      r_sc = lex.word_score_slp(right_raw)
      if l_sc <= 0 and r_sc <= 0:
        continue
      l_padas = [l_deva] if l_sc > 0 else split_chunk_to_padas_dp(l_deva, lex, next_tok_deva=r_deva)
      r_padas = [r_deva] if r_sc > 0 else split_chunk_to_padas_dp(r_deva, lex, is_end_of_clause=True)
      cand_padas = [_hyphenate_compound_pada(w, lex) for w in (l_padas + r_padas)]
      # Verify sandhi round-trip on the single chunk
      ok, _, _, _ = verify_mantra_sandhi(cand_padas, clean)
      if not ok:
        continue
      # Prefer splits where BOTH sides have positive lexicon score
      score = (2.0 if l_sc > 0 else 0.0) + (2.0 if r_sc > 0 else 0.0) - pen - 0.1 * len(cand_padas)
      if best is None or score > best[0]:
        best = (score, cand_padas)
  return best[1] if best is not None else None


def _valid_sandhi_mark_pairs(
  obs_mk: str,
  p1_key: tuple[str, str],
  p2_key: tuple[str, str],
  vp_piece: dict,
  vsi: int,
) -> list[tuple[str, str]]:
  """Return valid ``(m1, m2)`` padapāṭha accent pairs yielding ``obs_mk`` under ``पा॰ ८.२.४–६``."""
  v1 = p1_key[1]
  v2 = p2_key[1]
  vp_v = vp_piece["keys"][vsi][1]
  is_yan = v1 in ("i", "u", "r", "l") and v1 != vp_v and v2 == vp_v
  is_abhinihita = vsi in vp_piece.get("avagraha_after", set()) and v1 in ("e", "o") and v2 == "a"

  if obs_mk == "":
    return [("", "")]
  if obs_mk == "S":
    if is_yan or is_abhinihita:
      return [("U", ""), ("S", "")]
    # Praśliṣṭa / general svarita (पा॰ ८.२.६)
    return [("U", ""), ("", "S"), ("S", "")]
  # obs_mk == "U"
  if is_yan:
    # पा॰ ८.२.४: udātta i/u + anudātta V yields svarita, NEVER udātta! So V MUST be udātta.
    return [("", "U"), ("U", "U")]
  if is_abhinihita:
    # पा॰ ८.२.५: anudātta e/o + udātta a -> udātta (or optional पा॰ ८.२.६ udātta e/o + anudātta a -> udātta)
    return [("", "U"), ("U", ""), ("U", "U")]
  # General vowel ekādeśa पा॰ ८.२.५: udātta if either or both are udātta
  return [("U", ""), ("", "U"), ("U", "U")]


def _score_pada_accent_choice(
  pada_bare: str,
  marks: tuple[str, ...],
  lex: UnifiedVedicLexicon,
  *,
  is_clause_start: bool,
  prev_pada_bare: str = "",
  next_pada_bare: str = "",
) -> float:
  """Score how well ``marks`` fits ``pada_bare`` using Vedic corpora, Vidyut morphology, and nighāta rules."""
  key = _normalize_lookup_key(pada_bare)
  n_acc = sum(1 for m in marks if m)
  score = 0.0

  # 1. Hard ekasvara penalty (पा॰ ६.१.१५८)
  if n_acc > 1 and not _is_dual_accent_word(key):
    score -= 20.0

  # 2. Direct corpus attestation across RV, TS, AV, SB-M, VS-M, MW
  acc_map = lex.form_accents.get(key)
  if acc_map:
    srcs = acc_map.get(marks)
    if srcs:
      tot_freq = sum(srcs.values())
      score += 6.0 + min(4.0, tot_freq / 5.0)
    else:
      # Penalize contradicting a strongly attested accent pattern
      other_freq = sum(sum(s.values()) for s in acc_map.values())
      if n_acc == 0 and any(not any(mk) for mk in acc_map):
        score += 2.0
      elif other_freq >= 2:
        score -= 2.5

  # 3. Enclitics & particles (पा॰ ८.१.१८ / २.४.३४)
  if key in _ENCLITIC_ALWAYS_UNACCENTED:
    score += 7.0 if n_acc == 0 else -8.0
  elif key in _ANVADESHA_ENCLITICS and not is_clause_start:
    score += 1.5 if n_acc == 0 else 0.0
  elif key in ("वै", "एव", "अथ", "अथो", "हि", "खलु", "न", "मा", "इति", "तत्", "यत्", "सः", "यः", "एषः", "अयम्", "इदम्", "अत्र", "तत्र", "यत्र", "यथा", "तथा", "यदा", "तदा", "अपि", "उत", "आ"):
    if n_acc == 1:
      score += 2.0
    elif n_acc == 0:
      score -= 2.5

  # 4. Upasarga before finite verb (पा॰ ८.१.२८ / ८.१.७१)
  if key in _UPASARGAS_BARE:
    score += 1.5 if n_acc == 1 else 0.5

  # 5. Finite verb nighāta heuristic (पा॰ ८.१.२८)
  if not is_clause_start and key not in _UPASARGAS_BARE and key not in _ENCLITIC_ALWAYS_UNACCENTED:
    morph = lex.analyze_morph(key)
    if morph["is_tinanta"] and not morph["has_non_voc_subanta"] and not morph["is_avyaya"]:
      score += 2.0 if n_acc == 0 else 0.5
    elif morph["has_non_voc_subanta"] and not morph["is_tinanta"] and not morph["voc_possible"]:
      score += 1.5 if n_acc == 1 else -2.0

  return score


def _project_us_marks_onto_padas(
  padas_bare: list[str],
  mula_us_norm: str,
  post_udatta_sv: set[int],
  lex: UnifiedVedicLexicon,
  *,
  clause_starts: set[int] | None = None,
) -> tuple[list[tuple[str, ...]], int]:
  """Project ground-truth US syllable marks from ``mula_us_norm`` onto ``padas_bare``."""
  if not padas_bare:
    return [], 0
  clause_starts = clause_starts or {0}

  vp_pieces = _fast_extract_vp_pieces(mula_us_norm)
  vp_keys: list[tuple[str, str]] = []
  vp_meta: list[tuple[int, int]] = []
  vp_flat_idx_of: dict[tuple[int, int], int] = {}
  for pi, pc in enumerate(vp_pieces):
    for vsi, kv in enumerate(pc["keys"]):
      vp_flat_idx_of[(pi, vsi)] = len(vp_keys)
      vp_keys.append(kv)
      vp_meta.append((pi, vsi))

  pp_keys, pp_meta, member_starts, pada_syl_counts = _fast_flatten_pp_and_starts(padas_bare)
  if not pp_keys or not vp_keys:
    return [tuple("" for _ in range(c)) for c in pada_syl_counts], len(pp_keys)

  pc_syl_sources = _map_pp_to_vp_syllables(
    mula_us_norm, vp_pieces, pp_keys, pp_meta, vp_keys, vp_meta, member_starts
  )

  # Pass 1: Assign unambiguous 1:1 syllable marks directly; queue merged (2->1 or 3->1) syllables
  n_pp = len(pp_keys)
  pp_marks: list[str | None] = [None] * n_pp
  merged_constraints: list[tuple[tuple[int, ...], str, dict, int]] = []
  pp_first_vp_flat: dict[int, int] = {}

  for pi, pc in enumerate(vp_pieces):
    for vsi, src_list in enumerate(pc_syl_sources[pi]):
      if not src_list:
        continue
      obs_mk = pc["old_mks"][vsi]
      tup = src_list[0]
      v_flat = vp_flat_idx_of[(pi, vsi)]
      if len(tup) == 1:
        p_si = tup[0]
        pp_marks[p_si] = obs_mk
        pp_first_vp_flat[p_si] = v_flat
      else:
        for p_si in tup:
          pp_first_vp_flat.setdefault(p_si, v_flat)
        merged_constraints.append((tup, obs_mk, pc, vsi))

  # Compute per-pada slice ranges in pp_marks
  pada_ranges: list[tuple[int, int]] = []
  off = 0
  for cnt in pada_syl_counts:
    pada_ranges.append((off, off + cnt))
    off += cnt

  def _existing_other_accents(pada_idx: int, exclude_si: int) -> int:
    a, b = pada_ranges[pada_idx]
    return sum(1 for k in range(a, b) if k != exclude_si and pp_marks[k])

  # Pass 2: Resolve merged sandhi syllables using पा॰ ८.२.४–६ + पा॰ ६.१.१५८ + lexicon scoring
  for tup, obs_mk, pc, vsi in merged_constraints:
    if len(tup) == 2:
      p1, p2 = tup
      cand_pairs = _valid_sandhi_mark_pairs(obs_mk, pp_keys[p1], pp_keys[p2], pc, vsi)
      if len(cand_pairs) == 1:
        pp_marks[p1], pp_marks[p2] = cand_pairs[0]
        continue
      pi1, si1 = pp_meta[p1]
      pi2, si2 = pp_meta[p2]
      best_pair = cand_pairs[0]
      best_sc = -1e9
      for m1, m2 in cand_pairs:
        a1, b1 = pada_ranges[pi1]
        a2, b2 = pada_ranges[pi2]
        if pi1 == pi2:
          # Same compound internal sandhi
          trial = [m or "" for m in pp_marks[a1:b1]]
          trial[si1] = m1
          trial[si2] = m2
          sc = _score_pada_accent_choice(
            padas_bare[pi1], tuple(trial), lex, is_clause_start=(pi1 in clause_starts)
          )
        else:
          t1 = [m or "" for m in pp_marks[a1:b1]]
          t1[si1] = m1
          t2 = [m or "" for m in pp_marks[a2:b2]]
          t2[si2] = m2
          sc1 = _score_pada_accent_choice(
            padas_bare[pi1], tuple(t1), lex, is_clause_start=(pi1 in clause_starts)
          )
          sc2 = _score_pada_accent_choice(
            padas_bare[pi2], tuple(t2), lex, is_clause_start=(pi2 in clause_starts)
          )
          # Slight preference for single-accent explanation over double-accent when tied
          tie_pen = -0.3 if (m1 and m2) else 0.0
          sc = sc1 + sc2 + tie_pen
        if sc > best_sc:
          best_sc = sc
          best_pair = (m1, m2)
      pp_marks[p1], pp_marks[p2] = best_pair
    else:
      # 3-way merge (rare, e.g. `प्र + उ + अ -> प्रो`): assign obs_mk to the member lacking an accent
      if obs_mk == "":
        for p_si in tup:
          pp_marks[p_si] = ""
      else:
        assigned = False
        for p_si in tup:
          pi_k, _ = pp_meta[p_si]
          if _existing_other_accents(pi_k, p_si) == 0 and not assigned:
            pp_marks[p_si] = "U" if obs_mk == "S" else obs_mk
            assigned = True
          else:
            pp_marks[p_si] = ""
        if not assigned:
          for idx_k, p_si in enumerate(tup):
            pp_marks[p_si] = obs_mk if idx_k == 0 else ""

  unmapped = sum(1 for m in pp_marks if m is None)
  # Fill any unmapped syllables with "" and check post-udātta classical ॑ jātya-svarita restoration
  final_pada_marks: list[tuple[str, ...]] = []
  for pi_idx, (a, b) in enumerate(pada_ranges):
    cur = [m if m is not None else "" for m in pp_marks[a:b]]
    # Post-udātta classical ॑ ambiguity (`पर॒मे व्यो॑मन्न्`): if pada has 0 accents and its first syllable
    # carried classical ॑ right after udātta, restore lexical initial `S` when lexicon unambiguously expects `S`.
    if cur and not any(cur) and a in pp_first_vp_flat and pp_first_vp_flat[a] in post_udatta_sv:
      key = _normalize_lookup_key(padas_bare[pi_idx])
      acc_map = lex.form_accents.get(key)
      s_pat = ("S",) + ("",) * (len(cur) - 1)
      if acc_map and s_pat in acc_map and not any(not any(mk) for mk in acc_map):
        cur[0] = "S"
    final_pada_marks.append(tuple(cur))

  return final_pada_marks, unmapped


def build_block_padapatha(
  mula_raw: str | None,
  vp_raw: str | None,
  lex: UnifiedVedicLexicon,
) -> BlockPadapathaResult:
  """Split one Taittirīya ``(VP, मूलम्)`` block into verified US-accented padas."""
  mula_us_norm, post_udatta_sv, used_vp_fb = _mula_to_us_ground_truth(mula_raw, vp_raw)
  if not mula_us_norm or not _DEVANAGARI_RE.search(mula_us_norm):
    return BlockPadapathaResult([], [], True, "", [], 0, used_vp_fb)

  mula_bare = accent.strip_accents(mula_us_norm)
  padas_bare, clause_starts = split_vp_to_padas_with_clauses(mula_bare, lex)

  # Pre-pass: split any fallback chunk still containing internal `ऽ`
  expanded_bare: list[str] = []
  expanded_starts: set[int] = set()
  for idx, pd in enumerate(padas_bare):
    if idx in clause_starts:
      expanded_starts.add(len(expanded_bare))
    if "ऽ" in pd and not pd.startswith("ऽ"):
      sub = _split_chunk_with_avagraha_and_hints(pd, lex)
      expanded_bare.extend(sub)
    else:
      expanded_bare.append(pd)
  padas_bare = expanded_bare
  clause_starts = expanded_starts

  # Project ground-truth US accents onto padas
  pada_marks, unmapped = _project_us_marks_onto_padas(
    padas_bare, mula_us_norm, post_udatta_sv, lex, clause_starts=clause_starts
  )

  # Refine any unsplit multi-accent non-dual padas using accent-guided splitting
  refined_bare: list[str] = []
  refined_starts: set[int] = set()
  did_refine = False
  for idx, (pd, mks) in enumerate(zip(padas_bare, pada_marks)):
    if idx in clause_starts:
      refined_starts.add(len(refined_bare))
    if sum(1 for m in mks if m) > 1 and not _is_dual_accent_word(_normalize_lookup_key(pd)):
      sub = _try_split_multi_accent_pada(pd, mks, lex)
      if sub and len(sub) >= 2:
        refined_bare.extend(sub)
        did_refine = True
        continue
    refined_bare.append(pd)

  if did_refine:
    padas_bare = refined_bare
    clause_starts = refined_starts
    pada_marks, unmapped = _project_us_marks_onto_padas(
      padas_bare, mula_us_norm, post_udatta_sv, lex, clause_starts=clause_starts
    )

  padas_us: list[str] = []
  multi_udatta: list[str] = []
  for idx_p, (pd, mks) in enumerate(zip(padas_bare, pada_marks)):
    eff_mks = mks
    key = _normalize_lookup_key(pd)
    acc_idxs = [i for i, m in enumerate(eff_mks) if m]
    if len(acc_idxs) > 1 and not _is_dual_accent_word(key):
      # When raw Taittirīya classical e-text drops a single ॒ or ॑ causing adjacent double-udātta
      # (e.g. `अ᳓थ᳓`, `इ᳓ति᳓`, `अ᳓ग्नेः᳓`, `क्रतू᳓ना᳓म्`, `ये᳓न᳓`), resolve to the lexically attested
      # single-accent subset if unambiguous in Vedic corpora.
      acc_map = lex.form_accents.get(key)
      if acc_map:
        sub_cands: list[tuple[int, tuple[str, ...]]] = []
        for ai in acc_idxs:
          cand_mk = tuple(eff_mks[j] if j == ai else "" for j in range(len(eff_mks)))
          if cand_mk in acc_map:
            sub_cands.append((sum(acc_map[cand_mk].values()), cand_mk))
        if sub_cands:
          sub_cands.sort(key=lambda x: -x[0])
          if len(sub_cands) == 1 or sub_cands[0][0] >= 3 * sub_cands[1][0]:
            eff_mks = sub_cands[0][1]
    us_w = _fast_apply_us_marks(pd, eff_mks)
    padas_us.append(us_w)
    if sum(1 for m in eff_mks if m) > 1 and not _is_dual_accent_word(key):
      multi_udatta.append(us_w)

  res = verify_mantra_sandhi(padas_bare, mula_bare)
  sandhi_ok = bool(res[0])
  sandhi_detail = "" if sandhi_ok else repr(res[1:])

  return BlockPadapathaResult(
    padas_us=padas_us,
    padas_bare=padas_bare,
    sandhi_ok=sandhi_ok,
    sandhi_detail=sandhi_detail,
    multi_udatta_padas=multi_udatta,
    unmapped_syllables=unmapped,
    used_vp_fallback=used_vp_fb,
  )


def format_taittiriya_padapatha_details(padas_us: Sequence[str]) -> str:
  """Render a compact ``।``-separated US-accented ``पद-पाठः (यान्त्रिकः)`` details block."""
  body = " । ".join(padas_us) + " ।" if padas_us else ""
  return f"<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n{body}\n</details>"


def add_padapathas_to_markdown(
  markdown_text: str,
  lex: UnifiedVedicLexicon,
  *,
  overwrite_existing_mechanical: bool = True,
) -> tuple[str, list[BlockPadapathaResult]]:
  """Insert/update ``पद-पाठः (यान्त्रिकः)`` directly below every non-``js_include`` ``मूलम्`` block."""
  inc_spans = find_js_include_spans(markdown_text)
  matches = [
    m
    for m in DETAILS_RE.finditer(markdown_text)
    if not any(a <= m.start() < b for a, b in inc_spans)
  ]
  if not matches:
    return markdown_text, []

  # Collect edits as (start, end, replacement_text)
  edits: list[tuple[int, int, str]] = []
  results: list[BlockPadapathaResult] = []
  handled_vp_indices: set[int] = set()

  for idx, m in enumerate(matches):
    hdr = m.group(1).strip()
    if hdr != "मूलम्":
      continue

    # Find immediately preceding विश्वास-प्रस्तुतिः (if any within last 3 blocks before another मूलम्)
    vp_raw: str | None = None
    for j in range(idx - 1, max(-1, idx - 4), -1):
      jh = matches[j].group(1).strip()
      if jh == "मूलम्":
        break
      if jh.startswith("विश्वास-प्रस्तुतिः"):
        vp_raw = matches[j].group(2)
        handled_vp_indices.add(j)
        break

    # Check if an existing पद-पाठः block already immediately follows this मूलम्
    next_m = matches[idx + 1] if idx + 1 < len(matches) else None
    next_hdr = next_m.group(1).strip() if next_m is not None else ""
    next_between = markdown_text[m.end() : next_m.start()] if next_m is not None else ""
    has_adjacent_trad_pp = (
      next_m is not None
      and not next_between.strip()
      and (next_hdr == "पद-पाठः" or next_hdr.startswith("पद-पाठः-"))
    )
    has_adjacent_mech_pp = (
      next_m is not None
      and not next_between.strip()
      and next_hdr.startswith("पद-पाठः (यान्त्रिकः")
    )
    if has_adjacent_trad_pp:
      continue
    if has_adjacent_mech_pp and not overwrite_existing_mechanical:
      continue

    res = build_block_padapatha(m.group(2), vp_raw, lex)
    if not res.padas_us:
      continue
    results.append(res)
    pp_block = format_taittiriya_padapatha_details(res.padas_us)
    if has_adjacent_mech_pp and next_m is not None:
      edits.append((next_m.start(), next_m.end(), pp_block))
    else:
      edits.append((m.end(), m.end(), "\n\n" + pp_block))

  # Also check for any direct विश्वास-प्रस्तुतिः without a paired मूलम् (e.g., 1 block in TB)
  for idx, m in enumerate(matches):
    if idx in handled_vp_indices:
      continue
    hdr = m.group(1).strip()
    if not hdr.startswith("विश्वास-प्रस्तुतिः"):
      continue
    # Ensure no मूलम् follows before the next VP
    has_mula = False
    for j in range(idx + 1, min(len(matches), idx + 4)):
      jh = matches[j].group(1).strip()
      if jh.startswith("विश्वास-प्रस्तुतिः"):
        break
      if jh.startswith("मूलम्"):
        has_mula = True
        break
    if has_mula:
      continue
    next_m = matches[idx + 1] if idx + 1 < len(matches) else None
    next_hdr = next_m.group(1).strip() if next_m is not None else ""
    next_between = markdown_text[m.end() : next_m.start()] if next_m is not None else ""
    has_adjacent_mech_pp = (
      next_m is not None
      and not next_between.strip()
      and next_hdr.startswith("पद-पाठः (यान्त्रिकः")
    )
    if has_adjacent_mech_pp and not overwrite_existing_mechanical:
      continue
    res = build_block_padapatha(None, m.group(2), lex)
    if not res.padas_us:
      continue
    results.append(res)
    pp_block = format_taittiriya_padapatha_details(res.padas_us)
    if has_adjacent_mech_pp and next_m is not None:
      edits.append((next_m.start(), next_m.end(), pp_block))
    else:
      edits.append((m.end(), m.end(), "\n\n" + pp_block))

  if not edits:
    return markdown_text, results

  edits.sort(key=lambda x: x[0])
  out_parts: list[str] = []
  last = 0
  for s, e, rep in edits:
    out_parts.append(markdown_text[last:s])
    out_parts.append(rep)
    last = e
  out_parts.append(markdown_text[last:])
  return "".join(out_parts), results


def _init_worker() -> None:
  global _WORKER_LEX
  _WORKER_LEX = UnifiedVedicLexicon.load_or_build(include_sb_m=True, force_rebuild=False)


def _process_file_worker(args: tuple[str, bool, bool]) -> dict:
  path_str, write, overwrite = args
  assert _WORKER_LEX is not None
  p = Path(path_str)
  orig = p.read_text(encoding="utf-8")
  updated, results = add_padapathas_to_markdown(
    orig, _WORKER_LEX, overwrite_existing_mechanical=overwrite
  )
  changed = updated != orig
  if write and changed:
    p.write_text(updated, encoding="utf-8")
  return {
    "path": path_str,
    "changed": changed,
    "blocks": len(results),
    "padas": sum(len(r.padas_us) for r in results),
    "sandhi_ok": sum(1 for r in results if r.sandhi_ok),
    "sandhi_fail": [
      (r.padas_us[:14], r.sandhi_detail) for r in results if not r.sandhi_ok
    ],
    "multi_udatta": [w for r in results for w in r.multi_udatta_padas],
    "unmapped": sum(r.unmapped_syllables for r in results),
  }


def process_directory(
  root_dir: str | os.PathLike[str],
  *,
  write: bool = False,
  overwrite_existing_mechanical: bool = True,
  max_workers: int = 1,
) -> dict:
  """Process all Markdown files under ``root_dir`` and return aggregate diagnostics."""
  root = Path(root_dir)
  files = [
    str(p)
    for p in sorted(root.rglob("*.md"), key=lambda x: x.relative_to(root).as_posix())
    if p.name not in _SKIP_FILENAMES
  ]
  if max_workers <= 1:
    lex = UnifiedVedicLexicon.load_or_build(include_sb_m=True, force_rebuild=False)
    global _WORKER_LEX
    _WORKER_LEX = lex
    per_file = [_process_file_worker((f, write, overwrite_existing_mechanical)) for f in files]
  else:
    with concurrent.futures.ProcessPoolExecutor(
      max_workers=max_workers, initializer=_init_worker
    ) as ex:
      per_file = list(
        ex.map(_process_file_worker, [(f, write, overwrite_existing_mechanical) for f in files])
      )
  return {
    "files": len(files),
    "changed_files": sum(1 for r in per_file if r["changed"]),
    "blocks": sum(r["blocks"] for r in per_file),
    "padas": sum(r["padas"] for r in per_file),
    "sandhi_ok": sum(r["sandhi_ok"] for r in per_file),
    "sandhi_fail_count": sum(len(r["sandhi_fail"]) for r in per_file),
    "multi_udatta_count": sum(len(r["multi_udatta"]) for r in per_file),
    "unmapped_syllables": sum(r["unmapped"] for r in per_file),
    "per_file": per_file,
  }
