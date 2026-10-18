"""corpus_ra - part of the hyphenator package (see __init__.py)."""
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
    _RA_BADSPLITS_MAX_K,
    _RA_BADSPLITS_MAX_PIECE,
    _RA_BADSPLITS_MIN,
    _RA_BADSPLITS_UNIT,
    _RA_NGRAM_MAX_K,
    _SEP_SPLIT_RE
)
from . import segment as SG
from . import tries as T


_RA_DETAILS_RE = regex.compile(
    r"<details[^>]*><summary>([^<]+)</summary>(.*?)</details>", regex.DOTALL)


_RA_ANNOT_RE = regex.compile(r"[^\u0900-\u097f-]")


_RA_BAD_RE = regex.compile(r"[\u0964-\u096f]")


_RA_EDGE = ("\u0964\u0965\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d"
            "\u096e\u096f-*_`>")


def _load_ra_sources():
  """Parse ``rAmAnujIya-sources.toml`` into per-source ingestion dicts.

  Every entry carries ``path``, an exclusive ``until`` relative-path bound
  (or None) and ``included_details``: the accepted ``<summary>`` prefixes
  for that source.  An absent ``included_details`` yields an empty tuple,
  meaning every file of the source is ingested whole (all its Sanskrit
  text).
  """
  try:
    with open(C._RA_SOURCES_TOML, "rb") as f:
      cfg = tomllib.load(f)
  except (OSError, tomllib.TOMLDecodeError):
    return []
  sources = []
  for src in cfg.get("source", ()):
    sources.append({
        "path": src["path"],
        "until": src.get("until"),
        "included_details": tuple(src.get("included_details", ())),
    })
  return sources


def _ra_source_files():
  """Files contributing to ``rAmAnujIya.trie`` (see rAmAnujIya-sources.toml).

  ``_index.md`` navigation pages are never ingested.  For directory sources
  only relative paths strictly below ``until`` (if set) are considered.
  """
  return [path for path, _ in _ra_file_configs()]


def _ra_file_configs():
  """Yield ``(path, source-config)`` for every file of the TOML sources."""
  for src in _load_ra_sources():
    root = src["path"]
    if os.path.isfile(root):
      if os.path.basename(root) != "_index.md":
        yield root, src
      continue
    until = src["until"]
    for dirpath, dirnames, filenames in os.walk(root):
      dirnames.sort()
      for fn in sorted(filenames):
        if not fn.endswith(".md") or fn == "_index.md":
          continue
        path = os.path.join(dirpath, fn)
        if until is not None:
          rel = os.path.relpath(path, root).replace(os.sep, "/")
          if not rel < until:
            continue
        yield path, src


def _ra_file_bodies(text, accepted):
  """Ingestable bodies of a source file (whole file when nothing matches).

  Returns the bodies whose ``<summary>`` label starts with one of the
  accepted detail prefixes (``included_details`` of the source; empty when
  the field is absent).  When nothing matches, the whole file is returned
  instead - all its Sanskrit text is ingested.  The caller strips HTML tags;
  summary labels are removed here so they do not leak into the vocabulary).
  """
  bodies = []
  for label, body in _RA_DETAILS_RE.findall(text):
    if any(label.strip().startswith(p) for p in accepted):
      bodies.append(body)
  if bodies:
    return bodies
  text = regex.sub(r"<summary>.*?</summary>", " ", text, flags=regex.DOTALL)
  return [text]


