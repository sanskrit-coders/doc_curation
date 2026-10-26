"""validate - part of the hyphenator package (see __init__.py)."""
import bisect
import glob
import math
import os
import unicodedata

import regex
import tomllib
import marisa_trie
from indic_transliteration import sanscript
import logging

from . import constants as C
from .constants import (
    _SEP_CAPTURE_RE,
    _VOWELS
)
from . import segment as SG
from . import tries as T


def _count_of(hk):
  return T._load_words().count(hk)


def _halant_final(hk_piece):
  """True when the piece renders with a final consequent virama (bare
  consonant): ``tad``, ``jagat``, ``phalam``, ``sarv``.  Visarga (``H``),
  anusvAra (``M``), vowels and avagraha do not count."""
  if not hk_piece:
    return False
  ch = hk_piece[-1]
  if ch in _VOWELS or ch in ("H", "M", "'"):
    return False
  return ch.isalpha()


def _attested(hk_piece):
  """The corpus itself uses this token - as a hyphen piece or as a whole
  unhyphenated token (bit 1 of ``rAmAnujIya-attestations.trie``)."""
  T._load_words()
  hit = _CACHE_RA_ATTESTED.get(hk_piece)
  if hit is None:
    hit = bool(C._TRIE_RA_ATTESTATIONS.count(hk_piece) & 1) \
        if C._TRIE_RA_ATTESTATIONS is not None else True
    _CACHE_RA_ATTESTED[hk_piece] = hit
  return hit


def _joined_left_attested(hk_piece):
  """The corpus itself joins this inflected (e/o-final) piece to a following
  member (``गणे-श्वरम्``, ``पङ्के-रुह``, ``मनो-बुद्धि``).

  Bit 2 of ``rAmAnujIya-attestations.trie``."""
  T._load_words()
  hit = _CACHE_ELEFT.get(hk_piece)
  if hit is None:
    hit = bool(C._TRIE_RA_ATTESTATIONS.count(hk_piece) & 2) \
        if C._TRIE_RA_ATTESTATIONS is not None else True
    _CACHE_ELEFT[hk_piece] = hit
  return hit


def _dict_attested(dev_word):
  """rAmAnujIya corpus or DCS dictionary contains this Devanagari word."""
  hit = _CACHE_DICT.get(dev_word)
  if hit is None:
    T._load_words()
    try:
      hk_word = sanscript.transliterate(dev_word, sanscript.DEVANAGARI,
                                        sanscript.HK)
    except Exception:
      hk_word = None
    hit = bool(hk_word) and (
        hk_word in C._TRIE_RA or (C._TRIE_DCS is not None and hk_word in C._TRIE_DCS))
    _CACHE_DICT[dev_word] = hit
  return hit


def _junction_dict_ok(left, right):
  """A new boundary must sit against real words: the left fragment must end
  with a rAmAnujIya/DCS word (अनेकार्थ in शब्दस्यानेकार्थ) or the right one
  must begin with one (शब्द in शब्दस्यानेकार्थ..., मध्ये itself)."""
  n = min(len(left), 20)
  for L in range(n, 3, -1):
    if _dict_attested(left[-L:]):
      return True
  n = min(len(right), 20)
  for L in range(n, 3, -1):
    if _dict_attested(right[:L]):
      return True
  return False


def _prefix_in_dict(s):
  if not s:
    return False
  return T._load_words().has_prefix(s)


def _stem_valid(hk):
  """Strip a known ending, restore stem-final, dict-check."""
  hit = _CACHE_STEM.get(hk)
  if hit is not None:
    return hit
  res = _stem_valid_uncached(hk)
  _CACHE_STEM[hk] = res
  return res


def _stem_valid_uncached(hk):
  words = T._load_words()
  for end in C._SUP_ENDINGS:
    if not hk.endswith(end):
      continue
    if len(hk) <= len(end) + 1:
      continue
    pre = hk[:len(hk) - len(end)]
    if not pre or pre in C._AVYAYAS:
      continue
    if pre in words:
      return True
    for fin in C._STEM_FINALS:
      if pre + fin in words:
        return True
  return False


def _piece_ending_ok(hk, end):
  """Piece-mode endings: length >= 2, plus M/H/m with a base >= 4 chars.
  A single vowel case ending (anugrAhake <- anugrAhaka) is fine over a long
  base - the outer check still demands the listed base word."""
  if len(end) >= 2:
    return len(hk) > len(end) + 1
  if end in ("M", "H", "m"):
    return len(hk) > len(end) + 3
  return False


def _stem_valid_piece(hk):
  """Stricter stem check for split pieces: endings of length >= 2 (or
  M/H/m with a long base); rejects shrapnel like kasm/inn/rANi."""
  hit = _CACHE_STEM_PIECE.get(hk)
  if hit is not None:
    return hit
  res = _stem_valid_piece_uncached(hk)
  _CACHE_STEM_PIECE[hk] = res
  return res


def _stem_valid_piece_uncached(hk):
  words = T._load_words()
  for end in C._SUP_ENDINGS:
    if not hk.endswith(end):
      continue
    if not _piece_ending_ok(hk, end):
      continue
    pre = hk[:len(hk) - len(end)]
    if not pre or pre in C._AVYAYAS:
      continue
    if pre in words:
      return True
    if merger_chain_valid(pre):
      return True
    for fin in C._STEM_FINALS:
      if pre + fin in words:
        return True
  return False


