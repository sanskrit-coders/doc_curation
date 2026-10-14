"""Local Sanskrit hyphenator (sandhi-preserving pada/samAsa splitter).

Implements the ``bare-hyphenator`` LLM instruction locally, without an LLM:

* Split separable word/stem boundaries, **without reverting sandhi**.
* **Never** split non-separable dIrgha / guNa / vRddhi mergers (absolute veto,
  even inside samAsa): ``dharmArtha``, ``mahotsava``, ``sadaiva`` stay joined.
* Separable: yaN (``ity evam``, ``madhv-ariH``), visarga (``rAmo 'sti``,
  ``namas te``), final ``m`` before vowels (``phalam aznute``), consonant
  assimilation (``tad dhi``), plus plain samAsa concatenation
  (``hetu-BAve``, ``brahma-jijJAsA``).
* Separator: hyphen ``-`` for samAsa-internal joints, space `` `` otherwise.

Method
------
Transliterate each Devanagari token to Harvard-Kyoto (HK) where vowels are
explicit, so separable sandhi is pure concatenation (``ity``+``evam`` =
``ityevam``).  Segment the HK token over *units* (aspirates ``kh``..``bh`` and
diphthongs ``ai``/``au`` are atomic) using a cost-minimising DP that validates
each candidate piece against the ``stardict-sanskrit`` wordlist
(``words_sa_dev.txt``):

* exact dictionary words;
* reverse-sandhi restorations: yaN (``ity``->``iti``, ``madhv``->``madhu``),
  visarga (``rAmo``->``rAmaH``, ``ataz``->``ataH``), avagraha
  (``'sti``->``asti``), consonant assimilation (``AsId``->``AsIt``);
* light sup/tiG stemming (``vedasya``->``veda``, ``mizraM``->``mizra``);
* upasarga+stem compounds (``samutpadyante``, ``duSprakRti``) - kept joined.

Guards (empirically tuned against विश्वास-प्रस्तुतिः / मूलम् pairs):

* **Merger veto** - a split is forbidden when the boundary vowel admits a
  dIrgha/guNa/vRddhi merger analysis of two exact dictionary words
  (``dayA``+``Ardra``, ``svaprakAza``+``advitIya``, ``dharma``+``artha``).
  This is what protects ``dharmArtha`` and ``svaprakAzAdvitIya``.
* A token that is itself a valid dictionary word (exact or inflected
  ``stem+ending``) is split **only** at high-precision sandhi boundaries
  (yaN / visarga / m-before-vowel / consonant assimilation): ``vRttasya``,
  ``kzaNikatvam``, ``zrutvA``, ``sarvajJa`` stay whole, while
  ``jagatkAraNa`` -> ``jagat-kAraNa`` (assimilation is separable).
* Every cut must be *witnessed* by its sandhi type - yaN cuts need a yaN
  surface (``ity``), visarga cuts need a visarga surface (``namas``,
  ``rAmo``, ``duSprakRter``), assimilation cuts need an assimilating final
  (``jagaj``, ``tad``); ``H -> z/S/r`` is only valid before its proper
  environments (r before vowels, s/z before voiceless).
* A yaN boundary requires a vowel-initial right piece (``madhv``+``ariH``,
  never ``madhv``+``riH``).
* Rare/unattested shards (single-source dictionary entries such as ``yeva``,
  ``manaz``) and bare endings (``sya``, ``tva``, ``tvam``) are rejected as
  pieces; particles and pronouns after a cut become separate padas.

Separator choice per boundary:

* vowel-final left + consonant (plain samAsa concat) -> ``-``;
* m-vowel, visarga-o (incl. avagraha) -> space;
* yaN / visarga-r-s / assimilation -> space by default, ``-`` when the joint
  is a known compound (dictionary prefix) or a recognised suffix/idiom
  (``-Adi``, ``-antara``, ``-artha``, ``-zabda``, ``madhv-ari``...).

Fast: ~O(L^2) dict lookups per token with memoised validation; dictionary
cached as a pickle in ``/tmp`` after first load (~600k headwords).
Already-hyphenated compounds are left untouched (pieces adjacent to ``-`` are
not re-processed), so running on pre-split प्रस्तुति-style text is safe.
"""

import bisect
import os
import pickle
import regex
from indic_transliteration import sanscript

