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

Fast: ~O(L^2) dict lookups per token with memoised validation.  Evidence is
layered as
``doc_curation/data/vocabulary/sanskrit/{rAmAnujIya,dcs-frequency,sanskrit-words}.trie``
(all marisa-tries built on first use, rebuilt when their sources change):

* ``rAmAnujIya.trie`` - words + stems harvested from the rAmAnujIya
  prastuti corpus (sources and ingestion rules recorded in
  ``data/vocabulary/sanskrit/rAmAnujIya-sources.toml``); scored
  highest;
* ``dcs-frequency.trie`` - DCS corpus frequencies from
  ``dcs-frequency.babylon``; scored next;
* ``sanskrit-words.trie`` - ``words_sa_dev.txt`` stardict headwords
  (~600k, ~2.5 MB);
* ``rAmAnujIya-splits.trie`` - the corpus's own segmentations (joined
  surface -> hyphenated form; empty = attestably unsplit).  Consulted
  first by ``hyphenate_word`` and reusable as whole DP pieces;
* ``rAmAnujIya-ngram.trie`` - junction letter-context counts from the same
  corpus (longest context decides; >=2:1 attested hyphenation).  On a memo
  miss it refines the DP result: adds corpus-attested hyphens
  (``आकाशादि-विशेष-शब्दैर्``) and prefers ``-`` over `` `` at joints the
  corpus hyphenates (``जगत्-कारणे``);
* ``rAmAnujIya-surfaces.trie`` - the corpus's hyphen pieces + plain tokens.
  A halant-final piece taken as a dictionary word or inferred stem
  (``सर्व्`` = √सर्व्, ``अपास्``, ``तसम्``) is vetoed unless the corpus
  itself uses that surface.

