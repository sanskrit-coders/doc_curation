"""segment - part of the hyphenator package (see __init__.py)."""
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
    _HIGH_KINDS,
    _RA_BADSPLITS_MAX_K,
    _RA_BADSPLITS_MAX_PIECE,
    _RA_BADSPLITS_MIN,
    _RA_BADSPLITS_UNIT,
    _RA_NGRAM_MAX_K,
    _RA_NGRAM_MIN_SPLITS,
    _RA_NGRAM_MIN_SUPPORT,
    _RA_NGRAM_RATIO,
    _RENDER_SPLIT_RE,
    _SEP_GLYPHS,
    _VOWELS
)
from . import seps as SP
from . import tries as T
from . import validate as V


_CACHE_TOKEN = {}


_CACHE_MEMO_PIECE = {}


_CACHE_MEMO_SEPS = {}


_CACHE_BAD = {}


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


_MAX_UNITS = 200


_QUALITY = {
    "exact": 30, "yan": 22, "visarga-o": 22, "visarga": 22,
    "avagraha": 22, "t-assim": 22, "merger": 24, "stem": 8, "upasarga": 6,
    "memo": 30,
}


def _freq_quality(word):
  """Graded frequency preference, tiered rAmAnujIya > DCS stems > the word
  tries (padas / nominal-stems / verb-stems / avyayas).  Log-scaled and
  capped so that kind choices and length still dominate.  Higher evidence ->
  cheaper piece."""
  if not word:
    return 0
  p, n, v, a, d, r = T._load_words().layer_counts(word)
  if r:
    return min(14 + int(3 * math.log2(r + 1)), 21)
  if d:
    return min(6 + int(3 * math.log2(d + 1)), 21)
  w = max(p, n, v, a)
  return min(int(3 * math.log2(w + 1)), 21)