_DICT_TXT = "/home/vvasuki/gitland/indic-dict/dicts/stardict-sanskrit/wordlists/words_sa_dev.txt"
_CACHE_PKL = "/tmp/sanskrit_hyphenator_dict_hk3.pkl"

_WORDS_HK = None
_COUNTS_HK = None
_SORTED_HK = None


def _get_scheme_map():
  return sanscript.SchemeMap(sanscript.SCHEMES[sanscript.DEVANAGARI],
                             sanscript.SCHEMES[sanscript.HK])


def _load_words():
  global _WORDS_HK, _COUNTS_HK, _SORTED_HK
  if _WORDS_HK is not None:
    return _WORDS_HK
  try:
    if os.path.exists(_CACHE_PKL) and os.path.exists(_DICT_TXT):
      if os.path.getmtime(_CACHE_PKL) >= os.path.getmtime(_DICT_TXT):
        with open(_CACHE_PKL, "rb") as f:
          _WORDS_HK, _COUNTS_HK = pickle.load(f)
          _SORTED_HK = sorted(_WORDS_HK)
          return _WORDS_HK
  except Exception:
    pass
  words_hk = set()
  counts_hk = {}
  try:
    smap = _get_scheme_map()
    with open(_DICT_TXT, encoding="utf-8") as f:
      for line in f:
        line = line.strip()
        if not line:
          continue
        parts = line.split("\t")
        w = parts[0].strip()
        if not w or len(w) > 40:
          continue
        nsrc = len(parts[1].split(",")) if len(parts) > 1 and parts[1] else 1
        try:
          hk = sanscript.transliterate(w, scheme_map=smap)
        except Exception:
          continue
        if hk:
          words_hk.add(hk)
          if nsrc > counts_hk.get(hk, 0):
            counts_hk[hk] = nsrc
  except FileNotFoundError:
    pass
  words_hk.update([
      "ca", "vA", "hi", "tu", "api", "iti", "eva", "evam", "iva",
      "ati", "adhi", "anu", "upa", "pari", "prati", "sam", "vi",
      "na", "saH", "tat", "etat", "yat", "kim", "idam", "adas",
      "asmin", "tasmin", "yad", "tad", "etad", "sat", "asat",
      "asti", "santi", "bhavati", "gacCati", "ukta", "uktam",
      "dharma", "artha", "hetu", "brahma", "zabda", "Adi",
  ])
  for w in list(words_hk):
    counts_hk.setdefault(w, 3)
  _WORDS_HK = words_hk
  _COUNTS_HK = counts_hk
  _SORTED_HK = sorted(words_hk)
  try:
    with open(_CACHE_PKL, "wb") as f:
      pickle.dump((words_hk, counts_hk), f)
  except Exception:
    pass
  return _WORDS_HK


def _count_of(hk):
  if _COUNTS_HK is None:
    _load_words()
  return _COUNTS_HK.get(hk, 0)


def _prefix_in_dict(s):
  if _SORTED_HK is None:
    _load_words()
  if not s:
    return False
  i = bisect.bisect_left(_SORTED_HK, s)
  return i < len(_SORTED_HK) and _SORTED_HK[i].startswith(s)


# Closed classes (HK).
_AVYAYAS = frozenset([
    "eva", "evam", "iva", "hi", "ca", "vA", "tu", "api", "iti", "atha",
    "tathA", "yathA", "nanu", "khalu", "vai", "ha", "aho", "he", "are",
    "mA", "sma", "su", "dus", "anu", "upari", "atra", "tatra", "kutra",
])
_PRONOUNS = frozenset([
    "tat", "etat", "yat", "kim", "idam", "adas", "tad", "etad", "yad",
    "asmin", "tasmin", "etasmin", "tasmAt", "asmAt", "kasmin",
    "saH", "sA", "te", "tvam", "aham", "vayam", "yUyam", "asya",
    "etat", "idam", "etad",
])
_META_SUFFIXES = ("zabda", "DAtu", "sUtra", "pratyaya", "prakRti")
_COMPOUND_SUFFIXES = ("Adi", "antara", "artha", "anta", "anvaya")

_UPASARGAS = tuple(sorted([
    "prati", "abhi", "pari", "adhi", "sam", "anu", "ava", "nis", "nir",
    "dus", "dur", "ut", "ud", "pra", "parA", "apa", "vi", "ni", "A",
    "su", "api", "ati", "upa", "duS", "duz", "niS", "niz", "saM", "san",
], key=len, reverse=True))