def _stem_base_piece(hk):
  hit = _CACHE_STEM_BASE_PIECE.get(hk)
  if hit is not None:
    return hit or None
  res = _stem_base_piece_uncached(hk)
  _CACHE_STEM_BASE_PIECE[hk] = res or ""
  return res


def _stem_base_piece_uncached(hk):
  words = T._load_words()
  for end in C._SUP_ENDINGS:
    if not _piece_ending_ok(hk, end):
      continue
    if not hk.endswith(end):
      continue
    pre = hk[:len(hk) - len(end)]
    if not pre or pre in C._AVYAYAS:
      continue
    if pre in words:
      return pre
    if merger_chain_valid(pre):
      return pre
    for fin in C._STEM_FINALS:
      if pre + fin in words:
        return pre + fin
  return None


_CACHE_CORE = {}


_CACHE_RELIABLE = {}


_CACHE_STEM = {}


_CACHE_STEM_PIECE = {}


_CACHE_STEM_BASE_PIECE = {}


_CACHE_YAN_LEFT = {}


_CACHE_VIS_RESTORE = {}


_CACHE_YAN_RESTORE = {}


_CACHE_WITNESS = {}


_CACHE_RA_ATTESTED = {}


_CACHE_ELEFT = {}


_CACHE_DICT = {}


def _memo_form_seps(form):
  """(pieces, seps) of a memoised hyphenated form, with the corpus's own
  separator glyphs: ``-`` (within-pada joint) stays ``-``, while ``--`` /
  ``–`` / ``—`` (a glued pada boundary) normalise to the preferred ``–``."""
  cached = SG._CACHE_MEMO_SEPS.get(form)
  if cached is not None:
    return cached
  pieces, seps = [], []
  for i, part in enumerate(_SEP_CAPTURE_RE.split(form)):
    if i % 2 == 0:
      if part:
        pieces.append(part)
    else:
      seps.append("-" if part == "-" else "–")
  seps = seps[:max(0, len(pieces) - 1)]
  while len(seps) < len(pieces) - 1:
    seps.append("-")
  res = (pieces, seps)
  SG._CACHE_MEMO_SEPS[form] = res
  return res


def _memo_piece_split(hk_piece):
  """Corpus-subdivision of an HK piece, as (hk_parts, seps) or None.

  Lets the DP treat a whole memorised compound (whose internal samAsa
  joints are not sandhi-witnessed) as a single "memo" piece and expand it
  back into the corpus's own sub-segmentation at assembly time.
  """
  hit = SG._CACHE_MEMO_PIECE.get(hk_piece)
  if hit is not None:
    return hit or None
  res = ()
  try:
    dev = sanscript.transliterate(hk_piece, sanscript.HK, sanscript.DEVANAGARI)
  except Exception:
    dev = None
  if dev:
    form = T._ra_split_form(dev)
    if form:
      pieces, seps = _memo_form_seps(form)
      if len(pieces) > 1:
        hk_parts = []
        for part in pieces:
          try:
            hk_parts.append(sanscript.transliterate(
                part, sanscript.DEVANAGARI, sanscript.HK))
          except Exception:
            hk_parts = []
            break
        if len(hk_parts) > 1 and all(hk_parts):
          res = (tuple(hk_parts), tuple(seps))
  SG._CACHE_MEMO_PIECE[hk_piece] = res
  return res or None


def _tight_merger_surface(hk):
  """Two words joined by one merger, both with stardict/DCS backing.

  The boosted rAmAnujIya count alone (often a single prastuti piece) does
  not make a surface atomic: cenna is merely cet+na - a separable
  assimilation surface - and must stay open to the DP, while nobhaya
  (na + ubhaya) is a genuine tight merger."""
  words = T._load_words()
  n = len(hk)
  for p in range(1, n):
    for mlen in (2, 1):
      if p + mlen > n:
        continue
      mv = hk[p:p + mlen]
      exps = _merger_exps(mv)
      if not exps:
        continue
      if mlen == 1 and hk[p] not in "AIUeo":
        continue
      right_rest = hk[p + mlen:]
      if not right_rest:
        continue
      for lv, rv in exps:
        lu = hk[:p] + lv
        ru = rv + right_rest
        if lu in words and ru in words:
          lw = max(words.layer_counts(lu)[:5])
          rw = max(words.layer_counts(ru)[:5])
          if lw > 0 and rw > 0:
            return True
  return False