def _segment(hk, strict, strong_vc=False):
  """DP segmentation. ``strict``: only high-precision sandhi boundaries and
  dict-join compounds may split a token that is itself a valid word.
  ``strong_vc`` (whole kind ``stem``): a strong exact|exact vowel+consonant
  joint (sarva|rasaH) is allowed even in strict mode.

  Returns (pieces, seps) or None if no acceptable split."""
  if V.has_global_merger(hk):
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
      # Never keep the whole token as a single piece (both modes): a valid
      # whole token would take the strict path; in non-strict mode a lone
      # whole-piece path would shadow real splits and return None.
      if i == 0 and j == m:
        continue
      piece = "".join(units[i:j])
      if len(piece) < 3 and piece not in C._SHORT_OK:
        continue
      if piece == "a" and i > 0:
        continue  # naiJ prefix a- only ever heads a token
      # YAN requirement: after a y/v-final left piece the right must begin
      # with a vowel (the semivowel is inserted before a vowel only).
      if i > 0:
        lch = units[i - 1]
        if lch in ("y", "v"):
          if piece[:1] not in _VOWELS and piece[:2] not in ("ai", "au"):
            continue
      if piece in C._BARE_SUFFIXES and (i > 0 or j < m):
        continue
      kind, under = V._valid_piece_kind(piece, piece_mode=True)
      if kind is None:
        if V._memo_piece_split(piece) is None:
          continue
        kind, under = "memo", piece
      if kind == "stem":
        base = V._stem_base_piece(piece)
        if base:
          under = base
      if kind != "memo" and not V._piece_reliable(piece, kind, under):
        continue
      # An internal halant-final piece (dictionary "exact", inferred "stem"
      # or de-assimilation "t-assim") must be a surface the corpus itself
      # uses: root entries (सर्व् = √सर्व्), exotic headwords (अपास्),
      # stem husks (तसम्) and one-off reconstructions (साद् = "sAt") are
      # impossible padas.  Visarga/yan restores keep their own witnesses.
      if (j < m and kind in ("exact", "stem", "t-assim")
          and V._halant_final(piece)
          and not V._attested(piece)
          and not (kind in ("stem", "t-assim")
                   and (under or piece).endswith(("vat", "mat"))
                   and V._base_attested(V._stem_base_piece(under or piece)))
          and not (kind == "stem" and piece.endswith("m")
                   and V.merger_chain_valid(V._stem_base_piece(piece) or ""))
          and not (kind == "t-assim" and V._attested(under))
          and not (kind == "t-assim"
                   and V._stem_valid_piece(under or "")
                   and V._count_of(under or "") >= 2
                   and V._base_attested(V._stem_base_piece(under or "")))):
        continue  # a t-assim piece is witnessed by its attested restore
        # (zravaNAn <- zravaNAt, corpus-attested) or an ablative that is
        # itself seen (prANAd <- prANAt cnt=2); a base-only artifact
        # (maryAd <- maryAt cnt=0, base marya) is no witness
      if (j < m and kind == "exact" and len(piece) <= 3
          and (under in C._AVYAYAS or under.lower() in C._UPASARGAS)
          and piece not in C._PRONOUNS
          and not (piece.endswith("y")
                   and V._yan_restored_left(piece) in (C._AVYAYAS | C._PRONOUNS))):
        continue  # a short particle/prefix may not head an internal joint -
        # but a connective pronoun (yat|tUktam) or a yaN-restored particle
        # (apy|AdhAra = api) does
      if i > 0 and V.is_veto_split(hk, coff[i]):
        continue
      bad = 0
      if (i > 0 and V._count_of(info[i][0]) == 0
          and len(info[i][0]) <= _RA_BADSPLITS_MAX_PIECE):
        # Negative evidence only where the cut would create a short left
        # piece the corpus never uses: नमस्/तद्/फलम् are real pieces (नमस् ते
        # stays a split), while जान्य्/अधिर् are analyzer-only shards.
        if SP._boundary_kind(hk[:coff[i]], piece) == "m-vowel":
          bad = 0  # M + vowel is a core pada split (फलम् अश्नुते): the
          # negative memory must not veto it
        else:
          bad = _badsplit_evidence(hk, coff[i])
        if bad >= _RA_BADSPLITS_MIN and _junction_ngram_plain(hk, coff[i]):
          # ... except a genuine possessive-suffix t-restore (मर्यादावत् +
          # ऐश्वर्यम् = मर्यादावदैश्वर्यम्): mined false restores share its
          # cut position (…वद्|ऐ… वृद्धि), yet this द-final piece rests on
          # an attested stem base.
          if (info[i][2] == "t-assim"
              and (info[i][1] or "").endswith(("vat", "mat"))
              and V._base_attested(V._stem_base_piece(info[i][1]))):
            bad = 0
          else:
            continue
      # boundary kind computed on char strings:
      if i > 0:
        lhk = hk[:coff[i]]
        lpiece = info[i][0]
        rhk = piece
        bkind = SP._boundary_kind(lhk, rhk)
        lkind = info[i][2] if info[i] else None
        if (piece.startswith("y") and len(lpiece) >= 3
            and lkind not in ("t-assim", "visarga", "visarga-o", "memo")
            and lpiece not in C._PRONOUNS and lpiece not in C._AVYAYAS
            and lpiece.lower() not in C._UPASARGAS
            and V._prefix_in_dict(lpiece + "y")):
          continue  # inside a single dictionary word the y belongs to the
          # word (vid|yAH steals vidyA, viSa|yaiH steals viSayaiH); a real
          # pada join like tad|yathA stays

        if (rhk.startswith(("sya", "syA", "syo"))
            and ((lpiece + "sya") in T._load_words()
                 or V._stem_valid(lpiece + "sya"))):
          # -sya is the left word's genitive ending, not a new member
          # (परमेश्वर|स्याधार is no split).
          continue
        if (lpiece.endswith(("s", "z", "S")) and rhk.startswith("y")
            and (lpiece[:-1] + "sya") in T._load_words()):
          # the y stole the genitive स्य: पुरुषस्|याप्यति is no split
          continue
        # Right-side pieces must be surface-complete words (never restored):
        # a restored right piece (e.g. az->aH) is always a junk shard.
        # t-assim pieces are surface-true (zravaNAn = zravaNAt + na).
        if kind not in ("exact", "stem", "avagraha", "merger", "visarga",
                        "yan", "memo", "t-assim"):
          continue
        if (kind == "visarga" and not piece.endswith(("z", "S"))
            and not (j == m and piece.endswith(("s", "r")))):
          continue  # restored H->r shards (yar, yam) are never valid rights
          # (a token-final s/r surface is the prastuti H placeholder)
        if i > 0 and piece.endswith(("z", "S")) and kind not in (
            "visarga", "visarga-o", "exact"):
          continue
        # Sandhi-witness requirement - a boundary may only be cut when it is
        # phonologically witnessed by the sandhi type.
        if bkind == "vowel-cons":
          if (piece.startswith(("mAnaM", "mAnam", "mAnasya", "mAnAH",
                                "mAnaH", "mAnA"))
              and lpiece[-1:] in _VOWELS):
            continue  # the verbal -mAna tail (adhyasyamAna, gamyamAna)
            # binds to its root: asya|mAnam is no word boundary
          if strict and not (strong_vc and lkind == "exact"
                             and kind == "exact"
                             and V._count_of(lhk) >= 10
                             and V._count_of(piece) >= 10
                             and not V._stolen_final_shard(hk, piece, lpiece)):
            continue  # upasarga wholes (AkAzayati) never take this cut,
            # and the window must not chop an inflected single word
            # (viSayaiH is no viSa + yaiH)
          if lkind not in ("exact", "stem", "merger"):
            continue
          if kind not in ("exact", "stem", "merger", "visarga", "yan",
                          "memo", "t-assim"):
            continue  # t-assim rights are surface-true (zravaNAn)
          # A vibhakti-final form (लोके) is no samAsa member: an e/o-final
          # left piece only compounds where the corpus itself joins it
          # (गणे-श्वरम्, पङ्के-रुह) or as the -as compounding stem
          # (mano-, tejo-, svato- = manaH, tejaH, svataH).
          if lpiece[-1] in ("e", "o"):
            if not V._joined_left_attested(lpiece):
              if not (lpiece[-1] == "o"
                      and (lpiece[:-1] + "aH") in T._load_words()):
                continue
          # Visarga-r ambiguity: a vowel-final left + r-initial right must
          # not steal the H-placeholder r from the "…ir eva" reading
          # (ज्योति-रेव is wrong; ज्योतिर् एव is the convention) - unless the
          # r-initial piece is itself a corpus surface (मिथ्या-रूपम्).
          if (piece.startswith("r") and piece[1:2] in _VOWELS
              and not V._attested(piece)):
            # an r-initial piece after a vowel-final left is almost always
            # the stolen visarga-r placeholder (ज्योति-रेव): only corpus
            # tokens (मिथ्या-रूपम्) may start such a cut.
            continue
        elif bkind == "m-vowel":
          if (V._whole_kind(hk) is not None and piece[:1] in _VOWELS
              and V._prefix_in_dict(lpiece + piece[:1])):
            continue  # gamyam|Anasya: the A is the word's own mA (gamyamAna)
            # - a real pada join (phalam aznute) has no such whole word
        elif bkind in ("visarga", "visarga-o"):
          if kind == "merger":
            # merged units (asyaiva) never begin at a visarga joint
            continue
          if (lpiece.endswith(("s", "z", "S"))
              and piece.startswith(("y", "v", "r"))):
            continue  # a pada-final H shows as r before a semivowel
            # (bhUtAkAzar yApi): ...as|yApi merely steals the asya's y
          # the sandhi witness is the left *piece* (jyotir -> jyotiH), never
          # the accumulated prefix (AdityAdijyotir is no word)
          if lkind not in ("visarga", "visarga-o", "memo") and not V._has_visarga_restore(lpiece):
            continue
          if strict and lkind == "exact" and not lpiece.endswith("s"):
            continue
          if strict and lkind in ("visarga", "visarga-o"):
            # weak H-restores (duSprakRter->duSprakRtiH) are still fine when
            # the restored form leans on a frequent stem.
            lu = info[i][1]
            if V._count_of(lu) < 3:
              if not V._base_attested(V._stem_base_piece(lu)):
                continue
          # H -> r only before vowels; s/z/S before a vowel (including ऋ,
          # which is why pUrvakas|RSTy misreads सृष्ट्यादि) is not a sandhi.
          if ((rhk[:1] in _VOWELS or rhk[:1] == "R")
              and not lpiece.endswith("r")):
            continue
        elif bkind == "yan":
          if lkind not in ("yan", "memo") and not V._has_yan_restore(lhk):
            # ... or the left piece is itself a prastuti surface whose yaN
            # restore is a closed-class particle (अप्य् अविरोधात्: the corpus
            # writes api halant-final before a vowel).  A noun restore (दिश्य्
            # -> दिशि) is no witness: निर्दिश्यत is one verb form.
            restore = V._yan_restored_left(lpiece)
            if not (lkind == "exact" and restore in (C._AVYAYAS | C._PRONOUNS)
                    and V._attested(lpiece)):
              continue
          if strict and lkind == "yan" and V._count_of(info[i][1]) < 5:
            continue
          if strict and (under in C._WEAK_RIGHTS or piece in C._WEAK_RIGHTS):
            # iti + evam/atra style quotative collocations always split
            lu = info[i][1]
            if not (lkind in ("yan", "exact") and lu in ("iti", "ity")):
              continue
          whole_cnt = V._count_of(hk)
          if hk.endswith(("M", "m", "H")):
            whole_cnt = max(whole_cnt, V._count_of(hk[:-1]))
          if (strict and whole_cnt >= 8
              and under not in C._WEAK_RIGHTS and piece not in C._WEAK_RIGHTS):
            # heavily lexicalised whole words (sarvajJa, pratyakSa) stay
            # joined unless cut before a recognised compound suffix
            if not (under or piece).startswith(C._COMPOUND_SUFFIXES):
              continue
        elif bkind in ("t-assim", "cons-vowel"):
          if (bkind == "cons-vowel" and lhk.endswith("t")
              and not rhk.startswith("'")):
            # a surface t before a vowel is never a word-final t (that would
            # voice to d): it is a ta+A merger (bhUtAkAzaM = bhUta+AkAzaM) or
            # the right word's own -t- suffix (etAvatA).  Cut stays blocked.
            continue
          if lkind != "memo" and not V._left_final_witness(lhk):
            continue
          if strict:
            closed_pair = ((info[i][1] or lpiece) in (C._AVYAYAS | C._PRONOUNS)
                           and (under or piece) in (C._AVYAYAS | C._PRONOUNS))
            if not closed_pair and (under in C._WEAK_RIGHTS or piece in C._WEAK_RIGHTS):
              continue
            if (kind in ("exact", "stem") and V._count_of(piece) < 10
                and piece not in C._SANDHI_KEEP
                and not (kind == "stem"
                         and V.merger_chain_valid(piece))):
              continue  # a rare shard (अपाल, अत्वं) is no samAsa member;
              # merged surfaces (asyAmRtam = asya + amRtam) keep theirs
            lmax = V._count_of(lhk)
            for r in V._restores_of(lhk):
              lmax = max(lmax, V._count_of(r))
            if lmax < 10 and lhk not in C._SANDHI_KEEP:
              continue
        else:
          continue
      q = _QUALITY[kind] + 3 * min(len(piece), 20)
      if kind == "stem" and under:
        q += min(V._count_of(under), 20)  # frequent base -> plausible inflected form
      q += max(_freq_quality(under), _freq_quality(piece))
      extra = 0
      if (kind == "merger" and not V._count_of(piece)
          and not V._attested(piece) and V._witnessed_swallow(piece)):
        # an un-attested chain piece that hides a witnessed split on the
        # same span (zravaNAnna) must beat it on merit, not on piece count
        extra += 60
      if piece in C._PRONOUNS or piece in C._AVYAYAS:
        extra -= 4  # independent particles/pronouns favour a clean cut
      if (i > 0 and bkind == "vowel-cons" and lpiece.endswith("A")
          and lpiece not in C._TRIE_NOMINAL_STEMS
          and (lpiece[:-1] + "aH") in T._load_words()
          and V._count_of(lpiece[:-1] + "aH") >= 5):
        extra += 20  # a nom.pl "-A(H)" surface (prANA, devA) is a finished
        # pada, never a samAsa head: the restore reading prANAd eva adhi wins
      if i > 0:
        if bkind in _HIGH_KINDS:
          extra -= 10  # bonus for genuine sandhi boundary
        if bkind == "m-vowel":
          extra -= 6  # M + vowel is a high-precision split
        if j == m:
          extra -= 6  # prefer splitting off a clean final pada
      cost = dp[i] + 100 - q + extra + _RA_BADSPLITS_UNIT * bad
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
  return _segment_assemble(hk, coff, idx, pieces, unders, kinds)