def _extract_ra_corpus():
  """Harvest word counts and segmentation memory from the prastuti corpus.

  Returns ``(counts, split_votes, plain_counts)`` where

  * ``counts``: Devanagari hyphen-piece -> occurrences (as before);
  * ``split_votes``: hyphen-joined surface -> {hyphenated form: votes} for
    every multi-piece token (the corpus's own segmentation);
  * ``plain_counts``: unhyphenated token -> occurrences.

  Sources and their accepted ``<details>`` labels (``included_details``;
  files without a match contributing all their Sanskrit text) are declared
  in ``rAmAnujIya-sources.toml``.  Prastuti
  text is pada-split with ``-`` at samAsa joints, so the hyphen pieces are
  the attested words (the hyphen-joined chunk is deliberately NOT recorded
  as an "exact" word: as a whole it would swallow the internal splits the
  corpus itself makes).  Citation/annotation debris (ASCII, danda, digits)
  and ``+++(...)+++`` annotation spans (verbatim mUla) are skipped.
  """
  counts = {}
  split_votes = {}
  plain_counts = {}
  for path, src in _ra_file_configs():
    try:
      with open(path, encoding="utf-8") as f:
        text = f.read()
    except OSError:
      continue
    for body in _ra_file_bodies(text, src["included_details"]):
      body = SG._ANNO_RE.sub(" ", body)
      body = regex.sub(r"<[^>]*>", " ", body)
      # Space-separated dashes ("भूत-- -जड", "रूप- -सत्त्व"): the upapada
      # separator of a very long samAsa, written with an inner space for
      # readability.  The junction keeps its dash class - normalise to the
      # preferred "--" glyph so the joined surface is recorded and the seps
      # builder votes '–' there.
      body = regex.sub(r"[-–—]+\s+[-–—]+", "--", body)
      # "X-+V" editor junctions over a merged mUla: merge final a/ā with
      # the following independent vowel (…अनुरूप-+एक… = …अनुरूपैक…) via the
      # sandhi package; the dash run may be a normalised "--"
      # (…निरतिशय--+औज्ज्वल्य…).
      body = regex.sub(
          r"([\u0915-\u0939](?:[\u093e-\u094c])?)[-–—]+\s*\+([\u0905-\u0914])",
          _merge_editor_junction, body)
      # other "+" junctions (e.g. after virama) are non-sandhi seams whose
      # merged form is unknown: drop the token.
      body = regex.sub(r"[-–—]+\s*\+", "@", body)
      for raw in body.split():
        tok = raw.strip(_RA_EDGE)
        if not tok or _RA_ANNOT_RE.search(tok) or _RA_BAD_RE.search(tok):
          continue
        pieces = _SEP_SPLIT_RE.split(tok)
        if len(pieces) > 1:
          joined, _bounds = _join_pieces(pieces)
          votes = split_votes.setdefault(joined, {})
          votes[tok] = votes.get(tok, 0) + 1
        else:
          plain_counts[tok] = plain_counts.get(tok, 0) + 1
        for p in pieces:
          if p:
            counts[p] = counts.get(p, 0) + 1
  return counts, split_votes, plain_counts


_INDEPENDENT_VOWELS = frozenset("अआइईउऊऋऌऍऎएऐऑऒओऔ")


_SANDHI = None


_SANDHI_CACHE = {}


def _sandhi_single(left, right):
  """Merge two devanagari surfaces via the sandhi package (first analysis).

  Build-time helper for recreating the mUla sandhi at prastuti seams -
  rejoined pieces (…निरतिशय + औज्ज्वल्य = …निरतिशयौज्ज्वल्य) and editor
  junctions.  Sandhi is assumed always present at build time; the browser
  never reaches this (tries ship prebuilt).
  """
  global _SANDHI
  last = left[-1:]
  # Only vowel-initial right pieces after a consonant/virama-final left are
  # genuine merge spots (…य् + अनन्त, …न् + अपि, …प + एक): s-final stems
  # (रजस् + तमोमय) stay untouched.
  if not (right[:1] in _INDEPENDENT_VOWELS
          and (last == "\u094d" or ("\u0915" <= last <= "\u0939"))):
    return left + right
  key = (left, right)
  hit = _SANDHI_CACHE.get(key)
  if hit is not None:
    return hit
  if _SANDHI is None:
    from sandhi.sandhi import Sandhi
    _SANDHI = Sandhi()
  out = _SANDHI.sandhi(left, right)
  res = out[0][0] if out else left + right
  _SANDHI_CACHE[key] = res
  return res


def _join_pieces(pieces):
  """Join prastuti pieces into the merged mUla surface.

  Returns ``(joined, boundaries)``: ``boundaries[i]`` is the cut position of
  ``pieces[i + 1]`` inside the joined surface, or None when the sandhi
  absorbed the junction (…यस्मिन्न् + अपि…, देव + इन्द्र…): such a boundary
  has no displayable position.
  """
  pieces = [p for p in pieces if p]
  if not pieces:
    return "", []
  joined = pieces[0]
  boundaries = []
  for p in pieces[1:]:
    merged = _sandhi_single(joined, p)
    boundaries.append(len(joined) if merged.startswith(joined) else None)
    joined = merged
  return joined, boundaries