def _core_valid(hk_piece, piece_mode=False):
  """Core validation (no upasarga strip, no length guard)."""
  words = T._load_words()
  if hk_piece in words:
    if piece_mode and len(hk_piece) <= 4 and hk_piece[-1] in ("M", "m"):
      # inflected shards like naM/vaM are not usable as split pieces - but
      # the anusvAra spelling of listed pronouns/avyayas (idaM = idam) is.
      base = hk_piece[:-1] + "m" if hk_piece.endswith("M") else hk_piece
      if (base not in C._PRONOUNS and base not in C._AVYAYAS
          and base not in C._UPASARGAS):
        return (None, hk_piece)
    return ("exact", hk_piece)
  if hk_piece.startswith("'"):
    rest = hk_piece[1:]
    cand = "a" + rest
    if cand in words:
      return ("avagraha", cand)
    if _stem_valid(cand):
      return ("avagraha", cand)
  if len(hk_piece) >= 3 and hk_piece.endswith("y"):
    for v in ("i", "I"):
      cand = hk_piece[:-1] + v
      if cand in words:
        return ("yan", cand)
      if piece_mode:
        if merger_chain_valid(cand) and (len(cand) <= 12 or _attested(cand)):
          return ("yan", cand)  # a long unattested chain is a sponge:
          # vijJeyendra|stuty hides a compound boundary
        base = _stem_base_piece(cand)
        if base and len(base) >= 4 and _base_attested(base):
          return ("yan", cand)
  if len(hk_piece) >= 3 and hk_piece.endswith("v"):
    for v in ("u", "U"):
      cand = hk_piece[:-1] + v
      if cand in words:
        return ("yan", cand)
      if piece_mode:
        if merger_chain_valid(cand) and (len(cand) <= 12 or _attested(cand)):
          return ("yan", cand)
        base = _stem_base_piece(cand)
        if base and len(base) >= 4 and _base_attested(base):
          return ("yan", cand)
  if len(hk_piece) >= 3 and hk_piece.endswith("o"):
    cand = hk_piece[:-1] + "aH"
    if cand in words:
      return ("visarga-o", cand)
    if _stem_valid(cand):
      return ("visarga-o", cand)
  if len(hk_piece) >= 3 and hk_piece[-1] in ("r", "s", "z", "S"):
    cand = hk_piece[:-1] + "H"
    if cand in words:
      return ("visarga", cand)
    if _stem_valid_piece(cand) if piece_mode else _stem_valid(cand):
      return ("visarga", cand)
  if len(hk_piece) >= 3 and hk_piece.endswith(("d", "n")):
    cand = hk_piece[:-1] + "t"
    if cand in words:
      return ("t-assim", cand)
    if _stem_valid_piece(cand) if piece_mode else _stem_valid(cand):
      return ("t-assim", cand)
  if len(hk_piece) >= 3 and hk_piece.endswith("j"):
    cand = hk_piece[:-1] + "t"
    if cand in words:
      return ("t-assim", cand)
    if _stem_valid_piece(cand) if piece_mode else _stem_valid(cand):
      return ("t-assim", cand)
  if len(hk_piece) >= 3 and hk_piece.endswith("c"):
    cand = hk_piece[:-1] + "t"
    if cand in words:
      return ("t-assim", cand)
    if _stem_valid_piece(cand) if piece_mode else _stem_valid(cand):
      return ("t-assim", cand)
  # de-aspiration of an initial (tad+dhi -> tad dhi from tad+hi)
  if len(hk_piece) >= 3 and hk_piece.startswith("dh"):
    cand = "h" + hk_piece[2:]
    if cand in words:
      return ("t-assim", cand)
  if len(hk_piece) >= 3 and hk_piece[0] in ("g", "j", "D", "d", "b"):
    flip = {"g": "k", "j": "c", "D": "T", "d": "t", "b": "p"}[hk_piece[0]]
    cand = flip + hk_piece[1:]
    if cand in words:
      return ("t-assim", cand)
  if len(hk_piece) >= 4 and hk_piece.endswith("M"):
    # anusvAra surface of an m-final form (etaM <- etam); short shards like
    # naM/vaM stay excluded by the length guard
    cand = hk_piece[:-1] + "m"
    if cand in words:
      return ("stem", cand)
  if piece_mode and len(hk_piece) >= 7 and hk_piece.endswith("sminn"):
    # Prastuti writes a junctional doubled न् at the end of a sarvanAma
    # locative piece (उभयस्मिन्न् अपि, तस्मिन्न् इति): the surface underneath
    # is …स्मिन्, whose base must be attested - directly, or as a tight
    # merger surface (नोभय = na + ubhaya).  A merger veneer over an
    # unattested prastuti piece (चेन्न = cet + na) stays rejectable: the
    # separable assimilation joint must remain available to the DP.
    cand = hk_piece[:-1]
    if cand in words:
      return ("merger", cand)
    stem = hk_piece[:-5]
    if (len(stem) >= 3
        and (stem in words or _tight_merger_surface(stem))):
      return ("merger", cand)
  if piece_mode:
    if _stem_valid_piece(hk_piece):
      return ("stem", hk_piece)
    if merger_chain_valid(hk_piece):
      # un-splittable merger surface inside a larger compound (alpAsthira)
      return ("merger", hk_piece)
  elif _stem_valid(hk_piece):
    return ("stem", hk_piece)
  return (None, hk_piece)


def _valid_piece_kind(hk_piece, piece_mode=False):
  """Full validation: core or upasarga+core compound (kind may be None)."""
  key = (piece_mode, hk_piece)
  hit = _CACHE_CORE.get(key)
  if hit is not None:
    return hit
  kind, under = _core_valid(hk_piece, piece_mode=piece_mode)
  if kind is not None:
    _CACHE_CORE[key] = (kind, under)
    return (kind, under)
  # upasarga strip (longest first), up to 2 rounds
  cur = hk_piece
  for _ in range(2):
    hit = False
    for up in C._UPASARGAS:
      if cur.startswith(up) and len(cur) > len(up) + 2:
        rest = cur[len(up):]
        k2, u2 = _core_valid(rest, piece_mode=piece_mode)
        if k2 is not None:
          if (piece_mode and C._LAYERED is not None
              and _count_of(hk_piece) == 0 and not _attested(hk_piece)):
            break  # a non-lexicalised upasarga join (apyAdhAra) is no piece
          res = ("upasarga", hk_piece)
          _CACHE_CORE[key] = res
          return res
        cur = rest
        hit = True
        break
    if not hit:
      break
  res = (None, hk_piece)
  _CACHE_CORE[key] = res
  return res