def _segment_assemble(hk, coff, idx, pieces, unders, kinds):
  """DP traceback assembly: re-check the veto at every internal boundary,
  choose separators, and expand memo pieces into the corpus's own
  sub-segmentation.  Returns (pieces, seps) or None."""
  for k in range(1, len(idx)):
    if V.is_veto_split(hk, coff[idx[k][0]]):
      return None
  seps = []
  for k in range(len(pieces) - 1):
    seps.append(SP._sep(pieces[k], pieces[k + 1], unders[k], unders[k + 1],
                        ctx=(hk, coff[idx[k + 1][0]])))
  for k, s in enumerate(seps + [" "]):
    # a chunk shown as a separate pada must be a pada form, not a bare stem
    if s == " " and not V._pada_ok(pieces[k], unders[k], kinds[k]):
      return None
  if "memo" in kinds:
    out_pieces, out_seps = [], []
    for k, pc in enumerate(pieces):
      if k > 0:
        out_seps.append(seps[k - 1])
      if kinds[k] == "memo":
        mparts, mseps = V._memo_piece_split(pc)
        out_pieces.append(mparts[0])
        for s, p in zip(mseps, mparts[1:]):
          out_seps.append(s)
          out_pieces.append(p)
      else:
        out_pieces.append(pc)
    pieces, seps = out_pieces, out_seps
  return (pieces, seps)