def _merge_editor_junction(m):
  """guNa/vRddhi merge of a final a/ā with an editor-marked independent
  vowel (…अनुरूप-+एक… = …अनुरूपैक…), recreated via the sandhi package."""
  return _sandhi_single(m.group(1), m.group(2))


def _extract_ra_word_counts():
  return _extract_ra_corpus()[0]


def _build_ra_forms_trie(split_votes, plain_counts):
  """Surface -> preferred hyphenation memory -> ``rAmAnujIya-splits.trie``.

  Keys are the joined (hyphen-less) Devanagari surfaces.  A value is the
  corpus's most frequent hyphenated rendering; an empty value marks a
  surface that the corpus leaves *unhyphenated* (so the generic DP must not
  split it either).  A surface counts as plain when it is written
  unhyphenated at least as often as it is hyphenated (at least once): a
  single stray ``सर्व-ज्ञ`` does not outweigh a single plain ``सर्वज्ञ``,
  nor a stray ``अ-युक्त`` two plain ``अयुक्तं``.
  """
  entries = []
  for joined, votes in split_votes.items():
    n_plain = plain_counts.get(joined, 0)
    if n_plain >= 1 and n_plain >= sum(votes.values()):
      entries.append((joined, b""))
      continue
    form = max(votes.items(), key=lambda kv: (kv[1], -len(kv[0])))[0]
    # Normalised frequency of the winning segmentation, per-mille of the
    # surface's occurrences (split votes + plain) - available for scoring
    # experiments via ``T._ra_form_confidence``.
    total = n_plain + sum(votes.values())
    freq = (1000 * votes[form]) // max(total, 1)
    entries.append((joined, ("%d\t%s" % (freq, form)).encode("utf-8")))
  for tok in set(plain_counts) - set(split_votes):
    if plain_counts[tok] >= 3:
      entries.append((tok, b""))
  trie = marisa_trie.BytesTrie(entries)
  os.makedirs(C._DATA_DIR, exist_ok=True)
  tmp = C._RA_FORMS_TRIE_PATH + ".tmp"
  trie.save(tmp)
  os.replace(tmp, C._RA_FORMS_TRIE_PATH)
  return trie


def _ngram_ctx(surface, pos, k):
  """k letters before + k after the junction ``pos`` (no edge padding: the
  context is simply shorter near the token edges, as in training)."""
  return surface[pos - k:pos], surface[pos:pos + k]


def _ngram_add(tables, surface, pos, is_split, weight):
  """Accumulate one junction occurrence into the per-k context tables."""
  L = len(surface)
  for k in range(1, min(_RA_NGRAM_MAX_K, pos, L - pos) + 1):
    key = "%s\x1f%s" % _ngram_ctx(surface, pos, k)
    cell = tables.get(key)
    if cell is None:
      cell = tables[key] = [0, 0]
    cell[0 if is_split else 1] += weight


def _form_positions(form):
  """``(joined surface, split positions)`` of a hyphenated form.

  Uses ``_join_pieces`` (sandhi package: a virama-final piece + independent
  vowel or a bare a-final merge into the plain surface), so the positions
  are expressed in the joined surface's own coordinates.  A boundary
  absorbed by such a merge has no surface position and is dropped.
  """
  pieces = _SEP_SPLIT_RE.split(form)
  joined, boundaries = _join_pieces(pieces)
  return joined, [b for b in boundaries if b]


def _build_ra_ngram_trie(split_votes, plain_counts):
  """Junction letter-context counts -> ``rAmAnujIya-ngram.trie``.

  For every internal junction of every corpus surface (up to
  ``_RA_NGRAM_MAX_K`` letters on each side, key ``left\\x1fright``) the
  counts ``(n_split, n_plain)`` are recorded: hyphenated occurrences vote
  split at their hyphens (and plain at the remaining junctions), plain
  occurrences vote plain everywhere.  The trie lets ``_ngram_refine``
  hyphenate unseen surfaces where the local convention is unambiguous.
  """
  tables = {}
  for joined_key, votes in split_votes.items():
    for form, n in votes.items():
      joined, pos = _form_positions(form)
      if joined != joined_key:
        continue
      posset = set(pos)
      L = len(joined)
      for p in range(1, L):
        _ngram_add(tables, joined, p, p in posset, n)
  for tok, n in plain_counts.items():
    for p in range(1, len(tok)):
      _ngram_add(tables, tok, p, False, n)
  entries = []
  for key, (ns, nn) in tables.items():
    entries.append((key, (min(ns, 0xFFFFFFFF), min(nn, 0xFFFFFFFF))))
  trie = marisa_trie.RecordTrie("II", entries)
  os.makedirs(C._DATA_DIR, exist_ok=True)
  tmp = C._RA_NGRAM_TRIE_PATH + ".tmp"
  trie.save(tmp)
  os.replace(tmp, C._RA_NGRAM_TRIE_PATH)
  return trie