Already-hyphenated compounds are left untouched (pieces adjacent to ``-`` are
not re-processed), so running on pre-split प्रस्तुति-style text is safe.
"""

import bisect
import math
import os
import regex
import tomllib
import unicodedata
import marisa_trie
from indic_transliteration import sanscript
import logging

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


_DICT_TXT = "/home/vvasuki/gitland/indic-dict/dicts/stardict-sanskrit/wordlists/words_sa_dev.txt"
_DCS_BABYLON = ("/home/vvasuki/gitland/indic-dict/dicts/stardict-sanskrit-kAvya/"
                "dcs-frequency/dcs-frequency.babylon")
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "vocabulary", "sanskrit")
_TRIE_PATH = os.path.join(_DATA_DIR, "sanskrit-words.trie")
_DCS_TRIE_PATH = os.path.join(_DATA_DIR, "dcs-frequency.trie")
_RA_TRIE_PATH = os.path.join(_DATA_DIR, "rAmAnujIya.trie")
_RA_FORMS_TRIE_PATH = os.path.join(_DATA_DIR, "rAmAnujIya-splits.trie")
_RA_NGRAM_TRIE_PATH = os.path.join(_DATA_DIR, "rAmAnujIya-ngram.trie")
_RA_SURFACES_TRIE_PATH = os.path.join(_DATA_DIR, "rAmAnujIya-surfaces.trie")
_RA_SOURCES_TOML = os.path.join(_DATA_DIR, "rAmAnujIya-sources.toml")

_RA_BOOST = 20
# Junction n-gram refinement: a boundary is hyphenated when the corpus's
# longest attested local letter context (up to _RA_NGRAM_MAX_K letters on
# each side) is split-dominant.  See ``_ngram_refine``.
_RA_NGRAM_MAX_K = 3
_RA_NGRAM_MIN_SPLITS = 1
_RA_NGRAM_MIN_SUPPORT = 3  # required when backing off to a shorter context
_RA_NGRAM_RATIO = 2  # splits >= ratio * plains

_SEED_WORDS = (
    "ca", "vA", "hi", "tu", "api", "iti", "eva", "evam", "iva",
    "ati", "adhi", "anu", "upa", "pari", "prati", "sam", "vi",
    "na", "saH", "tat", "etat", "yat", "kim", "idam", "adas",
    "asmin", "tasmin", "yad", "tad", "etad", "sat", "asat",
    "asti", "santi", "bhavati", "gacCati", "ukta", "uktam",
    "dharma", "artha", "hetu", "brahma", "zabda", "Adi",
)
_SEED_COUNT = 3

_TRIE = None
_TRIE_DCS = None
_TRIE_RA = None
_TRIE_RA_FORMS = None
_TRIE_RA_NGRAM = None
_TRIE_RA_SURFACES = None
_LAYERED = None


class _WordTrie:
  """Word -> source-count map backed by a compact marisa RecordTrie.

  Supports ``word in trie`` (membership), ``trie.count(word)`` (frequency
  proxy used by the reliability guards) and ``trie.has_prefix(s)`` (compound
  detection in separator choice).
  """

  __slots__ = ("_rt", "_counts", "_prefixes")

  def __init__(self, rt):
    self._rt = rt
    self._counts = {}
    self._prefixes = {}

  def __contains__(self, word):
    return word in self._rt

  def count(self, word):
    c = self._counts.get(word)
    if c is None:
      rec = self._rt.get(word)
      c = rec[0][0] if rec else 0
      self._counts[word] = c
    return c

  def has_prefix(self, prefix):
    hit = self._prefixes.get(prefix)
    if hit is None:
      hit = False
      for _ in self._rt.iterkeys(prefix):
        hit = True
        break
      self._prefixes[prefix] = hit
    return hit


class _LayeredWords:
  """Union view over the stardict / DCS / rAmAnujIya word tries.

  Membership is the union of the layers.  ``count`` keeps the legacy
  reliability semantics (stardict source count, raised by the DCS tier and
  by a strong boost for rAmAnujIya-attested words and stems).
  ``layer_counts`` exposes the per-layer raw counts for the graded,
  tiered (rAmAnujIya > DCS > stardict) frequency preference.
  """

  __slots__ = ("_layers",)

  def __init__(self, words, dcs, ra):
    self._layers = (words, dcs, ra)

  def __contains__(self, word):
    return any(word in layer for layer in self._layers)

  def count(self, word):
    c = self._layers[0].count(word)
    d = self._layers[1].count(word)
    if d:
      c = max(c, _dcs_tier(d))
    r = self._layers[2].count(word)
    if r:
      c = max(c, _RA_BOOST + r)
    return c

  def layer_counts(self, word):
    return (self._layers[0].count(word), self._layers[1].count(word),
            self._layers[2].count(word))

  def has_prefix(self, prefix):
    return any(layer.has_prefix(prefix) for layer in self._layers)


def _get_scheme_map():
  return sanscript.SchemeMap(sanscript.SCHEMES[sanscript.DEVANAGARI],
                             sanscript.SCHEMES[sanscript.HK])


def _dcs_tier(total):
  """Map DCS corpus frequency to the same scale as stardict source counts."""
  if total >= 500:
    return 21
  if total >= 100:
    return 11
  if total >= 30:
    return 7
  if total >= 10:
    return 5
  if total >= 3:
    return 3
  if total >= 2:
    return 2
  return 1


def _dcs_label_is_vedic(label):
  """Whether a DCS source label names Vedic (brAhmaNa/upaniSad/mantra era)
  literature.  Classical sources (mahAbhArata, purANa, kAvya, Ayurveda,
  tAntra, ...) are of course never Vedic here."""
  if label in _DCS_VEDIC_LABELS:
    return True
  return label.endswith(_DCS_VEDIC_SUFFIXES)


_DCS_VEDIC_LABELS = frozenset([
    "Brahmana", "Upanishad", "Mantra", "Dharmasutra", "Grhyasutra",
    "Nirukta", "गोपथब्राह्मण", "शतपथब्राह्मण", "ऋग्वेदवेदाङ्गज्योतिष",
    "निरुक्त", "लगध", "सायणमाधवाचार्य", "कौशिकसूत्र",
    "कौशिकसूत्रदारिलभाष्य",
])
_DCS_VEDIC_SUFFIXES = ("ब्राह्मण", "उपनिषद्", "उपनिषत्", "धर्मसूत्र",
                       "गृह्यसूत्र")


def _parse_dcs(smap):
  """Headword -> total corpus frequency from the DCS frequency babylon.

  Vedic-only headwords are excluded: forms attested exclusively in the
  brAhmaNa/upaniSad/mantra layer (e.g. the aorists ``अदधि``, ``अध्याभू``)
  are not admissible evidence for classical-sanskrit split decisions.
  """
  if not os.path.exists(_DCS_BABYLON):
    return {}
  try:
    with open(_DCS_BABYLON, encoding="utf-8") as f:
      text = f.read()
  except OSError:
    return {}
  totals = {}
  for block in regex.split(r"\n\s*\n", text):
    block = block.strip()
    if not block or block.startswith("#"):
      continue
    head = block.split("\n", 1)[0].strip()
    if not head or " " in head or "\t" in head or len(head) > 40:
      continue
    if any(ch < "\u0900" or ch > "\u097f" for ch in head):
      continue
    m = regex.search(r"Total:\s*(\d+)", block)
    if not m:
      continue
    labels = [l.strip() for l in
              regex.findall(r"([^\n<>\-]+?)\s*-\s*\d+<BR>",
                            block.replace("<BR><BR>", "\n")) if l.strip()]
    if labels and not any(not _dcs_label_is_vedic(l) for l in labels):
      continue
    try:
      hk = sanscript.transliterate(head, scheme_map=smap)
    except Exception:
      continue
    if hk:
      totals[hk] = totals.get(hk, 0) + int(m.group(1))
  return totals


def _build_dcs_trie(smap):
  """Save DCS headword -> corpus total as ``dcs-frequency.trie``."""
  counts = {w: min(t, 65535) for w, t in _parse_dcs(smap).items()}
  rt = marisa_trie.RecordTrie("H", [(w, (c,)) for w, c in counts.items()])
  os.makedirs(_DATA_DIR, exist_ok=True)
  tmp = _DCS_TRIE_PATH + ".tmp"
  rt.save(tmp)
  os.replace(tmp, _DCS_TRIE_PATH)
  return rt


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
    with open(_RA_SOURCES_TOML, "rb") as f:
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
      body = _ANNO_RE.sub(" ", body)
      body = regex.sub(r"<[^>]*>", " ", body)
      # line-seam "- -" (pada boundary): treat as a plain joint so that the
      # joined surface of the whole chain is recorded.
      body = regex.sub(r"[-–—]\s+[-–—]", "-", body)
      # "X-+V" editor junctions over a merged mUla: merge final a/ā with
      # the following independent vowel (…अनुरूप-+एक… = …अनुरूपैक…).
      body = regex.sub(
          r"(?<=[\u0915-\u0939\u093e])[-–—]\s*\+([\u0905-\u0914])",
          _merge_editor_junction, body)
      # other "+" junctions (e.g. after virama) are non-sandhi seams whose
      # merged form is unknown: drop the token.
      body = regex.sub(r"[-–—]\s*\+", "@", body)
      for raw in body.split():
        tok = raw.strip(_RA_EDGE)
        if not tok or _RA_ANNOT_RE.search(tok) or _RA_BAD_RE.search(tok):
          continue
        pieces = tok.split("-")
        if len(pieces) > 1:
          joined = ""
          for p in pieces:
            if joined.endswith("\u094d") and p[:1] in _VOWEL_TO_MATRA:
              joined = joined[:-1] + _VOWEL_TO_MATRA[p[:1]] + p[1:]
            else:
              joined += p
          votes = split_votes.setdefault(joined, {})
          votes[tok] = votes.get(tok, 0) + 1
        else:
          plain_counts[tok] = plain_counts.get(tok, 0) + 1
        for p in pieces:
          if p:
            counts[p] = counts.get(p, 0) + 1
  return counts, split_votes, plain_counts


# independent vowels -> mAtra (for rejoining prastuti pieces into the
# plain sandhi-merged surface).
_VOWEL_TO_MATRA = {
    "\u0905": "", "\u0906": "\u093e", "\u0907": "\u093f", "\u0908": "\u0940",
    "\u0909": "\u0941", "\u090a": "\u0942", "\u090b": "\u0943",
    "\u090f": "\u0947", "\u0910": "\u0948", "\u0913": "\u094b",
    "\u0914": "\u094c",
}


def _merge_editor_junction(m):
  """guNa/vRddhi merge of a final a/ā with an editor-marked independent vowel."""
  return {
      "अ": "\u093e", "आ": "\u093e", "इ": "\u0947", "ई": "\u0947",
      "उ": "\u094b", "ऊ": "\u094b", "ऋ": "\u0943", "ए": "\u0948",
      "ऐ": "\u0948", "ओ": "\u094c", "औ": "\u094c",
  }.get(m.group(1), "\u093e")


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
    entries.append((joined, form.encode("utf-8")))
  for tok in set(plain_counts) - set(split_votes):
    if plain_counts[tok] >= 3:
      entries.append((tok, b""))
  trie = marisa_trie.BytesTrie(entries)
  os.makedirs(_DATA_DIR, exist_ok=True)
  tmp = _RA_FORMS_TRIE_PATH + ".tmp"
  trie.save(tmp)
  os.replace(tmp, _RA_FORMS_TRIE_PATH)
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

  Uses the extractor's own reassembly (``_VOWEL_TO_MATRA``: a piece-final
  virama + next-piece independent vowel merge into the plain surface), so the
  positions are expressed in the joined surface's own coordinates.  A
  boundary absorbed by such a merge has no surface position and is dropped.
  """
  pieces = form.split("-")
  joined = ""
  pos = []
  for i, p in enumerate(pieces):
    if joined.endswith("\u094d") and p[:1] in _VOWEL_TO_MATRA:
      if pos:
        pos[-1] = None
      joined = joined[:-1] + _VOWEL_TO_MATRA[p[:1]] + p[1:]
    else:
      joined += p
    if i < len(pieces) - 1:
      pos.append(len(joined))
  return joined, [p for p in pos if p]


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
  os.makedirs(_DATA_DIR, exist_ok=True)
  tmp = _RA_NGRAM_TRIE_PATH + ".tmp"
  trie.save(tmp)
  os.replace(tmp, _RA_NGRAM_TRIE_PATH)
  return trie