def _hyphenate_hk_token(hk):
  hit = _CACHE_TOKEN.get(hk)
  if hit is not None:
    return hit
  res = _hyphenate_hk_token_uncached(hk)
  _CACHE_TOKEN[hk] = res
  return res


def _hyphenate_hk_token_uncached(hk):
  whole = V._whole_kind(hk)
  # Very long "simplex" analyses are implausible: such tokens are compounds
  # with an inflectional tail (…karmajJAnatayA) - treat as compound.
  if whole in ("stem", "upasarga") and len(hk) >= 24:
    whole = None
  if whole is not None:
    res = _segment(hk, strict=True,
                   strong_vc=(whole == "stem"
                              and not SP._finite_verb_piece(hk)))
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



# consonant+virama followed by an independent vowel: an explicit non-sandhi
# joint (prastuti writes यद्-अनुगुणा for yad + anuguNA).
_DEV_DISJ_RE = regex.compile(r"(?<=[\u0915-\u0939]\u094d)(?=[\u0905-\u0914])")


def _badsplit_evidence(hk, cpos):
  """Negative split evidence at a boundary: weight of the longest attested
  badsplits context (>= 2 letters each side; a lone letter is never enough)."""
  trie = C._TRIE_BADSPLITS
  if trie is None or cpos <= 0 or cpos >= len(hk):
    return 0
  key = (hk, cpos)
  hit = _CACHE_BAD.get(key)
  if hit is not None:
    return hit
  res = 0
  kmax = min(_RA_BADSPLITS_MAX_K, cpos, len(hk) - cpos)
  for k in range(kmax, 1, -1):
    vals = trie.get(("%s\x1f%s" % (hk[cpos - k:cpos],
                                   hk[cpos:cpos + k])).encode("utf-8"))
    if vals:
      res = vals[0][0]
      break
  _CACHE_BAD[key] = res
  return res


