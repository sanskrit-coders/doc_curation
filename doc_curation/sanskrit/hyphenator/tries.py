"""tries - part of the hyphenator package (see __init__.py)."""
import bisect
import glob
import gzip
import math
import os
import shutil
import struct
import unicodedata

import regex
import tomllib
import marisa_trie
from indic_transliteration import sanscript
import logging

from . import constants as C
from .constants import (
    _RA_BOOST,
    _SEED_COUNT,
    _load_misc_data
)
from . import corpus_ra as RA
from . import segment as SG
from . import validate as V


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
  """Union view over the word tries: padas, nominal-stems, verb-stems,
  avyayas, dcs-stems and rAmAnujIya.

  Membership is the union of the layers.  ``count`` keeps the legacy
  reliability semantics (the best source count among the four word layers,
  raised by the DCS tier and by a strong boost for rAmAnujIya-attested
  words and stems).  ``layer_counts`` exposes the per-layer raw counts
  ``(padas, nominal-stems, verb-stems, avyayas, dcs-stems, rAmAnujIya)``
  for the graded, tiered frequency preference.
  """

  __slots__ = ("_layers",)

  def __init__(self, *layers):
    self._layers = layers

  def __contains__(self, word):
    return any(word in layer for layer in self._layers)

  def count(self, word):
    c = max(self._layers[i].count(word) for i in range(4))
    d = self._layers[4].count(word)
    if d:
      c = max(c, _dcs_tier(d))
    r = self._layers[5].count(word)
    if r:
      c = max(c, _RA_BOOST + r)
    return c

  def layer_counts(self, word):
    return tuple(layer.count(word) for layer in self._layers)

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
  if not os.path.exists(C._DCS_BABYLON):
    return {}
  try:
    with open(C._DCS_BABYLON, encoding="utf-8") as f:
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
  os.makedirs(C._DATA_DIR, exist_ok=True)
  tmp = C._DCS_TRIE_PATH + ".tmp"
  rt.save(tmp)
  os.replace(tmp, C._DCS_TRIE_PATH)
  return rt


def _babylon_head_lines(path):
  """Head (``|`` separated) lines of a stardict babylon file."""
  try:
    with open(path, encoding="utf-8") as f:
      text = f.read()
  except OSError:
    return
  for m in regex.finditer(r"(?:\A|\n\n)([^\n#][^\n]*)\n", text):
    yield m.group(1)


def _category_word_sets():
  """(avyaya, nominal-stem, verb-stem) devanagari sets from indic-dict.

  nominal stems come from the vidyut subanta tables (first column of each
  headword), verb stems/roots from the vidyut tiNanta tables (first two
  columns), avyayas from the svArAdi/cAdi gaNas of the aShTAdhyAyI
  gaNapAThaH.
  """
  avyaya, nominal, verb = set(), set(), set()
  for path in glob.glob(C._SUBANTA_GLOB):
    for head in _babylon_head_lines(path):
      first = head.split("|", 1)[0].strip()
      if first:
        nominal.add(first)
  for path in glob.glob(C._TINANTA_GLOB):
    for head in _babylon_head_lines(path):
      for field in head.split("|")[:2]:
        field = field.strip()
        if field:
          verb.add(field)
  try:
    with open(C._GANAPATHAH_PATH, encoding="utf-8") as f:
      text = f.read()
  except OSError:
    text = ""
  for gana in C._AVYAYA_GANAS:
    m = regex.search(r"^%s<BR>[^\n]*" % gana, text, regex.MULTILINE)
    if not m:
      continue
    for item in m.group(0).split("।"):
      item = item.strip().strip("*_()[]॥ ")
      if not item or " " in item or "<" in item:
        continue
      if any(ord(ch) < 0x900 or ord(ch) > 0x97F for ch in item):
        continue
      avyaya.add(item)
  # The DCS glossary marks indeclinables ("\u2026<BR>indeclinable ind<BR>\u2026");
  # a robust supplement to the gaNas (अपि etc. are not in svArAdi/cAdi).
  try:
    with open(C._DCS_BABYLON, encoding="utf-8") as f:
      dcs_text = f.read()
  except OSError:
    dcs_text = ""
  for entry in dcs_text.split("\n\n"):
    lines = entry.split("\n")
    if len(lines) >= 2 and "indeclinable ind" in "\n".join(lines[1:]):
      key = lines[0].strip()
      if key and all(0x900 <= ord(ch) <= 0x97F or ch in "-" for ch in key):
        avyaya.add(key)
  return avyaya, nominal, verb