# Whitelist for very short pieces (HK len < 3).
_SHORT_OK = frozenset(["ca", "vA", "hi", "tu", "na", "te", "me", "oM"])

# sup/tiG endings used by the light stemmer (longest first).
_SUP_ENDINGS = tuple(sorted([
    "ByAm", "ByaH", "bhyAm", "bhyah", "BhiH", "ezu", "nAm", "sya",
    "yoH", "oH", "eH", "EH", "AnAm", "Ani", "Ini", "Uni",
    "Aya", "Ayai", "AyAH", "yAH",
    "At", "Ad", "aH", "AH", "An", "e", "O", "ena", "enA",
    "inA", "unA", "AyA", "ayA",     "aye", "ave", "asya",
    # tiG endings (verbs)
    "ante", "anti", "ate", "nte", "nti", "te", "ti", "It", "us", "uH",
    "tum", "tvA", "sya", "vat", "vatI", "vAn", "mAn", "mat",
    "M", "m", "H", "n", "t", "d", "s", "r",
], key=len, reverse=True))

_STEM_FINALS = ("a", "A", "i", "I", "u", "U", "f", "t", "d", "n", "s", "as")

# pure endings that must never appear as standalone split pieces
_BARE_SUFFIXES = frozenset([
    "sya", "ByAm", "ByaH", "bhyAm", "bhyah", "BhiH", "ezu", "zu",
    "nAm", "yoH", "oH", "eH", "EH", "Aya", "Ayai", "AyAH",
    "At", "Ad", "An", "ena", "enA", "inA", "unA", "AyA", "ayA",
    "aye", "ave", "AsAm", "tva", "tvAt", "tA", "tvam", "tvaM", "vat",
    "mat", "vAn", "mAn", "vatI", "vant", "mant", "nAm", "nAM", "mAtram",
    "mAtrAM", "mAtra", "mAtrA", "Ani", "Ini", "Uni", "avaH", "ayaH",
    "aH", "AH", "e", "O",
])

# Weak (function-word) right pieces: after a prefix-like left these are
# almost always separate padas, never suffix-like compound members.
_SANDHI_KEEP = frozenset([
    "kiMcid", "yuzmad", "bavad", "etad", "idam", "kimcid", "yuSmad",
    "bhavad", "tad", "sad", "cid", "yat", "etat", "tat", "sat", "cit",
])

_WEAK_RIGHTS = _AVYAYAS | _PRONOUNS | frozenset([
    "yam", "yaM", "tam", "taM", "enam", "enaM", "imam", "imaM",
    "amum", "amUM", "asya", "tasya", "yasya",
    "tezAm", "ezAm", "yena", "tena", "kena", "tataH", "yataH",
    "idAnIm", "etat", "etad",
])


def _stem_valid(hk):
  """Strip a known ending, restore stem-final, dict-check."""
  words = _load_words()
  for end in _SUP_ENDINGS:
    if len(hk) <= len(end) + 1:
      continue
    if not hk.endswith(end):
      continue
    pre = hk[:len(hk) - len(end)]
    if not pre or pre in _AVYAYAS:
      continue
    if pre in words:
      return True
    for fin in _STEM_FINALS:
      if pre + fin in words:
        return True
  return False


def _piece_ending_ok(hk, end):
  """Piece-mode endings: length >= 2, plus M/H/m with a base >= 4 chars."""
  if len(end) >= 2:
    return len(hk) > len(end) + 2
  if end in ("M", "H", "m"):
    return len(hk) > len(end) + 4
  return False


def _stem_valid_piece(hk):
  """Stricter stem check for split pieces: endings of length >= 2 (or
  M/H/m with a long base); rejects shrapnel like kasm/inn/rANi."""
  words = _load_words()
  for end in _SUP_ENDINGS:
    if not _piece_ending_ok(hk, end):
      continue
    if not hk.endswith(end):
      continue
    pre = hk[:len(hk) - len(end)]
    if not pre or pre in _AVYAYAS:
      continue
    if pre in words:
      return True
    for fin in _STEM_FINALS:
      if pre + fin in words:
        return True
  return False


def _stem_base_piece(hk):
  words = _load_words()
  for end in _SUP_ENDINGS:
    if not _piece_ending_ok(hk, end):
      continue
    if not hk.endswith(end):
      continue
    pre = hk[:len(hk) - len(end)]
    if not pre or pre in _AVYAYAS:
      continue
    if pre in words:
      return pre
    for fin in _STEM_FINALS:
      if pre + fin in words:
        return pre + fin
  return None