def _bad_add(tables, lpiece, hk, cpos, weight):
  """Record negative evidence for a cut at ``cpos`` of HK surface ``hk``:
  the letter context around the cut plus the cut's left piece."""
  kmax = min(_RA_BADSPLITS_MAX_K, cpos, len(hk) - cpos)
  for k in range(2, kmax + 1):
    key = "%s\x1f%s" % (hk[cpos - k:cpos], hk[cpos:cpos + k])
    tables[key] = tables.get(key, 0) + weight


def _ra_to_hk(dev, smap):
  """Devanagari -> HK through the scheme map, None on failure."""
  try:
    hk = sanscript.transliterate(dev, scheme_map=smap)
  except Exception:
    return None
  return hk or None


def _cut_positions(hk_form):
  """(joined surface, cut positions) of an HK hyphenated form."""
  pos, acc = [], ""
  for ch in hk_form:
    if ch in " -":
      pos.append(len(acc))
    else:
      acc += ch
  return acc, pos


def _cut_pieces(hk_form):
  """Pieces + their end-position: ([(piece, cpos), ...], joined-surface)."""
  out, cur = [], ""
  for ch in hk_form:
    if ch in " -":
      out.append(cur)
      cur = ""
    else:
      cur += ch
  out.append(cur)
  pieces, cpos = [], 0
  for pc in out[:-1]:
    cpos += len(pc)
    pieces.append((pc, cpos))
  return pieces, "".join(out)


def _ra_badsplit_mine(tables, mine, split_votes, plain_counts, smap):
  """Record negative evidence from corpus-plain surfaces the analyzer cuts."""
  for tok, n in plain_counts.items():
    if tok in split_votes:
      continue  # the corpus splits this surface elsewhere
    hk = _ra_to_hk(tok, smap)
    if hk and len(hk) >= 3:
      mine(hk, min(n, 20))


def _ra_badsplit_mine_split(tables, mine, split_votes, smap):
  """Record negative evidence from cuts the corpus's own form lacks."""
  for tok, votes in split_votes.items():
    hk = _ra_to_hk(tok, smap)
    if not hk or len(hk) < 3:
      continue
    form = max(votes.items(), key=lambda kv: (kv[1], -len(kv[0])))[0]
    joined, dev_pos = _form_positions(form)
    if joined != tok:
      continue
    hk_pos = set()
    for p in dev_pos:
      pre_hk = _ra_to_hk(joined[:p], smap)
      if pre_hk is None:
        hk_pos = None
        break
      hk_pos.add(len(pre_hk))
    if hk_pos is not None:
      mine(hk, min(sum(votes.values()), 20), hk_pos)


def _build_ra_badsplits(split_votes, plain_counts, smap):
  """Negative split memory -> ``rAmAnujIya-badsplits.trie``.

  Runs the splitter itself (memo bypassed) over every corpus surface and
  records the junctions where it disagrees with the corpus:

  * a surface the corpus only ever writes plain - every junction the DP cut;
  * a surface the corpus hyphenates - the junctions the DP cut that the
    corpus form does not have.

  Keys are junction letter contexts of the analyzer's own cuts.  Weights are
  corpus occurrences (capped at 20).  ``_segment`` refuses a boundary whose
  longest attested negative context carries >= ``_RA_BADSPLITS_MIN`` evidence
  *and* where the corpus's own junction n-gram holds no split vote
  (``_junction_ngram_plain``); weaker evidence is only a cost
  (``_RA_BADSPLITS_UNIT`` per unit).  The cut's left piece must be
  corpus-unattested and short (``_RA_BADSPLITS_MAX_PIECE``).
  """
  tables = {}
  from . import segment as SG  # local: segment imports validate -> tries -> corpus_ra

  def mine(hk, weight, corpus_pos=()):
    try:
      out_hk = SG._hyphenate_hk_token(hk)
    except Exception:
      return
    if out_hk == hk:
      return
    pieces, joined = _cut_pieces(out_hk)
    if joined != hk:
      return  # transliteration drift: coordinates would not line up
    for pc, cpos in pieces:
      if cpos in corpus_pos:
        continue
      _bad_add(tables, pc, hk, cpos, weight)

  _ra_badsplit_mine(tables, mine, split_votes, plain_counts, smap)
  _ra_badsplit_mine_split(tables, mine, split_votes, smap)
  entries = [(key, (min(w, 0xFFFF),)) for key, w in tables.items()]
  trie = marisa_trie.RecordTrie("H", entries)
  os.makedirs(C._DATA_DIR, exist_ok=True)
  tmp = C._RA_BADSPLITS_TRIE_PATH + ".tmp"
  trie.save(tmp)
  os.replace(tmp, C._RA_BADSPLITS_TRIE_PATH)
  return trie