def _word_sources_mtime():
  """Newest mtime among the wordlist and the vyAkaraNa category sources."""
  paths = []
  for path in (C._DICT_TXT, C._GANAPATHAH_PATH):
    if os.path.exists(path):
      paths.append(path)
  for pattern in (C._SUBANTA_GLOB, C._TINANTA_GLOB):
    paths.extend(glob.glob(pattern))
  return max([os.path.getmtime(p) for p in paths if os.path.exists(p)],
             default=0)


def _build_tries():
  """Build the four marisa word tries (padas / nominal-stems / verb-stems /
  avyayas) by partitioning the stardict wordlist with the vyAkaraNa category
  sources (seed words are categorised by membership too)."""
  smap = _get_scheme_map()
  avyaya_set, nominal_set, verb_set = _category_word_sets()
  buckets = {name: {} for name in C._WORD_TRIE_PATHS}
  try:
    with open(C._DICT_TXT, encoding="utf-8") as f:
      for line in f:
        line = line.strip()
        if not line:
          continue
        parts = line.split("\t")
        w = parts[0].strip()
        if not w or len(w) > 40:
          continue
        nsrc = len(parts[1].split(",")) if len(parts) > 1 and parts[1] else 1
        if w in avyaya_set:
          bucket = "avyayas"
        elif w in verb_set:
          bucket = "verb-stems"
        elif w in nominal_set:
          bucket = "nominal-stems"
        else:
          bucket = "padas"
        try:
          hk = sanscript.transliterate(w, scheme_map=smap)
        except Exception:
          continue
        if hk and nsrc > buckets[bucket].get(hk, 0):
          buckets[bucket][hk] = nsrc
  except FileNotFoundError:
    pass
  for w in C._SEED_WORDS:
    try:
      dev = sanscript.transliterate(w, sanscript.HK, sanscript.DEVANAGARI)
    except Exception:
      dev = ""
    if dev and dev in avyaya_set:
      bucket = "avyayas"
    elif dev and dev in verb_set:
      bucket = "verb-stems"
    elif dev and dev in nominal_set:
      bucket = "nominal-stems"
    else:
      bucket = "padas"
    buckets[bucket].setdefault(w, _SEED_COUNT)
  os.makedirs(C._DATA_DIR, exist_ok=True)
  tries = {}
  for name, path in C._WORD_TRIE_PATHS.items():
    rt = marisa_trie.RecordTrie(
        "H", [(w, (min(c, 65535),)) for w, c in buckets[name].items()])
    tmp = path + ".tmp"
    rt.save(tmp)
    os.replace(tmp, path)
    tries[name] = rt
  return tries


def _invalidate_trie_caches():
  from . import segment as SG, seps as SP, validate as V  # local: avoid cycles
  for c in (V._CACHE_CORE, V._CACHE_RELIABLE, V._CACHE_STEM, V._CACHE_STEM_PIECE,
            V._CACHE_STEM_BASE_PIECE, V._CACHE_YAN_LEFT, SG._CACHE_TOKEN,
            V._CACHE_VIS_RESTORE, V._CACHE_YAN_RESTORE, V._CACHE_WITNESS,
            _CACHE_RA_FORM, SG._CACHE_MEMO_PIECE, SG._CACHE_MEMO_SEPS,
            V._CACHE_RA_ATTESTED, V._CACHE_ELEFT, V._CACHE_DICT, SG._CACHE_BAD, SP._CACHE_SEP):
    c.clear()


def rebuild_word_tries():
  """Force-rebuild the four word tries (padas / nominal-stems / verb-stems /
  avyayas) from the stardict wordlist + vyAkaraNa categories (also done
  automatically when a source is stale)."""
  _load_misc_data()
  tries = _build_tries()
  for name, rt in tries.items():
    setattr(C, C._WORD_TRIE_GLOBALS[name], _WordTrie(rt))
  C._LAYERED = None
  _invalidate_trie_caches()
  return C._TRIE_PADAS


rebuild_word_trie = rebuild_word_tries


def rebuild_dcs_trie():
  """Force-rebuild ``data/vocabulary/sanskrit/dcs-frequency.trie`` from the
  DCS frequency babylon."""
  C._TRIE_DCS = _WordTrie(_build_dcs_trie(_get_scheme_map()))
  C._LAYERED = None
  _invalidate_trie_caches()
  return C._TRIE_DCS


