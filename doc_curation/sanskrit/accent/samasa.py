"""Hyphenator-backed samāsa & sandhi member decomposition for pada-svara lookup.

Uses ``doc_curation.sanskrit.hyphenator`` (and its ``<2 ms`` mmap-backed
``hyphenator.lexicon`` helpers) to:
1. Split separable compound & sandhi seams via ``hyphenate_word``,
2. Restore sandhi-altered left members (``मध्व्`` → ``मधु``, ``हविर्`` → ``हविः``, ``जगद्`` → ``जगत्``),
3. Undo internal *dīrgha/guṇa/vṛddhi* compound vowel mergers vetoed in inline प्रस्तुति
   (``प्राणापानौ`` → ``प्राण`` + ``अपानौ``, ``अपोदकाभिः`` → ``अप`` + ``उदकाभिः``),
4. Split *nañ* (``अ-`` / ``अन्-``) prefixes and normalize Taittirīya *parasavarṇa* /
   retroflex allographs (``सङ्गत`` ↔ ``संगत``, ``ण्ण`` ↔ ``न्न``) for ``padasvara`` lookup.
"""

from __future__ import annotations

from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent
import regex

_SPLIT_SEPS_RE = regex.compile(r"[\s\-–—ऽ]+")
_PARASAVARNA_RE = regex.compile(
    r"ङ्(?=[कखगघ])|ञ्(?=[चछजझ])|ण्(?=[टठडढ])|न्(?=[तथदध])|म्(?=[पफबभ])"
)


def normalize_anusvara_dev(word: str) -> str:
  """Convert internal homorganic nasal + stop (``सङ्गत``) to anusvāra (``संगत``) for RV/AV/MW lookup."""
  return _PARASAVARNA_RE.sub("ं", word)


def _slp(dev: str) -> str:
  return sanscript.transliterate(dev, sanscript.DEVANAGARI, sanscript.SLP1)


def _dev(slp: str) -> str:
  return sanscript.transliterate(slp, sanscript.SLP1, sanscript.DEVANAGARI)


def _split_nan_slp1(slp_w: str, is_valid_fn, stem_base_fn) -> list[tuple[str, str]]:
  out: list[tuple[str, str]] = []
  for pref, cond in (
      ("an", len(slp_w) >= 5 and slp_w[2:3] in "aAiIuUfFeEoO"),
      ("a", len(slp_w) >= 4 and slp_w[1:2] not in "aAiIuUfFeEoO"),
  ):
    if slp_w.startswith(pref) and cond:
      rest = slp_w[len(pref) :]
      for cand in dict.fromkeys((rest, rest.replace("RR", "nn"))):
        if is_valid_fn(cand, is_right=True) or stem_base_fn(cand) is not None or (
            cand.startswith(("nir", "niS", "niz", "vi", "sam", "saM", "pra", "upa", "apa", "ava", "pari", "prati", "aBi", "aDi"))
            and len(cand) >= 5
        ):
          out.append((pref, rest))
          if cand != rest:
            out.append((pref, cand))
          break
      if out:
        return out
  return out


def decompose_samasa_for_padasvara(token: str) -> list[str]:
  """Decompose a Devanagari word/compound into candidate lexical members for padasvara lookup."""
  from doc_curation.sanskrit.hyphenator import hyphenate_word
  from doc_curation.sanskrit.hyphenator.lexicon import (
      is_valid_member_slp1,
      restore_left_member_slp1,
      split_vowel_merger_slp1,
      stem_base_slp1,
      word_count_slp1,
  )

  bare = accent.strip_accents(token).strip()
  bare = regex.sub(r"[^\u0900-\u097f\-–—ऽ]", "", bare)
  if len(bare) < 3:
    return [bare] if bare else []

  hyph = hyphenate_word(bare) if "ऽ" not in bare and "-" not in bare else bare
  raw_pieces = [p for p in _SPLIT_SEPS_RE.split(hyph) if p]

  members_dev: list[str] = []
  for idx, piece in enumerate(raw_pieces):
    slp_piece = _slp(piece)
    is_last = idx == len(raw_pieces) - 1

    if not is_last:
      for restored_slp in restore_left_member_slp1(slp_piece):
        members_dev.append(_dev(restored_slp))
    else:
      if slp_piece.startswith("'") and len(slp_piece) >= 2:
        members_dev.append(_dev("a" + slp_piece[1:]))
      else:
        members_dev.append(piece)

    mergers = split_vowel_merger_slp1(slp_piece)
    for lu, ru in mergers:
      members_dev.append(_dev(lu))
      members_dev.append(_dev(ru))

    for p_s, r_s in _split_nan_slp1(slp_piece, is_valid_member_slp1, stem_base_slp1):
      members_dev.append(_dev(p_s))
      members_dev.append(_dev(r_s))

  slp_bare = _slp(bare.replace("-", "").replace("ऽ", ""))
  if len(raw_pieces) == 1 or any(len(_slp(p)) <= 2 for p in raw_pieces):
    for cut in range(2, len(slp_bare) - 1):
      l_s, r_s = slp_bare[:cut], slp_bare[cut:]
      if not is_valid_member_slp1(r_s, is_right=True):
        continue
      if len(l_s) >= 3 and l_s[-1] in "aAiIuU" and r_s[0] not in "aAiIuUfFeEoO" and word_count_slp1(l_s) >= 3:
        members_dev.append(_dev(l_s))
        members_dev.append(_dev(r_s))
        break
      if l_s[-1] in "yv" and len(l_s) >= 3 and r_s[0] in "aAiIuUfFeEoO":
        restored = [c for c in restore_left_member_slp1(l_s) if c != l_s and word_count_slp1(c) >= 3]
        if restored:
          members_dev.append(_dev(restored[0]))
          members_dev.append(_dev(r_s))
          break
      if l_s[-1] in "rsSzdcjgtyvkpb" and len(l_s) >= 3 and r_s[0] not in "aAiIuUfFeEoO":
        restored = [c for c in restore_left_member_slp1(l_s) if word_count_slp1(c) >= 3]
        if restored:
          members_dev.append(_dev(restored[0]))
          members_dev.append(_dev(r_s))
          break

  enriched: list[str] = []
  for m in members_dev:
    if not m:
      continue
    enriched.append(m)
    anusv = normalize_anusvara_dev(m)
    if anusv != m:
      enriched.append(anusv)
    base_s = stem_base_slp1(_slp(m))
    if base_s and len(base_s) >= 2:
      b_dev = _dev(base_s)
      enriched.append(b_dev)
      b_anusv = normalize_anusvara_dev(b_dev)
      if b_anusv != b_dev:
        enriched.append(b_anusv)

  # Also include parasavarṇa-normalized whole token if different (e.g. सङ्गतोपस्थौ / सङ्गतानि -> संगतानि)
  bare_anusv = normalize_anusvara_dev(bare.replace("-", "").replace("ऽ", ""))
  if bare_anusv != bare.replace("-", "").replace("ऽ", ""):
    enriched.insert(0, bare_anusv)

  return [x for x in dict.fromkeys(enriched) if x and x != bare]