def _whole_kind(hk):
  """Validation for the whole token: exact / stem / upasarga / None."""
  kind, under = _valid_piece_kind(hk)
  return kind


def _has_visarga_restore(hk):
  """True if hk can be read as a visarga-sandhi surface form."""
  hit = _CACHE_VIS_RESTORE.get(hk)
  if hit is not None:
    return hit
  words = T._load_words()
  if not hk:
    return False
  if hk.endswith("o"):
    res = (hk[:-1] + "aH") in words
  elif hk[-1] in ("r", "s", "z", "S"):
    cand = hk[:-1] + "H"
    res = cand in words or _stem_valid(cand)
  else:
    res = False
  _CACHE_VIS_RESTORE[hk] = res
  return res


def _left_final_witness(lhk):
  """True if a consonant-final left piece ends in a separable-sandhi stop:
  d/t/n directly, or j/c/g/D/b that de-assimilate to a dictionary word."""
  hit = _CACHE_WITNESS.get(lhk)
  if hit is not None:
    return hit
  if not lhk:
    return False
  c = lhk[-1]
  words = T._load_words()
  if c in ("d", "t", "n"):
    res = True
  elif c in ("j", "c"):
    cand = lhk[:-1] + "t"
    res = cand in words or _stem_valid_piece(cand)
  elif c in ("g", "D", "b"):
    flip = {"g": "k", "D": "T", "b": "p"}[c]
    res = (lhk[:-1] + flip) in words
  elif c in ("l", "T"):
    # tad + l/T assimilation surface (talliGga, taTTIkA): de-assimilates to tad
    res = (lhk[:-1] + "d") in words or (lhk[:-1] + "t") in words
  elif c == "k":
    # a k-final pada kept before s (prastuti ऋक् स…): the unsandhied form
    res = lhk in words
  else:
    res = False
  _CACHE_WITNESS[lhk] = res
  return res


_RELIABLE_MIN = 2


_STEM_BASE_MIN = 5


def _restores_of(hk):
  """All plausible underlying dictionary forms for a surface piece."""
  out = []
  if not hk:
    return out
  if hk.endswith("y") and len(hk) >= 3:
    out.extend([hk[:-1] + "i", hk[:-1] + "I"])
  if hk.endswith("v") and len(hk) >= 3:
    out.extend([hk[:-1] + "u", hk[:-1] + "U"])
  if hk.endswith("o") and len(hk) >= 3:
    out.append(hk[:-1] + "aH")
  if hk[-1] in ("r", "s", "z", "S") and len(hk) >= 3:
    out.append(hk[:-1] + "H")
  if hk.endswith(("d", "n", "j", "c")) and len(hk) >= 3:
    out.append(hk[:-1] + "t")
  if hk.endswith("M") and len(hk) >= 3:
    out.append(hk[:-1] + "m")
  if hk.startswith("'") and len(hk) >= 2:
    out.append("a" + hk[1:])
  if len(hk) >= 3 and hk.startswith("dh"):
    out.append("h" + hk[2:])
  if hk.startswith("ch") and len(hk) >= 3:
    # cch surface (sat + zabda -> sacchabda): right piece stands for z...
    out.append("z" + hk[2:])
  return out


def _has_yan_restore(hk):
  hit = _CACHE_YAN_RESTORE.get(hk)
  if hit is not None:
    return hit
  words = T._load_words()
  res = False
  if hk:
    if hk.endswith("y"):
      res = (hk[:-1] + "i") in words or (hk[:-1] + "I") in words
      if not res:
        res = (merger_chain_valid(hk[:-1] + "i")
               or merger_chain_valid(hk[:-1] + "I"))
    elif hk.endswith("v"):
      res = (hk[:-1] + "u") in words or (hk[:-1] + "U") in words
      if not res:
        res = (merger_chain_valid(hk[:-1] + "u")
               or merger_chain_valid(hk[:-1] + "U"))
  _CACHE_YAN_RESTORE[hk] = res
  return res


_BASE_ATTESTED_MIN = 3


def _base_attested(base):
  """A stem base is good evidence when it (or its naiJ form, अ- stripped)
  is attested (>= _BASE_ATTESTED_MIN sources)."""
  if not base:
    return False
  if _count_of(base) >= _BASE_ATTESTED_MIN:
    return True
  if merger_chain_valid(base):
    return True
  return (base.startswith("a") and len(base) > 3
          and _count_of(base[1:]) >= _BASE_ATTESTED_MIN
          and base[1:] in T._load_words())