def _export_hyp1(rt, kind, dest_path):
  """Write ``rt`` as the browser's HYP1 format (gzip-compressed).

  ``kind``: 0 = RecordTrie("H") (uint16 values), 1 = BytesTrie,
  2 = RecordTrie("II") (two uint32 values).  Keys are sorted: the browser
  shim binary-searches them.
  """
  keys = sorted(rt.iterkeys())
  n = len(keys)
  value_blob = bytearray()
  if kind == 0:
    for k in keys:
      value_blob += struct.pack("<H", rt.get(k)[0][0])
  elif kind == 2:
    for k in keys:
      a, b = rt.get(k)[0]
      value_blob += struct.pack("<II", a, b)
  else:
    for k in keys:
      v = rt.get(k)[0]
      value_blob += struct.pack("<I", len(v)) + v
  keys_blob = bytearray()
  ends = []
  for k in keys:
    keys_blob += k.encode("utf-8")
    ends.append(len(keys_blob))
  data = (b"HYP1" + bytes([kind]) + struct.pack("<I", n)
          + bytes(value_blob)
          + struct.pack("<%dI" % n, *ends)
          + bytes(keys_blob))
  tmp = dest_path + ".tmp"
  with open(tmp, "wb") as f:
    f.write(gzip.compress(data, compresslevel=9, mtime=0))
  os.replace(tmp, dest_path)


def export_browser_data(dest_dir=None):
  """Update the Pyodide browser distribution (package source + tries).

  Copies ``hyphenator/*.py`` and the misc TOMLs, then exports all tries as
  ``*.bin.gz`` (HYP1 format read by the page's ``marisa_trie`` shim).
  Returns the destination directory (or None when it does not exist).
  """
  dest_dir = dest_dir or C._BROWSER_HYPHENATOR_DIR
  if not os.path.isdir(dest_dir):
    logging.warning("hyphenator: browser dir missing: %s", dest_dir)
    return None
  _load_words()
  pkg_dir = os.path.dirname(os.path.abspath(__file__))
  dest_pkg = os.path.join(dest_dir, "hyphenator")
  os.makedirs(dest_pkg, exist_ok=True)
  for fn in sorted(os.listdir(pkg_dir)):
    if fn.endswith(".py"):
      shutil.copy2(os.path.join(pkg_dir, fn), os.path.join(dest_pkg, fn))
  for src in (C._MISC_DATA_TOML, C._MISC_VOCAB_TOML):
    if os.path.exists(src):
      shutil.copy2(src, os.path.join(dest_dir, os.path.basename(src)))

  def raw(t):
    return t._rt if isinstance(t, _WordTrie) else t

  exports = (
      ("padas.bin.gz", raw(C._TRIE_PADAS), 0),
      ("nominal-stems.bin.gz", raw(C._TRIE_NOMINAL_STEMS), 0),
      ("verb-stems.bin.gz", raw(C._TRIE_VERB_STEMS), 0),
      ("avyayas.bin.gz", raw(C._TRIE_AVYAYAS), 0),
      ("dcs-stems.bin.gz", raw(C._TRIE_DCS), 0),
      ("ramAnujIya.bin.gz", raw(C._TRIE_RA), 0),
      ("ramAnujIya-splits.bin.gz", raw(C._TRIE_RA_FORMS), 1),
      ("ramAnujIya-ngram.bin.gz", raw(C._TRIE_RA_NGRAM), 2),
      ("ramAnujIya-attestations.bin.gz",
       raw(C._TRIE_RA_ATTESTATIONS), 0),
      ("ramAnujIya-badsplits.bin.gz", raw(C._TRIE_BADSPLITS), 0),
      ("ramAnujIya-seps.bin.gz", raw(C._TRIE_SEPS), 2),
  )
  for name, rt, kind in exports:
    _export_hyp1(rt, kind, os.path.join(dest_dir, name))
  return dest_dir