_CACHE_CORE = {}
_CACHE_RELIABLE = {}
_CACHE_STEM = {}
_CACHE_VIS_RESTORE = {}
_CACHE_YAN_RESTORE = {}
_CACHE_WITNESS = {}


def _core_valid(hk_piece, piece_mode=False):
  """Core validation (no upasarga strip, no length guard)."""
  words = _load_words()
  if hk_piece in words:
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
  if len(hk_piece) >= 3 and hk_piece.endswith("v"):
    for v in ("u", "U"):
      cand = hk_piece[:-1] + v
      if cand in words:
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
    if _stem_valid(cand):
      return ("visarga", cand)
  if len(hk_piece) >= 3 and hk_piece.endswith(("d", "n")):
    cand = hk_piece[:-1] + "t"
    if cand in words:
      return ("t-assim", cand)
    if not piece_mode and _stem_valid(cand):
      return ("t-assim", cand)
  if len(hk_piece) >= 3 and hk_piece.endswith("j"):
    cand = hk_piece[:-1] + "t"
    if cand in words:
      return ("t-assim", cand)
  if len(hk_piece) >= 3 and hk_piece.endswith("c"):
    cand = hk_piece[:-1] + "t"
    if cand in words:
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
  if piece_mode:
    if _stem_valid_piece(hk_piece):
      return ("stem", hk_piece)
    if has_global_merger(hk_piece):
      # un-splittable merger surface inside a larger compound (alpAsthira)
      return ("merger", hk_piece)
  elif _stem_valid(hk_piece):
    return ("stem", hk_piece)
  return (None, hk_piece)


_UPASARGA_HEADS = frozenset(x[0] for x in _UPASARGAS)


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
    for up in _UPASARGAS:
      if cur.startswith(up) and len(cur) > len(up) + 2:
        rest = cur[len(up):]
        k2, u2 = _core_valid(rest, piece_mode=piece_mode)
        if k2 is not None:
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
  words = _load_words()
  if not hk:
    return False
  if hk.endswith("o"):
    res = (hk[:-1] + "aH") in words
  elif hk[-1] in ("r", "s", "z", "S"):
    res = (hk[:-1] + "H") in words
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
  words = _load_words()
  if c in ("d", "t", "n"):
    res = True
  elif c in ("j", "c"):
    res = (lhk[:-1] + "t") in words
  elif c in ("g", "D", "b"):
    flip = {"g": "k", "D": "T", "b": "p"}[c]
    res = (lhk[:-1] + flip) in words
  else:
    res = False
  _CACHE_WITNESS[lhk] = res
  return res


_RELIABLE_MIN = 2


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
  words = _load_words()
  res = False
  if hk:
    if hk.endswith("y"):
      res = (hk[:-1] + "i") in words or (hk[:-1] + "I") in words
    elif hk.endswith("v"):
      res = (hk[:-1] + "u") in words or (hk[:-1] + "U") in words
  _CACHE_YAN_RESTORE[hk] = res
  return res


def _reliable(hk, depth=2):
  """Frequency guard with restoration: a piece is reliable when it, or a
  plausible underlying form of it, is an attested dictionary word."""
  if depth == 2:
    hit = _CACHE_RELIABLE.get(hk)
    if hit is not None:
      return hit
  if depth < 0:
    return False
  if _count_of(hk) >= _RELIABLE_MIN:
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
      if base and _count_of(base) >= _RELIABLE_MIN:
        return True
  if _stem_valid_piece(hk):
    base = _stem_base_piece(hk)
    if base and _count_of(base) >= _RELIABLE_MIN:
      return True
  if depth > 0:
    for up in _UPASARGAS:
      if hk.startswith(up) and len(hk) > len(up) + 2:
        if _reliable(hk[len(up):], depth - 1):
          _CACHE_RELIABLE[hk] = True
          return True
        break
  if depth == 2:
    _CACHE_RELIABLE[hk] = False
  return False


def _piece_reliable(piece, kind, under):
  return _reliable(piece)


# ---- veto (non-separability) ----

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
    "ai": [("a", "e"), ("A", "e"), ("a", "e")],
    "au": [("a", "o"), ("A", "o"), ("a", "o")],
}