def _junction_ngram_plain(hk, cpos):
  """True when the corpus n-gram at this junction holds no split vote (the
  longest attested devanagari context is plain-dominant).  Gate for the
  badsplits veto: negative evidence may only block cuts the corpus's own
  junction statistics do not sanction."""
  try:
    dev_l = sanscript.transliterate(
        hk[max(0, cpos - _RA_NGRAM_MAX_K):cpos],
        sanscript.HK, sanscript.DEVANAGARI)
    dev_r = sanscript.transliterate(
        hk[cpos:cpos + _RA_NGRAM_MAX_K],
        sanscript.HK, sanscript.DEVANAGARI)
  except Exception:
    return False
  if not dev_l or not dev_r:
    return False
  return not _ngram_votes_hyphen(dev_l, dev_r)


def _ngram_cell(wleft, wright):
  """Longest *attested* junction context: ``((ns, nn), k, kmax)`` or None.

  ``wleft``/``wright`` are the surface letters adjacent to the junction (the
  caller passes at most ``_RA_NGRAM_MAX_K`` each side).  The longest context
  present in the trie decides - an attested negative context (e.g.
  ``कान|विध`` against the tempting ``ान|वि``) blocks the shorter, noisier
  context.  ``k < kmax`` marks a backoff to a shorter context.
  """
  T._load_words()
  trie = C._TRIE_RA_NGRAM
  if trie is None:
    return None
  kmax = min(_RA_NGRAM_MAX_K, len(wleft), len(wright))
  for k in range(kmax, 0, -1):
    vals = trie.get(("%s\x1f%s" % (wleft[-k:], wright[:k])).encode("utf-8"))
    if vals:
      return vals[0], k, kmax
  return None