def _reliable(hk, depth=2):
  """Frequency guard with restoration: a piece is reliable when it, or a
  plausible underlying form of it, is an attested dictionary word."""
  if depth == 2:
    hit = _CACHE_RELIABLE.get(hk)
    if hit is not None:
      return hit
  if depth < 0:
    return False
  cnt = _count_of(hk)
  if cnt >= 3:
    if depth == 2:
      _CACHE_RELIABLE[hk] = True
    return True
  if cnt >= _RELIABLE_MIN:
    base = _stem_base_piece(hk)
    if base and _count_of(base) >= _STEM_BASE_MIN:
      if depth == 2:
        _CACHE_RELIABLE[hk] = True
      return True
    if hk.endswith("H") and hk[:-1] in T._load_words() and _count_of(hk[:-1]) >= _STEM_BASE_MIN:
      if depth == 2:
        _CACHE_RELIABLE[hk] = True
      return True
    for cand in _restores_of(hk):
      if _count_of(cand) >= 3 or (
          _count_of(cand) >= _RELIABLE_MIN
          and _stem_base_piece(cand)
          and _count_of(_stem_base_piece(cand)) >= _STEM_BASE_MIN):
        if depth == 2:
          _CACHE_RELIABLE[hk] = True
        return True
      if merger_chain_valid(cand) and _count_of(cand) > 0:
        if depth == 2:
          _CACHE_RELIABLE[hk] = True
        return True
  for cand in _restores_of(hk):
    if _count_of(cand) >= _RELIABLE_MIN:
      if depth == 2:
        _CACHE_RELIABLE[hk] = True
      return True
    if _stem_valid_piece(cand):
      base = _stem_base_piece(cand)
      if _base_attested(base):
        return True
  if _stem_valid_piece(hk):
    base = _stem_base_piece(hk)
    if _base_attested(base):
      return True
  if depth > 0:
    for up in C._UPASARGAS:
      if hk.startswith(up) and len(hk) > len(up) + 2:
        if _reliable(hk[len(up):], depth - 1):
          _CACHE_RELIABLE[hk] = True
          return True
        break
  if depth == 2:
    _CACHE_RELIABLE[hk] = False
  return False


_SHORT_YAN_OK = ("iti", "api", "adhi", "eva", "evA", "iti")


def _piece_reliable(piece, kind, under):
  if (kind == "stem" and not _attested(piece)
      and piece.endswith(_FINITE_VERB_TAILS)):
    return False  # tiSyate: an unattested tiG-form shard stands for no stem
  if kind == "exact" and piece in T._load_words():
    if not _attested(piece) and _count_of(piece) < 5:
      base = _stem_base_piece(piece)
      if not (base and (base.endswith(tuple(C._BARE_SUFFIXES))
                        or (len(base) >= 4 and _count_of(base) >= 3))):
        return False  # a workbook relic (AkA cnt=2, zasi cnt=2, vaga cnt=4)
        # is no word; a real suffix form (tvena <- tva) or an inflection of
        # a real, non-tiny base (ahanam <- ahana, tvASTram <- tvASTra)
        # stays - but a two/three-letter base (AnaH <- An, canAni <- can)
        # is a shard
    return True  # a listed dictionary word is usable even when the counted
    # layers hold none of it (tUktaM lives only in a corpus-forms layer)
  if kind == "yan" and under:
    if (len(piece) <= 3 and under not in _SHORT_YAN_OK
        and under not in C._PRONOUNS and under.lower() not in C._UPASARGAS):
      return False  # a short yaN piece is a particle shard (ity/apy);
      # atv <- atu / asy <- asi are verb-form shards, no samAsa members
    if not (_attested(under) or _count_of(under) >= 3
            or merger_chain_valid(under)
            or (_stem_valid_piece(under)
                and _base_attested(_stem_base_piece(under)))):
      return False  # a yaN restore with no witness (zasy -> zasi cnt=2);
      # a solid inflected restore (sAhasAni <- sAhasa) is a witness
  if kind == "avagraha" and under:
    return _attested(under) or under in T._load_words() or _reliable(under)
  if (kind == "stem" and not _attested(piece)):
    base = _stem_base_piece(piece)
    if (base and base.endswith(tuple(C._BARE_SUFFIXES))
        and not _attested(base)):
      return False  # dAtvena (dA + tva): a bare-suffix base is no member
  if kind == "merger":
    return True
  if kind == "yan" and under and merger_chain_valid(under):
    return True
  if (kind == "stem" and piece.endswith("M") and under
      and _count_of(under) >= _RELIABLE_MIN):
    return True
  if kind in ("visarga", "visarga-o") and under and under not in T._load_words():
    base = _stem_base_piece(under)
    if not base or len(base) < 4:
      return False  # yadAs->yadAH: restore leans on a tiny closed-class base
  return _reliable(piece)


_DIRGHA_MAP = {
    "A": [("a", "a"), ("A", "a"), ("a", "A"), ("A", "A")],
    "I": [("i", "i"), ("I", "i"), ("i", "I")],
    "U": [("u", "u"), ("U", "u"), ("u", "U")],
}


_GUNA_MAP = {
    "e": [("a", "i"), ("A", "i"), ("a", "I"), ("A", "I")],
    "o": [("a", "u"), ("A", "u"), ("a", "U"), ("A", "U")],
}


_VRDDHI_MAP = {
    "ai": [("a", "e"), ("A", "e"), ("a", "ai"), ("A", "ai")],
    "au": [("a", "o"), ("A", "o"), ("a", "au"), ("A", "au")],
}


def _merger_exps(mv):
  return _DIRGHA_MAP.get(mv) or _GUNA_MAP.get(mv) or _VRDDHI_MAP.get(mv)


def _yan_restored_left(left_surface):
  """If left_surface ends in a semivowel y/v that restores to a dictionary
  word (ity->iti, nandy->nandi), return that word (yaN parse witness)."""
  hit = _CACHE_YAN_LEFT.get(left_surface)
  if hit is not None:
    return hit or None
  res = _yan_restored_left_uncached(left_surface)
  _CACHE_YAN_LEFT[left_surface] = res or ""
  return res