def _merger_exps(mv):
  return _DIRGHA_MAP.get(mv) or _GUNA_MAP.get(mv) or _VRDDHI_MAP.get(mv)


def _yan_restored_left(left_surface):
  """If left_surface ends in a semivowel y/v that restores to a dictionary
  word (ity->iti, nandy->nandi), return that word (yaN parse witness)."""
  words = _load_words()
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
  if cpos <= 0 or cpos >= len(hk_full):
    return False
  words = _load_words()
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
      if (left_pre + lv) in words and (rv + right_rest) in words:
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


def has_global_merger(hk):
  """Whole token explainable as one dIrgha/guNa/vRddhi merger of two exact
  dictionary words -> never split (e.g. dayArdra, dharmArtha, svaprakAzAdvitIya)."""
  words = _load_words()
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
      yan_left = None
      if hk[p - 1] in ("y", "v"):
        yan_left = _yan_restored_left(hk[:p])
      for lv, rv in exps:
        lu = left_pre + lv
        ru = rv + right_rest
        if lu in words and ru in words:
          if yan_left and _count_of(yan_left) > _count_of(lu):
            continue
          if _count_of(lu) >= 5 and _count_of(ru) >= 5:
            return True
  return False


# ---- HK units ----

_ASPIRATE_FIRST = frozenset(list("kgcjTDtdpb"))


def hk_to_units(hk):
  units = []
  i = 0
  n = len(hk)
  while i < n:
    if hk[i] == "'":
      units.append("'")
      i += 1
      continue
    if i + 1 < n and hk[i:i + 2] in ("ai", "au"):
      units.append(hk[i:i + 2])
      i += 2
      continue
    if i + 1 < n and hk[i] in _ASPIRATE_FIRST and hk[i + 1] == "h":
      units.append(hk[i:i + 2])
      i += 2
      continue
    units.append(hk[i])
    i += 1
  return units


_VOWELS = frozenset("aAiIuUeo")
_HIGH_KINDS = frozenset(["yan", "visarga-o", "visarga", "m-vowel",
                         "t-assim", "avagraha"])


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
  if lc in "kgcjTDtdpbN":
    if rc not in _VOWELS and rc != "'":
      return "t-assim"
    return "cons-vowel"
  return "cons-cons"


def _sep(left_hk, right_hk, left_under, right_under, whole_hk=None):
  """Choose separator at a boundary: '-' for samAsa, ' ' for separate pada."""
  k = _boundary_kind(left_hk, right_hk)
  if k == "vowel-cons":
    return "-"
  if k in ("m-vowel", "visarga-o"):
    return " "
  lu = left_under or left_hk
  ru = right_under or right_hk
  if ru.startswith(_COMPOUND_SUFFIXES):
    return "-"
  if ru.startswith(_META_SUFFIXES):
    return "-"
  if k == "yan" and ru.startswith("ari") and lu != "iti":
    return "-"
  if k == "visarga" and left_hk.endswith(("z", "S")) and right_hk[0] in "zSscC":
    return "-"
  # Particles / pronouns / verbs after a sandhi boundary are separate padas.
  if ru in _AVYAYAS or ru in _PRONOUNS:
    return " "
  if right_hk in _AVYAYAS or right_hk in _PRONOUNS:
    return " "
  if k == "t-assim" and (ru == "hi" or right_hk == "dhi"):
    return " "
  if lu == "iti":
    return " "
  jn = left_hk + right_hk
  if _prefix_in_dict(jn) or jn in _load_words():
    return "-"
  right_variants = [right_under] if right_under else []
  for rv in list(right_variants):
    if len(rv) > 2 and rv.endswith(("M", "m", "H")):
      right_variants.append(rv[:-1])
  for rv in right_variants:
    if not rv:
      continue
    jn2 = (left_under or left_hk) + rv
    if _prefix_in_dict(jn2) or jn2 in _load_words():
      return "-"
  return " "


_MAX_UNITS = 40
_QUALITY = {
    "exact": 30, "yan": 22, "visarga-o": 22, "visarga": 22,
    "avagraha": 22, "t-assim": 22, "merger": 24, "stem": 8, "upasarga": 6,
}


