"""Shared constants and mutable state of the hyphenator package.

Paths, thresholds and the externalised tuning data (loaded lazily via
``_load_misc_data``); the trie globals live here so every submodule
can reach them through ``from . import constants as C``.
"""
import logging
import os

import regex
import tomllib


_DICT_TXT = "/home/vvasuki/gitland/indic-dict/dicts/stardict-sanskrit/wordlists/words_sa_dev.txt"


_DCS_BABYLON = ("/home/vvasuki/gitland/indic-dict/dicts/stardict-sanskrit-kAvya/"
                "dcs-frequency/dcs-frequency.babylon")


# vyAkaraNa category sources (indic-dict) used to split the stardict
# wordlist into padas / nominal-stems / verb-stems / avyayas.
_VYAKARANA_DIR = ("/home/vvasuki/gitland/indic-dict/dicts/"
                  "stardict-sanskrit-vyAkaraNa")


_SUBANTA_GLOB = os.path.join(_VYAKARANA_DIR, "subanta", "vidyut", "*",
                             "*.babylon")


_TINANTA_GLOB = os.path.join(_VYAKARANA_DIR, "tiNanta", "vidyut", "*",
                             "*.babylon")


_GANAPATHAH_PATH = os.path.join(_VYAKARANA_DIR, "aShTAdhyAyI", "gaNapAThaH",
                                "gaNapAThaH.babylon")


_AVYAYA_GANAS = ("स्वरादिः", "चादिः")


_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "vocabulary", "sanskrit")


_WORD_TRIE_PATHS = {
    "padas": os.path.join(_DATA_DIR, "padas.trie"),
    "nominal-stems": os.path.join(_DATA_DIR, "nominal-stems.trie"),
    "verb-stems": os.path.join(_DATA_DIR, "verb-stems.trie"),
    "avyayas": os.path.join(_DATA_DIR, "avyayas.trie"),
}


_DCS_TRIE_PATH = os.path.join(_DATA_DIR, "dcs-stems.trie")


_RA_TRIE_PATH = os.path.join(_DATA_DIR, "rAmAnujIya.trie")


_RA_FORMS_TRIE_PATH = os.path.join(_DATA_DIR, "rAmAnujIya-splits.trie")


_RA_NGRAM_TRIE_PATH = os.path.join(_DATA_DIR, "rAmAnujIya-ngram.trie")


_RA_ATTESTATIONS_TRIE_PATH = os.path.join(
    _DATA_DIR, "rAmAnujIya-attestations.trie")


_RA_BADSPLITS_TRIE_PATH = os.path.join(_DATA_DIR, "rAmAnujIya-badsplits.trie")


_RA_SEPS_TRIE_PATH = os.path.join(_DATA_DIR, "rAmAnujIya-seps.trie")


_RA_SOURCES_TOML = os.path.join(_DATA_DIR, "rAmAnujIya-sources.toml")


# Browser (Pyodide) distribution: package source, misc data and exported
# tries for https://…/lekhanam/hyphenator.  See export_browser_data().
_BROWSER_HYPHENATOR_DIR = (
    "/home/vvasuki/gitland/vishvAsa/sanskrit/content/lekhanam/hyphenator")


_RA_BOOST = 20


# Junction n-gram refinement: a boundary is hyphenated when the corpus's
# longest attested local letter context (up to _RA_NGRAM_MAX_K letters on
# each side) is split-dominant.  See ``_ngram_refine``.
_RA_NGRAM_MAX_K = 3


_RA_NGRAM_MIN_SPLITS = 1


_RA_NGRAM_MIN_SUPPORT = 3  # required when backing off to a shorter context


_RA_NGRAM_RATIO = 2  # splits >= ratio * plains



# Negative split memory (``_build_ra_badsplits``): junction letter contexts
# of splits the analyzer itself produced over surfaces the corpus never splits
# that way.  Longest attested context decides; >= _RA_BADSPLITS_MIN evidence
# vetoes a boundary, weaker evidence only costs _RA_BADSPLITS_UNIT per unit.
_RA_BADSPLITS_MAX_K = 3


_RA_BADSPLITS_MIN = 2


_RA_BADSPLITS_UNIT = 4


# The piece ending at a cut is only policed up to this length: beyond the
# scoring horizon a "piece" is just an unsplit sponge, not a shard to veto.
_RA_BADSPLITS_MAX_PIECE = 20



# Separator glyphs in prastuti-style text: '-' is a within-samAsa joint,
# '–' (spelled '--' in older corpus text; preferred over it) separates
# upapadas of a samAsa where the upapadas themselves are samAsas - long
# chains may write it with a space between the dashes ("भूत-- -जड"), and
# ' ' separates padas outright.
_SEP_SPLIT_RE = regex.compile(r"[-–—]+")