def _yan_restored_left_uncached(left_surface):
  words = T._load_words()
  if left_surface.endswith("y"):
    for vv in ("i", "I"):
      if (left_surface[:-1] + vv) in words:
        return left_surface[:-1] + vv
  if left_surface.endswith("v"):
    for vv in ("u", "U"):
      if (left_surface[:-1] + vv) in words:
        return left_surface[:-1] + vv
  return None


def is_veto_split(hk_full, cpos):
  """True if splitting at cpos cuts a dIrgha/guNa/vRddhi merger of two
  exact dictionary words. Absolute veto (instruction precedence rule)."""
  key = (hk_full, cpos)
  hit = _CACHE_VETO.get(key)
  if hit is not None:
    return hit
  res = _is_veto_split_uncached(hk_full, cpos)
  _CACHE_VETO[key] = res
  return res


def _veto_side_ok(s):
  """A veto witness word may be exact or a light inflection of a common one."""
  if s in T._load_words():
    return True
  if _stem_valid_piece(s):
    base = _stem_base_piece(s)
    return bool(base) and _count_of(base) >= _STEM_BASE_MIN
  return False


def _is_veto_split_uncached(hk_full, cpos):
  if cpos <= 0 or cpos >= len(hk_full):
    return False
  words = T._load_words()
  # Case L: merger vowel ends the left piece.
  for mlen in (2, 1):
    if cpos - mlen < 0:
      continue
    mv = hk_full[cpos - mlen:cpos]
    exps = _merger_exps(mv)
    if not exps:
      continue
    if hk_full[cpos] in "aAiIuUeEoO":
      continue
    left_pre = hk_full[:cpos - mlen]
    right_rest = hk_full[cpos:]
    for lv, rv in exps:
      if (left_pre + lv) in words and _veto_side_ok(rv + right_rest):
        if not _attested(left_pre + lv):
          # a synthesised left (bhagavadgItA) is no merger witness: the
          # t-assim reading bhagavad|gItA|darzanAt stays available
          continue
        return True
  # Case R: merger vowel starts the right piece.
  # If the char before the split is a semivowel whose yaN-restore is a more
  # common word than the merger-left (nandy|Adi vs nandya|adi), the vowel
  # belongs to the right word - not a merger.
  yan_left = None
  if cpos > 0 and hk_full[cpos - 1] in ("y", "v"):
    yan_left = _yan_restored_left(hk_full[:cpos])
  for mlen in (2, 1):
    if cpos + mlen > len(hk_full):
      continue
    mv = hk_full[cpos:cpos + mlen]
    exps = _merger_exps(mv)
    if not exps:
      continue
    left_pre = hk_full[:cpos]
    right_rest = hk_full[cpos + mlen:]
    # Ambiguous t-assim reading (tadeva = tad+eva, yadAste = yad+Aste): the
    # same surface reads as a consonant-final word + vowel-initial word, so
    # the merger witness is not decisive.
    if (hk_full[cpos - 1] in "dtn" and left_pre in words
        and _count_of(left_pre) >= 5
        and (mv + right_rest) in words
        and _count_of(mv + right_rest) >= 5):
      continue
    for lv, rv in exps:
      lu = left_pre + lv
      ru = rv + right_rest
      if lu in words and ru in words:
        if yan_left and _count_of(yan_left) > _count_of(lu):
          continue
        # both merger words must be reasonably attested (jagada+ika is not)
        if _count_of(lu) >= 5 and _count_of(ru) >= 5:
          return True
  return False


_CACHE_GLOBAL_MERGER = {}


_CACHE_VETO = {}


def has_global_merger(hk):
  """Whole token explainable as one dIrgha/guNa/vRddhi merger of two exact
  dictionary words -> never split (e.g. dayArdra, dharmArtha, svaprakAzAdvitIya)."""
  hit = _CACHE_GLOBAL_MERGER.get(hk)
  if hit is not None:
    return hit
  res = _has_global_merger_uncached(hk)
  _CACHE_GLOBAL_MERGER[hk] = res
  return res


def _has_global_merger_uncached(hk):
  words = T._load_words()
  n = len(hk)
  for p in range(1, n):
    for mlen in (2, 1):
      if p + mlen > n:
        continue
      mv = hk[p:p + mlen]
      exps = _merger_exps(mv)
      if not exps:
        continue
      if mlen == 1 and hk[p] not in "AIUeo":
        continue
      left_pre = hk[:p]
      right_rest = hk[p + mlen:]
      if not right_rest:
        continue  # bare final vowel is never a merger partner
      if (hk[p - 1] not in "aAiIuUeEoO'"
          and hk[:p - 1] in words and hk[p - 1:] in words):
        continue  # the stop may double instead of merging: yat|tUktam
        # outranks the yattu|uktaM reading
      # Ambiguous t-assim reading: yadAste = yad+Aste and tadeva = tad+eva
      # share the surface with a merger parse, so the merger witness is not
      # decisive; leave the token to the internal splitter.
      if (hk[p - 1] in "dtn" and left_pre in words
          and _count_of(left_pre) >= 5
          and (hk[p:p + mlen] + right_rest) in words
          and _count_of(hk[p:p + mlen] + right_rest) >= 5):
        continue
      yan_left = None
      if hk[p - 1] in ("y", "v"):
        yan_left = _yan_restored_left(hk[:p])
      for lv, rv in exps:
        lu = left_pre + lv
        ru = rv + right_rest
        if _merger_side_ok(lu) and _merger_side_ok(ru):
          if not _attested(lu):
            continue  # synthesised left is no merger witness (bhagavadgItA)
          if yan_left and _count_of(yan_left) > _count_of(lu):
            continue
          return True
  return False


