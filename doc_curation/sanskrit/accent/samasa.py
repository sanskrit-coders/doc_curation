"""Hyphenator-backed samāsa & sandhi member decomposition for pada-svara lookup.

Why inline ``hyphenate_word`` helps — and where ``pada-svara`` needs one extra step:
1. ``doc_curation.sanskrit.hyphenator.hyphenate_word`` splits separable word and
   compound seams (plain concatenation ``पुण्य-पापैः``, assimilation ``जगत्-कारणम्``,
   yaṇ ``मध्व्-अरिः``, visarga ``यशो-दा``) against fast prebuilt ``marisa`` tries.
2. However, inline प्रस्तुति hyphenation enforces an **absolute non-separability veto**
   on *dīrgha / guṇa / vṛddhi* vowel mergers (``प्राणापानौ``, ``अपोदकाभिः``, ``सूर्यास्तम्``).
   For ``पद-पाठः`` / ``pada-svara`` creation, we MUST also decompose across internal
   vowel-merger and *nañ* (``अ-`` / ``अन्-``) compound joints and restore sandhi-altered
   left members (``मध्व्`` → ``मधु``, ``हविर्`` → ``हविः``, ``जगद्`` → ``जगत्``) so each
   member's attested accent can be retrieved from ``*padasvara*.babylon`` lexicons
   before applying Pāṇinian ``समास-स्वरः`` rules (पा० ६.१.२२३, ६.२.१, ६.२.२, ६.२.४९, ६.२.१३९).
"""

from __future__ import annotations

from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent
import regex

_SPLIT_SEPS_RE = regex.compile(r"[\s\-–—ऽ]+")
_EXTRA_RIGHT_ENDINGS = (
    "au", "aiH", "ebhyaH", "AbhiH", "Asu", "eSu", "AnAm", "InAm", "UnAm",
    "am", "aH", "ena", "Aya", "At", "asya", "e", "A", "AH", "An", "In", "Un",
)


def _load_hyphenator_modules():
  """Lazy import to avoid circular import with ``doc_curation.sanskrit.__init__``."""
  from doc_curation.sanskrit.hyphenator import constants as hc
  from doc_curation.sanskrit.hyphenator import hyphenate_word
  from doc_curation.sanskrit.hyphenator import tries as ht
  from doc_curation.sanskrit.hyphenator import validate as hv
  return hc, ht, hv, hyphenate_word


def _hk(dev: str) -> str:
  return sanscript.transliterate(dev, sanscript.DEVANAGARI, sanscript.HK)


def _dev(hk: str) -> str:
  return sanscript.transliterate(hk, sanscript.HK, sanscript.DEVANAGARI)


def _stem_base_extra_hk(hk: str, ht, hv) -> str | None:
  base = hv._stem_base_piece(hk)
  if base:
    return base
  words = ht._load_words()
  for end in _EXTRA_RIGHT_ENDINGS:
    if hk.endswith(end) and len(hk) >= len(end) + 2:
      pre = hk[: -len(end)]
      for fin in ("a", "A", "i", "I", "u", "U", ""):
        cand = pre + fin
        if len(cand) >= 3 and cand in words and hv._count_of(cand) >= 2:
          return cand
  return None


def _is_valid_member_hk(hk: str, hc, ht, hv, *, is_right: bool = False) -> bool:
  if not hk:
    return False
  words = ht._load_words()
  if hk in hc._UPASARGAS or hk in hc._AVYAYAS or hk in hc._PRONOUNS:
    return True
  if len(hk) < 2:
    return False
  if hk in words and (hv._count_of(hk) >= 2 or len(hk) >= 4):
    return True
  if is_right and (hv._stem_valid(hk) or hv._stem_valid_piece(hk) or _stem_base_extra_hk(hk, ht, hv) is not None):
    return True
  if not is_right and hk in hc._TRIE_NOMINAL_STEMS:
    return True
  return False


def _restore_left_member_hk(hk: str, hc, ht, hv) -> list[str]:
  words = ht._load_words()
  out: list[str] = []
  for cand in hv._restores_of(hk):
    if cand in words or cand in hc._AVYAYAS or cand in hc._UPASARGAS or hv._stem_valid(cand):
      out.append(cand)
  if hk in words or hk in hc._TRIE_NOMINAL_STEMS or hk in hc._AVYAYAS or hk in hc._UPASARGAS:
    out.append(hk)
  if not out:
    out.append(hk)
  return list(dict.fromkeys(out))