_SEP_CAPTURE_RE = regex.compile(r"([-–—]+)")


_RENDER_SPLIT_RE = regex.compile(r"([ \-–—])")


_SEP_GLYPHS = (" ", "-", "–", "—")


_MISC_DATA_TOML = os.path.join(_DATA_DIR, "misc_hyphenator_data.toml")


_MISC_VOCAB_TOML = os.path.join(_DATA_DIR, "misc-vocab.toml")


_SEED_COUNT = 3



# Externalised data: ``misc_hyphenator_data.toml`` (seed words, bare
# suffixes, sandhi keeps, weak rights, short pieces) and
# ``misc-vocab.toml`` (avyayas, upasargas, pronouns, next to the tries).
# Loaded lazily via ``_load_misc_data`` (see ``_load_words``).
_SEED_WORDS = ()


_BARE_SUFFIXES = frozenset()


_SANDHI_KEEP = frozenset()


_WEAK_RIGHTS = frozenset()


_SHORT_OK = frozenset()


_SUP_ENDINGS = ()


_STEM_FINALS = ()


_META_SUFFIXES = ()


_COMPOUND_SUFFIXES = ()


_AVYAYAS = frozenset()


_WEAK_RIGHTS_EXTRA = frozenset()


_PRONOUNS = frozenset()


_UPASARGAS = ()


_UPASARGA_HEADS = frozenset()


_MISC_LOADED = False


def _read_toml_file(path):
  try:
    with open(path, "rb") as f:
      return tomllib.load(f)
  except (OSError, tomllib.TOMLDecodeError):
    logging.warning("hyphenator: cannot read %s", path)
    return {}


def _load_misc_data():
  """Load misc_hyphenator_data.toml + misc-vocab.toml (idempotent)."""
  global _SEED_WORDS, _BARE_SUFFIXES, _SANDHI_KEEP, _WEAK_RIGHTS, _SHORT_OK, \
      _SUP_ENDINGS, _STEM_FINALS, _META_SUFFIXES, _COMPOUND_SUFFIXES, \
      _PRONOUNS, _UPASARGAS, _UPASARGA_HEADS, _WEAK_RIGHTS_EXTRA, _MISC_LOADED
  if _MISC_LOADED:
    return
  data = _read_toml_file(_MISC_DATA_TOML)
  vocab = _read_toml_file(_MISC_VOCAB_TOML)
  _SEED_WORDS = tuple(data.get("seed_words", ()))
  _BARE_SUFFIXES = frozenset(data.get("bare_suffixes", ()))
  _SANDHI_KEEP = frozenset(data.get("sandhi_keep", ()))
  _SHORT_OK = frozenset(data.get("short_ok", ()))
  _META_SUFFIXES = tuple(data.get("meta_suffixes", ()))
  _COMPOUND_SUFFIXES = tuple(data.get("compound_suffixes", ()))
  _SUP_ENDINGS = tuple(sorted(data.get("sup_endings", ()),
                              key=len, reverse=True))
  _STEM_FINALS = tuple(data.get("stem_finals", ()))
  _PRONOUNS = frozenset(vocab.get("pronouns", ()))
  _UPASARGAS = tuple(sorted(vocab.get("upasargas", ()), key=len, reverse=True))
  _UPASARGA_HEADS = frozenset(x[0] for x in _UPASARGAS)
  # _AVYAYAS comes from avyayas.trie (see _load_words); _WEAK_RIGHTS is
  # recomputed there once the avyaya set is known.
  _WEAK_RIGHTS_EXTRA = frozenset(data.get("weak_rights", ()))
  _WEAK_RIGHTS = _PRONOUNS | _WEAK_RIGHTS_EXTRA
  _MISC_LOADED = True


_TRIE_PADAS = None


_TRIE_NOMINAL_STEMS = None


_TRIE_VERB_STEMS = None


_TRIE_AVYAYAS = None


_TRIE_DCS = None


_TRIE_RA = None


_TRIE_RA_FORMS = None


_TRIE_RA_NGRAM = None


_TRIE_RA_ATTESTATIONS = None


_TRIE_BADSPLITS = None


_TRIE_SEPS = None


_WORD_TRIE_GLOBALS = {
    "padas": "_TRIE_PADAS",
    "nominal-stems": "_TRIE_NOMINAL_STEMS",
    "verb-stems": "_TRIE_VERB_STEMS",
    "avyayas": "_TRIE_AVYAYAS",
}


_LAYERED = None


_VOWELS = frozenset("aAiIuUeo")


_HIGH_KINDS = frozenset(["yan", "visarga-o", "visarga", "m-vowel",
                         "t-assim", "cons-vowel", "avagraha"])