def _ngram_votes_hyphen(wleft, wright):
  """True when the corpus hyphenates this junction unambiguously.

  Requires at least 2 split occurrences per plain one; a backoff to a
  shorter-than-available context additionally needs ``_RA_NGRAM_MIN_SUPPORT``
  instances (one-off witnesses like ``विपरीत|व्याप्तो`` must not generalise
  to ``ग्रहीतव्यः``).  A lone 1-letter context is never enough - ``ष|श्``
  in ``ज्योतिषश्`` (the visarga placeholder) must not ride on corpus joins
  like ``दोष-शमन``.
  """
  hit = _ngram_cell(wleft, wright)
  if hit is None:
    return False
  (ns, nn), k, kmax = hit
  if k < 2:
    return False
  if k < kmax and ns + nn < _RA_NGRAM_MIN_SUPPORT:
    return False
  return ns >= _RA_NGRAM_MIN_SPLITS and ns >= _RA_NGRAM_RATIO * nn


def _ngram_refine(word, hk, out):
  """Add corpus-attested hyphens to a generic DP result.

  At every junction the DP did not split, a hyphen is added when the corpus's
  local letter context votes for a cut; a space separator is upgraded to a
  hyphen when the same evidence holds.  Merger vetoes from ``is_veto_split``
  apply unchanged, and nothing is ever merged back.
  """
  if C._TRIE_RA_NGRAM is None:
    T._load_words()
    if C._TRIE_RA_NGRAM is None:
      return out
  if len(word) < 4:
    return out
  if _RENDER_SPLIT_RE.sub("", out) != word:
    # The DP re-expanded a sandhi joint (tadvad eva for tadvadeva): the two
    # outputs live in different coordinate systems - leave it alone.
    return out
  if V.has_global_merger(hk):
    # Non-separable merger chains (svaprakAzAdvitIya) are absolute-veto
    # tokens: never touch them, even at non-merger junctions.
    return out
  cuts = {}
  pos = 0
  for ch in out:
    if ch in ("-", " ", "–", "—"):
      cuts[pos] = ch
    else:
      pos += 1
  K = _RA_NGRAM_MAX_K
  changed = False
  for p in range(1, len(word)):
    if unicodedata.category(word[p]) in ("Mn", "Mc"):
      continue  # a cut may not precede a dependent sign (mAtrA/virama)
    sep = cuts.get(p)
    if sep in ("-", "–"):
      continue
    lft_dev = word[max(0, p - K):p]
    rgt_dev = word[p:p + K]
    if (sep is None and rgt_dev == "च"
        and lft_dev.endswith(("श्", "ष्", "स्", "र्"))):
      # a visarga surface followed by the bare particle ca is a pada break
      # (श्रुतेश् च side by side; पश्चात् stays whole - its right is not च).
      cuts[p] = " "
      changed = True
      continue
    wleft, wright = word[max(0, p - K):p], word[p:p + K]
    if not _ngram_votes_hyphen(wleft, wright):
      continue
    # The n-gram vote alone never suffices: the new boundary must sit
    # against rAmAnujIya/DCS dictionary words.
    lstart = max((q for q in cuts if q < p), default=0)
    rend = min((q for q in cuts if q > p), default=len(word))
    lft_dev = word[lstart:p]
    rgt_dev = word[p:rend]
    # A yaN-restored locative-plural pada can't head a samAsa
    # (गानेष्व्|अस्य: restore the व to उ before testing).
    lft_restore = (lft_dev[:-1] + "उ") if lft_dev.endswith("व") else lft_dev
    if lft_restore.endswith(("षु", "सु")):
      continue
    # A finished ablative pada (…ād/…āt) can't head a samAsa: the junction
    # is a pada boundary (तल्लिङ्गाद् ब्रह्मण), never a hyphen.
    if lft_dev.endswith(("ाद्", "ात्")):
      continue
    # पुरुषस्|याप्यति: the y stole the genitive स्य (my sya guard covers the
    # DP, the refine needs its own).
    if lft_dev.endswith("स्") and rgt_dev.startswith("य"):
      try:
        if (sanscript.transliterate(lft_dev[:-1] + "स्य", sanscript.DEVANAGARI,
                                    sanscript.HK) in T._load_words()):
          continue
      except Exception:
        pass
    # two tiG-antas never samAsa-join (याप्यति|दिशति)
    try:
      lhk_piece = sanscript.transliterate(lft_dev, sanscript.DEVANAGARI,
                                          sanscript.HK)
      rhk_piece = sanscript.transliterate(rgt_dev, sanscript.DEVANAGARI,
                                          sanscript.HK)
      if (SP._finite_verb_piece(lhk_piece)
          and SP._finite_verb_piece(rhk_piece)):
        continue
      if (rhk_piece.startswith(("mAnaM", "mAnam", "mAnasya", "mAnAH",
                                "mAnaH", "mAnA"))
          and lhk_piece[-1:] in "aAiIuUfFxXeEoO"):
        continue  # the verbal -mAna tail binds to its root (adhyasyamAna)
      if (rhk_piece in C._PRONOUNS and lhk_piece.endswith(("y", "v"))
          and (V._yan_restored_left(lhk_piece) or "").lower()
          in C._UPASARGAS):
        continue  # adhy|asya: a prefix-y does not take a pronoun pada here
      word_hk = sanscript.transliterate(word, sanscript.DEVANAGARI,
                                        sanscript.HK)
      if V._stolen_final_shard(word_hk, rhk_piece, lhk_piece):
        continue  # viSayaiH is no viSa|yaiH: the y is the base's own
    except Exception:
      pass
    if not V._junction_dict_ok(word[lstart:p], word[p:rend]):
      continue
    try:
      pre = sanscript.transliterate(word[:p], sanscript.DEVANAGARI,
                                    sanscript.HK)
    except Exception:
      continue
    if not pre or not hk.startswith(pre):
      continue
    if V.is_veto_split(hk, len(pre)):
      continue
    new_sep = "–" if SP._sep_dash(hk, len(pre)) else "-"
    cuts[p] = new_sep
    if sep != new_sep:
      changed = True
  if not changed:
    return out
  pieces, seps = [], []
  start = 0
  for p in sorted(cuts):
    pieces.append(word[start:p])
    seps.append(cuts[p])
    start = p
  pieces.append(word[start:])
  out = [pieces[0]]
  for s, p in zip(seps, pieces[1:]):
    out.append(s)
    out.append(p)
  return "".join(out)