def _segment(hk, strict):
  """DP segmentation. ``strict``: only high-precision sandhi boundaries and
  dict-join compounds may split a token that is itself a valid word.

  Returns (pieces, seps) or None if no acceptable split."""
  if has_global_merger(hk):
    return None
  units = hk_to_units(hk)
  m = len(units)
  if m < 3:
    return None
  coff = [0]
  for u in units:
    coff.append(coff[-1] + len(u))
  NEG = float("inf")
  dp = [NEG] * (m + 1)
  prev = [-1] * (m + 1)
  info = [None] * (m + 1)
  dp[0] = 0
  for i in range(m):
    if dp[i] == NEG:
      continue
    upper = min(m, i + _MAX_UNITS)
    # longest-first (tie-break prefers longer/earlier pieces)
    for j in range(upper, i, -1):
      nunits = j - i
      if nunits < 2:
        continue
      # In strict mode never keep the whole token as a single piece; a split
      # must win on its own merits.
      if strict and i == 0 and j == m:
        continue
      piece = "".join(units[i:j])
      if len(piece) < 3 and piece not in _SHORT_OK:
        continue
      # YAN requirement: after a y/v-final left piece the right must begin
      # with a vowel (the semivowel is inserted before a vowel only).
      if i > 0:
        lch = units[i - 1]
        if lch in ("y", "v"):
          if piece[:1] not in _VOWELS and piece[:2] not in ("ai", "au"):
            continue
      if piece in _BARE_SUFFIXES and (i > 0 or j < m):
        continue
      kind, under = _valid_piece_kind(piece, piece_mode=True)
      if kind is None:
        continue
      if kind == "stem":
        base = _stem_base_piece(piece)
        if base:
          under = base
      if not _piece_reliable(piece, kind, under):
        continue
      if j < m and under in _AVYAYAS and kind == "exact" and len(piece) <= 3:
        continue
      if i > 0 and is_veto_split(hk, coff[i]):
        continue
      # boundary kind computed on char strings:
      if i > 0:
        lhk = hk[:coff[i]]
        rhk = piece
        bkind = _boundary_kind(lhk, rhk)
        lkind = info[i][2] if info[i] else None
        # Right-side pieces must be surface-complete words (never restored):
        # a restored right piece (e.g. az->aH) is always a junk shard.
        if kind not in ("exact", "stem", "avagraha", "merger"):
          continue
        if i > 0 and piece.endswith(("z", "S")):
          continue
        # Sandhi-witness requirement - a boundary may only be cut when it is
        # phonologically witnessed by the sandhi type.
        if bkind == "vowel-cons":
          if strict:
            continue
          if lkind not in ("exact", "stem", "merger"):
            continue
          if kind not in ("exact", "stem", "merger"):
            continue
        elif bkind == "m-vowel":
          pass
        elif bkind in ("visarga", "visarga-o"):
          if lkind not in ("visarga", "visarga-o") and not _has_visarga_restore(lhk):
            continue
          if strict and lkind == "exact" and not lhk.endswith("s"):
            continue
          if strict and lkind in ("visarga", "visarga-o") and _count_of(info[i][1]) < 3:
            continue
          # H -> r only before vowels; s/z/S before vowels is not a sandhi.
          if rhk[:1] in _VOWELS and not lhk.endswith("r"):
            continue
        elif bkind == "yan":
          if lkind != "yan" and not _has_yan_restore(lhk):
            continue
          if strict and lkind == "yan" and _count_of(info[i][1]) < 5:
            continue
          if strict and (under in _WEAK_RIGHTS or piece in _WEAK_RIGHTS):
            # iti + evam/atra style quotative collocations always split
            if not (lkind == "yan" and info[i][1] == "iti"):
              continue
          whole_cnt = _count_of(hk)
          if hk.endswith(("M", "m", "H")):
            whole_cnt = max(whole_cnt, _count_of(hk[:-1]))
          if strict and whole_cnt >= 8:
            # heavily lexicalised whole words (sarvajJa, pratyakSa) stay
            # joined unless cut before a recognised compound suffix
            if not (under or piece).startswith(_COMPOUND_SUFFIXES):
              continue
        elif bkind in ("t-assim", "cons-vowel"):
          if not _left_final_witness(lhk):
            continue
          if strict:
            if under in _WEAK_RIGHTS or piece in _WEAK_RIGHTS:
              continue
            lmax = _count_of(lhk)
            for r in _restores_of(lhk):
              lmax = max(lmax, _count_of(r))
            if lmax < 10 and lhk not in _SANDHI_KEEP:
              continue
        else:
          continue
      q = _QUALITY[kind] + 3 * min(len(piece), 20)
      extra = 0
      if piece in _PRONOUNS or piece in _AVYAYAS:
        extra -= 4  # independent particles/pronouns favour a clean cut
      if i > 0:
        if bkind in _HIGH_KINDS:
          extra -= 10  # bonus for genuine sandhi boundary
        if j == m:
          extra -= 6  # prefer splitting off a clean final pada
      cost = dp[i] + 100 - q + extra
      if cost < dp[j]:
        dp[j] = cost
        prev[j] = i
        info[j] = (piece, under, kind)
  if dp[m] == NEG:
    return None
  idx = []
  cur = m
  while cur > 0:
    p = prev[cur]
    if p < 0:
      return None
    idx.append((p, cur))
    cur = p
  idx.reverse()
  if len(idx) <= 1:
    return None
  pieces, unders, kinds = [], [], []
  for (a, b) in idx:
    pc, un, kn = info[b]
    pieces.append(pc)
    unders.append(un)
    kinds.append(kn)
  # safety: re-check veto at every internal boundary
  for k in range(1, len(idx)):
    if is_veto_split(hk, coff[idx[k][0]]):
      return None
  seps = []
  for k in range(len(pieces) - 1):
    seps.append(_sep(pieces[k], pieces[k + 1], unders[k], unders[k + 1]))
  return (pieces, seps)


