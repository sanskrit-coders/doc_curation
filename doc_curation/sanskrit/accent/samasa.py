"""Hyphenator-backed samāsa & sandhi member decomposition for pada-svara lookup.

Combines ``doc_curation.sanskrit.hyphenator.hyphenate_word`` (distilled neural SLP1
hyphenator) with trie-free in-memory SLP1 lexicon checks (`lexicon.py`) to restore
sandhi-altered left members (`मध्व्` → `मधु`, `हविर्` → `हविः`, `जगद्` → `जगत्`),
decompose internal *dīrgha/guṇa/vṛddhi* compound mergers (`प्राणापानौ` → `प्राण` + `अपानौ`,
`अपोदकाभिः` → `अप` + `उदकाभिः`), and split *nañ* (`अ-`/`अन्-`) prefixes for
`*padasvara*.babylon` lookup.
"""
from __future__ import annotations

import regex
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.hyphenator import hyphenate_word
from doc_curation.sanskrit.hyphenator.lexicon import (
  is_valid_member_slp1,
  restore_left_member_slp1,
  split_vowel_merger_slp1,
  stem_base_slp1,
  word_count_slp1,
)

_SPLIT_SEPS_RE = regex.compile(r"[\s\-–—ऽ]+")
_ALL_VOWELS_SLP = frozenset("aAiIuUfFxXeEoO")


def _to_slp(dev: str) -> str:
  return sanscript.transliterate(dev, sanscript.DEVANAGARI, sanscript.SLP1)


def _to_dev(slp: str) -> str:
  return sanscript.transliterate(slp, sanscript.SLP1, sanscript.DEVANAGARI)


def _split_nan_prefix_slp1(slp_w: str) -> list[tuple[str, str]]:
  """Split *nañ* (``अ-`` / ``अन्-``) prefix when stem (or Taittirīya ``ण्ण→न्न`` norm) is attested."""
  out: list[tuple[str, str]] = []
  for pref, cond in (
    ("an", len(slp_w) >= 6 and slp_w[2:3] in _ALL_VOWELS_SLP),
    ("a", len(slp_w) >= 5 and slp_w[1:2] not in _ALL_VOWELS_SLP),
  ):
    if slp_w.startswith(pref) and cond:
      rest = slp_w[len(pref):]
      for cand in dict.fromkeys((rest, rest.replace("RR", "nn"))):
        if is_valid_member_slp1(cand, is_right=True):
          out.append((pref, rest))
          if cand != rest:
            out.append((pref, cand))
          break
      if out:
        return out
  return out


def decompose_samasa_for_padasvara(token: str) -> list[str]:
  """Decompose a Devanāgarī word/compound into candidate lexical members for padasvara lookup."""
  bare = accent.strip_accents(token).strip()
  bare = regex.sub(r"[^\u0900-\u097f\-–—ऽ]", "", bare)
  if len(bare) < 3:
    return [bare] if bare else []

  hyph = hyphenate_word(bare) if "ऽ" not in bare and "-" not in bare else bare
  raw_pieces = [p for p in _SPLIT_SEPS_RE.split(hyph) if p]

  members_dev: list[str] = []
  for idx, piece in enumerate(raw_pieces):
    slp_piece = _to_slp(piece)
    is_last = idx == len(raw_pieces) - 1

    if not is_last:
      for restored_slp in restore_left_member_slp1(slp_piece):
        members_dev.append(_to_dev(restored_slp))
    else:
      if slp_piece.startswith(("Z", "'")) and len(slp_piece) >= 2:
        members_dev.append(_to_dev("a" + slp_piece[1:]))
      else:
        members_dev.append(piece)

    mergers = split_vowel_merger_slp1(slp_piece)
    for lu, ru in mergers:
      members_dev.append(_to_dev(lu))
      members_dev.append(_to_dev(ru))

    # Decompose lexicalized dictionary compounds (आण्डकोशे -> आण्ड + कोशे, हविर्वाट् -> हविः + वाट्)
    if len(raw_pieces) == 1 and not mergers:
      for cut in range(2, len(slp_piece) - 1):
        l_s, r_s = slp_piece[:cut], slp_piece[cut:]
        if not is_valid_member_slp1(r_s, is_right=True):
          continue
        if l_s[-1] in "aAiIuU" and r_s[0] not in _ALL_VOWELS_SLP and word_count_slp1(l_s) >= 3:
          members_dev.append(_to_dev(l_s))
          members_dev.append(_to_dev(r_s))
          break
        if l_s[-1] in "trszSdnjcyvk" and len(l_s) >= 3 and r_s[0] not in _ALL_VOWELS_SLP:
          restored = [c for c in restore_left_member_slp1(l_s) if word_count_slp1(c) >= 3]
          if restored:
            members_dev.append(_to_dev(restored[0]))
            members_dev.append(_to_dev(r_s))
            break

    for p_s, r_s in _split_nan_prefix_slp1(slp_piece):
      members_dev.append(_to_dev(p_s))
      members_dev.append(_to_dev(r_s))

  enriched: list[str] = []
  for m in members_dev:
    if not m:
      continue
    enriched.append(m)
    base_s = stem_base_slp1(_to_slp(m))
    if base_s and len(base_s) >= 2:
      enriched.append(_to_dev(base_s))
  return [x for x in dict.fromkeys(enriched) if x and x != bare]