def rebuild_ra_trie():
  """Force-rebuild the ``rAmAnujIya*`` tries from the sources declared in
  ``data/vocabulary/sanskrit/rAmAnujIya-sources.toml`` and refresh the
  browser distribution."""
  loaded = _load_words()
  layers = tuple(loaded._layers[:5])
  C._TRIE_RA = _WordTrie(RA._build_ra_trie(_get_scheme_map(), layers))
  counts, split_votes, plain_counts = RA._extract_ra_corpus()
  C._TRIE_RA_FORMS = RA._build_ra_forms_trie(split_votes, plain_counts)
  C._TRIE_RA_NGRAM = RA._build_ra_ngram_trie(split_votes, plain_counts)
  C._TRIE_RA_ATTESTATIONS = _WordTrie(RA._build_ra_attestations_trie(
      counts, plain_counts, split_votes, _get_scheme_map()))
  from . import seps as _seps  # local: seps imports tries (avoid the cycle)
  C._TRIE_SEPS = _seps._build_ra_seps_trie(split_votes, _get_scheme_map())
  export_browser_data()
  C._LAYERED = None
  _invalidate_trie_caches()
  return C._TRIE_RA


def _load_word_tries():
  """The four word tries (prebuilt when fresh, else rebuilt), plus the
  avyaya keys that form the closed class."""
  word_src = _word_sources_mtime()
  fresh = (all(os.path.exists(path) for path in C._WORD_TRIE_PATHS.values())
           and (not word_src or all(os.path.getmtime(path) >= word_src
                                    for path in C._WORD_TRIE_PATHS.values())))
  raw = {}
  if fresh:
    for name, path in C._WORD_TRIE_PATHS.items():
      rt = marisa_trie.RecordTrie("H")
      rt.load(path)
      raw[name] = rt
  else:
    raw = _build_tries()
  word_tries, av_keys = {}, []
  for name, rt in raw.items():
    word_tries[name] = _WordTrie(rt)
    if name == "avyayas":
      av_keys = list(rt.iterkeys())
  return word_tries, av_keys


def _load_dcs_trie(smap):
  if (os.path.exists(C._DCS_TRIE_PATH)
      and (not os.path.exists(C._DCS_BABYLON)
           or os.path.getmtime(C._DCS_TRIE_PATH)
           >= os.path.getmtime(C._DCS_BABYLON))):
    rt = marisa_trie.RecordTrie("H")
    rt.load(C._DCS_TRIE_PATH)
    return rt
  return _build_dcs_trie(smap)


def _ra_source_mtime():
  return max([os.path.getmtime(p) for p in RA._ra_source_files()
              if os.path.exists(p)]
             + ([os.path.getmtime(C._RA_SOURCES_TOML)]
                if os.path.exists(C._RA_SOURCES_TOML) else []),
             default=0)


def _load_ra_tries(smap, ra_mtime, word_tries, rt_dcs):
  """Load-or-build the rAmAnujIya* tries (words / forms / ngram /
  attestations / seps); badsplits stays None until mined once every layer
  is active."""
  from . import seps as _seps  # local: seps imports tries (avoid the cycle)
  out = {}
  if (os.path.exists(C._RA_TRIE_PATH)
      and os.path.getmtime(C._RA_TRIE_PATH) >= ra_mtime):
    out["ra"] = marisa_trie.RecordTrie("H")
    out["ra"].load(C._RA_TRIE_PATH)
  else:
    base_layers = tuple(word_tries.values()) + (_WordTrie(rt_dcs),)
    out["ra"] = RA._build_ra_trie(smap, base_layers)
  if (os.path.exists(C._RA_FORMS_TRIE_PATH)
      and os.path.getmtime(C._RA_FORMS_TRIE_PATH) >= ra_mtime):
    out["forms"] = marisa_trie.BytesTrie()
    out["forms"].load(C._RA_FORMS_TRIE_PATH)
  else:
    _, split_votes, plain_counts = RA._extract_ra_corpus()
    out["forms"] = RA._build_ra_forms_trie(split_votes, plain_counts)
  if (os.path.exists(C._RA_NGRAM_TRIE_PATH)
      and os.path.getmtime(C._RA_NGRAM_TRIE_PATH) >= ra_mtime):
    out["ngram"] = marisa_trie.RecordTrie("II")
    out["ngram"].load(C._RA_NGRAM_TRIE_PATH)
  else:
    _, split_votes, plain_counts = RA._extract_ra_corpus()
    out["ngram"] = RA._build_ra_ngram_trie(split_votes, plain_counts)
  if (os.path.exists(C._RA_ATTESTATIONS_TRIE_PATH)
      and os.path.getmtime(C._RA_ATTESTATIONS_TRIE_PATH) >= ra_mtime):
    out["attestations"] = marisa_trie.RecordTrie("H")
    out["attestations"].load(C._RA_ATTESTATIONS_TRIE_PATH)
  else:
    counts, split_votes, plain_counts = RA._extract_ra_corpus()
    out["attestations"] = RA._build_ra_attestations_trie(
        counts, plain_counts, split_votes, smap)
  if (os.path.exists(C._RA_BADSPLITS_TRIE_PATH)
      and os.path.getmtime(C._RA_BADSPLITS_TRIE_PATH) >= ra_mtime):
    out["badsplits"] = marisa_trie.RecordTrie("H")
    out["badsplits"].load(C._RA_BADSPLITS_TRIE_PATH)
  else:
    out["badsplits"] = None
  if (os.path.exists(C._RA_SEPS_TRIE_PATH)
      and os.path.getmtime(C._RA_SEPS_TRIE_PATH) >= ra_mtime):
    out["seps"] = marisa_trie.RecordTrie("II")
    out["seps"].load(C._RA_SEPS_TRIE_PATH)
  else:
    _, split_votes, _plain = RA._extract_ra_corpus()
    out["seps"] = _seps._build_ra_seps_trie(split_votes, smap)
  return out