def _hyphenate_hk_token(hk):
  whole = _whole_kind(hk)
  # Very long "simplex" analyses are implausible: such tokens are compounds
  # with an inflectional tail (…karmajJAnatayA) - treat as compound.
  if whole in ("stem", "upasarga") and len(hk) >= 24:
    whole = None
  if whole is not None:
    res = _segment(hk, strict=True)
    if res is None:
      return hk
  else:
    res = _segment(hk, strict=False)
    if res is None:
      return hk
  pieces, seps = res
  out = [pieces[0]]
  for s, p in zip(seps, pieces[1:]):
    out.append(s)
    out.append(p)
  return "".join(out)


def hyphenate_word(word):
  """Hyphenate a single Devanagari word (no spaces). Idempotent."""
  if not word or len(word) < 2:
    return word
  try:
    hk = sanscript.transliterate(word, sanscript.DEVANAGARI, sanscript.HK)
  except Exception:
    return word
  if not hk or len(hk) < 3:
    return word
  if regex.fullmatch(r"[^a-zA-Z']+", hk):
    return word
  hyph_hk = _hyphenate_hk_token(hk)
  if hyph_hk == hk:
    return word
  parts = regex.split(r"([ \-])", hyph_hk)
  out = []
  for pt in parts:
    if pt in (" ", "-") or pt == "":
      out.append(pt)
    else:
      try:
        out.append(sanscript.transliterate(pt, sanscript.HK,
                                           sanscript.DEVANAGARI))
      except Exception:
        out.append(pt)
  return "".join(out)


_WORD_RE = regex.compile(r"[ऀ-ॣऽ]+")


def hyphene(text, show_progress=False):
  """Hyphenate (split) Sanskrit text per the bare-hyphenator rules.

  Preserves sandhi (never reverts it), never splits dIrgha/guNa/vRddhi
  mergers, splits separable yaN / visarga / final-m / assimilation + samAsa
  joints with ``-`` (samAsa) or `` `` (separate padas).

  >>> hyphene("इत्येवम्")
  'इत्य् एवम्'
  >>> hyphene("मध्वरिः")
  'मध्व्-अरिः'
  >>> hyphene("धर्मार्थ")
  'धर्मार्थ'

  :param text: Devanagari (possibly markdown-mixed) string.
  :param show_progress: unused, kept for API compatibility.
  :return: hyphenated string.
  """
  if not text:
    return text
  _load_words()

  def _repl(m):
    w = m.group(0)
    # Tokens touching a hyphen are part of an already-split compound: leave
    # them alone (this also makes hyphene idempotent).
    if text[m.start() - 1:m.start()] == "-" or text[m.end():m.end() + 1] == "-":
      return w
    return hyphenate_word(w)

  return _WORD_RE.sub(_repl, text)


# Aliases (the prompt spells it ``hyphene``; accept common variants).
hyphen = hyphene
hyphenate = hyphene
hyphenate_text = hyphene