def hyphenate_word(word):
  """Hyphenate a single Devanagari word (no spaces). Idempotent."""
  if not word or len(word) < 2:
    return word
  memo = T._ra_split_form(word)
  if memo is not None:
    if not memo:
      return word
    mp, ms = V._memo_form_seps(memo)
    out = [mp[0]]
    for s, p in zip(ms, mp[1:]):
      out.append(s)
      out.append(p)
    return "".join(out)
  if _DEV_DISJ_RE.search(word):
    return "-".join(hyphenate_word(c) for c in _DEV_DISJ_RE.split(word) if c)
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
    out = word
  else:
    parts = _RENDER_SPLIT_RE.split(hyph_hk)
    out_parts = []
    for pt in parts:
      if pt in _SEP_GLYPHS or pt == "":
        out_parts.append(pt)
      else:
        try:
          out_parts.append(sanscript.transliterate(pt, sanscript.HK,
                                                   sanscript.DEVANAGARI))
        except Exception:
          out_parts.append(pt)
    out = "".join(out_parts)
  return _ngram_refine(word, hk, out)


_WORD_RE = regex.compile(r"[ऀ-ॣऽ]+")


# (प्रस्तुतौ mUlam-verbatim) annotation spans are protected: never hyphenated.
_ANNO_RE = regex.compile(r"\+\+\+\(.*?\)\+\+\+", regex.DOTALL)


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
  T._load_words()
  anno_spans = [(m.start(), m.end()) for m in _ANNO_RE.finditer(text)]
  anno_starts = [s for s, _ in anno_spans]

  def _in_anno(pos):
    i = bisect.bisect_right(anno_starts, pos) - 1
    return i >= 0 and pos < anno_spans[i][1]

  def _repl(m):
    w = m.group(0)
    # Tokens touching a hyphen are part of an already-split compound: leave
    # them alone (this also makes hyphene idempotent).  '–' (glued pada
    # dash) and '—' count as separators just like '-'.
    if (text[m.start() - 1:m.start()] in ("-", "–", "—")
        or text[m.end():m.end() + 1] in ("-", "–", "—")):
      return w
    if _in_anno(m.start()):
      return w
    return hyphenate_word(w)

  return _WORD_RE.sub(_repl, text)



# Aliases (the prompt spells it ``hyphene``; accept common variants).
hyphen = hyphene


hyphenate = hyphene


hyphenate_text = hyphene