def _build_ra_trie(smap, base_layers):
  """Words + stems from the rAmAnujIya prastuti corpus -> ``rAmAnujIya.trie``.

  Stems are the mechanical light-stemmer truncations of attested words
  (longest sup/tiG ending, plus stem-final restorations) that are themselves
  known (in this corpus or in the base layers).  The corpus attestation memory
  (pieces + whole tokens, joined-lefts) lives separately in
  ``rAmAnujIya-attestations.trie``.
  """
  word_counts = {}
  for dev, n in _extract_ra_word_counts().items():
    try:
      hk = sanscript.transliterate(dev, scheme_map=smap)
    except Exception:
      continue
    if hk:
      word_counts[hk] = word_counts.get(hk, 0) + n

  def known(hk):
    return hk in word_counts or any(hk in layer for layer in base_layers)

  stem_counts = {}
  for hk, n in word_counts.items():
    for end in C._SUP_ENDINGS:
      if len(hk) <= len(end) + 1 or not hk.endswith(end):
        continue
      pre = hk[:-len(end)]
      for cand in (pre,) + tuple(pre + f for f in C._STEM_FINALS):
        if len(cand) >= 3 and known(cand):
          stem_counts[cand] = stem_counts.get(cand, 0) + n
      break
  for cand, n in stem_counts.items():
    if n > word_counts.get(cand, 0):
      word_counts[cand] = n

  rt = marisa_trie.RecordTrie(
      "H", [(w, (min(c, 65535),)) for w, c in word_counts.items()])
  os.makedirs(C._DATA_DIR, exist_ok=True)
  tmp = C._RA_TRIE_PATH + ".tmp"
  rt.save(tmp)
  os.replace(tmp, C._RA_TRIE_PATH)
  return rt


def _build_ra_attestations_trie(counts, plain_counts, split_votes, smap):
  """Corpus attestation memory -> ``rAmAnujIya-attestations.trie``.

  HK token -> bit flags: 1 = the corpus itself uses this token (as a hyphen
  piece or as a whole unhyphenated token); 2 = an e/o-final piece the corpus
  joins to a following member (``गणे-श्वरम्``, ``पङ्के-रुह``; implies bit 1).
  A halant-final piece taken from a dictionary entry or inferred stem
  (``सर्व्`` = √सर्व्, ``अपास्``, ``तसम्``) is vetoed unless flagged here -
  see ``_attested`` / ``_joined_left_attested``.
  """
  flags = {}
  for dev in set(counts) | set(plain_counts):
    try:
      hk = sanscript.transliterate(dev, scheme_map=smap)
    except Exception:
      continue
    if hk:
      flags[hk] = flags.get(hk, 0) | 1
  for forms in split_votes.values():
    for form in forms:
      for pc in [p for p in _SEP_SPLIT_RE.split(form) if p][:-1]:
        if not pc.endswith(("\u0947", "\u094b")):
          continue
        try:
          hk = sanscript.transliterate(pc, scheme_map=smap)
        except Exception:
          continue
        if hk:
          flags[hk] = flags.get(hk, 0) | 3
  entries = [(w, (min(c, 0xFFFF),)) for w, c in flags.items()]
  trie = marisa_trie.RecordTrie("H", entries)
  os.makedirs(C._DATA_DIR, exist_ok=True)
  tmp = C._RA_ATTESTATIONS_TRIE_PATH + ".tmp"
  trie.save(tmp)
  os.replace(tmp, C._RA_ATTESTATIONS_TRIE_PATH)
  return trie
