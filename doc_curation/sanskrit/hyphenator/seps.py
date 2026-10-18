"""seps - part of the hyphenator package (see __init__.py)."""
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
    _RA_NGRAM_MAX_K,
    _RA_NGRAM_RATIO,
    _SEP_CAPTURE_RE,
    _VOWELS
)
from . import corpus_ra as RA
from . import tries as T
from . import validate as V


def _sep_add(tables, hk, cpos, dash):
  """Record one separator vote at a junction of HK surface ``hk``."""
  kmax = min(_RA_NGRAM_MAX_K, cpos, len(hk) - cpos)
  for k in range(2, kmax + 1):
    key = "%s\x1f%s" % (hk[cpos - k:cpos], hk[cpos:cpos + k])
    cell = tables.get(key)
    if cell is None:
      cell = tables[key] = [0, 0]
    cell[1 if dash else 0] += 1


def _build_ra_seps_trie(split_votes, smap):
  """Corpus separator memory -> ``rAmAnujIya-seps.trie``.

  Every internal junction of every hyphenated corpus token votes for its
  separator class: ``-`` = a within-samAsa joint, ``–`` = the boundary
  between upapadas of a samAsa where the upapadas are themselves samAsas
  (spelled ``--`` in older text, sometimes with a space between the dashes
  in very long chains; normalised to the preferred ``–``).  ``_sep``
  consults the longest attested context - dash-dominant renders with ``–``;
  a junction the corpus hyphenates keeps ``-``.
  """
  tables = {}
  for tok, votes in split_votes.items():
    try:
      hk = sanscript.transliterate(tok, scheme_map=smap)
    except Exception:
      continue
    if not hk or len(hk) < 4:
      continue
    for form in votes:
      pieces, seps = [], []
      for i, part in enumerate(_SEP_CAPTURE_RE.split(form)):
        if i % 2 == 0:
          if part:
            pieces.append(part)
        else:
          seps.append(part)
      seps = seps[:max(0, len(pieces) - 1)]
      if len(pieces) < 2 or len(seps) != len(pieces) - 1:
        continue
      joined, boundaries = RA._join_pieces(pieces)
      if joined != tok:
        continue
      for sep, pos in zip(seps, boundaries):
        if pos is None:
          continue  # the boundary was absorbed by a sandhi merge
        try:
          pre_hk = sanscript.transliterate(joined[:pos], scheme_map=smap)
        except Exception:
          break
        if pre_hk:
          dash = ("–" in sep) or ("—" in sep) or len(sep) > 1
          _sep_add(tables, hk, len(pre_hk), dash)
  entries = [("%s" % k, (min(h, 0xFFFFFFFF), min(d, 0xFFFFFFFF)))
             for k, (h, d) in tables.items()]
  trie = marisa_trie.RecordTrie("II", entries)
  os.makedirs(C._DATA_DIR, exist_ok=True)
  tmp = C._RA_SEPS_TRIE_PATH + ".tmp"
  trie.save(tmp)
  os.replace(tmp, C._RA_SEPS_TRIE_PATH)
  return trie


_CACHE_SEP = {}


def _boundary_kind(left_hk, right_hk):
  """Classify HK boundary for separator choice."""
  if not left_hk or not right_hk:
    return "plain"
  if left_hk.endswith(("ai", "au")):
    lc = left_hk[-2:]
  else:
    lc = left_hk[-1]
  rc = right_hk[0]
  if lc in ("y", "v"):
    if rc in _VOWELS or right_hk.startswith(("ai", "au")):
      return "yan"
    return "cons-cons"
  if lc == "o" and (rc == "'" or rc in _VOWELS):
    return "visarga-o"
  if lc == "e" and (rc == "'" or rc in ("a", "A")):
    return "visarga-o"
  if lc in ("r", "s", "z", "S"):
    return "visarga"
  if lc == "m" and (rc in _VOWELS or right_hk.startswith(("ai", "au"))):
    return "m-vowel"
  if lc in _VOWELS or lc in ("ai", "au"):
    return "vowel-cons"
  if lc in "kgcjTDtdpbNnl":
    if rc not in _VOWELS and rc != "'":
      return "t-assim"
    return "cons-vowel"
  return "cons-cons"


def _sep_dash(hk, cpos):
  """True when the corpus renders this junction with the glued pada dash
  (``–``/``--``): dash votes dominate hyphen votes at the longest attested
  separator context."""
  trie = C._TRIE_SEPS
  if trie is None or cpos <= 0 or cpos >= len(hk):
    return False
  key = (hk, cpos)
  hit = _CACHE_SEP.get(key)
  if hit is not None:
    return hit
  res = False
  kmax = min(_RA_NGRAM_MAX_K, cpos, len(hk) - cpos)
  for k in range(kmax, 1, -1):
    vals = trie.get(("%s\x1f%s" % (hk[cpos - k:cpos],
                                   hk[cpos:cpos + k])).encode("utf-8"))
    if vals:
      n_h, n_d = vals[0]
      res = n_d > 0 and n_d >= _RA_NGRAM_RATIO * n_h
      break
  _CACHE_SEP[key] = res
  return res


def _sep(left_hk, right_hk, left_under, right_under, whole_hk=None, ctx=None):
  """Choose separator at a boundary: ' ' for separate padas, '–' for a pada
  boundary the corpus keeps glued (``_sep_dash``), '-' for samAsa joints."""
  if ctx is not None and _sep_dash(ctx[0], ctx[1]):
    return "–"
  k = _boundary_kind(left_hk, right_hk)
  if k == "vowel-cons":
    return "-"
  if k in ("m-vowel", "visarga-o"):
    return " "
  lu = left_under or left_hk
  ru = right_under or right_hk
  if ru.startswith(C._COMPOUND_SUFFIXES):
    return "-"
  if ru.startswith(C._META_SUFFIXES):
    return "-"
  if k == "yan" and ru.startswith("ari") and lu != "iti":
    return "-"
  if k == "yan" and V.merger_chain_valid(lu):
    return "-"
  # Particles / pronouns / verbs after a sandhi boundary are separate padas.
  if ru in C._AVYAYAS or ru in C._PRONOUNS:
    return " "
  if right_hk in C._AVYAYAS or right_hk in C._PRONOUNS:
    return " "
  if k == "t-assim" and (ru == "hi" or right_hk == "dhi"):
    return " "
  if lu == "iti":
    return " "
  jn = left_hk + right_hk
  if V._prefix_in_dict(jn) or jn in T._load_words():
    return "-"
  right_variants = [right_under] if right_under else []
  for rv in list(right_variants):
    if len(rv) > 2 and rv.endswith(("M", "m", "H")):
      right_variants.append(rv[:-1])
  for rv in right_variants:
    if not rv:
      continue
    jn2 = (left_under or left_hk) + rv
    if V._prefix_in_dict(jn2) or jn2 in T._load_words():
      return "-"
  return " "