def _merger_side_ok(s):
  """A merger side with >=5 attestation - or a stemmed form whose base is
  a settled, vowel-final word (paramezvarasya -> paramezvara).  A
  halant-final base (tripAdasya -> tripAd) keeps the t-assim reading
  alive instead of freezing the whole as a merger."""
  if s in T._load_words():
    return _count_of(s) >= 5
  if not _stem_valid_piece(s):
    return False
  base = _stem_base_piece(s)
  return (bool(base) and not _halant_final(base)
          and _base_attested(base) and _count_of(base) >= _STEM_BASE_MIN)


_MERGER_MIN = 6


_CACHE_CHAIN = {}


_CACHE_SWALLOW = {}


def _witnessed_swallow(hk_piece):
  """True when an un-attested merger-chain piece itself contains a
  witnessed (t-assim) split (zravaNAnna = zravaNAn + na).  Such a piece
  must not swallow the split; anukramyAha (no internal witness) may."""
  hit = _CACHE_SWALLOW.get(hk_piece)
  if hit is not None:
    return hit
  res = False
  for p in range(4, len(hk_piece) - 1):
    if hk_piece[p - 1] not in ("n", "d") or hk_piece[p] not in "dntTkpszS":
      continue
    kL, _u = _valid_piece_kind(hk_piece[:p], piece_mode=True)
    if kL == "t-assim":
      res = True
      break
  _CACHE_SWALLOW[hk_piece] = res
  return res


def merger_chain_valid(hk):
  """True if ``hk`` is a chain of dictionary words joined only by
  dIrgha/guNa/vRddhi mergers (sakaletara = sakala+itara, jJAnAnandaika =
  jJAna+Ananda+eka).  At most one middle word may be unattested, provided
  both of its junctions lean on a well-attested neighbour."""
  hit = _CACHE_CHAIN.get(hk)
  if hit is not None:
    return hit
  res = _merger_chain_uncached(hk)
  _CACHE_CHAIN[hk] = res
  return res


_MERGER_GLUE = ("eva", "adhi")


def _chain_word_ok(s):
  """Merger-chain component: a well-attested word, never a closed-class or
  suffix shard.  Short components need proportionally more attestation
  (ape/Iti/naM do not qualify, eka/Adi do) - except the short closed-class
  joiners ca/vA (cAdhyAtmam = ca + adhyAtmam) and the merging particles
  eva/adhi (prANAdevAdhi = prANAd eva adhi)."""
  n = len(s)
  if n < 3:
    return s in ("ca", "vA", "tu")
  if (s in C._BARE_SUFFIXES
      or (s in C._AVYAYAS and s not in _MERGER_GLUE)
      or (s.lower() in C._UPASARGAS and s not in _MERGER_GLUE)):
    return False
  if s in C._PRONOUNS and n < 4:
    return False
  if n >= 4 and not _attested(s):
    base = _stem_base_piece(s)
    if base and len(base) >= 4 and _base_attested(base):
      return True  # a solid inflected member (arthatvena <- arthatva)
    if s in T._load_words() and _count_of(s) >= _MERGER_MIN:
      return True  # a real dictionary word (pravibhajya)
    return False  # a synthesised surface (zravaNA, Anna, apya) is no word
    # (short Vedic particles like evA pass on frequency alone)

  cnt = _count_of(s)
  if n == 3:
    return cnt >= 20
  return cnt >= _MERGER_MIN


_FINITE_VERB_TAILS = ("ante", "anti", "ate", "nti", "nte", "te", "ti")


def _samasa_head_ok(hk, under=None):
  """A non-final samAsa member: a nominal stem / particle / upasarga may
  head a compound, an inflected verb form or a bare dhAtu never may."""
  cands = []
  for s in (under, hk):
    if s and s not in cands:
      cands.append(s)
  for s in cands:
    if (s in C._TRIE_NOMINAL_STEMS or s in C._AVYAYAS
        or s in C._PRONOUNS or s.lower() in C._UPASARGAS):
      return True
  for s in cands:
    if (s in C._TRIE_VERB_STEMS
        and not (_attested(s) and _count_of(s) >= 100)):
      return False  # a bare verb stem heads no samAsa; a homonymous,
      # well-attested noun (jIva, bhU) does
    if (s.endswith(_FINITE_VERB_TAILS) and s in T._load_words()
        and len(s) >= 4):
      return False  # a tiG-anta is a pada, never a member
  return True


def merger_first_word(hk):
  """First merged component of a chain piece (evAdhi -> eva, asyAmRtam ->
  asya): the component may consume a merged long vowel at its end."""
  if not hk:
    return None
  for r in range(2, min(7, len(hk))):
    cand = hk[:r]
    if cand[-1] not in "AIU":
      continue
    cand = cand[:-1] + {"A": "a", "I": "i", "U": "u"}[cand[-1]]
    if cand in T._load_words():
      return cand
  return None