def _load_words():
  """Load every evidence layer (idempotent; builds what is missing)."""
  _load_misc_data()
  if C._LAYERED is not None:
    return C._LAYERED
  smap = _get_scheme_map()
  word_tries, av_keys = _load_word_tries()
  # The avyaya closed class is the corpus wordlist's avyayas.trie itself.
  C._AVYAYAS = frozenset(av_keys)
  C._WEAK_RIGHTS = C._AVYAYAS | C._PRONOUNS | C._WEAK_RIGHTS_EXTRA
  rt_dcs = _load_dcs_trie(smap)
  rt = _load_ra_tries(smap, _ra_source_mtime(), word_tries, rt_dcs)
  C._TRIE_PADAS = word_tries["padas"]
  C._TRIE_NOMINAL_STEMS = word_tries["nominal-stems"]
  C._TRIE_VERB_STEMS = word_tries["verb-stems"]
  C._TRIE_AVYAYAS = word_tries["avyayas"]
  C._TRIE_DCS = _WordTrie(rt_dcs)
  C._TRIE_RA = _WordTrie(rt["ra"])
  C._TRIE_RA_FORMS = rt["forms"]
  C._TRIE_RA_NGRAM = rt["ngram"]
  C._TRIE_RA_ATTESTATIONS = _WordTrie(rt["attestations"])
  C._TRIE_BADSPLITS = rt["badsplits"]
  C._TRIE_SEPS = rt["seps"]
  C._LAYERED = _LayeredWords(C._TRIE_PADAS, C._TRIE_NOMINAL_STEMS,
                             C._TRIE_VERB_STEMS, C._TRIE_AVYAYAS,
                             C._TRIE_DCS, C._TRIE_RA)
  if C._TRIE_BADSPLITS is None:
    # Mine the negative splits only now that every layer is active - the
    # builder runs the splitter itself over the corpus (memo bypassed).
    _invalidate_trie_caches()
    _, split_votes, plain_counts = RA._extract_ra_corpus()
    C._TRIE_BADSPLITS = RA._build_ra_badsplits(split_votes, plain_counts, smap)
    _invalidate_trie_caches()
  return C._LAYERED

def _ra_split_form(dev_word):
  """Corpus memorised segmentation for ``dev_word``.

  Returns the memorised hyphenated form, ``""`` when the corpus attests the
  surface plainly (must stay unchanged) and ``None`` when unseen.
  """
  cached = _CACHE_RA_FORM.get(dev_word)
  if cached is not None:
    return cached
  _load_words()
  vals = C._TRIE_RA_FORMS.get(dev_word) if C._TRIE_RA_FORMS is not None else None
  form = None
  if vals:
    raw = vals[0]
    if not raw:
      form = ""
    else:
      text = raw.decode("utf-8")
      tilde = text.find("\t")
      form = text[tilde + 1:] if tilde >= 0 else text
  _CACHE_RA_FORM[dev_word] = form
  return form


def _ra_form_confidence(dev_word):
  """Per-mille frequency of the corpus's winning segmentation of a surface
  (None when unseen or unattested-plain)."""
  _load_words()
  vals = C._TRIE_RA_FORMS.get(dev_word) if C._TRIE_RA_FORMS is not None else None
  if not vals or not vals[0]:
    return None
  text = vals[0].decode("utf-8")
  tilde = text.find("\t")
  return int(text[:tilde]) if tilde >= 0 else None


_CACHE_RA_FORM = {}