def _split_vowel_merger_hk(hk: str, hc, ht, hv) -> list[tuple[str, str]]:
  n = len(hk)
  if n < 5:
    return []
  words = ht._load_words()
  scored: list[tuple[int, str, str]] = []
  for p in range(1, n - 2):
    for mlen in (2, 1):
      if p + mlen >= n:
        continue
      mv = hk[p : p + mlen]
      if mlen == 1 and mv not in "AIUeo":
        continue
      exps = hv._merger_exps(mv)
      if not exps:
        continue
      left_pre = hk[:p]
      right_rest = hk[p + mlen :]
      for lv, rv in exps:
        lu = left_pre + lv
        ru = rv + right_rest
        if len(lu) < 2 or len(ru) < 2:
          continue
        if not _is_valid_member_hk(lu, hc, ht, hv, is_right=False):
          continue
        if not _is_valid_member_hk(ru, hc, ht, hv, is_right=True):
          continue
        score = min(hv._count_of(lu), 50) + min(hv._count_of(ru), 50)
        if lu in words:
          score += 20
        if ru in words:
          score += 20
        scored.append((score, lu, ru))
  scored.sort(key=lambda t: (-t[0], len(t[1])))
  seen: set[tuple[str, str]] = set()
  out: list[tuple[str, str]] = []
  for _, lu, ru in scored:
    if (lu, ru) not in seen:
      seen.add((lu, ru))
      out.append((lu, ru))
  return out[:2]


def _split_nan_or_upasarga_hk(hk: str, ht, hv) -> list[tuple[str, str]]:
  words = ht._load_words()
  out: list[tuple[str, str]] = []
  for pref, cond in (
      ("an", len(hk) >= 6 and hk[2:3] in "aAiIuUfFeEoO"),
      ("a", len(hk) >= 5 and hk[1:2] not in "aAiIuUfFeEoO"),
  ):
    if hk.startswith(pref) and cond:
      rest = hk[len(pref) :]
      for cand in dict.fromkeys((rest, rest.replace("NN", "nn"))):
        if (
            cand in words
            or hv._stem_valid(cand)
            or _stem_base_extra_hk(cand, ht, hv) is not None
            or hv._valid_piece_kind(cand)[0] is not None
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
  bare = accent.strip_accents(token).strip()
  bare = regex.sub(r"[^\u0900-\u097f\-–—ऽ]", "", bare)
  if len(bare) < 3:
    return [bare] if bare else []

  hc, ht, hv, hyphenate_word = _load_hyphenator_modules()

  hyph = hyphenate_word(bare) if "ऽ" not in bare and "-" not in bare else bare
  raw_pieces = [p for p in _SPLIT_SEPS_RE.split(hyph) if p]

  members_dev: list[str] = []
  for idx, piece in enumerate(raw_pieces):
    hk_piece = _hk(piece)
    is_last = idx == len(raw_pieces) - 1

    if not is_last:
      for restored_hk in _restore_left_member_hk(hk_piece, hc, ht, hv):
        members_dev.append(_dev(restored_hk))
    else:
      if hk_piece.startswith("'") and len(hk_piece) >= 2:
        members_dev.append(_dev("a" + hk_piece[1:]))
      else:
        members_dev.append(piece)

    mergers = _split_vowel_merger_hk(hk_piece, hc, ht, hv)
    for lu, ru in mergers:
      members_dev.append(_dev(lu))
      members_dev.append(_dev(ru))

    if len(raw_pieces) == 1 and not mergers:
      words = ht._load_words()
      for cut in range(2, len(hk_piece) - 1):
        l_hk, r_hk = hk_piece[:cut], hk_piece[cut:]
        if not (r_hk in words or hv._stem_valid(r_hk) or _stem_base_extra_hk(r_hk, ht, hv) is not None):
          continue
        if l_hk[-1] in "aAiIuU" and r_hk[0] not in "aAiIuUeEoO":
          if l_hk in hc._TRIE_NOMINAL_STEMS and hv._count_of(l_hk) >= 3:
            members_dev.append(_dev(l_hk))
            members_dev.append(_dev(r_hk))
            break
        elif l_hk[-1] in "rszSdnjcyv" and len(l_hk) >= 3 and r_hk[0] not in "aAiIuUeEoO":
          restored = [c for c in hv._restores_of(l_hk) if c in words and hv._count_of(c) >= 3]
          if restored:
            members_dev.append(_dev(restored[0]))
            members_dev.append(_dev(r_hk))
            break

    for p_hk, r_hk in _split_nan_or_upasarga_hk(hk_piece, ht, hv):
      members_dev.append(_dev(p_hk))
      members_dev.append(_dev(r_hk))

  enriched: list[str] = []
  for m in members_dev:
    if not m:
      continue
    enriched.append(m)
    m_hk = _hk(m)
    base_hk = _stem_base_extra_hk(m_hk, ht, hv)
    if base_hk and len(base_hk) >= 3:
      enriched.append(_dev(base_hk))

  return [x for x in dict.fromkeys(enriched) if x and x != bare]