def _build_ra_surfaces_trie(counts, plain_counts, smap):
  """Corpus surface tokens (hyphen pieces + unhyphenated tokens) -> trie.

  The prastuti convention's own vocabulary of *surfaces*: this is what may
  be carved as a halant-final piece (``तद्``, ``जगत्``, ``फलम्``,
  ``शब्दैर्``).  Dictionary root entries (``सर्व्``), exotic headwords
  (``अपास्``) and stem inferences (``तसम्``) that never surface in the
  corpus as such are vetoed instead.
  """
  merged = {}
  for table in (counts, plain_counts):
    for dev, n in table.items():
      merged[dev] = merged.get(dev, 0) + n
  entries = []
  for dev, n in merged.items():
    try:
      hk = sanscript.transliterate(dev, scheme_map=smap)
    except Exception:
      continue
    if hk:
      entries.append((hk, (min(n, 0xFFFF),)))
  trie = marisa_trie.RecordTrie("H", entries)
  os.makedirs(_DATA_DIR, exist_ok=True)
  tmp = _RA_SURFACES_TRIE_PATH + ".tmp"
  trie.save(tmp)
  os.replace(tmp, _RA_SURFACES_TRIE_PATH)
  return trie


def _build_ra_trie(smap, base_layers):
  """Words + stems from the rAmAnujIya prastuti corpus -> ``rAmAnujIya.trie``.

  Stems are the mechanical light-stemmer truncations of attested words
  (longest sup/tiG ending, plus stem-final restorations) that are themselves
  known (in this corpus or in the base layers).
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
    for end in _SUP_ENDINGS:
      if len(hk) <= len(end) + 1 or not hk.endswith(end):
        continue
      pre = hk[:-len(end)]
      for cand in (pre,) + tuple(pre + f for f in _STEM_FINALS):
        if len(cand) >= 3 and known(cand):
          stem_counts[cand] = stem_counts.get(cand, 0) + n
      break
  for cand, n in stem_counts.items():
    if n > word_counts.get(cand, 0):
      word_counts[cand] = n

  rt = marisa_trie.RecordTrie(
      "H", [(w, (min(c, 65535),)) for w, c in word_counts.items()])
  os.makedirs(_DATA_DIR, exist_ok=True)
  tmp = _RA_TRIE_PATH + ".tmp"
  rt.save(tmp)
  os.replace(tmp, _RA_TRIE_PATH)
  return rt


def _build_trie():
  """Build the marisa word trie from the stardict wordlist + DCS frequency
  babylon + seed words."""
  smap = _get_scheme_map()
  counts = {}
  try:
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
        if hk and nsrc > counts.get(hk, 0):
          counts[hk] = nsrc
  except FileNotFoundError:
    pass
  for hk, total in _parse_dcs(smap).items():
    tier = _dcs_tier(total)
    if tier > counts.get(hk, 0):
      counts[hk] = tier
  for w in _SEED_WORDS:
    counts.setdefault(w, _SEED_COUNT)
  rt = marisa_trie.RecordTrie(
      "H", [(w, (min(c, 65535),)) for w, c in counts.items()])
  os.makedirs(_DATA_DIR, exist_ok=True)
  tmp = _TRIE_PATH + ".tmp"
  rt.save(tmp)
  os.replace(tmp, _TRIE_PATH)
  return rt


def _invalidate_trie_caches():
  for c in (_CACHE_CORE, _CACHE_RELIABLE, _CACHE_STEM, _CACHE_STEM_PIECE,
            _CACHE_STEM_BASE_PIECE, _CACHE_YAN_LEFT, _CACHE_TOKEN,
            _CACHE_VIS_RESTORE, _CACHE_YAN_RESTORE, _CACHE_WITNESS,
            _CACHE_RA_FORM, _CACHE_MEMO_PIECE, _CACHE_MEMO_SEPS,
            _CACHE_SURFACE):
    c.clear()


def rebuild_word_trie():
  """Force-rebuild ``data/vocabulary/sanskrit/sanskrit-words.trie`` from the
  stardict wordlist (also done automatically when the trie is stale)."""
  global _TRIE, _LAYERED
  _TRIE = _WordTrie(_build_trie())
  _LAYERED = None
  _invalidate_trie_caches()
  return _TRIE


def rebuild_dcs_trie():
  """Force-rebuild ``data/vocabulary/sanskrit/dcs-frequency.trie`` from the
  DCS frequency babylon."""
  global _TRIE_DCS, _LAYERED
  _TRIE_DCS = _WordTrie(_build_dcs_trie(_get_scheme_map()))
  _LAYERED = None
  _invalidate_trie_caches()
  return _TRIE_DCS


def rebuild_ra_trie():
  """Force-rebuild the ``rAmAnujIya*`` tries from the sources declared in
  ``data/vocabulary/sanskrit/rAmAnujIya-sources.toml``."""
  global _TRIE_RA, _TRIE_RA_FORMS, _TRIE_RA_NGRAM, _TRIE_RA_SURFACES, _LAYERED
  _load_words()
  layers = (_TRIE, _TRIE_DCS)
  _TRIE_RA = _WordTrie(_build_ra_trie(_get_scheme_map(), layers))
  counts, split_votes, plain_counts = _extract_ra_corpus()
  _TRIE_RA_FORMS = _build_ra_forms_trie(split_votes, plain_counts)
  _TRIE_RA_NGRAM = _build_ra_ngram_trie(split_votes, plain_counts)
  _TRIE_RA_SURFACES = _build_ra_surfaces_trie(counts, plain_counts,
                                              _get_scheme_map())
  _LAYERED = None
  _invalidate_trie_caches()
  return _TRIE_RA


def _load_words():
  global _TRIE, _TRIE_DCS, _TRIE_RA, _TRIE_RA_FORMS, _TRIE_RA_NGRAM, \
      _TRIE_RA_SURFACES, _LAYERED
  if _LAYERED is not None:
    return _LAYERED
  smap = _get_scheme_map()
  if (os.path.exists(_TRIE_PATH) and os.path.exists(_DICT_TXT)
      and os.path.getmtime(_TRIE_PATH) >= os.path.getmtime(_DICT_TXT)):
    rt_words = marisa_trie.RecordTrie("H")
    rt_words.load(_TRIE_PATH)
  else:
    rt_words = _build_trie()
  if (os.path.exists(_DCS_TRIE_PATH) and os.path.exists(_DCS_BABYLON)
      and os.path.getmtime(_DCS_TRIE_PATH) >= os.path.getmtime(_DCS_BABYLON)):
    rt_dcs = marisa_trie.RecordTrie("H")
    rt_dcs.load(_DCS_TRIE_PATH)
  else:
    rt_dcs = _build_dcs_trie(smap)
  ra_mtime = max([os.path.getmtime(p) for p in _ra_source_files()
                  if os.path.exists(p)]
                 + ([os.path.getmtime(_RA_SOURCES_TOML)]
                    if os.path.exists(_RA_SOURCES_TOML) else []),
                 default=0)
  if (os.path.exists(_RA_TRIE_PATH)
      and os.path.getmtime(_RA_TRIE_PATH) >= ra_mtime):
    rt_ra = marisa_trie.RecordTrie("H")
    rt_ra.load(_RA_TRIE_PATH)
  else:
    rt_ra = _build_ra_trie(smap, (_WordTrie(rt_words), _WordTrie(rt_dcs)))
  if (os.path.exists(_RA_FORMS_TRIE_PATH)
      and os.path.getmtime(_RA_FORMS_TRIE_PATH) >= ra_mtime):
    rt_forms = marisa_trie.BytesTrie()
    rt_forms.load(_RA_FORMS_TRIE_PATH)
  else:
    _, split_votes, plain_counts = _extract_ra_corpus()
    rt_forms = _build_ra_forms_trie(split_votes, plain_counts)
  if (os.path.exists(_RA_NGRAM_TRIE_PATH)
      and os.path.getmtime(_RA_NGRAM_TRIE_PATH) >= ra_mtime):
    rt_ngram = marisa_trie.RecordTrie("II")
    rt_ngram.load(_RA_NGRAM_TRIE_PATH)
  else:
    _, split_votes, plain_counts = _extract_ra_corpus()
    rt_ngram = _build_ra_ngram_trie(split_votes, plain_counts)
  if (os.path.exists(_RA_SURFACES_TRIE_PATH)
      and os.path.getmtime(_RA_SURFACES_TRIE_PATH) >= ra_mtime):
    rt_surfaces = marisa_trie.RecordTrie("H")
    rt_surfaces.load(_RA_SURFACES_TRIE_PATH)
  else:
    counts, _, plain_counts = _extract_ra_corpus()
    rt_surfaces = _build_ra_surfaces_trie(counts, plain_counts, smap)
  _TRIE = _WordTrie(rt_words)
  _TRIE_DCS = _WordTrie(rt_dcs)
  _TRIE_RA = _WordTrie(rt_ra)
  _TRIE_RA_FORMS = rt_forms
  _TRIE_RA_NGRAM = rt_ngram
  _TRIE_RA_SURFACES = rt_surfaces
  _LAYERED = _LayeredWords(_TRIE, _TRIE_DCS, _TRIE_RA)
  return _LAYERED


def _ra_split_form(dev_word):
  """Corpus memorised segmentation for ``dev_word``.

  Returns the memorised hyphenated form, ``""`` when the corpus attests the
  surface plainly (must stay unchanged) and ``None`` when unseen.
  """
  cached = _CACHE_RA_FORM.get(dev_word)
  if cached is not None:
    return cached
  _load_words()
  vals = _TRIE_RA_FORMS.get(dev_word) if _TRIE_RA_FORMS is not None else None
  form = vals[0].decode("utf-8") if vals else None
  _CACHE_RA_FORM[dev_word] = form
  return form


def _count_of(hk):
  return _load_words().count(hk)


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


def _surface_attested(hk_piece):
  """Corpus (hyphen pieces + plain tokens) attests this exact surface."""
  _load_words()
  trie = _TRIE_RA_SURFACES
  if trie is None:
    return True  # no corpus data loaded: do not veto
  hit = _CACHE_SURFACE.get(hk_piece)
  if hit is None:
    hit = hk_piece in trie
    _CACHE_SURFACE[hk_piece] = hit
  return hit


def _prefix_in_dict(s):
  if not s:
    return False
  return _load_words().has_prefix(s)


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
_SHORT_OK = frozenset(["ca", "vA", "hi", "tu", "na", "te", "me", "oM", "jA", "a"])

# sup/tiG endings used by the light stemmer (longest first).
_SUP_ENDINGS = tuple(sorted([
    "ByAm", "ByaH", "bhyAm", "bhyah", "BhiH", "ezu", "nAm", "sya",
    "yoH", "oH", "eH", "EH", "AnAm", "Ani", "Ini", "Uni",
    "Aya", "Ayai", "AyAH", "yAH",
    "At", "Ad", "aH", "AH", "An", "Am", "e", "O", "ena", "enA",
    "inA", "unA", "AyA", "ayA",     "aye", "ave", "asya",
    # tiG endings (verbs)
    "ante", "anti", "ate", "nte", "nti", "te", "ti", "It", "us", "uH",
    "tum", "tvA", "sya", "vat", "vatI", "vAn", "mAn", "mat",
    "M", "m", "H", "n", "t", "d", "s", "r",
], key=len, reverse=True))

_STEM_FINALS = ("a", "A", "i", "I", "u", "U", "f", "t", "d", "n", "s", "as")

# pure endings that must never appear as standalone split pieces
_BARE_SUFFIXES = frozenset([
    "sya", "ByAm", "ByaH", "bhyaH", "Byah", "bhyAm", "bhyah", "BhiH", "ezu", "zu",
    "nAm", "yoH", "oH", "eH", "EH", "Aya", "Ayai", "AyAH", "aiH", "auH",
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
  hit = _CACHE_STEM.get(hk)
  if hit is not None:
    return hit
  res = _stem_valid_uncached(hk)
  _CACHE_STEM[hk] = res
  return res


def _stem_valid_uncached(hk):
  words = _load_words()
  for end in _SUP_ENDINGS:
    if not hk.endswith(end):
      continue
    if len(hk) <= len(end) + 1:
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
  words = _load_words()
  for end in _SUP_ENDINGS:
    if not hk.endswith(end):
      continue
    if not _piece_ending_ok(hk, end):
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
  hit = _CACHE_STEM_BASE_PIECE.get(hk)
  if hit is not None:
    return hit or None
  res = _stem_base_piece_uncached(hk)
  _CACHE_STEM_BASE_PIECE[hk] = res or ""
  return res


def _stem_base_piece_uncached(hk):
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
_CACHE_STEM_PIECE = {}
_CACHE_STEM_BASE_PIECE = {}
_CACHE_YAN_LEFT = {}
_CACHE_TOKEN = {}
_CACHE_VIS_RESTORE = {}
_CACHE_YAN_RESTORE = {}
_CACHE_WITNESS = {}
_CACHE_RA_FORM = {}
_CACHE_MEMO_PIECE = {}
_CACHE_MEMO_SEPS = {}
_CACHE_SURFACE = {}


def _memo_form_seps(form):
  """(pieces, seps) of a memoised hyphenated form.

  The granularity is the corpus's; separators are re-derived with ``_sep``
  so that pada boundaries come out as spaces (the prastuti sometimes writes
  them with ``-``).
  """
  cached = _CACHE_MEMO_SEPS.get(form)
  if cached is not None:
    return cached
  pieces = [p for p in regex.split(r"[- ]+", form) if p]
  hks = []
  for p in pieces:
    try:
      hks.append(sanscript.transliterate(p, sanscript.DEVANAGARI, sanscript.HK))
    except Exception:
      hks.append("")
  seps = [_sep(a, b, a, b) for a, b in zip(hks, hks[1:])]
  res = (pieces, seps)
  _CACHE_MEMO_SEPS[form] = res
  return res


def _memo_piece_split(hk_piece):
  """Corpus-subdivision of an HK piece, as (hk_parts, seps) or None.

  Lets the DP treat a whole memorised compound (whose internal samAsa
  joints are not sandhi-witnessed) as a single "memo" piece and expand it
  back into the corpus's own sub-segmentation at assembly time.
  """
  hit = _CACHE_MEMO_PIECE.get(hk_piece)
  if hit is not None:
    return hit or None
  res = ()
  try:
    dev = sanscript.transliterate(hk_piece, sanscript.HK, sanscript.DEVANAGARI)
  except Exception:
    dev = None
  if dev:
    form = _ra_split_form(dev)
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
  _CACHE_MEMO_PIECE[hk_piece] = res
  return res or None


def _core_valid(hk_piece, piece_mode=False):
  """Core validation (no upasarga strip, no length guard)."""
  words = _load_words()
  if hk_piece in words:
    if (piece_mode and len(hk_piece) <= 4 and hk_piece[-1] in ("M", "m")
        and hk_piece not in _PRONOUNS and hk_piece not in _AVYAYAS
        and hk_piece not in _UPASARGAS):
      # inflected shards like naM/vaM are not usable as split pieces
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
      if piece_mode and merger_chain_valid(cand):
        return ("yan", cand)
  if len(hk_piece) >= 3 and hk_piece.endswith("v"):
    for v in ("u", "U"):
      cand = hk_piece[:-1] + v
      if cand in words:
        return ("yan", cand)
      if piece_mode and merger_chain_valid(cand):
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
  if len(hk_piece) >= 4 and hk_piece.endswith("M"):
    # anusvAra surface of an m-final form (etaM <- etam); short shards like
    # naM/vaM stay excluded by the length guard
    cand = hk_piece[:-1] + "m"
    if cand in words:
      return ("stem", cand)
  if piece_mode:
    if _stem_valid_piece(hk_piece):
      return ("stem", hk_piece)
    if merger_chain_valid(hk_piece):
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
  elif c in ("l", "T"):
    # tad + l/T assimilation surface (talliGga, taTTIkA): de-assimilates to tad
    res = (lhk[:-1] + "d") in words or (lhk[:-1] + "t") in words
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
    if hk.endswith("H") and hk[:-1] in _load_words() and _count_of(hk[:-1]) >= _STEM_BASE_MIN:
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
  for cand in _restores_of(hk):
    if _count_of(cand) >= _RELIABLE_MIN:
      if depth == 2:
        _CACHE_RELIABLE[hk] = True
      return True
    if _stem_valid_piece(cand):
      base = _stem_base_piece(cand)
      if base and _count_of(base) >= _STEM_BASE_MIN:
        return True
  if _stem_valid_piece(hk):
    base = _stem_base_piece(hk)
    if base and _count_of(base) >= _STEM_BASE_MIN:
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
  if kind == "merger":
    return True
  if kind == "yan" and under and merger_chain_valid(under):
    return True
  if (kind == "stem" and piece.endswith("M") and under
      and _count_of(under) >= _RELIABLE_MIN):
    return True
  if kind in ("visarga", "visarga-o") and under and under not in _load_words():
    base = _stem_base_piece(under)
    if not base or len(base) < 4:
      return False  # yadAs->yadAH: restore leans on a tiny closed-class base
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
  key = (hk_full, cpos)
  hit = _CACHE_VETO.get(key)
  if hit is not None:
    return hit
  res = _is_veto_split_uncached(hk_full, cpos)
  _CACHE_VETO[key] = res
  return res


def _veto_side_ok(s):
  """A veto witness word may be exact or a light inflection of a common one."""
  if s in _load_words():
    return True
  if _stem_valid_piece(s):
    base = _stem_base_piece(s)
    return bool(base) and _count_of(base) >= _STEM_BASE_MIN
  return False


def _is_veto_split_uncached(hk_full, cpos):
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
      if (left_pre + lv) in words and _veto_side_ok(rv + right_rest):
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
      if not right_rest:
        continue  # bare final vowel is never a merger partner
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
        if lu in words and ru in words:
          if yan_left and _count_of(yan_left) > _count_of(lu):
            continue
          if _count_of(lu) >= 5 and _count_of(ru) >= 5:
            return True
  return False


_MERGER_MIN = 6
_CACHE_CHAIN = {}


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


def _chain_word_ok(s):
  """Merger-chain component: a well-attested word, never a closed-class or
  suffix shard.  Short components need proportionally more attestation
  (ape/Iti/naM do not qualify, eka/Adi do)."""
  n = len(s)
  if n < 3 or s in _BARE_SUFFIXES or s in _AVYAYAS or s.lower() in _UPASARGAS:
    return False
  if s in _PRONOUNS and n < 4:
    return False
  cnt = _count_of(s)
  if n == 3:
    return cnt >= 20
  return cnt >= _MERGER_MIN


def _chain_end_ok(base, apo):
  """Final chain component: strict for merger chains; after an avagraha
  joint a restorable consonant-final word (abhivadan = abhi + vadan) is
  accepted too."""
  if _chain_word_ok(base):
    return True
  if not apo:
    return False
  n = len(base)
  if (n < 4 or base in _BARE_SUFFIXES or base in _AVYAYAS
      or base in _PRONOUNS or base.lower() in _UPASARGAS):
    return False
  if base[-1] in _VOWELS or base[-1] in ("H", "o"):
    return False
  return _reliable(base)


def _merger_chain_uncached(hk):
  n = len(hk)
  if n < 4:
    return False
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
        if 1 <= junc <= 3 and _chain_end_ok(base, apo):
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
                and "ai" not in hk[q:r] and "au" not in hk[q:r]):
            stack.append((r + mlen, rv2, 1, 1, junc + 1, apo2))
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
  if lc in "kgcjTDtdpbNnl":
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
  if k == "yan" and merger_chain_valid(lu):
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


_MAX_UNITS = 200
_QUALITY = {
    "exact": 30, "yan": 22, "visarga-o": 22, "visarga": 22,
    "avagraha": 22, "t-assim": 22, "merger": 24, "stem": 8, "upasarga": 6,
    "memo": 30,
}


def _freq_quality(word):
  """Graded frequency preference, tiered rAmAnujIya > DCS-frequency >
  stardict wordlist.  Log-scaled and capped so that kind choices and
  length still dominate.  Higher evidence -> cheaper piece."""
  if not word:
    return 0
  w, d, r = _load_words().layer_counts(word)
  if r:
    return min(14 + int(3 * math.log2(r + 1)), 21)
  if d:
    return min(6 + int(3 * math.log2(d + 1)), 21)
  return min(int(3 * math.log2(w + 1)), 21)


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
      # Never keep the whole token as a single piece (both modes): a valid
      # whole token would take the strict path; in non-strict mode a lone
      # whole-piece path would shadow real splits and return None.
      if i == 0 and j == m:
        continue
      piece = "".join(units[i:j])
      if len(piece) < 3 and piece not in _SHORT_OK:
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
      if piece in _BARE_SUFFIXES and (i > 0 or j < m):
        continue
      kind, under = _valid_piece_kind(piece, piece_mode=True)
      if kind is None:
        if _memo_piece_split(piece) is None:
          continue
        kind, under = "memo", piece
      if kind == "stem":
        base = _stem_base_piece(piece)
        if base:
          under = base
      if kind != "memo" and not _piece_reliable(piece, kind, under):
        continue
      # An internal halant-final piece (dictionary "exact" or inferred
      # "stem") must be a surface the corpus itself uses: root entries
      # (सर्व् = √सर्व्), exotic headwords (अपास्) and stem husks (तसम्)
      # are impossible padas.  Restore-based kinds (visarga/yan/...,
      # दुष्प्रकृतेर् -> दुष्प्रकृतेः) keep their own witnesses.
      if (j < m and kind in ("exact", "stem") and _halant_final(piece)
          and not _surface_attested(piece)):
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
        if kind not in ("exact", "stem", "avagraha", "merger", "visarga", "yan", "memo"):
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
          if strict:
            continue
          if lkind not in ("exact", "stem", "merger"):
            continue
          if kind not in ("exact", "stem", "merger", "visarga", "yan", "memo"):
            continue
        elif bkind == "m-vowel":
          pass
        elif bkind in ("visarga", "visarga-o"):
          if kind == "merger":
            # merged units (asyaiva) never begin at a visarga joint
            continue
          if lkind not in ("visarga", "visarga-o", "memo") and not _has_visarga_restore(lhk):
            continue
          if strict and lkind == "exact" and not lhk.endswith("s"):
            continue
          if strict and lkind in ("visarga", "visarga-o"):
            # weak H-restores (duSprakRter->duSprakRtiH) are still fine when
            # the restored form leans on a frequent stem.
            lu = info[i][1]
            if _count_of(lu) < 3:
              base = _stem_base_piece(lu)
              if not base or _count_of(base) < _STEM_BASE_MIN:
                continue
          # H -> r only before vowels; s/z/S before vowels is not a sandhi.
          if rhk[:1] in _VOWELS and not lhk.endswith("r"):
            continue
        elif bkind == "yan":
          if lkind not in ("yan", "memo") and not _has_yan_restore(lhk):
            continue
          if strict and lkind == "yan" and _count_of(info[i][1]) < 5:
            continue
          if strict and (under in _WEAK_RIGHTS or piece in _WEAK_RIGHTS):
            # iti + evam/atra style quotative collocations always split
            lu = info[i][1]
            if not (lkind in ("yan", "exact") and lu in ("iti", "ity")):
              continue
          whole_cnt = _count_of(hk)
          if hk.endswith(("M", "m", "H")):
            whole_cnt = max(whole_cnt, _count_of(hk[:-1]))
          if (strict and whole_cnt >= 8
              and under not in _WEAK_RIGHTS and piece not in _WEAK_RIGHTS):
            # heavily lexicalised whole words (sarvajJa, pratyakSa) stay
            # joined unless cut before a recognised compound suffix
            if not (under or piece).startswith(_COMPOUND_SUFFIXES):
              continue
        elif bkind in ("t-assim", "cons-vowel"):
          if lkind != "memo" and not _left_final_witness(lhk):
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
      if kind == "stem" and under:
        q += min(_count_of(under), 20)  # frequent base -> plausible inflected form
      q += max(_freq_quality(under), _freq_quality(piece))
      extra = 0
      if piece in _PRONOUNS or piece in _AVYAYAS:
        extra -= 4  # independent particles/pronouns favour a clean cut
      if i > 0:
        if bkind in _HIGH_KINDS:
          extra -= 10  # bonus for genuine sandhi boundary
        if bkind == "m-vowel":
          extra -= 6  # M + vowel is a high-precision split
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
  # Expand "memo" pieces into the corpus's own sub-segmentation.
  if "memo" in kinds:
    out_pieces, out_seps = [], []
    for k, pc in enumerate(pieces):
      if k > 0:
        out_seps.append(seps[k - 1])
      if kinds[k] == "memo":
        mparts, mseps = _memo_piece_split(pc)
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


# consonant+virama followed by an independent vowel: an explicit non-sandhi
# joint (prastuti writes यद्-अनुगुणा for yad + anuguNA).
_DEV_DISJ_RE = regex.compile(r"(?<=[\u0915-\u0939]\u094d)(?=[\u0905-\u0914])")


def _ngram_cell(wleft, wright):
  """Longest *attested* junction context: ``((ns, nn), k, kmax)`` or None.

  ``wleft``/``wright`` are the surface letters adjacent to the junction (the
  caller passes at most ``_RA_NGRAM_MAX_K`` each side).  The longest context
  present in the trie decides - an attested negative context (e.g.
  ``कान|विध`` against the tempting ``ान|वि``) blocks the shorter, noisier
  context.  ``k < kmax`` marks a backoff to a shorter context.
  """
  _load_words()
  trie = _TRIE_RA_NGRAM
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
  to ``ग्रहीतव्यः``).
  """
  hit = _ngram_cell(wleft, wright)
  if hit is None:
    return False
  (ns, nn), k, kmax = hit
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
  if _TRIE_RA_NGRAM is None:
    _load_words()
    if _TRIE_RA_NGRAM is None:
      return out
  if len(word) < 4:
    return out
  if out.replace("-", "").replace(" ", "") != word:
    # The DP re-expanded a sandhi joint (tadvad eva for tadvadeva): the two
    # outputs live in different coordinate systems - leave it alone.
    return out
  if has_global_merger(hk):
    # Non-separable merger chains (svaprakAzAdvitIya) are absolute-veto
    # tokens: never touch them, even at non-merger junctions.
    return out
  cuts = {}
  pos = 0
  for ch in out:
    if ch in ("-", " "):
      cuts[pos] = ch
    else:
      pos += 1
  K = _RA_NGRAM_MAX_K
  changed = False
  for p in range(1, len(word)):
    if unicodedata.category(word[p]) in ("Mn", "Mc"):
      continue  # a cut may not precede a dependent sign (mAtrA/virama)
    sep = cuts.get(p)
    if sep == "-":
      continue
    wleft, wright = word[max(0, p - K):p], word[p:p + K]
    if not _ngram_votes_hyphen(wleft, wright):
      continue
    try:
      pre = sanscript.transliterate(word[:p], sanscript.DEVANAGARI,
                                    sanscript.HK)
    except Exception:
      continue
    if not pre or not hk.startswith(pre):
      continue
    if is_veto_split(hk, len(pre)):
      continue
    cuts[p] = "-"
    if sep != "-":
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
  memo = _ra_split_form(word)
  if memo is not None:
    if not memo:
      return word
    mp, ms = _memo_form_seps(memo)
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
    parts = regex.split(r"([ \-])", hyph_hk)
    out_parts = []
    for pt in parts:
      if pt in (" ", "-") or pt == "":
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
  _load_words()
  anno_spans = [(m.start(), m.end()) for m in _ANNO_RE.finditer(text)]
  anno_starts = [s for s, _ in anno_spans]

  def _in_anno(pos):
    i = bisect.bisect_right(anno_starts, pos) - 1
    return i >= 0 and pos < anno_spans[i][1]

  def _repl(m):
    w = m.group(0)
    # Tokens touching a hyphen are part of an already-split compound: leave
    # them alone (this also makes hyphene idempotent).
    if text[m.start() - 1:m.start()] == "-" or text[m.end():m.end() + 1] == "-":
      return w
    if _in_anno(m.start()):
      return w
    return hyphenate_word(w)

  return _WORD_RE.sub(_repl, text)


# Aliases (the prompt spells it ``hyphene``; accept common variants).
hyphen = hyphene
hyphenate = hyphene
hyphenate_text = hyphene


if __name__ == '__main__':
  pass
  logging.info(hyphene("नामानि कृत्वाऽभिवदन्यदास्ते (तै.य.आर.३.१२), वेदाहमेतं पुरुषं महान्तम्।"))