def _pada_ok(piece, under, kind):
  """A chunk shown as a separate pada must be a word form, not a bare
  prAtipadika stem/lemma (द्यु- is a member, द्यौर् is a pada; atu is a dcs
  stem).  Closed-class words pass, and so do attested forms with a
  padas-style surface; a bare listed stem does not."""
  if kind == "memo":
    return True
  for s in ((under or ""), piece):
    if not s:
      continue
    if s in C._AVYAYAS or s in C._PRONOUNS or s.lower() in C._UPASARGAS:
      return True
    if _attested(s) and s.endswith(("H", "z", "S", "r", "t", "d", "n",
                                    "m", "M", "s", "a", "A", "i", "I",
                                    "u", "U", "e", "o")):
      return True
    if (s not in C._TRIE_NOMINAL_STEMS
        and (C._TRIE_DCS is None or s not in C._TRIE_DCS)):
      return True
  return False


def _merged_token_shard(s):
  """An exact dictionary token that is itself a closed-class-led sandhi
  merge (ityAdy = iti + Ady): using it as an internal piece hides a word
  boundary."""
  if not s or len(s) < 5:
    return False
  fw = merger_first_word(s)
  if (fw and len(fw) < len(s) - 1
      and (fw in C._AVYAYAS or fw in C._PRONOUNS
           or fw.lower() in C._UPASARGAS)):
    # bhUtaH is no bhu + taH merge: only a closed-class lead makes an
    # exact token a shard hiding a word boundary (ityAdy, tasyApi).
    rest = s[len(fw):]
    heads = [rest, "a" + rest, "A" + rest]
    if rest[:1] in ("A", "I", "U"):
      heads.append({"A": "a", "I": "i", "U": "u"}[rest[0]] + rest[1:])
    for head in heads:
      if head and (head in C._AVYAYAS or head in C._PRONOUNS):
        return True
  for L in range(3, min(7, len(s) - 1)):
    if s[L - 1] not in ("y", "v"):
      continue  # only a yaN-shaped prefix (ity = iti + Ady); a plain
      # particle-led compound (prati-sambandhi) is a normal member
    restored = _yan_restored_left(s[:L])
    if restored and (restored in C._AVYAYAS or restored in C._PRONOUNS):
      return True
  return False


def _stolen_final_shard(hk, piece, lpiece=None):
  """The strong window (sarva|rasaH, vid|yAH, gamya|mAnasya) must not cut
  a single word whose stem continues into the right piece: viSayaiH (base
  viSaya) is no viSa + yaiH, and gamyamAnasya is no gamya + mAnasya (the
  continuation gamyam is only the word's own dictionary prefix)."""
  base = _stem_base_piece(hk)
  if base:
    stem = base.rstrip("aAiIuUfFxXeEoO")
    if stem and piece.startswith(stem[-1]):
      return True
  if lpiece:
    cont = lpiece + piece[:1]
    if (cont in T._load_words() and hk.startswith(cont)
        and len(hk) > len(cont)):
      return True
  return False


def _chain_end_ok(base, apo, wild=0):
  """Final chain component: strict for merger chains; after an avagraha
  joint a restorable consonant-final word (abhivadan = abhi + vadan) is
  accepted too, and a real inflected word form (anugrAhake) is a fine
  merged tail even without corpus attestation."""
  if _chain_word_ok(base):
    return True
  if (wild == 0 and len(base) >= 6
      and not base.endswith(_FINITE_VERB_TAILS)
      and _stem_valid(base)):
    return True
  if not apo:
    return False
  n = len(base)
  if (n < 4 or base in C._BARE_SUFFIXES or base in C._AVYAYAS
      or base in C._PRONOUNS or base.lower() in C._UPASARGAS):
    return False
  if base[-1] in _VOWELS or base[-1] in ("H", "o"):
    return False
  return _reliable(base)


def _merger_chain_uncached(hk):
  n = len(hk)
  if n < 4:
    return False
  words = T._load_words()
  seen = set()
  stack = [(0, "", 0, 0, 0, 0)]
  while stack:
    q, rv, pending, wild, junc, apo = stack.pop()
    if (q, rv, pending, wild, junc, apo) in seen:
      continue
    seen.add((q, rv, pending, wild, junc, apo))
    for r in range(q + 1, n + 1):
      base = rv + hk[q:r]
      if r == n:
        if 1 <= junc <= 3 and _chain_end_ok(base, apo, wild):
          return True
        continue
      for mlen in (1, 2):
        if r + mlen > n:
          continue
        mv = hk[r:r + mlen]
        if mlen == 1 and mv == "'":
          # avagraha joint: left word unchanged, right word drops initial a
          exps = (("", "a"),)
        else:
          if mlen == 1 and mv not in "AIUeo":
            continue
          exps = _merger_exps(mv)
          if not exps:
            continue
        apo2 = 1 if mv == "'" else apo
        for lv, rv2 in exps:
          lknown = _chain_word_ok(base + lv)
          if pending and not lknown:
            continue
          if wild and junc + 1 > 3:
            continue
          if lknown:
            stack.append((r + mlen, rv2, 0, wild, junc + 1, apo2))
          elif (q > 0 and wild == 0 and junc + 1 <= 3 and 2 <= r - q <= 8
                and not any(c in "AIUeo" for c in hk[q:r])
                and "ai" not in hk[q:r] and "au" not in hk[q:r]
                and base in words):
            # the one tolerated unattested middle word must still be a
            # dictionary surface somewhere (chanda|o|uviSayatv|A|annA is
            # no merger chain: uviSayatv is nothing at all)
            stack.append((r + mlen, rv2, 1, 1, junc + 1, apo2))
  return False
