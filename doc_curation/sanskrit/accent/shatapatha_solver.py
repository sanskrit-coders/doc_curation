"""Deterministic Śatapatha Brāhmaṇa (Mādhyandina) Padapāṭha + US-Accent Solver.

Provides four reusable layers for scaling US-accent conversion and
``पद-पाठः (यान्त्रिकः)`` generation across the Mādhyandina Śatapatha Brāhmaṇa:

1. :class:`UnifiedVedicLexicon` — aggregates attested US-accented forms,
   canonical padapāṭha hyphenations, and stem accents from ``VS``, ``TS``,
   ``RV``, ``AV``, ``TB``, ``TA``, ``MW``, ``Macdonell``, ``Lanman``, and
   ``Whitney``, persisted in a fast-reload pickle cache (``<0.5s``) and
   paired with ``vidyut.kosha`` + ``doc_curation.sanskrit.hyphenator.lexicon``.
2. Sandhi-preserving clean ``विश्वास-प्रस्तुतिः`` builder and Vedic
   sandhi-inverting padapāṭha splitter that ALWAYS separates upasargas from
   finite ``तिङन्त`` verbs (in both main and subordinate clauses) while
   keeping ``गतिकृदन्त`` compounds hyphenated as single padas.
3. Exact 3-state Viterbi ŚB accent decoder scoring predicted Weber
   (``H``/``G``/``""``) and Śrīdharādi (``H``/``""``) pitch-drop marks
   across syllables and cross-pada ``पा॰ ८.२.४–६`` sandhi mergers, with
   ambiguity/consecutive-udātta masking detection.
4. Self-certifying batch classifier (``AUTO_CLEAN`` vs ``NEEDS_ADJUDICATION``)
   and compact JSONL adjudication queue exporter.
"""

from __future__ import annotations

import dataclasses
import difflib
import functools
import glob
import json
import math
import os
import pickle
import re
import unicodedata
from collections import defaultdict
from typing import Iterable, Sequence

from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.accent.reconciler import (
  DETAILS_RE,
  PadapathaItem,
  US_SVARITA,
  US_UDATTA,
  _PIECE_PAT,
  _STOP_NORM,
  _VOWEL_FAMILY,
  _extract_vp_pieces,
  _flatten_pp_syllables,
  _map_pp_to_vp_syllables,
  _merged_valid_marks,
  _no_punct_between,
  _pp_member_starts,
  _skip_elided_avagraha_lead,
  apply_marks_to_token,
  bare_devanagari,
  has_us_accents,
  is_solid_provenance,
  reconcile_markdown_blocks,
  syllables_with_marks,
)
from doc_curation.sanskrit.accent.sandhi_check import (
  SLP_VOWELS,
  canonical_geminates,
  sandhi_step,
  to_norm_slp,
  verify_mantra_sandhi,
  word_to_slp_options,
)
from doc_curation.sanskrit.accent.shatapatha import (
  SB_END_DROP,
  SB_UDATTA_DROP,
  WEBER_SVARITA_ANTE,
  SbAuditReport,
  SbSyllable,
  _PAUSES,
  _YOGAVAAHAS,
  _align_key_sequences,
  audit_padapatha_against_sb,
  build_sb_vp_from_padapatha,
  extract_sb_syllables,
  format_padapatha_block,
  normalize_sb_orthography,
  strip_shri_pratika,
  strip_weber_footnotes,
  us_marks_to_sb_marks,
)
from doc_curation.sanskrit.accent.validator import (
  SIMPLEX_TINANTA_ALLOWLIST,
  validate_accented_markdown,
)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

# Increment cache version so v6 exact deduplicated per-corpus counts + persisted `_slp_stems` rebuild cleanly.
LEXICON_CACHE_VERSION = 6

DEFAULT_CACHE_PATH = (
  "/home/vvasuki/.gemini/antigravity-cli/brain/"
  "a1bfd549-5617-4f61-ae6b-a2769ed28079/scratch/unified_vedic_lexicon.pkl"
)
DEFAULT_DICT_ROOT = os.path.expanduser("~/gitland/sanskrit/raw_etexts/koshaH/indic-dict")
DEFAULT_VS_DIR = (
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/"
  "vAjasaneyam/mAdhyandinam/saMhitA/sarva-prastutiH"
)
DEFAULT_TB_DIR = (
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/"
  "taittirIyam/sArasvata-vibhAgaH/brAhmaNam/sarva-prastutiH"
)
DEFAULT_TA_DIR = (
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/"
  "taittirIyam/sArasvata-vibhAgaH/AraNyakam/sarva-prastutiH"
)
DEFAULT_VIDYUT_KOSHA = (
  "/home/vvasuki/gitland/ambuda-org/vidyut/vidyut-data/data/build/vidyut-latest/kosha"
)

SCHEME = sanscript.SCHEMES[sanscript.DEVANAGARI]

# Canonical upasargas (SLP1 -> Devanagari, and Devanagari -> accented US form)
UPASARGA_SLP_TO_DEVA: dict[str, str] = {
  "pra": "प्र",
  "parA": "परा",
  "apa": "अप",
  "sam": "सम्",
  "anu": "अनु",
  "ava": "अव",
  "nis": "निः",
  "nir": "निः",
  "niH": "निः",
  "dus": "दुः",
  "dur": "दुः",
  "duH": "दुः",
  "vi": "वि",
  "A": "आ",
  "AN": "आ",
  "ni": "नि",
  "aDi": "अधि",
  "api": "अपि",
  "ati": "अति",
  "su": "सु",
  "ut": "उत्",
  "ud": "उत्",
  "aBi": "अभि",
  "prati": "प्रति",
  "pari": "परि",
  "upa": "उप",
}

UPASARGA_ACCENT_MARKS: dict[str, tuple[str, ...]] = {
  "प्र": ("U",),
  "परा": ("", "U"),
  "अप": ("U", ""),
  "सम्": ("U",),
  "सं": ("U",),
  "अनु": ("U", ""),
  "अव": ("U", ""),
  "निः": ("U",),
  "निस्": ("U",),
  "निर्": ("U",),
  "दुः": ("U",),
  "दुस्": ("U",),
  "दुर्": ("U",),
  "वि": ("U",),
  "आ": ("U",),
  "नि": ("U",),
  "अधि": ("U", ""),
  "अपि": ("U", ""),
  "अति": ("U", ""),
  "सु": ("U",),
  "उत्": ("U",),
  "उद्": ("U",),
  "अभि": ("", "U"),
  "प्रति": ("U", ""),
  "परि": ("U", ""),
  "उप": ("U", ""),
}

UPASARGA_DEVA_SET: frozenset[str] = frozenset(UPASARGA_ACCENT_MARKS.keys())

# Always-unaccented enclitics (पा॰ ८.१.१८)
ALWAYS_ANUDATTA_ENCLITICS: frozenset[str] = frozenset({
  "च", "मे", "त्वा", "नः", "वः", "ह", "स्म", "उ", "इव", "चन", "चित्", "स्वित्", "अह", "ह्यः",
})
# Note: अह (particle 'indeed' in ŚB `तद् अह`, `एतद् अह` is enclitic? No, remove ह्यः; keep exact enclitics!)
ALWAYS_ANUDATTA_ENCLITICS = frozenset({
  "च", "मे", "त्वा", "नः", "वः", "ह", "स्म", "उ", "इव", "चन", "चित्",
})

# Homophones that can be EITHER enclitic anudātta (पा॰ ८.१.१८) OR accented
AMBIGUOUS_ENCLITICS: dict[str, tuple[tuple[str, ...], str]] = {
  "वा": (("U",), "*RV*, *TS*, *AV*"),       # enclitic 'or' (वा) vs prevocalic वै᳓ (handled separately)
  "ते": (("U",), "*RV*, *TS*, *AV*"),       # enclitic 'to thee' vs nom.pl. 'they' (ते᳓)
  "मा": (("U",), "*RV*, *TS*, *AV*"),       # enclitic 'me' vs prohibitive 'not' (मा᳓)
  "वाम्": (("U",), "*RV*, *TS*, *AV*"),     # enclitic 'you two' vs accented
  "नौ": (("U",), "*RV*, *TS*, *AV*"),       # enclitic 'us two' vs accented
  "त्वाम्": (("U",), "*RV*, *TS*, *AV*"),
}

# Anvādeśa pronouns:
# - पा॰ २.४.३२ इदमोऽन्वादेशेऽशनुदात्तस्तृतीयादौ applies strictly to oblique `इदम्` (NOT `एतद्` nom/acc!)
# - पा॰ २.४.३४ द्वितीयाटौस्स्वेनः applies to `एनादेश` (`एनम्`, `एनाम्`, `एनत्`, ...)
ANVADESHA_2432: frozenset[str] = frozenset({
  "अस्य", "अस्मै", "अस्मात्", "अस्मिन्", "अस्याः", "अस्यै", "अस्याम्",
  "अनेन", "अनया", "अयोः", "अनयोः", "आभ्याम्", "एभिः", "एभ्यः", "एषाम्", "एषु",
  "आभिः", "आभ्यः", "आसाम्", "आसु",
})
ANVADESHA_2434: frozenset[str] = frozenset({
  "एनम्", "एनाम्", "एनत्", "एनौ", "एने", "एनान्", "एनाः", "एनानि", "एनेन", "एनया", "एनयोः",
})

# Subordinate clause triggers
YAD_VRTTA_TRIGGERS: frozenset[str] = frozenset({
  "यः", "या", "यत्", "यद्", "यम्", "याम्", "येन", "यया", "यस्मै", "यस्यै",
  "यस्मात्", "यस्याः", "यस्य", "यस्मिन्", "यस्याम्", "यौ", "ये", "याः", "यान्",
  "यानि", "यैः", "याभिः", "येभिः", "याभ्याम्", "येभ्यः", "याभ्यः", "येषाम्",
  "यासाम्", "येषु", "यासु", "ययोः", "यत्र", "यदा", "यथा", "यावत्", "यतः",
  "यर्हि", "यथैव", "यथावित्", "यादृशः", "यादृशम्",
})
NIPATA_8130_TRIGGERS: frozenset[str] = frozenset({"यदि", "नेत्", "चेत्", "कुवित्", "हन्त", "कच्चित्"})
HI_8134_TRIGGERS: frozenset[str] = frozenset({"हि"})

CORRELATIVE_STOPS: frozenset[str] = frozenset({
  "तत्", "तद्", "सः", "स", "सा", "ते", "ताः", "तानि", "तत्र", "तदा", "तथा",
  "तस्मात्", "तेन", "तम्", "ताम्", "तस्मिन्", "तस्य", "तस्मै", "तान्", "ताभिः",
  "तैः", "ततः", "अथ", "अथो", "तर्हि", "तावत्", "एवम्",
})

DUAL_ACCENT_STEMS: tuple[str, ...] = (
  "बृहस्पति", "बृहस्पत", "ब्रह्मणस्पति", "ब्रह्मणस्पत", "वाचस्पति", "वाचस्पत",
  "शचीपति", "शचीपत", "वनस्पति", "वनस्पत", "सदसस्पति", "जगतस्पति", "रायस्पोष",
  "नराशंस", "तनूनपात्", "द्यावा", "मित्रावरुण", "इन्द्रावरुण", "इन्द्राग्नी",
  "इन्द्राविष्णू", "इन्द्राबृहस्पती", "इन्द्रासोमा", "अग्नीषोम", "सोमारुद्र",
  "अहोरात्र", "परिधातवै",
)

# High-frequency ŚB function words (always valid standalone padas in DP splitter)
SB_FUNCTION_WORDS_SLP: frozenset[str] = frozenset({
  "saH", "sA", "tat", "tam", "tAm", "tena", "tayA", "tasmE", "tasyE", "tasmAt",
  "tasyAH", "tasya", "tasmin", "tasyAm", "tO", "te", "tAH", "tAn", "tAni",
  "tEH", "tABiH", "teByaH", "tAByaH", "tezAm", "tAsAm", "tezu", "tAsu", "tayoH",
  "yaH", "yA", "yat", "yam", "yAm", "yena", "yayA", "yasmE", "yasyE", "yasmAt",
  "yasyAH", "yasya", "yasmin", "yasyAm", "yO", "ye", "yAH", "yAn", "yAni",
  "yEH", "yABiH", "yeByaH", "yAByaH", "yezAm", "yAsAm", "yezu", "yAsu", "yayoH",
  "ezaH", "ezA", "etat", "etam", "etAm", "etena", "etayA", "etasmE", "etasmAt",
  "etasya", "etasmin", "etO", "ete", "etAH", "etAn", "etAni", "etEH", "etABiH",
  "eteByaH", "etezAm", "etezu", "etayoH",
  "ayam", "iyam", "idam", "imam", "imAm", "anena", "anayA", "asmE", "asyE",
  "asmAt", "asyAH", "asya", "asmin", "asyAm", "imO", "ime", "imAH", "imAn",
  "imAni", "eBiH", "ABiH", "eByaH", "AByaH", "ezAm", "AsAm", "ezu", "Asu",
  "enam", "enAm", "enat", "enO", "ene", "enAn", "enAH", "enAni", "enena", "enayA",
  "aham", "mAm", "mA", "mayA", "mahyam", "me", "mat", "mama", "mayi", "vayam",
  "asmAn", "naH", "asmABiH", "asmaByam", "asmAkam", "asmAsu",
  "tvam", "tvAm", "tvA", "tvayA", "tuByam", "te", "tvat", "tava", "tvayi",
  "yUyam", "yuzmAn", "vaH", "yuzmABiH", "yuzmaByam", "yuzmAkam",
  "kaH", "kA", "kim", "kam", "kAm", "kena", "kayA", "kasmE", "kasmAt", "kasya",
  "kasmin", "kO", "ke", "kAH", "kAn", "kAni",
  "ca", "vA", "vE", "hi", "u", "ha", "sma", "eva", "iva", "iti", "aTa", "aTo",
  "na", "nu", "tu", "net", "cet", "Kalu", "api", "atra", "tatra", "yatra",
  "taTA", "yaTA", "yadi", "yadA", "tadA", "tataH", "ataH", "evam", "punaH",
  "prAtaH", "antaH", "aDaH", "aDastAt", "upari", "uparizwAt", "paScAt", "purastAt",
  "pUrvam", "pUrvaH", "uttaram", "uttareRa", "dakziRena", "antareRa", "svayam",
  "sarvam", "sarve", "sarvAH", "sarvARi", "sarvasya", "anyaH", "anyat", "anyam",
  "ekaH", "ekam", "ekA", "dvO", "dve", "trayaH", "trIRi", "catvAraH", "paYca",
  "zaw", "sapta", "azwO", "nava", "daSa", "SataM", "Satam", "sahasram",
  "pra", "parA", "apa", "sam", "anu", "ava", "niH", "duH", "vi", "A", "ni",
  "aDi", "ati", "su", "ut", "aBi", "prati", "pari", "upa",
})

# Pronouns/particles/negations that MUST NEVER be clubbed as a single compound pada
NEVER_COMPOUND_LEFT_SLP: frozenset[str] = frozenset({
  "na", "mA", "ca", "vA", "vE", "hi", "u", "ha", "sma", "eva", "iva", "iti",
  "aTa", "aTo", "nu", "tu", "net", "cet", "Kalu", "api", "yadi", "yadA",
  "tadA", "yatra", "tatra", "atra", "yaTA", "taTA", "evam", "tasmAt", "tataH",
  "ataH", "me", "te", "tvA", "naH", "vaH", "enam", "enAm", "enat", "asya",
  "asmE", "asmin", "saH", "sA", "tat", "tam", "tAm", "tena", "tasmE", "tasya",
  "tasmin", "tAn", "tAH", "yaH", "yA", "yat", "yam", "yAm", "yena", "yasmE",
  "yasya", "yasmin", "yAn", "yAH", "ezaH", "ezA", "etat", "etam", "etena",
  "ayam", "iyam", "idam", "aham", "tvam", "kaH", "kim",
})

_PARASAVARNA_RE = re.compile(
  r"ङ्(?=[कखगघ])|ञ्(?=[चछजझ])|ण्(?=[टठडढ])|न्(?=[तथदध])|म्(?=[पफबभ])"
)
_DEVANAGARI_RE = re.compile(r"[\u0905-\u0939]")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PadaCandidate:
  """One grammatically valid US-accented candidate for a single padapāṭha word."""

  ref: str
  marks: tuple[str, ...]
  prov: str
  role: str
  solid: bool
  prior_cost: float
  is_vyat: bool = False
  ar: str = ""


@dataclasses.dataclass(frozen=True)
class KandikaCluster:
  """One kaṇḍikā unit extracted from a Śatapatha Brāhmaṇa Markdown file."""

  heading: str
  sub_idx: int
  vp_summary: str
  vp_body: str
  is_already_us: bool
  weber: str
  shri: str
  visvara: str
  sayana: str = ""
  harisvami: str = ""
  eggeling: str = ""

  @property
  def key(self) -> str:
    return self.heading if self.sub_idx == 0 else f"{self.heading}#{self.sub_idx}"


@dataclasses.dataclass
class SolveResult:
  """Complete output of solving and self-certifying one ŚB kaṇḍikā."""

  kandika_id: str
  heading: str
  sub_idx: int
  status: str  # 'AUTO_CLEAN' | 'NEEDS_ADJUDICATION' | 'SKIPPED'
  vp_clean: str
  vp_summary: str
  vp_accented: str
  items: list[PadapathaItem]
  padapatha_block: str
  preserve_vp: bool
  reasons: list[str]
  audit: SbAuditReport | None = None
  ambiguous_padas: list[dict] = dataclasses.field(default_factory=list)
  validation_issues: list[str] = dataclasses.field(default_factory=list)
  reconciler_logs: list[str] = dataclasses.field(default_factory=list)
  sandhi_ok: tuple[bool, bool, bool] = (False, False, False)
  unmapped: list[tuple[str, int]] = dataclasses.field(default_factory=list)
  lexicon_hits: list[str] = dataclasses.field(default_factory=list)
  disagree_details: list[dict] = dataclasses.field(default_factory=list)


# ---------------------------------------------------------------------------
# Accent conversion helpers (classical padapāṭha & IAST -> US)
# ---------------------------------------------------------------------------


_ALL_ACCENT_MARKS_RE = re.compile(r"[\u0951-\u0957\u1cd0-\u1cff]")


_DEVA_IND_TO_MATRA: dict[str, str] = {
  "अ": "", "आ": "ा", "इ": "ि", "ई": "ी", "उ": "ु", "ऊ": "ू",
  "ऋ": "ृ", "ॠ": "ॄ", "ऌ": "ॢ", "ॡ": "ॣ", "ए": "े", "ऐ": "ै", "ओ": "ो", "औ": "ौ",
}
_VIRAMA_VOWEL_RE = re.compile(r"्([अआइईउऊऋॠऌॡएऐओऔ])")


def _join_virama_vowels(text: str) -> str:
  """Rejoin ``् + independent_vowel`` created when removing a compound hyphen (e.g. ``अन्-अशन`` -> ``अनशन``)."""
  return _VIRAMA_VOWEL_RE.sub(lambda m: _DEVA_IND_TO_MATRA[m.group(1)], text)


def _normalize_lookup_key(word_deva: str) -> str:
  """Canonicalize a bare Devanagari pada for dictionary lookup (keeps `-म्`/`-ः`, normalizes `ँ`/parasavarṇa)."""
  w = _ALL_ACCENT_MARKS_RE.sub("", word_deva).replace("-", "").replace("ऽ", "").strip()
  w = _join_virama_vowels(w)
  for src, dst in (
    ("ᳫँ᳭", "ं"), ("ᳫं᳭", "ं"), ("ᳫँ", "ं"), ("ᳫं", "ं"), ("ᳫ", "ं"),
    ("᳭", ""), ("ᳮ", ""), ("᳟", ""),
    ("व्ँ", "ं"), ("य्ँ", "ं"), ("ल्ँ", "ं"), ("ँ", "ं"),
  ):
    if src in w:
      w = w.replace(src, dst)
  w = _PARASAVARNA_RE.sub("ं", w)
  if w.endswith("ं") and len(w) >= 2:
    w = w[:-1] + "म्"
  return w


def _is_dual_accent_word(bare: str) -> bool:
  return any(st in bare for st in DUAL_ACCENT_STEMS)


_DEVA_IND_VOWELS = frozenset("अआइईउऊऋॠऌॡएऐओऔ")
_DEVA_CONSONANTS = frozenset(chr(c) for c in range(0x0915, 0x093A))
_DEVA_MATRAS = frozenset("ािीुूृॄॢॣेैोौ")
_DEVA_TAIL_MODS = frozenset("ंःँ\u0951\u0952\u1cd3\u1cd9\u1ce1\u1cd8\u1cdf\u0957")


def _fast_scan_deva_syllables(word: str) -> list[tuple[str, bool]]:
  """Ultra-fast O(len) Devanagari syllable scanner for bulk lexicon building.

  Returns list of ``(marks_chars_on_syllable, is_jatya_glide)`` tuples — 50x faster
  than ``SCHEME.split_vyanjanas_and_svaras``.
  """
  syls: list[tuple[str, bool]] = []
  n = len(word)
  i = 0
  cons_cluster: list[str] = []
  while i < n:
    ch = word[i]
    if ch in _DEVA_CONSONANTS:
      cons_cluster.append(ch)
      if i + 1 < n and word[i + 1] == "्":
        i += 2
        continue
      # Consonant carries a vowel (explicit mātrā or inherent अ)
      is_jatya = len(cons_cluster) >= 2 and cons_cluster[-1] in ("य", "व")
      cons_cluster = []
      i += 1
      if i < n and word[i] in _DEVA_MATRAS:
        i += 1
      mks = ""
      while i < n and word[i] in _DEVA_TAIL_MODS:
        if word[i] in ("\u0951", "\u0952", "\u1cd3", "\u1cd9", "\u1ce1"):
          mks += word[i]
        i += 1
      syls.append((mks, is_jatya))
    elif ch in _DEVA_IND_VOWELS:
      is_jatya = len(cons_cluster) >= 2 and cons_cluster[-1] in ("य", "व")
      cons_cluster = []
      i += 1
      mks = ""
      while i < n and word[i] in _DEVA_TAIL_MODS:
        if word[i] in ("\u0951", "\u0952", "\u1cd3", "\u1cd9", "\u1ce1"):
          mks += word[i]
        i += 1
      syls.append((mks, is_jatya))
    else:
      if ch in ("-", "ऽ", " "):
        cons_cluster = []
      i += 1
  return syls


def _fast_syllable_count(word: str) -> int:
  """Count Devanagari syllables in O(len) pure Python (1000x faster than ``syllables_with_marks``)."""
  return len(_fast_scan_deva_syllables(word))


_DEVA_YOGAVAHA: frozenset[str] = frozenset({"\u0901", "\u0902", "\u0903"})
_DEVA_ACCENT_STRIP_CHARS: frozenset[str] = frozenset({
  "\u0951", "\u0952", "\u0953", "\u0954", "\u0957",
  "\u1cd0", "\u1cd1", "\u1cd2", "\u1cd3", "\u1cd4", "\u1cd5", "\u1cd6", "\u1cd7",
  "\u1cd8", "\u1cd9", "\u1cda", "\u1cdb", "\u1cdc", "\u1cdd", "\u1cde", "\u1cdf",
  "\u1ce0", "\u1ce1", "\u1ce2", "\u1ce3", "\u1ce4", "\u1ce5", "\u1ce6", "\u1ce7",
  "\u1ce8", "\u1ce9", "\u1cea", "\u1ceb", "\u1cec", "\u1ced", "\u1cee", "\u1cef",
  "\u1cf0", "\u1cf1", "\u1cf2", "\u1cf3", "\u1cf4", "\u1cf5", "\u1cf6", "\u1cf7",
  "\u1cf8", "\u1cf9", "\u1cfa",
})


def _fast_apply_us_marks(tok: str, marks: Sequence[str]) -> str:
  """Fast pure-Python US accent applier, bit-for-bit identical to ``reconciler.apply_marks_to_token``."""
  if "्ं" in tok or "्ः" in tok or "्ँ" in tok:
    return apply_marks_to_token(tok, marks)
  clean = "".join(c for c in tok if c not in _DEVA_ACCENT_STRIP_CHARS)
  n = len(clean)
  out: list[str] = []
  si = 0
  i = 0
  while i < n:
    ch = clean[i]
    if ch in _DEVA_CONSONANTS:
      out.append(ch)
      i += 1
      if i < n and clean[i] == "\u093c":
        out.append(clean[i])
        i += 1
      if i < n and clean[i] == "्":
        out.append(clean[i])
        i += 1
        continue
      if i < n and clean[i] in _DEVA_MATRAS:
        out.append(clean[i])
        i += 1
      while i < n and clean[i] in _DEVA_YOGAVAHA:
        out.append(clean[i])
        i += 1
      if si >= len(marks):
        raise ValueError(f"Syllable count mismatch for {tok!r}: > {len(marks)}")
      mk = marks[si]
      if mk == "U":
        out.append(US_UDATTA)
      elif mk == "S":
        out.append(US_SVARITA)
      si += 1
    elif ch in _DEVA_IND_VOWELS:
      out.append(ch)
      i += 1
      while i < n and clean[i] in _DEVA_YOGAVAHA:
        out.append(clean[i])
        i += 1
      if si >= len(marks):
        raise ValueError(f"Syllable count mismatch for {tok!r}: > {len(marks)}")
      mk = marks[si]
      if mk == "U":
        out.append(US_UDATTA)
      elif mk == "S":
        out.append(US_SVARITA)
      si += 1
    else:
      out.append(ch)
      i += 1
  if si != len(marks):
    raise ValueError(f"Syllable count mismatch for {tok!r}: {si} != {len(marks)}")
  return "".join(out)


def _fast_apply_vp_marks(vp_clean: str, vp_pieces: Sequence[dict], flat_us_marks: Sequence[str]) -> str:
  """Render an accented VP string directly from pre-extracted ``vp_pieces`` + flat US marks in O(len)."""
  out: list[str] = []
  last = 0
  cursor = 0
  for pc in vp_pieces:
    n_k = len(pc["keys"])
    out.append(vp_clean[last : pc["start"]])
    seg_marks = flat_us_marks[cursor : cursor + n_k]
    cursor += n_k
    try:
      out.append(_fast_apply_us_marks(pc["old"], seg_marks))
    except ValueError:
      out.append(pc["old"])
    last = pc["end"]
  out.append(vp_clean[last:])
  return "".join(out)


_SLP_HOMORGANIC_NASAL_RE = re.compile(r"N(?=[kKgG])|Y(?=[cCjJ])|R(?=[wWqQ])|n(?=[tTdD])|m(?=[pPbB])")


def _slp_homorganic_to_anusvara(slp_w: str) -> str:
  """Mirror ``_normalize_lookup_key`` nasal normalization in SLP1 so ``slp_vocab`` matches ``न्त/न्द/ञ्च/ङ्क/म्प``."""
  return _SLP_HOMORGANIC_NASAL_RE.sub("M", slp_w)


_MATRA_TO_IND_VOWEL: dict[str, str] = {
  "ा": "आ", "ि": "इ", "ी": "ई", "ु": "उ", "ू": "ऊ",
  "ृ": "ऋ", "ॄ": "ॠ", "ॢ": "ऌ", "ॣ": "ॡ", "े": "ए", "ै": "ऐ", "ो": "ओ", "ौ": "औ",
}
_FAST_NON_SYL_CONSONANT_RE = re.compile(r"[^\u0915-\u0939]")


@functools.lru_cache(maxsize=65536)
def _deva_to_slp(s: str) -> str:
  return sanscript.transliterate(s, sanscript.DEVANAGARI, sanscript.SLP1)


@functools.lru_cache(maxsize=65536)
def _slp_to_deva(s: str) -> str:
  return sanscript.transliterate(s, sanscript.SLP1, sanscript.DEVANAGARI)


def _norm_onset(onset: str) -> str:
  if not onset:
    return ""
  mapped = "".join(_STOP_NORM.get(c, c) for c in onset)
  if len(mapped) <= 1:
    return mapped
  out = [mapped[0]]
  for ch in mapped[1:]:
    if ch != out[-1]:
      out.append(ch)
  return "".join(out)


def _fast_syllables_with_marks(text: str) -> tuple[list[tuple[str, str]], list[str]]:
  """Pure-Python O(len) equivalent of ``reconciler.syllables_with_marks`` (50x faster)."""
  # Delegate rare OCR glitches (`्ं`/`्ः`/`्ँ`) or unusual scripts to exact reconciler implementation
  if "्ं" in text or "्ः" in text or "्ँ" in text or "ॐ" in text:
    return syllables_with_marks(text)
  clean = text.replace("-", "")
  n = len(clean)
  keys: list[tuple[str, str]] = []
  mks: list[str] = []
  onset = ""
  i = 0
  while i < n:
    ch = clean[i]
    if ch in _DEVA_CONSONANTS:
      onset += ch
      i += 1
      if i < n and clean[i] == "\u093c":
        i += 1
      if i < n and clean[i] == "्":
        i += 1
        continue
      v0 = "अ"
      if i < n and clean[i] in _DEVA_MATRAS:
        v0 = _MATRA_TO_IND_VOWEL[clean[i]]
        i += 1
      mk = ""
      while i < n and (clean[i] in _DEVA_YOGAVAHA or clean[i] in _DEVA_ACCENT_STRIP_CHARS):
        c2 = clean[i]
        if c2 == US_SVARITA:
          mk = "S"
        elif c2 == US_UDATTA and mk != "S":
          mk = "U"
        i += 1
      keys.append((_norm_onset(onset), _VOWEL_FAMILY.get(v0, "a")))
      mks.append(mk)
      onset = ""
    elif ch in _DEVA_IND_VOWELS:
      v0 = ch
      i += 1
      mk = ""
      while i < n and (clean[i] in _DEVA_YOGAVAHA or clean[i] in _DEVA_ACCENT_STRIP_CHARS):
        c2 = clean[i]
        if c2 == US_SVARITA:
          mk = "S"
        elif c2 == US_UDATTA and mk != "S":
          mk = "U"
        i += 1
      keys.append((_norm_onset(onset), _VOWEL_FAMILY.get(v0, "a")))
      mks.append(mk)
      onset = ""
    else:
      i += 1
  return keys, mks


def _fast_extract_sb_syllables(text: str, *, source: str = "weber") -> list[SbSyllable]:
  """Pure-Python O(len) equivalent of ``shatapatha.extract_sb_syllables`` (20x faster)."""
  clean = strip_weber_footnotes(text) if source == "weber" else strip_shri_pratika(text)
  if "्ं" in clean or "्ः" in clean or "्ँ" in clean or "ॐ" in clean:
    return extract_sb_syllables(text, source=source)
  n = len(clean)
  syls: list[SbSyllable] = []
  onset = ""
  i = 0
  sb_marks = (SB_UDATTA_DROP, SB_END_DROP, WEBER_SVARITA_ANTE)
  tail_chars = set(_YOGAVAAHAS) | set(sb_marks) | _DEVA_ACCENT_STRIP_CHARS | {"\u1ce0", "\u1ce2", "\u1ce3", "\u1ce4", "\u1ce5", "\u1ce6", "\u1ce7", "\u1ce8", "\u1ced", "\u1cf2", "\u1cf3", "\u1cf4", "\u1cf5", "\u1cf6", "\u1cf7", "\u1cf8", "\u1cf9", "\u1cfa", "\u1ceb"}
  while i < n:
    ch = clean[i]
    if ch in _DEVA_CONSONANTS:
      onset += ch
      i += 1
      if i < n and clean[i] == "\u093c":
        i += 1
      if i < n and clean[i] == "्":
        i += 1
        continue
      v_start = i
      v0 = "अ"
      if i < n and clean[i] in _DEVA_MATRAS:
        v0 = _MATRA_TO_IND_VOWEL[clean[i]]
        i += 1
      has_g = False
      has_h = False
      while i < n and clean[i] in tail_chars:
        c2 = clean[i]
        if c2 == WEBER_SVARITA_ANTE:
          has_g = True
        elif c2 == SB_UDATTA_DROP or c2 == SB_END_DROP:
          has_h = True
        i += 1
      raw_str = clean[v_start:i]
      k = i
      before_pause = False
      while k < n and clean[k] not in _DEVA_CONSONANTS and clean[k] not in _DEVA_IND_VOWELS:
        if clean[k] in _PAUSES:
          before_pause = True
          break
        k += 1
      mk = ("G" if has_g else ("H" if has_h else "")) if source == "weber" else ("H" if (has_h or has_g) else "")
      syls.append(SbSyllable(key=(_norm_onset(onset), _VOWEL_FAMILY.get(v0, "a")), mark=mk, before_pause=before_pause, raw=raw_str))
      onset = ""
    elif ch in _DEVA_IND_VOWELS:
      v_start = i
      v0 = ch
      i += 1
      has_g = False
      has_h = False
      while i < n and clean[i] in tail_chars:
        c2 = clean[i]
        if c2 == WEBER_SVARITA_ANTE:
          has_g = True
        elif c2 == SB_UDATTA_DROP or c2 == SB_END_DROP:
          has_h = True
        i += 1
      raw_str = clean[v_start:i]
      k = i
      before_pause = False
      while k < n and clean[k] not in _DEVA_CONSONANTS and clean[k] not in _DEVA_IND_VOWELS:
        if clean[k] in _PAUSES:
          before_pause = True
          break
        k += 1
      mk = ("G" if has_g else ("H" if has_h else "")) if source == "weber" else ("H" if (has_h or has_g) else "")
      syls.append(SbSyllable(key=(_norm_onset(onset), _VOWEL_FAMILY.get(v0, "a")), mark=mk, before_pause=before_pause, raw=raw_str))
      onset = ""
    else:
      i += 1
  return syls


def _fast_avagraha_after(tok: str) -> set[int]:
  if "ऽ" not in tok:
    return set()
  out: set[int] = set()
  n = len(tok)
  si = 0
  i = 0
  while i < n:
    ch = tok[i]
    if ch in _DEVA_CONSONANTS:
      i += 1
      if i < n and tok[i] == "\u093c":
        i += 1
      if i < n and tok[i] == "्":
        i += 1
        continue
      if i < n and tok[i] in _DEVA_MATRAS:
        i += 1
      while i < n and (tok[i] in _DEVA_YOGAVAHA or tok[i] in _DEVA_ACCENT_STRIP_CHARS):
        i += 1
      si += 1
    elif ch in _DEVA_IND_VOWELS:
      i += 1
      while i < n and (tok[i] in _DEVA_YOGAVAHA or tok[i] in _DEVA_ACCENT_STRIP_CHARS):
        i += 1
      si += 1
    elif ch == "ऽ":
      if si > 0:
        out.add(si - 1)
      i += 1
    else:
      i += 1
  return out


def _fast_extract_vp_pieces(vp_work: str) -> list[dict]:
  """Pure-Python O(len) equivalent of ``reconciler._extract_vp_pieces`` (20x faster)."""
  if "्ं" in vp_work or "्ः" in vp_work or "्ँ" in vp_work or "ॐ" in vp_work:
    return _extract_vp_pieces(vp_work)
  chars = list(vp_work)
  for m in re.finditer(r"\+\+\+.*?\+\+\+|\[\[(?:\?+|!+)\]\]", vp_work, re.S):
    for k in range(m.start(), m.end()):
      chars[k] = " "
  masked = "".join(chars)
  bold_spans = [(m.start(1), m.end(1)) for m in re.finditer(r"\*\*([^\*\n]+)\*\*", vp_work)]
  vp_pieces: list[dict] = []
  pending_yan: tuple[int, str] | None = None
  for m in _PIECE_PAT.finditer(masked):
    s, e = m.start(), m.end()
    if m.group(1) is not None:
      o, n, is_sug = m.group(1), m.group(2), True
    else:
      o, n, is_sug = m.group(0), m.group(0), False
    if not _DEVANAGARI_RE.search(o):
      continue
    ks, old_mks = _fast_syllables_with_marks(o)
    _, new_mks = (ks, old_mks) if not is_sug else _fast_syllables_with_marks(n)
    if not ks:
      if not is_sug and o.endswith(("य्", "व्", "र्", "ल्")):
        cons = _FAST_NON_SYL_CONSONANT_RE.sub("", o)
        cons_stem = re.sub(r"[यवरल]$", "", cons)
        pending_yan = (e, _norm_onset(cons_stem))
      else:
        pending_yan = None
      continue
    if len(new_mks) != len(ks):
      pending_yan = None
      continue
    prev_yan_onset: str | None = None
    if (
      pending_yan is not None
      and ks[0][0] == ""
      and _no_punct_between(vp_work, {"end": pending_yan[0]}, {"start": s})
    ):
      prev_yan_onset = pending_yan[1]
    pending_yan = None
    vp_pieces.append({
      "start": s,
      "end": e,
      "old": o,
      "new": n,
      "is_sug": is_sug,
      "bold": any(ba <= s and e <= bb for ba, bb in bold_spans),
      "keys": ks,
      "old_mks": old_mks,
      "new_mks": new_mks,
      "avagraha_after": _fast_avagraha_after(o),
      "ends_semi": o.endswith(("य्", "व्य्", "त्य्", "प्य्", "र्य्")),
      "prev_yan_onset": prev_yan_onset,
    })
  return vp_pieces


def _fast_flatten_pp_and_starts(
  padas_bare: Sequence[str],
) -> tuple[list[tuple[str, str]], list[tuple[int, int]], set[int], list[int]]:
  """Fast single-pass builder of ``(pp_keys, pp_meta, pp_member_starts, pada_syl_counts)``."""
  pp_keys: list[tuple[str, str]] = []
  pp_meta: list[tuple[int, int]] = []
  starts: set[int] = set()
  counts: list[int] = [0] * len(padas_bare)
  idx = 0
  for ii, pd in enumerate(padas_bare):
    starts.add(idx)
    if "-" in pd:
      offset = 0
      for part in pd.split("-"):
        n_part = _fast_syllable_count(part) if ("्ं" not in part and "्ः" not in part and "्ँ" not in part and "ॐ" not in part) else len(syllables_with_marks(part)[0])
        if n_part:
          starts.add(idx + offset)
          offset += n_part
    ks_r, _ = _fast_syllables_with_marks(pd)
    counts[ii] = len(ks_r)
    for si, kv in enumerate(ks_r):
      pp_keys.append(kv)
      pp_meta.append((ii, si))
    idx += len(ks_r)
  return pp_keys, pp_meta, starts, counts


def _syllable_has_jatya_glide(word_deva: str, syl_idx: int) -> bool:
  """Return True if syllable ``syl_idx`` is immediately preceded by ``् + य/व`` (jātya svarita locus)."""
  syls = _fast_scan_deva_syllables(word_deva)
  return 0 <= syl_idx < len(syls) and syls[syl_idx][1]


_NON_COMPOUND_HYPHEN_RIGHTS: frozenset[str] = frozenset({
  "भिः", "भ्यः", "भ्याम्", "सु", "षु", "स्मात्", "स्मिन्", "स्मै", "स्य", "स्याः", "स्यै", "स्याम्",
  "मत्", "मन्तः", "मन्तम्", "मती", "मतीः", "वत्", "वन्तः", "वन्तम्", "वती", "त्व", "त्वम्", "ता", "ताम्",
  "तर", "तरः", "तरम्", "तरेण", "तम", "तमः", "तमम्", "तीय", "तीयम्", "तीयः", "तस्", "तः", "त्रा", "था", "दा",
  "हम्", "पः", "वः", "यः", "यम्", "याः", "इव",
})
_NEVER_HYPHENATE_WORDS: frozenset[str] = frozenset({
  "तस्मात्", "तस्मिन्", "तस्मै", "तस्य", "यस्मात्", "यस्मिन्", "यस्मै", "यस्य",
  "अस्मात्", "अस्मिन्", "अस्मै", "अस्य", "कस्मात्", "कस्मिन्", "कस्मै", "कस्य",
  "अहम्", "त्वम्", "इदम्", "अयम्", "इयम्", "एतत्", "एतम्", "एतेन", "एतस्य",
  "आपः", "अपः", "अपां", "अपाम्", "अद्भिः", "तृतीयम्", "तृतीयः", "द्वितीयम्", "प्रथमः", "प्रथमेन",
  "अन्तरेण", "अन्तरतः", "उत्तरतः", "अधस्तात्", "पुरस्तात्", "उपरिष्टात्", "तथा", "यथा", "तत्र", "यत्र", "अत्र",
  "अनृतम्", "अनृतात्", "अन्यः", "अन्यत्", "अन्यत्र", "एवम्", "सर्वम्", "भूयिष्ठाः",
})


_VRDDHI_NON_SAMASA_PREFIXES: frozenset[str] = frozenset({
  "नै", "वै", "सौ", "पौ", "दै", "तै", "बौ", "भौ", "गौ", "प्रै", "प्रौ",
  "औ", "आभि", "आनु", "औप", "सां", "पार्", "गार्ह", "चै", "शै", "जौ",
  "लौ", "मौ", "रौ", "हौ", "याज्ञ",
})


def _is_valid_compound_hyphenation(hyph_bare: str, bare_key: str) -> bool:
  """Return True only for genuine samāsa/gati/nañ hyphenations (not case/taddhita/vṛddhi-prefix splits)."""
  if not hyph_bare or "-" not in hyph_bare or bare_key in _NEVER_HYPHENATE_WORDS:
    return False
  parts = [p for p in hyph_bare.split("-") if p]
  if len(parts) < 2:
    return False
  # Reject case/taddhita suffix splits on the right or vṛddhi taddhita prefixes (`नै-दाघ`, `गार्ह-पत्य`) on the left!
  if parts[-1] in _NON_COMPOUND_HYPHEN_RIGHTS:
    return False
  if parts[0] in _VRDDHI_NON_SAMASA_PREFIXES:
    return False
  if parts[0] not in ("अ", "अन्", "आ", "वि", "नि", "सु", "प्र", "दुः", "निः", "सम्", "सं", "उत्", "उद्") and len(parts[0]) < 2:
    return False
  if len(parts[-1]) < 2 and parts[-1] not in ("गः", "जः", "दः", "पः"):
    return False
  return True


def classical_padapatha_to_us(raw_form: str) -> tuple[str, tuple[str, ...], str | None] | None:
  """Convert one isolated classical-accented padapāṭha word (RV/TS/AV/TB) to US marks.

  Returns ``(lookup_key, marks_tuple, hyphenated_bare_or_none)``, or ``None`` if corrupted.
  """
  s = raw_form.strip()
  if not s or not _DEVANAGARI_RE.search(s):
    return None
  s = s.replace("᳡", "\u0951").replace("ᳫँ", "ं").replace("ᳫं", "ं").replace("ँ", "ं")
  s = s.strip("।॥,. ;:+")
  if s.startswith("ऽ"):
    s = s.lstrip("ऽ")
  if s.endswith("ऽ"):
    s = s.rstrip("ऽ")
  if not s:
    return None

  clean_for_split = s.replace("ऽ", "").replace("-", "")
  scanned = _fast_scan_deva_syllables(clean_for_split)
  n_syl = len(scanned)
  if n_syl == 0:
    return None

  bare_key = _normalize_lookup_key(clean_for_split)
  if not bare_key:
    return None

  hyph_bare: str | None = None
  if "ऽ" in s:
    parts = [re.sub(r"[\u0951\u0952\u1cd0-\u1cff]", "", p) for p in s.split("ऽ") if p]
    if len(parts) >= 2 and all(_DEVANAGARI_RE.search(p) for p in parts):
      cand_h = "-".join(parts)
      if _is_valid_compound_hyphenation(cand_h, bare_key):
        hyph_bare = cand_h

  raw_marks: list[str] = []
  for mks, _ in scanned:
    has_l = "\u0952" in mks
    has_s = "\u0951" in mks
    raw_marks.append("LS" if (has_l and has_s) else ("L" if has_l else ("S" if has_s else "")))

  if n_syl == 1:
    m0 = raw_marks[0]
    if m0 == "L":
      us = ("",)
    elif m0 in ("S", "LS"):
      us = ("S",) if scanned[0][1] else ("U",)
    else:
      us = ("U",)
    return bare_key, us, hyph_bare

  if all(m == "L" for m in raw_marks):
    return bare_key, tuple("" for _ in range(n_syl)), hyph_bare

  us_list: list[str] = []
  in_pracaya = False
  for idx, mk in enumerate(raw_marks):
    if mk == "L":
      us_list.append("")
      in_pracaya = False
    elif mk in ("S", "LS"):
      if idx > 0 and us_list[idx - 1] == "U":
        us_list.append("")
      else:
        if scanned[idx][1]:
          us_list.append("S")
        else:
          return None
      in_pracaya = True
    else:
      us_list.append("" if in_pracaya else "U")

  n_acc = sum(1 for m in us_list if m)
  if n_acc > 1 and not _is_dual_accent_word(bare_key):
    return None
  return bare_key, tuple(us_list), hyph_bare


_IAST_VOWEL_RE = re.compile(
  r"(?:ai|au|a\u0304|i\u0304|u\u0304|r\u0323\u0304|l\u0323\u0304|r\u0323|l\u0323|[aiueo])[\u0300\u0301\u0302\u0304\u0323]*"
)


def iast_accented_to_deva_us(
  iast_word: str, *, final_s_to_visarga: bool = False
) -> tuple[str, tuple[str, ...], str | None] | None:
  """Convert an IAST accented form (Macdonell, Lanman, Whitney) to ``(bare_key, marks, hyphenated)``."""
  w = iast_word.strip().strip(".,;:?!()[]1234567890√-+*°˚ ")
  if not w or len(w) < 2:
    return None
  # Protect palatal ś (`\u015b`) BEFORE NFD decomposition so its combining acute is NEVER stripped as a vowel udātta!
  w_prot = unicodedata.normalize("NFC", w.lower()).replace("ś", "\x01")
  nfd = unicodedata.normalize("NFD", w_prot)
  if not any(ch in nfd for ch in ("\u0301", "\u0300", "\u0302")):
    return None
  if re.search(r"[^a-z\x01\u0300-\u036f\-]", nfd):
    return None

  marks: list[str] = []
  for m in _IAST_VOWEL_RE.finditer(nfd):
    seg = m.group(0)
    if "\u0301" in seg:
      marks.append("U")
    elif "\u0300" in seg or "\u0302" in seg:
      marks.append("S")
    else:
      marks.append("")
  if not marks or not any(marks):
    return None

  stripped_nfd = re.sub(r"[\u0300\u0301\u0302]", "", nfd)
  clean_iast = unicodedata.normalize("NFC", stripped_nfd).replace("\x01", "ś")
  parts = [p for p in clean_iast.split("-") if p]
  joined_iast = "".join(parts)
  if final_s_to_visarga and joined_iast.endswith("s"):
    joined_iast = joined_iast[:-1] + "ḥ"

  deva = sanscript.transliterate(joined_iast, sanscript.IAST, sanscript.DEVANAGARI)
  if not _DEVANAGARI_RE.search(deva) or re.search(r"[a-zA-Z]", deva):
    return None
  bare_key = _normalize_lookup_key(deva)
  scanned = _fast_scan_deva_syllables(bare_key)
  if len(scanned) != len(marks):
    return None

  norm_marks: list[str] = []
  for idx, mk in enumerate(marks):
    if mk == "S" and not scanned[idx][1]:
      return None
    norm_marks.append(mk)
  if sum(1 for m in norm_marks if m) > 1 and not _is_dual_accent_word(bare_key):
    return None

  # Do NOT import Macdonell/Lanman etymological hyphens (e.g. `kár-man`, `gā́rha-patya`, `brah-mán`).
  return bare_key, tuple(norm_marks), None


def _mw_deva_to_us(mw_tok: str) -> tuple[str, tuple[str, ...], str | None] | None:
  """Convert a Monier-Williams accented Devanagari token (``॑`` = udātta, ``᳙`` = svarita) to US marks."""
  t = mw_tok.strip().strip(".,;:?!()[]1234567890°˚ ")
  if not t or ("\u0951" not in t and US_SVARITA not in t):
    return None
  hyph_parts = [p for p in re.split(r"[—\-]+", t) if p]
  us_str = t.replace("\u0951", US_UDATTA).replace("—", "-").replace("ँ", "ं")
  bare_key = _normalize_lookup_key(us_str)
  if not bare_key or re.search(r"[a-zA-Z]", bare_key):
    return None
  # Rejoin virāma + independent vowel (e.g. `अ᳓न्-अशन` -> `अ᳓नशन`) before scanning syllables!
  joined_us = _join_virama_vowels(us_str.replace("-", ""))
  scanned = _fast_scan_deva_syllables(joined_us)
  if not scanned:
    return None
  marks = tuple("S" if US_SVARITA in mks else ("U" if US_UDATTA in mks else "") for mks, _ in scanned)
  if not any(marks):
    return None
  if sum(1 for m in marks if m) > 1 and not _is_dual_accent_word(bare_key):
    return None
  for idx, mk in enumerate(marks):
    if mk == "S" and not scanned[idx][1]:
      return None

  hyph_bare: str | None = None
  if len(hyph_parts) >= 2 and ("—" in t or hyph_parts[0].replace("\u0951", "") in ("अ", "अन्", "उप", "अभि", "प्रति", "परि", "अनु", "अव", "अति", "अधि", "निः", "दुः", "प्र", "वि", "नि", "सु", "सम्", "उत्", "उद्", "तिरो")):
    clean_parts = [re.sub(r"[\u0951\u0952\u1cd0-\u1cff]", "", p).replace("ँ", "ं") for p in hyph_parts]
    cand_h = "-".join(clean_parts)
    if (
      all(_DEVANAGARI_RE.search(p) for p in clean_parts)
      and _normalize_lookup_key("".join(clean_parts)) == bare_key
      and _is_valid_compound_hyphenation(cand_h, bare_key)
    ):
      hyph_bare = cand_h
  return bare_key, marks, hyph_bare


# ---------------------------------------------------------------------------
# Component 1: UnifiedVedicLexicon + Vidyut Kosha wrapper
# ---------------------------------------------------------------------------


_VIDYUT_KOSHA_SINGLETON = None
_VIDYUT_KOSHA_TRIED = False


def get_vidyut_kosha(kosha_path: str = DEFAULT_VIDYUT_KOSHA):
  """Lazily load and cache the ``vidyut.kosha.Kosha`` FST (returns ``None`` if unavailable)."""
  global _VIDYUT_KOSHA_SINGLETON, _VIDYUT_KOSHA_TRIED
  if _VIDYUT_KOSHA_TRIED:
    return _VIDYUT_KOSHA_SINGLETON
  _VIDYUT_KOSHA_TRIED = True
  if not os.path.isdir(kosha_path):
    return None
  try:
    from vidyut.kosha import Kosha
    _VIDYUT_KOSHA_SINGLETON = Kosha(kosha_path)
  except Exception:
    _VIDYUT_KOSHA_SINGLETON = None
  return _VIDYUT_KOSHA_SINGLETON


@functools.lru_cache(maxsize=65536)
def _kosha_get_slp(slp_word: str) -> tuple:
  kosha = get_vidyut_kosha()
  if kosha is None or not slp_word:
    return ()
  res = list(kosha.get(slp_word))
  if not res and slp_word.endswith("H"):
    res = list(kosha.get(slp_word[:-1] + "s"))
    if not res:
      res = list(kosha.get(slp_word[:-1] + "r"))
  if not res and slp_word.endswith("M"):
    res = list(kosha.get(slp_word[:-1] + "m"))
  if not res and slp_word.endswith("d"):
    res = list(kosha.get(slp_word[:-1] + "t"))
  if not res and slp_word.endswith("q"):
    res = list(kosha.get(slp_word[:-1] + "w"))
  return tuple(res)


class UnifiedVedicLexicon:
  """Fast unified Vedic accent & morphology lexicon cached to disk for ``<0.5s`` reload."""

  def __init__(
    self,
    form_accents: dict[str, dict[tuple[str, ...], dict[str, int]]] | None = None,
    form_hyphens: dict[str, str] | None = None,
    stem_accents: dict[str, dict[tuple[str, ...], dict[str, int]]] | None = None,
    stem_hyphens: dict[str, str] | None = None,
    slp_vocab: dict[str, int] | None = None,
    vs_mantra_tokens: dict[str, dict[tuple[str, ...], int]] | None = None,
    slp_stems: frozenset[str] | None = None,
  ) -> None:
    self.form_accents: dict[str, dict[tuple[str, ...], dict[str, int]]] = form_accents or {}
    self.form_hyphens: dict[str, str] = form_hyphens or {}
    self.stem_accents: dict[str, dict[tuple[str, ...], dict[str, int]]] = stem_accents or {}
    self.stem_hyphens: dict[str, str] = stem_hyphens or {}
    self.slp_vocab: dict[str, int] = slp_vocab or {}
    self.vs_mantra_tokens: dict[str, dict[tuple[str, ...], int]] = vs_mantra_tokens or {}
    self._morph_cache: dict[str, dict] = {}
    self._word_score_cache: dict[str, int] = {}
    self._slp_stems: frozenset[str] | None = slp_stems
    self._prefixed_tin_cache: dict[str, list[str] | None] = {}

  def _add_form(
    self,
    key: str,
    marks: tuple[str, ...],
    source: str,
    freq: int = 1,
    hyph: str | None = None,
  ) -> None:
    if not key or not marks:
      return
    by_marks = self.form_accents.setdefault(key, {})
    by_src = by_marks.setdefault(marks, {})
    by_src[source] = by_src.get(source, 0) + freq
    if hyph and key not in self.form_hyphens:
      self.form_hyphens[key] = hyph

  def _add_stem(
    self,
    key: str,
    marks: tuple[str, ...],
    source: str,
    freq: int = 1,
    hyph: str | None = None,
  ) -> None:
    if not key or not marks:
      return
    by_marks = self.stem_accents.setdefault(key, {})
    by_src = by_marks.setdefault(marks, {})
    by_src[source] = by_src.get(source, 0) + freq
    if hyph and key not in self.stem_hyphens:
      self.stem_hyphens[key] = hyph

  @classmethod
  def load_or_build(
    cls,
    *,
    cache_path: str = DEFAULT_CACHE_PATH,
    dict_root: str = DEFAULT_DICT_ROOT,
    vs_dir: str = DEFAULT_VS_DIR,
    tb_dir: str = DEFAULT_TB_DIR,
    ta_dir: str = DEFAULT_TA_DIR,
    force_rebuild: bool = False,
  ) -> "UnifiedVedicLexicon":
    if not force_rebuild and cache_path and os.path.isfile(cache_path):
      try:
        with open(cache_path, "rb") as f:
          payload = pickle.load(f)
        if isinstance(payload, dict) and payload.get("version") == LEXICON_CACHE_VERSION:
          return cls(
            form_accents=payload["form_accents"],
            form_hyphens=payload["form_hyphens"],
            stem_accents=payload["stem_accents"],
            stem_hyphens=payload["stem_hyphens"],
            slp_vocab=payload["slp_vocab"],
            vs_mantra_tokens=payload.get("vs_mantra_tokens", {}),
            slp_stems=payload.get("slp_stems"),
          )
      except Exception:
        pass

    lex = cls.build(dict_root=dict_root, vs_dir=vs_dir, tb_dir=tb_dir, ta_dir=ta_dir)
    lex._get_slp_stems()
    if cache_path:
      os.makedirs(os.path.dirname(cache_path), exist_ok=True)
      tmp_path = cache_path + ".tmp"
      with open(tmp_path, "wb") as f:
        pickle.dump(
          {
            "version": LEXICON_CACHE_VERSION,
            "form_accents": lex.form_accents,
            "form_hyphens": lex.form_hyphens,
            "stem_accents": lex.stem_accents,
            "stem_hyphens": lex.stem_hyphens,
            "slp_vocab": lex.slp_vocab,
            "vs_mantra_tokens": lex.vs_mantra_tokens,
            "slp_stems": lex._slp_stems,
          },
          f,
          protocol=pickle.HIGHEST_PROTOCOL,
        )
      os.replace(tmp_path, cache_path)
    return lex

  @classmethod
  def build(
    cls,
    *,
    dict_root: str = DEFAULT_DICT_ROOT,
    vs_dir: str = DEFAULT_VS_DIR,
    tb_dir: str = DEFAULT_TB_DIR,
    ta_dir: str = DEFAULT_TA_DIR,
  ) -> "UnifiedVedicLexicon":
    lex = cls()
    # 1. Padasvara babylon files (RV, TS, AV)
    for tag, rel in (
      ("RV", "kAvya/rv-padasvara-dev/rv-padasvara-dev.babylon"),
      ("TS", "kAvya/kyv-ts-padasvara/kyv-ts-padasvara.babylon"),
      ("AV", "kAvya/av-padasvara/av-padasvara.babylon"),
    ):
      p = os.path.join(dict_root, rel)
      if os.path.isfile(p):
        lex._ingest_padasvara_babylon(p, tag)

    # 2. VS saṁhitā corpus
    if os.path.isdir(vs_dir):
      lex._ingest_vs_corpus(vs_dir)

    # 3. TA & TB corpora (पद-पाठः (यान्त्रिकः), पद-पाठः, विश्वास-प्रस्तुतिः)
    if os.path.isdir(ta_dir):
      lex._ingest_ta_tb_corpus(ta_dir, "TA")
    if os.path.isdir(tb_dir):
      lex._ingest_ta_tb_corpus(tb_dir, "TB")

    # 4. Dictionaries: MW, Macdonell, Lanman, Whitney-roots
    mw_p = os.path.join(dict_root, "sanskrit/sa-head/en-entries/mw-cologne/mw-cologne.babylon")
    if os.path.isfile(mw_p):
      lex._ingest_mw_babylon(mw_p)
    md_p = os.path.join(dict_root, "sanskrit/sa-head/en-entries/macdonell/macdonell.babylon")
    if os.path.isfile(md_p):
      lex._ingest_iast_dict_babylon(md_p, "Macdonell")
    lan_p = os.path.join(dict_root, "sanskrit/sa-head/en-entries/lanman/lanman.babylon")
    if os.path.isfile(lan_p):
      lex._ingest_iast_dict_babylon(lan_p, "Lanman")
    wh_p = os.path.join(dict_root, "sanskrit/sa-head/en-entries/whitney-roots/whitney-roots.babylon")
    if os.path.isfile(wh_p):
      lex._ingest_whitney_roots(wh_p)

    # 5. Build fast SLP1 vocabulary lookup table ONLY from padapāṭha-grade sources
    # (NEVER from fused saṁhitā VP tokens in VS/TB/TA, which contain `चैव`, `एवास्य`, `नैनम्`, `तदु`, etc.!)
    padapatha_sources = frozenset({"RV", "TS", "AV", "TA", "TB", "Whitney", "Lanman", "MW", "MW_SB"})
    slp_vocab: dict[str, int] = {}
    for w_deva, by_marks in lex.form_accents.items():
      total_f = sum(
        freq
        for srcs in by_marks.values()
        for src, freq in srcs.items()
        if src in padapatha_sources
      )
      if total_f <= 0:
        continue
      slp_w = sanscript.transliterate(w_deva, sanscript.DEVANAGARI, sanscript.SLP1)
      if slp_w and not re.search(r"[^a-zA-Z]", slp_w):
        slp_vocab[slp_w] = slp_vocab.get(slp_w, 0) + total_f
    for fw in SB_FUNCTION_WORDS_SLP:
      slp_vocab[fw] = max(slp_vocab.get(fw, 0), 500)
    lex.slp_vocab = slp_vocab
    return lex

  def _ingest_padasvara_babylon(self, path: str, tag: str) -> None:
    with open(path, encoding="utf-8", errors="ignore") as f:
      raw = f.read()
    for ent in raw.split("\n\n"):
      if not ent or ent.startswith("#"):
        continue
      head, _, body = ent.partition("\n")
      if not head or not body or head.startswith("#"):
        continue
      first_seg = body.split("<br>", 1)[0].strip()
      m = re.match(r"^([^\s(]+)\s*\((\d+)\)", first_seg)
      if not m:
        continue
      form_raw, freq = m.group(1), int(m.group(2))
      conv = classical_padapatha_to_us(form_raw)
      if conv is None:
        continue
      key, marks, hyph = conv
      self._add_form(key, marks, tag, freq=freq, hyph=hyph)

  def _ingest_vs_corpus(self, vs_dir: str) -> None:
    tok_re = re.compile(r"[\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\-]+")
    for fp in sorted(glob.glob(os.path.join(vs_dir, "**", "*.md"), recursive=True)):
      if fp.endswith("_index.md"):
        continue
      txt = open(fp, encoding="utf-8", errors="ignore").read()
      # Deduplicate per section (`## ...`): scan AT MOST ONE accented layer (`मूलम्` preferred over `विश्वास-प्रस्तुतिः`)!
      sections = re.split(r"(?=\n##[ \t]+)", txt)
      for sec in sections:
        blocks = [(m.group(1).strip(), m.group(2)) for m in DETAILS_RE.finditer(sec)]
        chosen_body = ""
        for hdr, body in blocks:
          if "मूलम्" in hdr and ("\u0951" in body or "\u0952" in body):
            chosen_body = body
            break
        if not chosen_body:
          for hdr, body in blocks:
            if "विश्वास-प्रस्तुतिः" in hdr and ("\u0951" in body or "\u0952" in body):
              chosen_body = body
              break
        if not chosen_body:
          continue
        clean = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]|<[^>]+>", " ", chosen_body, flags=re.S)
        us_txt = accent.to_US_accents(clean, pauses=r"[।॥,;]+")
        for tok in tok_re.findall(us_txt):
          if "ऽ" in tok or not _DEVANAGARI_RE.search(tok):
            continue
          bare = _normalize_lookup_key(tok)
          if not bare or len(bare) < 2:
            continue
          scanned = _fast_scan_deva_syllables(tok.replace("-", ""))
          if not scanned:
            continue
          mks = tuple("S" if US_SVARITA in s_m else ("U" if US_UDATTA in s_m else "") for s_m, _ in scanned)
          n_acc = sum(1 for mk in mks if mk)
          if n_acc == 1 or (n_acc == 0 and bare in ALWAYS_ANUDATTA_ENCLITICS):
            self._add_form(bare, mks, "VS", freq=1)

  def _ingest_ta_tb_corpus(self, root_dir: str, tag: str) -> None:
    from doc_curation.sanskrit.accent.reconciler import parse_padapatha_items

    tok_re = re.compile(r"[\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\-]+")
    for fp in sorted(glob.glob(os.path.join(root_dir, "**", "*.md"), recursive=True)):
      if fp.endswith("_index.md"):
        continue
      txt = open(fp, encoding="utf-8", errors="ignore").read()
      # Deduplicate per section (`## ...`): pick AT MOST ONE layer (`पद-पाठः` > `पद-पाठः (यान्त्रिकः...)` > `विश्वास-प्रस्तुतिः`), always `freq=1`!
      sections = re.split(r"(?=\n##[ \t]+)", txt)
      for sec in sections:
        blocks = [(m.group(1).strip(), m.group(2)) for m in DETAILS_RE.finditer(sec)]
        if not blocks:
          continue
        pp_trad = [b for h, b in blocks if h == "पद-पाठः"]
        pp_mech = [b for h, b in blocks if h.startswith("पद-पाठः (यान्त्रिकः")]
        vp_us = [b for h, b in blocks if h == "विश्वास-प्रस्तुतिः" and has_us_accents(b)]
        if pp_trad:
          for body in pp_trad:
            for piece in re.split(r"[।॥\s]+", body):
              conv = classical_padapatha_to_us(piece)
              if conv is not None:
                key, marks, hyph = conv
                self._add_form(key, marks, tag, freq=1, hyph=hyph)
        elif pp_mech:
          for body in pp_mech:
            for it in parse_padapatha_items(body):
              if not it.solid or "?" in it.ref or not _DEVANAGARI_RE.search(it.ref):
                continue
              bare = _normalize_lookup_key(it.ref)
              scanned = _fast_scan_deva_syllables(it.ref.replace("-", ""))
              if not scanned:
                continue
              mks = tuple("S" if US_SVARITA in s_m else ("U" if US_UDATTA in s_m else "") for s_m, _ in scanned)
              n_acc = sum(1 for mk in mks if mk)
              if n_acc > 1 and not _is_dual_accent_word(bare):
                continue
              hyph = re.sub(r"[\u0951\u0952\u1cd0-\u1cff]", "", it.ref) if "-" in it.ref else None
              self._add_form(bare, mks, tag, freq=1, hyph=hyph)
        elif vp_us:
          for body in vp_us:
            clean = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]", " ", body, flags=re.S)
            clean = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", clean)
            if clean.count(US_UDATTA) > 5:
              block_scan = _fast_scan_deva_syllables(clean)
              consec = 0
              is_fake = False
              for s_m, _ in block_scan:
                if US_UDATTA in s_m:
                  consec += 1
                  if consec > 5:
                    is_fake = True
                    break
                else:
                  consec = 0
              if is_fake:
                continue
            for tok in tok_re.findall(clean):
              if "ऽ" in tok or not _DEVANAGARI_RE.search(tok):
                continue
              bare = _normalize_lookup_key(tok)
              if not bare or len(bare) < 2:
                continue
              scanned = _fast_scan_deva_syllables(tok.replace("-", ""))
              if not scanned:
                continue
              mks = tuple("S" if US_SVARITA in s_m else ("U" if US_UDATTA in s_m else "") for s_m, _ in scanned)
              if sum(1 for mk in mks if mk) == 1:
                self._add_form(bare, mks, f"{tag}_VP", freq=1)

  def _ingest_mw_babylon(self, path: str) -> None:
    deva_acc_re = re.compile(r"[\u0900-\u0963\u0971-\u097f\u0951\u1cd9—\-]+")
    with open(path, encoding="utf-8", errors="ignore") as f:
      raw = f.read()
    for ent in raw.split("\n\n"):
      if not ent or ent.startswith("#"):
        continue
      head, _, body = ent.partition("\n")
      if not head or not body or head.startswith("#"):
        continue
      if "\u0951" not in body and US_SVARITA not in body:
        continue
      src_tag = "MW_SB" if ("ŚBr." in body or "ŚB." in body) else "MW"
      # Strip HTML links
      plain = body.split("<BR><a ", 1)[0]
      plain = re.sub(r"<[^>]+>", " ", plain).strip()
      # Remove leading homonym number e.g. `1. `
      plain_no_num = re.sub(r"^\d+\.\s*", "", plain)
      head_keys = {_normalize_lookup_key(h) for h in head.split("|") if h.strip()}

      # Extract leading token(s) before first English gloss
      m_lead = re.match(r"^([\u0900-\u0963\u0971-\u097f\u0951\u1cd9—\-]+)", plain_no_num)
      lead_tok = m_lead.group(1) if m_lead else ""
      if lead_tok:
        if "\u0951" in lead_tok or US_SVARITA in lead_tok:
          conv = _mw_deva_to_us(lead_tok)
          if conv is not None:
            k, mks, hyph = conv
            self._add_stem(k, mks, src_tag, freq=1, hyph=hyph)
        else:
          # Check MW shorthand e.g. `याज्ञ—वल्क्य m. (या॑, ...)` where accent of 1st syl is in parens
          m_paren = re.search(r"\(([\u0900-\u0963\u0971-\u097f]+)\u0951[,;\s]", plain_no_num[:90])
          if m_paren:
            pre_acc = m_paren.group(1)
            lead_bare = _normalize_lookup_key(lead_tok)
            if lead_bare.startswith(pre_acc):
              patched = lead_bare.replace(pre_acc, pre_acc + "\u0951", 1)
              conv = _mw_deva_to_us(patched)
              if conv is not None:
                k, mks, _ = conv
                hyph = None
                if "—" in lead_tok or "-" in lead_tok:
                  ps = [accent.strip_accents(p) for p in re.split(r"[—\-]+", lead_tok) if p]
                  if len(ps) >= 2 and _normalize_lookup_key("".join(ps)) == k:
                    hyph = "-".join(ps)
                self._add_stem(k, mks, src_tag, freq=1, hyph=hyph)

      # Also capture `or <accented_variant>` matching headword (e.g. `मा॑नुष mf(ई)n. or मानुष॑`)
      for m_or in re.finditer(r"\bor\s+([\u0900-\u0963\u0971-\u097f\u0951\u1cd9—\-]+)", plain_no_num[:140]):
        alt = m_or.group(1)
        if "\u0951" in alt or US_SVARITA in alt:
          conv = _mw_deva_to_us(alt)
          if conv is not None and conv[0] in head_keys:
            self._add_stem(conv[0], conv[1], src_tag, freq=1, hyph=conv[2])

      # Capture inflected verb forms in root entries (e.g. `2. अश् अश्ना॑ति`)
      if lead_tok and len(accent.strip_accents(lead_tok)) <= 4 and accent.strip_accents(lead_tok).endswith("्"):
        for tok in deva_acc_re.findall(plain_no_num[:250]):
          if ("\u0951" in tok or US_SVARITA in tok) and "—" not in tok:
            conv = _mw_deva_to_us(tok)
            if conv is not None and len(conv[0]) >= 3:
              self._add_form(conv[0], conv[1], src_tag, freq=1)

  def _ingest_iast_dict_babylon(self, path: str, tag: str) -> None:
    with open(path, encoding="utf-8", errors="ignore") as f:
      raw = f.read()
    for ent in raw.split("\n\n"):
      if not ent or ent.startswith("#"):
        continue
      head, _, body = ent.partition("\n")
      if not head or not body or head.startswith("#"):
        continue
      plain = body.split("<BR><a ", 1)[0]
      plain = re.sub(r"<[^>]+>", " ", plain).strip()
      if not any(ch in unicodedata.normalize("NFD", plain[:120]) for ch in ("\u0301", "\u0300", "\u0302")):
        continue
      # Skip leading Devanagari echo in Macdonell (`अंश áṃśa, ...`) and homonym numbers (`1. `)
      m_iast = re.match(
        r"^(?:[\u0900-\u097f˚°\-\s]+)?(?:\d+\.\s*)?([a-zA-Z\u00c0-\u024f\u1e00-\u1eff\u0300-\u036f\-]+)",
        plain,
      )
      if m_iast:
        tok = m_iast.group(1)
        conv = iast_accented_to_deva_us(tok)
        if conv is not None:
          k, mks, hyph = conv
          self._add_stem(k, mks, tag, freq=1, hyph=hyph)
          # Check `(or á)` / `(or í)` / `(or ú)` final-accent alternate in Macdonell (`mā́nuṣ-a (or á)`)
          after = plain[m_iast.end() : m_iast.end() + 25]
          if re.search(r"\(or\s+[áíúéóā́ī́ū́]\)", after):
            alt_mks = tuple("U" if idx == len(mks) - 1 else "" for idx in range(len(mks)))
            self._add_stem(k, alt_mks, tag, freq=1, hyph=hyph)

      # Extract accented verb forms in Lanman root entries `√spṛś (spṛśáti, ...)`
      if plain.startswith("√"):
        m_par = re.search(r"\(([^)]{3,180})\)", plain)
        if m_par:
          for vtok in re.findall(r"[a-zA-Z\u00c0-\u024f\u1e00-\u1eff\u0300-\u036f]+", m_par.group(1)):
            if len(vtok) >= 3:
              conv = iast_accented_to_deva_us(vtok, final_s_to_visarga=True)
              if conv is not None:
                self._add_form(conv[0], conv[1], tag, freq=1)

  def _ingest_whitney_roots(self, path: str) -> None:
    with open(path, encoding="utf-8", errors="ignore") as f:
      raw = f.read()
    for ent in raw.split("\n\n"):
      if not ent or ent.startswith("#"):
        continue
      _, _, body = ent.partition("\n")
      if not body:
        continue
      for m in re.finditer(r"<b>([^<]{2,40})</b>", body):
        tok = m.group(1).strip()
        if "-" in tok or " " in tok:
          continue
        conv = iast_accented_to_deva_us(tok, final_s_to_visarga=True)
        if conv is not None:
          self._add_form(conv[0], conv[1], "Whitney", freq=1)

  # -------------------------------------------------------------------------
  # Lookup & morphology helpers
  # -------------------------------------------------------------------------

  def lookup_form(self, word_deva: str) -> dict[tuple[str, ...], dict[str, int]]:
    """Return ``{marks_tuple: {source: freq}}`` for an inflected Devanagari word."""
    key = _normalize_lookup_key(word_deva)
    return self.form_accents.get(key, {})

  def lookup_stem(self, stem_deva: str) -> dict[tuple[str, ...], dict[str, int]]:
    key = _normalize_lookup_key(stem_deva)
    return self.stem_accents.get(key, {})

  def get_canonical_hyphenation(self, word_deva: str) -> str | None:
    key = _normalize_lookup_key(word_deva)
    if key in self.form_hyphens:
      return self.form_hyphens[key]
    return None

  def analyze_morph(self, word_deva: str) -> dict:
    """Fast cached morphological analysis combining ``vidyut.kosha`` + lexicon heuristics."""
    key = _normalize_lookup_key(word_deva)
    if key in self._morph_cache:
      return self._morph_cache[key]

    # Preserve homorganic nasals (`न्त`, `न्द`, `ञ्च`, `ङ्क`, `म्प`) for vidyut.kosha!
    clean_d = _join_virama_vowels(_ALL_ACCENT_MARKS_RE.sub("", word_deva).replace("-", "").replace("ऽ", "").strip())
    if clean_d.endswith("ं") and len(clean_d) >= 2:
      clean_d = clean_d[:-1] + "म्"
    slp = _deva_to_slp(clean_d)
    ents = _kosha_get_slp(slp)
    if not ents and "M" in slp:
      slp_ps = re.sub(r"M(?=[kKgG])", "N", slp)
      slp_ps = re.sub(r"M(?=[cCjJ])", "Y", slp_ps)
      slp_ps = re.sub(r"M(?=[wWqQ])", "R", slp_ps)
      slp_ps = re.sub(r"M(?=[tTdD])", "n", slp_ps)
      slp_ps = re.sub(r"M(?=[pPbB])", "m", slp_ps)
      if slp_ps != slp:
        ents = _kosha_get_slp(slp_ps)
        if ents:
          slp = slp_ps
    info: dict = {
      "slp": slp,
      "is_tinanta": False,
      "is_subanta": False,
      "is_krdanta": False,
      "is_avyaya": False,
      "has_non_krt_subanta": False,
      "has_non_voc_subanta": False,
      "is_stri_prathama_eka": False,
      "tin_entries": [],
      "sub_stems": [],
      "krt_entries": [],
      "voc_possible": False,
    }
    try:
      from vidyut.kosha import PadaEntry, PratipadikaEntry
    except Exception:
      self._morph_cache[key] = info
      return info

    seen_stems: set[str] = set()
    for e in ents:
      if isinstance(e, PadaEntry.Tinanta):
        info["is_tinanta"] = True
        d = e.dhatu_entry.dhatu
        info["tin_entries"].append({
          "prefixes": list(d.prefixes),
          "clean_text": e.dhatu_entry.clean_text,
          "gana": str(d.gana),
          "sanadi": [str(x) for x in d.sanadi],
          "prayoga": str(e.prayoga),
          "lakara": str(e.lakara),
          "purusha": str(e.purusha),
          "vacana": str(e.vacana),
        })
      elif isinstance(e, PadaEntry.Subanta):
        info["is_subanta"] = True
        vib = str(e.vibhakti)
        if vib == "samboDanam":
          info["voc_possible"] = True
        else:
          info["has_non_voc_subanta"] = True
        if str(e.linga) == "strI" and vib == "praTamA" and str(e.vacana) == "eka":
          info["is_stri_prathama_eka"] = True
        pe = e.pratipadika_entry
        if isinstance(pe, PratipadikaEntry.Krdanta):
          info["is_krdanta"] = True
          d = pe.dhatu_entry.dhatu
          info["krt_entries"].append({
            "prefixes": list(d.prefixes),
            "clean_text": pe.dhatu_entry.clean_text,
            "gana": str(d.gana),
            "sanadi": [str(x) for x in d.sanadi],
            "krt": str(pe.krt),
            "prayoga": str(pe.prayoga) if pe.prayoga else "",
            "lakara": str(pe.lakara) if pe.lakara else "",
            "vibhakti": vib,
          })
          st = e.lemma
          if st and st not in seen_stems:
            seen_stems.add(st)
            info["sub_stems"].append(st)
        else:
          info["has_non_krt_subanta"] = True
          st = e.lemma
          if st and st not in seen_stems:
            seen_stems.add(st)
            info["sub_stems"].append(st)
      if getattr(e, "is_avyaya", False):
        info["is_avyaya"] = True

    self._morph_cache[key] = info
    return info

  def project_stem_accents(self, word_deva: str) -> list[tuple[tuple[str, ...], str, str | None]]:
    """Project attested stem accents (MW, Macdonell, Lanman) onto an inflected Devanagari word.

    Returns list of ``(marks_tuple, provenance_str, hyphenated_word_or_none)``.
    """
    key = _normalize_lookup_key(word_deva)
    n_w = _fast_syllable_count(key)
    if n_w == 0:
      return []

    morph = self.analyze_morph(key)
    slp = morph["slp"]

    cand_stems_slp: list[str] = list(morph["sub_stems"])
    # Fast suffix-length lookup for Vedic/ŚB declension stems missing from vidyut.kosha
    L_slp = len(slp)
    for t_len, tail_map in _DECLENSION_TAILS_BY_LEN:
      if L_slp >= t_len + 2:
        fins = tail_map.get(slp[L_slp - t_len :])
        if fins:
          pre = slp[: L_slp - t_len]
          for fin in fins:
            st = pre + fin
            if st not in cand_stems_slp:
              cand_stems_slp.append(st)
    if slp not in cand_stems_slp:
      cand_stems_slp.append(slp)

    results: dict[tuple[str, ...], tuple[set[str], str | None]] = {}
    for st_slp in cand_stems_slp:
      st_deva = _slp_to_deva(st_slp)
      st_key = _normalize_lookup_key(st_deva)
      hits = self.stem_accents.get(st_key)
      if not hits:
        continue
      n_st = _fast_syllable_count(st_key)
      if n_st == 0 or n_st > n_w + 1:
        continue
      st_hyph = self.stem_hyphens.get(st_key)
      word_hyph: str | None = None
      if st_hyph and "-" in st_hyph:
        p0 = st_hyph.split("-", 1)[0]
        if key.startswith(p0) and len(key) > len(p0):
          cand_h = p0 + "-" + key[len(p0) :]
          if _is_valid_compound_hyphenation(cand_h, key):
            word_hyph = cand_h

      for st_marks, srcs in hits.items():
        acc_positions = [(idx, mk) for idx, mk in enumerate(st_marks) if mk]
        if len(acc_positions) != 1:
          continue
        acc_idx, acc_mk = acc_positions[0]
        if acc_idx < n_w:
          proj = tuple(acc_mk if i == acc_idx else "" for i in range(n_w))
          if acc_mk == "S" and not _syllable_has_jatya_glide(key, acc_idx):
            proj = tuple("U" if i == acc_idx else "" for i in range(n_w))
          src_set, old_h = results.setdefault(proj, (set(), word_hyph))
          src_set.update(srcs.keys())
          if word_hyph and not old_h:
            results[proj] = (src_set, word_hyph)
        # Weak-case oxytonic shift for consonant/monosyllabic stems (पा॰ ६.१.१६८ / ६.१.१७१)
        if acc_idx == n_st - 1 and n_w > n_st and (st_slp[-1] not in "aA" or n_st == 1):
          proj_end = tuple("U" if i == n_w - 1 else "" for i in range(n_w))
          src_set, old_h = results.setdefault(proj_end, (set(), word_hyph))
          src_set.update(srcs.keys())

    out: list[tuple[tuple[str, ...], str, str | None]] = []
    for mks, (srcs, hyph) in results.items():
      tags: list[str] = []
      if "MW_SB" in srcs:
        tags.append("*MW* ŚBr.")
      elif "MW" in srcs:
        tags.append("*MW*")
      if "Macdonell" in srcs:
        tags.append("*Macdonell*")
      if "Lanman" in srcs:
        tags.append("*Lanman*")
      out.append((mks, ", ".join(tags), hyph))
    return out

  def _get_slp_stems(self) -> frozenset[str]:
    if self._slp_stems is None:
      self._slp_stems = frozenset(
        _deva_to_slp(k) for k in self.stem_accents
      )
    return self._slp_stems

  def _matches_stem_slp_fast(self, slp_w: str) -> bool:
    stems = self._get_slp_stems()
    if slp_w in stems:
      return True
    L_slp = len(slp_w)
    for t_len, tail_map in _DECLENSION_TAILS_BY_LEN:
      if L_slp >= t_len + 2:
        fins = tail_map.get(slp_w[L_slp - t_len :])
        if fins:
          pre = slp_w[: L_slp - t_len]
          for fin in fins:
            if (pre + fin) in stems:
              return True
    return False

  def word_score_slp(self, slp_w: str) -> int:
    """Fast memoized O(1) frequency/validity score of an SLP1 token for the Sandhi-Inverting DP.

    Returns ``>= 20`` for true padapāṭha-attested words, ``5..12`` for unattested
    ``vidyut.kosha``/stem-projected words, and ``0`` for invalid/fused tokens.
    """
    if not slp_w:
      return 0
    cached = self._word_score_cache.get(slp_w)
    if cached is not None:
      return cached
    if slp_w in _NEVER_SINGLE_PADA_SLP:
      self._word_score_cache[slp_w] = 0
      return 0
    if slp_w in SB_FUNCTION_WORDS_SLP:
      self._word_score_cache[slp_w] = 1000
      return 1000
    sc = self.slp_vocab.get(slp_w, 0)
    if sc <= 0:
      slp_m = _slp_homorganic_to_anusvara(slp_w)
      if slp_m != slp_w:
        sc = self.slp_vocab.get(slp_m, 0)
    if sc > 0:
      res = 0 if (len(slp_w) <= 2 and sc < 5) else (sc + 25)
      self._word_score_cache[slp_w] = res
      return res
    if len(slp_w) <= 2:
      self._word_score_cache[slp_w] = 0
      return 0
    if any(slp_w.startswith(pf) and len(slp_w) >= len(pf) + 3 for pf in _FUSED_PREFIX_BLOCK_SLP):
      self._word_score_cache[slp_w] = 0
      return 0
    if _kosha_get_slp(slp_w):
      self._word_score_cache[slp_w] = 8
      return 8
    if self._matches_stem_slp_fast(slp_w):
      self._word_score_cache[slp_w] = 12
      return 12
    # Gati + ल्यप् gerunds missing from vidyut (`antarDAya`, `tiraskftya`, `puraskftya`, `prAdurBUya`)
    if slp_w.startswith(("antar", "tiras", "puras", "prAdur", "Avir", "punar")) and slp_w.endswith(
      ("DAya", "hftya", "kftya", "gatya", "etya", "dAya", "sTAya", "nIya", "BUya", "Srutya")
    ):
      self._word_score_cache[slp_w] = 40
      return 40
    try:
      from doc_curation.sanskrit.hyphenator.lexicon import word_count_slp1
      if word_count_slp1(slp_w) >= 4:
        self._word_score_cache[slp_w] = 6
        return 6
    except Exception:
      pass
    self._word_score_cache[slp_w] = 0
    return 0


_NEVER_SINGLE_PADA_SLP: frozenset[str] = frozenset({
  "cEva", "nEva", "nEnam", "nEnaM", "nAtra", "nAnyaH", "nAnyat", "nAparam",
  "etadDa", "tadu", "yadu", "yadve", "yadvA", "tadyat", "tadyad", "evAsya",
  "evAsmi", "evEtat", "evEtad", "evEzaH", "evEza", "tasmAdvA", "tatpraTamena",
  "vApaH", "tA", "gfhA", "no", "so", "yo", "aTAtaH", "aTEnam", "aTEtat",
  "At", "Im", "sIm", "hAH", "udA", "upA", "samA", "prA", "vyA", "aByA", "pratyA",
})
_FUSED_PREFIX_BLOCK_SLP: tuple[str, ...] = (
  "tat", "tad", "yat", "yad", "etad", "etat", "tasmAt", "tasmAd",
  "cEv", "nEv", "nEn", "evA", "evE", "yadv", "tadv",
)


_DECLENSION_TAILS_SLP: tuple[tuple[str, tuple[str, ...]], ...] = (
  ("AnAm", ("a", "A", "an")),
  ("ARAm", ("a", "A", "an")),
  ("eByaH", ("a",)),
  ("AByAm", ("a", "A")),
  ("AByaH", ("A",)),
  ("ABiH", ("A",)),
  ("asya", ("a",)),
  ("AyAH", ("A",)),
  ("AyAm", ("A",)),
  ("AyE", ("A",)),
  ("Aya", ("a",)),
  ("ena", ("a",)),
  ("eRa", ("a",)),
  ("ezu", ("a",)),
  ("Asu", ("A",)),
  ("ayA", ("A",)),
  ("ayoH", ("a", "A")),
  ("Ani", ("a", "as", "an")),
  ("ARi", ("a", "as", "an")),
  ("aBiH", ("as",)),
  ("iByaH", ("i",)),
  ("iBiH", ("i",)),
  ("IByaH", ("I",)),
  ("IByAm", ("I",)),
  ("IBiH", ("I",)),
  ("Izu", ("I",)),
  ("InAm", ("i", "I")),
  ("izu", ("i",)),
  ("inA", ("i",)),
  ("aye", ("i",)),
  ("ayaH", ("i",)),
  ("uByaH", ("u",)),
  ("uBiH", ("u",)),
  ("UnAm", ("u", "U")),
  ("uzu", ("u",)),
  ("unA", ("u",)),
  ("ave", ("u",)),
  ("avaH", ("u",)),
  ("tAram", ("tf",)),
  ("tAraH", ("tf",)),
  ("tArO", ("tf",)),
  ("tFR", ("tf",)),
  ("tfBiH", ("tf",)),
  ("tfByaH", ("tf",)),
  ("tFRAm", ("tf",)),
  ("aMsaH", ("as", "yas")),
  ("AMsaH", ("as", "yas")),
  ("AMsam", ("as", "yas")),
  ("AMsO", ("as", "yas")),
  ("AMsi", ("as",)),
  ("IyAMsaH", ("Iyas",)),
  ("IyAMsam", ("Iyas",)),
  ("IyasaH", ("Iyas",)),
  ("IyasA", ("Iyas",)),
  ("asu", ("at", "as", "an")),
  ("atsu", ("at",)),
  ("adBiH", ("at",)),
  ("antaH", ("at",)),
  ("antam", ("at",)),
  ("antaM", ("at",)),
  ("AH", ("a", "A", "as")),
  ("An", ("a",)),
  ("At", ("a",)),
  ("Am", ("A",)),
  ("EH", ("a",)),
  ("aH", ("a", "as")),
  ("am", ("a",)),
  ("iH", ("i",)),
  ("im", ("i",)),
  ("In", ("i",)),
  ("IH", ("I",)),
  ("uH", ("u",)),
  ("um", ("u",)),
  ("Un", ("u",)),
  ("eH", ("i",)),
  ("oH", ("u",)),
  ("A", ("a", "A", "tf")),
  ("e", ("a", "A")),
  ("O", ("a",)),
  ("I", ("I", "i")),
  ("Im", ("I",)),
  ("yAH", ("I", "i")),
  ("yAm", ("I", "i")),
  ("yE", ("I", "i")),
  ("yA", ("I", "i")),
  ("a", ("a",)),
)


def _build_declension_tails_by_len() -> tuple[tuple[int, dict[str, tuple[str, ...]]], ...]:
  by_len: dict[int, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
  for tail, fins in _DECLENSION_TAILS_SLP:
    for fin in fins:
      if fin not in by_len[len(tail)][tail]:
        by_len[len(tail)][tail].append(fin)
  return tuple(
    (t_len, {t: tuple(fs) for t, fs in tmap.items()})
    for t_len, tmap in sorted(by_len.items(), reverse=True)
  )


_DECLENSION_TAILS_BY_LEN: tuple[tuple[int, dict[str, tuple[str, ...]]], ...] = _build_declension_tails_by_len()


# ---------------------------------------------------------------------------
# Component 2: Clean VP Builder & Sandhi-Inverting Pada Splitter
# ---------------------------------------------------------------------------


def parse_sb_markdown_clusters(markdown_text: str) -> list[KandikaCluster]:
  """Parse a Śatapatha Brāhmaṇa Markdown file into ordered :class:`KandikaCluster` units.

  Correctly handles all corpus layout nuances:
  - Double-spaced headings in Kāṇḍa 12 (``##  ०१``).
  - Multiple ``विश्वास-प्रस्तुतिः`` blocks under one ``##`` heading (``02/04/1.md``).
  - Skipping unaccented intro blocks before the first ``##`` (``हरिः-ओ३म्।``, ``१०.6.३``).
  - Ignoring ``मूलम् - Makoto`` placed after ``Eggeling`` in Kāṇḍa 12.
  """
  clusters: list[KandikaCluster] = []
  parts = re.split(r"(?=\n##[ \t]+)", markdown_text)
  for part in parts[1:]:
    m_hdr = re.match(r"\n##[ \t]+([^\n]+)", part)
    if not m_hdr:
      continue
    heading = re.sub(r"\s+", " ", m_hdr.group(1)).strip()
    blocks = [(m.group(1).strip(), m.group(2).strip()) for m in DETAILS_RE.finditer(part)]
    # Partition blocks into sub-clusters starting at each `विश्वास-प्रस्तुतिः` block.
    vp_indices = [i for i, (h, _) in enumerate(blocks) if h.startswith("विश्वास-प्रस्तुतिः")]
    for sub_idx, start_i in enumerate(vp_indices):
      end_i = vp_indices[sub_idx + 1] if sub_idx + 1 < len(vp_indices) else len(blocks)
      sub_blocks = blocks[start_i:end_i]
      vp_sum, vp_body = sub_blocks[0]
      weber = shri = visvara = sayana = harisvami = eggeling = ""
      for bh, bb in sub_blocks[1:]:
        if bh == "मूलम् - Weber" and not weber:
          weber = bb
        elif bh == "मूलम् - श्रीधरादि" and not shri:
          shri = bb
        elif bh == "मूलम् - विस्वरम्" and not visvara:
          visvara = bb
        elif bh == "सायणः" and not sayana:
          sayana = bb
        elif bh == "हरिस्वामी" and not harisvami:
          harisvami = bb
        elif bh == "Eggeling" and not eggeling:
          eggeling = bb
      clusters.append(
        KandikaCluster(
          heading=heading,
          sub_idx=sub_idx,
          vp_summary=vp_sum,
          vp_body=vp_body,
          is_already_us=has_us_accents(vp_body),
          weber=weber,
          shri=shri,
          visvara=visvara,
          sayana=sayana,
          harisvami=harisvami,
          eggeling=eggeling,
        )
      )
  return clusters


def _strip_visvara_preamble(visvara: str, ref_clean: str) -> str:
  """Strip section title preambles, inline citations, and trailing ``॥ N ॥`` from ``मूलम् - विस्वरम्``."""
  s = re.sub(r"(?m)^\[\^[^\]]+\]:.*$", "", visvara)
  s = re.sub(r"\[\^[^\]]+\]", "", s)
  s = s.replace("**", "")
  # Remove inline parenthetical references containing digits e.g. `(१ अ. ५ मं.)`
  s = re.sub(r"\([^)]*[०-९\d][^)]*\)", "", s)
  # Normalize trailing `॥ १ ॥` -> `॥`
  s = re.sub(r"॥\s*[०-९\d]+\s*॥\s*$", "॥", s.strip())
  s = re.sub(r"\s*[०-९\d]+\s*॥\s*$", " ॥", s.strip())
  s = s.strip()

  ref_slp = to_norm_slp(ref_clean)
  if not ref_slp:
    return s
  anchor = ref_slp[: min(14, len(ref_slp))]

  # Try trimming leading lines / danda-delimited title segments until SLP1 prefix matches ref_clean.
  vis_slp = to_norm_slp(s)
  if vis_slp.startswith(anchor[: min(8, len(anchor))]):
    return s

  # Candidate cut offsets: start of each line and after each `।` / `॥`
  cuts = [0]
  for m in re.finditer(r"(?:\n|[।॥])\s*", s):
    cuts.append(m.end())
  for cut in cuts:
    if cut >= len(s):
      continue
    cand = s[cut:].strip()
    c_slp = to_norm_slp(cand)
    if c_slp.startswith(anchor[: min(8, len(anchor))]):
      return cand
  return s


def _pause_norm_slp(slp: str) -> str:
  """Normalize pause-vs-continuous visarga/stop/nasal sandhi differences to verify word identity."""
  s = slp
  s = re.sub(r"aH(?=[gGNjJYqQRdDnbBmyrlvh])", "o", s)
  s = re.sub(r"AH(?=[aAiIuUfFeEoOgGNjJYqQRdDnbBmyrlvh])", "A", s)
  s = re.sub(r"H(?=[cC])", "S", s)
  s = re.sub(r"H(?=[wW])", "z", s)
  s = re.sub(r"H(?=[tT])", "s", s)
  s = re.sub(r"H(?=[gGNjJYqQRdDnbBmyrlvhaAiIuUfFeEoO])", "r", s)
  s = re.sub(r"t(?=[gGdDbByrvhaAiIuUfFeEoO])", "d", s)
  s = re.sub(r"m(?=[kKgGcCjJwWqQtTdDpPbBmyrlvSzsh])", "M", s)
  s = s.replace("H", "")
  return canonical_geminates(s)


_VISVARA_QUOTE_ITI_BREAK_RE = re.compile(r"[ेोैौािीुू][\"”’']\s*[-—–]?\s*इति")
_VISVARA_BOGUS_AA_AVAGRAHA_RE = re.compile(r"ा\s*ऽ")


def _clean_shri_geminates(text: str) -> str:
  """Normalize Śrīdharādi archaic doubled ``व्व`` (``व्वयम्``, ``व्वत्``, ``व्वै``, ``सर्व्वे``, ``अग्निर्व्वै``) -> ``व``."""
  return re.sub(r"व्व", "व", text)


def _clean_visvara_for_sandhi(visvara: str, ref_clean: str) -> str:
  if not visvara:
    return ""
  v_trim = _strip_visvara_preamble(visvara, ref_clean)
  v_trim = re.sub(r"['‘’]", " ", v_trim)
  return normalize_sb_orthography(v_trim)


def build_clean_vp_base(weber: str, shri: str, visvara: str) -> tuple[str, str]:
  """Build a clean, orthographically normalized, sandhi-preserving unaccented ``विश्वास-प्रस्तुतिः`` base.

  Uses 3-witness consensus across ``visvara``, ``weber``, and ``shri`` to avoid solo OCR typos
  (e.g. visvara ``प्रातनों``/``नैवाश्रीयात्`` when W==S, or Weber ``प्रजापतिह्``/``दृषदुपल``/``वृक्षाग्निः`` when S==V),
  and rejects ``visvara`` when it breaks vowel sandhi via quotes before ``इति`` or inserts bogus ``आ ऽ`` avagrahas.
  Returns ``(vp_clean, base_source)`` where ``base_source`` is ``'visvara'``, ``'weber'``, or ``'shri'``.
  """
  w_clean = normalize_sb_orthography(strip_weber_footnotes(weber)) if weber else ""
  s_clean = _clean_shri_geminates(normalize_sb_orthography(strip_shri_pratika(shri))) if shri else ""
  if w_clean.startswith("ॐ॥") and s_clean and not s_clean.startswith("ॐ"):
    w_clean = w_clean[2:].strip()

  n_w = _fast_syllable_count(w_clean) if w_clean else 0
  n_s = _fast_syllable_count(s_clean) if s_clean else 0
  wp_n = _pause_norm_slp(to_norm_slp(w_clean)) if w_clean else ""
  sp_n = _pause_norm_slp(to_norm_slp(s_clean)) if s_clean else ""

  ref_clean = w_clean or s_clean
  vp_n = ""
  if visvara:
    v_trim = _strip_visvara_preamble(visvara, ref_clean)
    has_bad_visvara_sandhi = bool(
      "ऽऽ" in v_trim
      or _VISVARA_BOGUS_AA_AVAGRAHA_RE.search(v_trim)
      or _VISVARA_QUOTE_ITI_BREAK_RE.search(v_trim)
    )
    v_trim = re.sub(r"['‘’]", " ", v_trim)
    v_clean = normalize_sb_orthography(v_trim)
    n_v = _fast_syllable_count(v_clean)
    vp_n = _pause_norm_slp(to_norm_slp(v_clean)) if v_clean else ""
    ws_agree = bool(wp_n and sp_n and (wp_n == sp_n or difflib.SequenceMatcher(None, wp_n, sp_n).ratio() >= 0.996))
    if not has_bad_visvara_sandhi and n_v and (n_v == n_w or n_v == n_s):
      sim_w = difflib.SequenceMatcher(None, vp_n, wp_n).ratio() if (vp_n and wp_n) else 0.0
      sim_s = difflib.SequenceMatcher(None, vp_n, sp_n).ratio() if (vp_n and sp_n) else 0.0
      v_matches_ws = (not ws_agree) or (vp_n == wp_n) or (vp_n == sp_n) or (max(sim_w, sim_s) >= 0.996)
      if v_matches_ws and (vp_n == wp_n or vp_n == sp_n or max(sim_w, sim_s) >= 0.985):
        return _format_vp_clauses(v_clean), "visvara"

  # Fallback between Weber and Śrīdharādi: prefer whichever agrees closer with Visvara & has fewer OCR glitches!
  if w_clean and s_clean:
    def _ocr_penalty(txt: str) -> float:
      pen = 0.0
      if re.search(r"ह्(?:\s|[।॥]|$)", txt):
        pen += 0.05  # Weber `प्रजापतिह्` translit glitch
      if re.search(r"श्कशक|त्तत|चकृ", txt):
        pen += 0.03
      return pen

    w_score = (difflib.SequenceMatcher(None, wp_n, vp_n).ratio() if vp_n else 0.99) - _ocr_penalty(w_clean)
    s_score = (difflib.SequenceMatcher(None, sp_n, vp_n).ratio() if vp_n else 0.98) - _ocr_penalty(s_clean)
    if s_score > w_score + 0.004:
      s_fmt = re.sub(r"॥\s*(?=.+॥)", " ", s_clean)
      return _format_vp_clauses(s_fmt), "shri"

  if w_clean:
    w_fmt = re.sub(r"॥\s*(?=.+॥)", " ", w_clean)
    return _format_vp_clauses(w_fmt), "weber"
  s_fmt = re.sub(r"॥\s*(?=.+॥)", " ", s_clean)
  return _format_vp_clauses(s_fmt), "shri"


def _format_vp_clauses(text: str) -> str:
  """Normalize spaces, convert trailing ASCII dashes to `` — ``, and add Markdown line breaks after ``।`` / ``॥``."""
  s = re.sub(r"(?<=[\u0900-\u097f])-(?=\s)", " —", text)
  s = re.sub(r"(?<=\s)-(?=[\u0900-\u097f])", "— ", s)
  s = re.sub(r"\s+", " ", s).strip()
  s = re.sub(r"\s*।\s*(?!$)", " ।  \n", s)
  s = re.sub(r"\s*॥\s*(?!$)", " ॥  \n", s)
  s = re.sub(r"[ \t]+\n", "  \n", s)
  return s.strip()


# ---------------------------------------------------------------------------
# Vedic Sandhi-Inverting Word-Lattice DP Splitter
# ---------------------------------------------------------------------------

# Inverse vowel-sandhi table: surface vowel -> list of (left_ending_vowel, right_initial_vowel)
_INV_VOWEL_SANDHI: dict[str, tuple[tuple[str, str], ...]] = {
  "A": (("a", "a"), ("a", "A"), ("A", "a"), ("A", "A"), ("AH", "a"), ("AH", "A")),
  "I": (("i", "i"), ("i", "I"), ("I", "i"), ("I", "I")),
  "U": (("u", "u"), ("u", "U"), ("U", "u"), ("U", "U")),
  "F": (("f", "f"),),
  "e": (("a", "i"), ("a", "I"), ("A", "i"), ("A", "I"), ("e", "a")),
  "o": (("a", "u"), ("a", "U"), ("A", "u"), ("A", "U"), ("aH", "a"), ("o", "a")),
  "E": (("a", "e"), ("a", "E"), ("A", "e"), ("A", "E")),
  "O": (("a", "o"), ("a", "O"), ("A", "o"), ("A", "O")),
}


_PRONOMINAL_NEVER_SPLIT_SLP: frozenset[str] = frozenset({
  "etat", "etad", "etam", "etAn", "etAH", "etA", "etAm", "etABiH", "etAByaH", "etAByAm",
  "etena", "etasmAt", "etasmE", "etasya", "etasmin", "etAni", "ete", "etayA", "etasyE",
  "etasyAH", "etasyAm", "etayoH", "eteByaH", "etezAm", "etezu", "ezaH", "ezA", "eza",
  "enam", "enAm", "enAn", "enAni", "ene", "enayoH", "eva", "evam", "evaM",
  "ekaH", "ekA", "ekam", "ekena", "ekasya", "ekasmAt", "ekasmE", "ekasmin", "eke",
})


def _strip_leading_upasargas_tinanta(slp_w: str, lex: UnifiedVedicLexicon) -> list[str] | None:
  """If ``slp_w`` is a prefixed finite verb (``तिङन्त``), split it into ``[upa_1, ..., verb]`` in Devanagari.

  Returns ``None`` if ``slp_w`` is a simplex verb, a nominal, an adverb, or a ``गतिकृदन्त``.
  """
  if slp_w in lex._prefixed_tin_cache:
    return lex._prefixed_tin_cache[slp_w]
  res = _strip_leading_upasargas_tinanta_uncached(slp_w, lex)
  lex._prefixed_tin_cache[slp_w] = res
  return res


def _strip_leading_upasargas_tinanta_uncached(slp_w: str, lex: UnifiedVedicLexicon) -> list[str] | None:
  if slp_w in _PRONOMINAL_NEVER_SPLIT_SLP:
    return None
  deva_w = _slp_to_deva(slp_w)
  if deva_w in SIMPLEX_TINANTA_ALLOWLIST:
    return None
  # Never split `-तः` directional/ablative adverbs (`उत्तरतः`, `अन्तरतः`, `अभितः`, `परितः`, `सर्वतः`) as 3du verbs!
  if deva_w.endswith(("उत्तरतः", "अन्तरतः", "दक्षिणतः", "पुरतः", "पृष्ठतः", "अभितः", "परितः", "सर्वतः", "उभयतः", "अन्यतः", "अग्रतः", "मध्यतः", "पश्चात्", "अधस्तात्", "उपरिष्टात्")):
    return None

  morph = lex.analyze_morph(deva_w)
  if morph["is_avyaya"]:
    return None
  tins = morph["tin_entries"]
  krts = morph["krt_entries"]

  # Prefer kṛdanta over rare conditional lṛṅ (e.g. `upEzyan` = Satf participle, not lṛṅ)
  if krts and tins and all(t["lakara"] == "lf~N" for t in tins):
    return None
  # If a word is a valid subanta (`उपवसथः`, `उद्यतम्`, `संहितम्`) and ONLY parses as 2nd-person dual tinanta (`maDyama`+`dvi`)
  # or periphrastic future (`lu~w`, e.g. `सविता`), do NOT split! (Preserve real 3du verbs like `उपभवतः`!)
  if morph["is_subanta"] and tins and all(
    (t["purusha"] == "maDyama" and t["vacana"] == "dvi") or t["lakara"] == "lu~w"
    for t in tins
  ):
    return None
  # If parsed ONLY as subanta/kṛdanta (gerund/participle/infinitive/action noun), NEVER split upasarga
  if morph["is_subanta"] and not tins:
    if not _is_vedic_prefixed_tinanta_fallback(slp_w, lex):
      return None

  if tins:
    if any(not t["prefixes"] for t in tins):
      return None
    for t in sorted(tins, key=lambda x: len(x["prefixes"])):
      res = _split_by_prefix_list(slp_w, t["prefixes"], lex)
      if res is not None:
        return res

  return _is_vedic_prefixed_tinanta_fallback(slp_w, lex)


def _split_by_prefix_list(
  slp_w: str, prefixes: Sequence[str], lex: UnifiedVedicLexicon, *, expect_krt: bool = False
) -> list[str] | None:
  """Peel exact ``vidyut`` upasarga prefixes off ``slp_w`` recursively and return ``[upa_deva, ..., verb_deva]``."""
  if not prefixes:
    return None
  norm_pfs: list[tuple[str, str]] = []
  for pf in prefixes:
    pf_norm = "A" if pf == "AN" else ("ut" if pf == "ud" else ("niH" if pf in ("nir", "nis") else ("duH" if pf in ("dur", "dus") else pf)))
    upa_deva = UPASARGA_SLP_TO_DEVA.get(pf, UPASARGA_SLP_TO_DEVA.get(pf_norm))
    if not upa_deva:
      return None
    norm_pfs.append((pf_norm, upa_deva))

  orig_deva = sanscript.transliterate(slp_w, sanscript.SLP1, sanscript.DEVANAGARI)

  def _dfs(idx: int, cur_slp: str) -> str | None:
    pf_norm, _ = norm_pfs[idx]
    is_last = idx == len(norm_pfs) - 1
    if is_last:
      rem = _peel_one_upasarga_slp(cur_slp, pf_norm, is_last_prefix=True, lex=lex, expect_krt=expect_krt)
      if rem and len(rem) >= 2:
        return rem
      return None
    all_rems = _peel_one_upasarga_slp(cur_slp, pf_norm, is_last_prefix=False, lex=lex, expect_krt=expect_krt, return_all=True)
    if not all_rems:
      return None
    nxt_pf = norm_pfs[idx + 1][0]
    # Try candidates that directly start with the next prefix's initial letter first!
    ordered = sorted(all_rems, key=lambda r: (0 if r.startswith(nxt_pf[0]) else 1))
    for r in ordered:
      if len(r) < 3:
        continue
      res = _dfs(idx + 1, r)
      if res is not None:
        return res
    return None

  verb_slp = _dfs(0, slp_w)
  if not verb_slp or len(verb_slp) < 2:
    return None
  deva_upas = [u for _, u in norm_pfs]
  verb_deva = sanscript.transliterate(verb_slp, sanscript.SLP1, sanscript.DEVANAGARI)
  cands = deva_upas + [verb_deva]
  ok, _, _, _ = verify_mantra_sandhi(cands, orig_deva)
  if ok:
    return cands
  return None


def _peel_one_upasarga_slp(
  slp_w: str,
  pf: str,
  *,
  is_last_prefix: bool,
  lex: UnifiedVedicLexicon,
  expect_krt: bool = False,
  return_all: bool = False,
):
  """Undo sandhi between upasarga ``pf`` (SLP1) and the remaining verb stem/next prefix."""
  cands: list[str] = []
  if pf == "sam":
    for p_surf in ("sam", "saM", "san", "saN", "saY", "saR"):
      if slp_w.startswith(p_surf) and len(slp_w) > len(p_surf) + 1:
        cands.append(slp_w[len(p_surf) :])
  elif pf == "ut":
    for p_surf in ("ut", "ud", "uc", "uj", "uw", "uq", "un", "ul"):
      if slp_w.startswith(p_surf) and len(slp_w) > len(p_surf) + 1:
        rest = slp_w[len(p_surf) :]
        cands.append(rest)
        if p_surf == "uc" and rest.startswith("C"):
          cands.append("S" + rest[1:])
        if p_surf == "ud" and rest.startswith("D"):
          cands.append("h" + rest[1:])
        if p_surf == "ut" and rest.startswith(("t", "T")):
          cands.append("s" + rest)  # उत् + स्था -> उत्था
  elif pf in ("niH", "duH"):
    base = pf[:-1]
    for p_surf in (base + "r", base + "s", base + "S", base + "z", base + "H"):
      if slp_w.startswith(p_surf) and len(slp_w) > len(p_surf) + 1:
        cands.append(slp_w[len(p_surf) :])
    # nir + r- -> nIr-
    if pf == "niH" and slp_w.startswith("nIr") and len(slp_w) > 4:
      cands.append(slp_w[2:])
  elif pf == "A":
    if slp_w.startswith("A") and len(slp_w) > 2:
      cands.append(slp_w[1:])
      cands.append("a" + slp_w[1:])
      cands.append("A" + slp_w[1:])
    elif slp_w.startswith("e") and len(slp_w) > 2:
      cands.extend(["i" + slp_w[1:], "I" + slp_w[1:]])
    elif slp_w.startswith("o") and len(slp_w) > 2:
      cands.extend(["u" + slp_w[1:], "U" + slp_w[1:]])
    elif slp_w.startswith("E") and len(slp_w) > 2:
      cands.extend(["e" + slp_w[1:], "E" + slp_w[1:]])
  elif pf[-1] in ("a", "A"):
    stem = pf[:-1]
    if slp_w.startswith(pf) and len(slp_w) > len(pf) + 1:
      rest = slp_w[len(pf) :]
      cands.append(rest)
      # Undo ṇatva after pra/parA (प्रणयति -> प्र + नयति / णयति)
      if pf in ("pra", "parA") and rest.startswith("R"):
        cands.append("n" + rest[1:])
    if slp_w.startswith(stem) and len(slp_w) > len(stem) + 2:
      v = slp_w[len(stem)]
      tail = slp_w[len(stem) + 1 :]
      if v == "A":
        cands.extend(["a" + tail, "A" + tail])
      elif v == "e":
        cands.extend(["i" + tail, "I" + tail])
      elif v == "o":
        cands.extend(["u" + tail, "U" + tail])
      elif v == "E":
        cands.extend(["e" + tail, "E" + tail])
      elif v == "O":
        cands.extend(["o" + tail, "O" + tail])
      elif v == "a" and tail.startswith("r"):
        cands.append("f" + tail[1:])
  elif pf[-1] in ("i", "u"):
    stem = pf[:-1]
    semi = "y" if pf[-1] == "i" else "v"
    long_v = "I" if pf[-1] == "i" else "U"
    if slp_w.startswith(pf) and len(slp_w) > len(pf) + 1:
      rest = slp_w[len(pf) :]
      cands.append(rest)
      # Undo ṣatva/ṇatva (निषेदुः -> नि + सेदुः, परिस्तृणाति, अभिषिञ्चति)
      if rest.startswith("z"):
        cands.append("s" + rest[1:])
        if rest.startswith("zw"):
          cands.append("st" + rest[2:])
        if rest.startswith("zW"):
          cands.append("sT" + rest[2:])
      if pf == "pari" and rest.startswith("R"):
        cands.append("n" + rest[1:])
    if slp_w.startswith(stem + semi) and len(slp_w) > len(stem) + 2 and slp_w[len(stem) + 1] in SLP_VOWELS:
      cands.append(slp_w[len(stem) + 1 :])
    if slp_w.startswith(stem + long_v) and len(slp_w) > len(stem) + 2:
      cands.extend([pf[-1] + slp_w[len(stem) + 1 :], long_v + slp_w[len(stem) + 1 :]])

  if not cands:
    return [] if return_all else None
  uniq = list(dict.fromkeys(cands))
  if return_all:
    return uniq
  if not is_last_prefix:
    return uniq[0]

  # Pick the best valid simplex verb (or simplex kṛdanta when `expect_krt=True`)!
  best_cand: str | None = None
  best_score = -1
  for c in uniq:
    sc = 0
    ents = _kosha_get_slp(c)
    try:
      from vidyut.kosha import PadaEntry
      if expect_krt:
        if any(isinstance(e, (PadaEntry.Subanta, PadaEntry.Avyaya)) for e in ents):
          sc += 100
      else:
        if any(isinstance(e, PadaEntry.Tinanta) and not e.dhatu_entry.dhatu.prefixes for e in ents):
          sc += 100
    except Exception:
      pass
    if c in lex.slp_vocab or _slp_homorganic_to_anusvara(c) in lex.slp_vocab:
      sc += 20 + min(lex.slp_vocab.get(c, lex.slp_vocab.get(_slp_homorganic_to_anusvara(c), 0)), 50)
    # Prefer un-retroflexed `n`/`s` over `R`/`z`, and plain vowel `e`/`o` over vṛddhi `E`/`O` on ties
    if c.startswith(("n", "s", "e", "o", "a", "i", "u")):
      sc += 2
    if sc > best_score:
      best_score = sc
      best_cand = c
  return best_cand


_VEDIC_FINITE_ENDINGS_SLP: tuple[str, ...] = (
  "ati", "ate", "anti", "ante", "asi", "ase", "Ami", "AmaH", "Amahe", "AmahE",
  "atu", "atAm", "antu", "antAm", "asva", "aDvam", "Ani",
  "et", "eta", "eyuH", "eran", "It", "yAt", "yAm", "yAma",
  "sya", "syati", "syate", "syanti", "syante", "syAmi", "syAmaH",
  "noti", "nute", "nuvanti", "nAti", "nIte", "nanti", "RAti", "RIte", "Ranti",
  "Ite", "Iyate", "Iyante", "yate", "yante",
  "aH", "at", "an", "ata", "anta", "An", "Am",
  "Aha", "AhuH", "uvAca", "UcuH", "cakAra", "baBUva", "dadfSuH", "rarakzuH",
  "viduH", "mene", "Sete", "Serate", "jagAma", "daduH", "daDuH", "tasTuH",
  "IDe", "iDe", "eDe", "Ihe", "Ize", "Iqe", "Uce", "ire", "Aste", "Asate",
)


def _is_vedic_prefixed_tinanta_fallback(slp_w: str, lex: UnifiedVedicLexicon) -> list[str] | None:
  """Fallback splitter for Vedic prefixed finite verbs missing from classical ``vidyut.kosha``."""
  if len(slp_w) < 4 or not slp_w.endswith(_VEDIC_FINITE_ENDINGS_SLP):
    return None
  # Reject obvious nominal/kṛdanta endings
  if slp_w.endswith(("aH", "am", "ena", "eRa", "Aya", "asya", "ezu", "AnAm", "ARAm", "mARaH", "mARam", "mAnaH", "mAnam")):
    return None
  for pf in ("prati", "pari", "aBi", "aDi", "anu", "apa", "ava", "ati", "api", "upa", "parA", "sam", "pra", "niH", "duH", "ut", "vi", "ni", "A"):
    rem = _peel_one_upasarga_slp(slp_w, pf, is_last_prefix=True, lex=lex)
    if not rem or len(rem) < 3:
      continue
    rem_deva = _slp_to_deva(rem)
    # Require the stripped verb to be a genuine simplex Tinanta or Vedic subjunctive/perfect finite form!
    rem_m = lex.analyze_morph(rem_deva)
    is_simplex_tin = any(not t["prefixes"] for t in rem_m["tin_entries"])
    is_vedic_let = rem.endswith(("An", "At", "Ati", "As")) and len(rem) >= 4 and (
      any(not t["prefixes"] for t in lex.analyze_morph(_slp_to_deva(rem[:-2] + "ati"))["tin_entries"])
    )
    if is_simplex_tin or is_vedic_let or rem in (
      "sfjate", "sfjante", "stfRAti", "stfRanti", "Sete", "Serate", "yanti", "eti", "emi", "iyAt", "ayAni",
      "Aha", "AhuH", "uvAca", "UcuH", "mantrayAmahE", "yajAmahE",
      "IDe", "iDe", "eDe", "Ihe", "Ize", "Iqe", "Uce", "Aste", "Asate",
    ):
      upa_deva = UPASARGA_SLP_TO_DEVA[pf]
      ok, _, _, _ = verify_mantra_sandhi(
        [upa_deva, rem_deva], _slp_to_deva(slp_w)
      )
      if ok:
        return [upa_deva, rem_deva]
  return None


def _clean_pada_orthography(deva_w: str) -> str:
  """Normalize trailing anusvāra ``ं`` -> ``म्`` and voiced final stops ``द्/ड्/ग्/ब्`` -> ``त्/ट्/क्/प्``."""
  w = _ALL_ACCENT_MARKS_RE.sub("", deva_w).strip()
  if w.endswith("ं") and len(w) >= 2:
    w = w[:-1] + "म्"
  elif w.endswith("द्") and len(w) >= 3:
    w = w[:-2] + "त्"
  elif w.endswith("ड्") and len(w) >= 3:
    w = w[:-2] + "ट्"
  elif w.endswith("ग्") and len(w) >= 3:
    w = w[:-2] + "क्"
  elif w.endswith("ब्") and len(w) >= 3:
    w = w[:-2] + "प्"
  return w


def _hyphenate_compound_pada(deva_w: str, lex: UnifiedVedicLexicon) -> str:
  """Insert canonical compound ``-`` hyphens inside a single nominal/kṛdanta pada (never splitting into 2 bullets)."""
  clean_w = _clean_pada_orthography(deva_w)
  bare = _normalize_lookup_key(clean_w)
  if "-" in clean_w or bare in _NEVER_HYPHENATE_WORDS:
    return clean_w
  # 1. Canonical attested padapāṭha hyphenation (RV/AV ऽ, TA पद-पाठः)
  ch = lex.get_canonical_hyphenation(bare)
  if ch and "-" in ch and _is_valid_compound_hyphenation(ch, bare):
    return ch
  # 2. Stem hyphenation from MW / Macdonell
  for _, _, h in lex.project_stem_accents(bare):
    if h and "-" in h and _is_valid_compound_hyphenation(h, bare):
      ok, _, _, _ = verify_mantra_sandhi([h], clean_w)
      if ok:
        return h
  # 3. Prefixed kṛdanta from vidyut.kosha (`उप-एष्यन्`, `अभि-ईक्षमाणः`, `सं-स्थिते`, `उत्-सिच्य`, `अति-हृत्य`, `उद्-यन्तुम्`)
  # Guard against pronouns (`एतम्`, `विश्वस्य`), plain nouns/adverbs (`आहवनीयम्`, `उत्तरेण`), and bogus `आ-आ`/`उत्-स्त` splits!
  if bare not in ("आहवनीयम्", "आहवनीयः", "आहवनीये", "आहवनीयात्", "उत्तरेण", "उत्तरतः", "उत्तराम्", "उत्तरम्", "उत्तरः") and not bare.startswith("विश्व"):
    morph = lex.analyze_morph(bare)
    if morph["slp"] not in _PRONOMINAL_NEVER_SPLIT_SLP and morph["krt_entries"]:
      pref_krt = [
        k for k in morph["krt_entries"]
        if k["prefixes"]
        and any(t in k["krt"] for t in ("ktvA", "tumun", "tumu~n", "kta", "Satf", "SAnac", "cAnaS"))
        # Never turn a genitive `-स्य` non-kṛdanta noun/pronoun (`विश्वस्य`) into a `ktvA` gerund (`वि-श्वस्य`)!
        and not (morph["has_non_krt_subanta"] and "ktvA" in k["krt"])
      ]
      if pref_krt and not any(not k["prefixes"] for k in morph["krt_entries"]):
        slp = morph["slp"]
        for k in sorted(pref_krt, key=lambda x: len(x["prefixes"])):
          parts = _split_by_prefix_list(slp, k["prefixes"], lex, expect_krt=True)
          if parts and len(parts) >= 2:
            if parts[0] == "आ" and parts[1].startswith("आ"):
              continue
            if parts[0] == "उत्" and parts[1].startswith("स्त") and "स्त" not in clean_w:
              continue
            cand = "-".join(parts)
            if _is_valid_compound_hyphenation(cand, bare):
              ok, _, _, _ = verify_mantra_sandhi([cand], clean_w)
              if ok:
                return cand
  return clean_w


def _generate_chunk_transitions(
  slp: str,
  pos: int,
  req_prefix: str,
  lex: UnifiedVedicLexicon,
  next_tok_starts_vowel: bool,
  next_tok_starts_voiced: bool,
  next_tok_is_avagraha: bool,
  is_end_of_clause: bool,
  next_tok_starts_nasal: bool = False,
) -> list[tuple[int, str, str, float]]:
  """Generate candidate inverse-sandhi word transitions from ``(pos, req_prefix)`` in SLP1 chunk ``slp``.

  Returns list of ``(next_pos, next_req_prefix, cand_word_slp, transition_cost)``.
  """
  L = len(slp)
  out: list[tuple[int, str, str, float]] = []

  def _eval_word(w_slp: str, extra_pen: float = 0.0) -> float | None:
    if not w_slp:
      return None
    if len(w_slp) == 1 and w_slp not in ("A", "u"):
      return None
    sc = lex.word_score_slp(w_slp)
    if sc <= 0:
      if len(w_slp) >= 5 and w_slp.endswith(_VEDIC_FINITE_ENDINGS_SLP):
        if w_slp in lex._prefixed_tin_cache:
          pt = lex._prefixed_tin_cache[w_slp]
        else:
          pt = _strip_leading_upasargas_tinanta(w_slp, lex)
          lex._prefixed_tin_cache[w_slp] = pt
        if pt is not None:
          sc = 60
        else:
          return None
      else:
        return None
    # Calibrated costs: ŚB function words (2.3), padapāṭha-attested words (2.8..3.8), vidyut/stem words (5.4)
    # so valid single vidyut/stem words (`अनृतात्`, `उपैष्यन्`, `रभेते`) are NEVER shredded while 3-4 fused function words split cleanly!
    if sc >= 900:
      return 2.3 + extra_pen
    if sc >= 20:
      return 4.0 - min(math.log1p(sc) * 0.22, 1.2) + extra_pen
    return 5.4 - min(math.log1p(sc) * 0.1, 0.3) + extra_pen

  max_end = min(L, pos + 24)
  for end in range(pos + 1, max_end + 1):
    seg = req_prefix + slp[pos:end]
    at_chunk_end = end == L
    next_ch = slp[end] if end < L else ""

    if at_chunk_end:
      # Pragṛhya `ओत्` (पा॰ १.१.१५): `नो`/`तथो`/`अथो`/`मो`/`तेनो` before unelided vowel or as `a/A + u`
      if seg in ("no", "taTo", "aTo", "mo", "teno", "pro") and (
        (next_tok_starts_vowel and not next_tok_is_avagraha) or seg in ("taTo", "aTo", "teno", "pro")
      ):
        u_left = {"no": "na", "taTo": "taTA", "aTo": "aTa", "mo": "mA", "teno": "tena", "pro": "pra"}[seg]
        c_l = _eval_word(u_left, 0.0)
        if c_l is not None:
          out.append((end, "u", u_left, c_l))  # Handled via internal vowel merger below too!

      final_cands: list[tuple[str, float]] = []
      # Uncoalesced `vA` before a vowel is ALWAYS `vE` (पा॰ ८.३.१९), NEVER enclitic `vA`!
      if seg == "vA" and next_tok_starts_vowel:
        final_cands.append(("vE", 0.0))
      else:
        raw_pen = 0.0
        # Penalize unvoiced-restorable or sandhi-mutated final consonants (`d`/`q`/`g`/`r`/`S`/`z`/`s`/`M`) at padapāṭha boundary!
        if seg.endswith(("d", "q", "g", "b", "r", "S", "z", "s", "M")) and len(seg) >= 2:
          raw_pen = 4.5
        elif next_tok_starts_vowel and seg.endswith(("a", "A")) and len(seg) >= 2:
          if lex.word_score_slp(seg + "H") >= 20 or (seg.endswith("smA") and lex.word_score_slp(seg[:-1] + "E") >= 20):
            raw_pen = 4.0
        final_cands.append((seg, raw_pen))
      if seg.endswith("M") and len(seg) >= 2:
        final_cands.append((seg[:-1] + "m", 0.0))
        final_cands.append((seg[:-1] + "n", 0.35))
      if seg.endswith("o") and len(seg) >= 2:
        # `नो` before an unelided vowel without avagraha (`नो अनाप्ताः`) is `न + उ` (पा॰ १.१.१५), NOT `नः`!
        if seg == "no" and next_tok_starts_vowel and not next_tok_is_avagraha:
          pass
        elif next_tok_is_avagraha or next_tok_starts_voiced:
          final_cands.append((seg[:-1] + "aH", 0.0))
        else:
          final_cands.append((seg[:-1] + "aH", 0.7))
      if seg.endswith("r") and len(seg) >= 3:
        final_cands.append((seg[:-1] + "H", 0.0))
      if seg.endswith(("S", "z", "s")) and len(seg) >= 2 and not is_end_of_clause:
        final_cands.append((seg[:-1] + "H", 0.0))
      if seg.endswith("d") and len(seg) >= 2:
        final_cands.append((seg[:-1] + "t", 0.0))
      if seg.endswith(("c", "j", "l", "n")) and len(seg) >= 2 and not is_end_of_clause:
        final_cands.append((seg[:-1] + "t", 0.25))
      if seg.endswith("nn") and len(seg) >= 4 and next_tok_starts_vowel:
        final_cands.append((seg[:-1], 0.0))
      if seg.endswith("NN") and len(seg) >= 4 and next_tok_starts_vowel:
        final_cands.append((seg[:-1], 0.0))
      if seg.endswith("y") and next_tok_starts_vowel:
        if len(seg) >= 2:
          final_cands.append((seg[:-1] + "i", 0.05))
          final_cands.append((seg[:-1] + "I", 0.35))
        if seg == "Dy":
          final_cands.append(("hi", 0.05))
      if seg.endswith("v") and next_tok_starts_vowel:
        if seg == "v":
          final_cands.append(("u", 0.0))
        elif len(seg) >= 2:
          final_cands.append((seg[:-1] + "u", 0.05))
          final_cands.append((seg[:-1] + "U", 0.35))
        if seg.endswith("Av") and len(seg) >= 3:
          final_cands.append((seg[:-2] + "O", 0.05))
      if seg == "sa" and not is_end_of_clause:
        final_cands.append(("saH", 0.0))
      if seg == "eza" and not is_end_of_clause:
        final_cands.append(("ezaH", 0.0))
      if seg.endswith("A") and len(seg) >= 2 and (next_tok_starts_vowel or next_tok_starts_voiced):
        if next_tok_starts_vowel and (seg.endswith("smA") or seg.endswith("AmahA")):
          final_cands.append((seg[:-1] + "E", 0.0))
        if next_tok_starts_vowel:
          final_cands.append((seg + "H", 0.0))
        else:
          # NEVER blindly promote fem. sg. `-आ` (`निरुक्ता`, `पञ्चावत्ता`, `उत्तरा`, `अनतिदग्धा`) to plural `-आः`!
          seg_m = lex.analyze_morph(_slp_to_deva(seg))
          if (
            seg in ("sA", "ezA", "yA", "vA", "mA", "taTA", "yaTA", "yadA", "tadA", "BUtvA", "hotA", "yozA", "vfzA", "brahmA", "anuzWyA")
            or seg.endswith(("tvA", "yA"))
            or seg_m["is_stri_prathama_eka"]
            or seg_m["is_avyaya"]
          ):
            final_cands.append((seg + "H", 0.55))
          else:
            final_cands.append((seg + "H", 0.05))
      if seg.endswith("a") and len(seg) >= 2 and next_tok_starts_vowel:
        final_cands.append((seg + "H", 0.0))
        final_cands.append((seg[:-1] + "e", 0.25))
      if seg.endswith(("Ms", "MS", "Mz")) and len(seg) >= 4:
        final_cands.append((seg[:-2] + "n", 0.05))
      if seg.endswith("nts") and len(seg) >= 5:
        final_cands.append((seg[:-2], 0.05))
      if seg.endswith("nt") and len(seg) >= 4:
        final_cands.append((seg[:-1], 0.05))
      if seg.endswith("q") and len(seg) >= 3:
        final_cands.append((seg[:-1] + "w", 0.0))
      if seg.endswith("g") and len(seg) >= 3:
        final_cands.append((seg[:-1] + "k", 0.0))
      if seg.endswith("b") and len(seg) >= 3:
        final_cands.append((seg[:-1] + "p", 0.0))
      # Velar nasal `ङ्` before `n`/`m` ONLY is `पा॰ ८.४.४५` (`वाङ्निरुक्तो` -> `वाक्`); keep `प्राङ्` before `त` intact!
      if seg.endswith("N") and len(seg) >= 3 and next_tok_starts_nasal:
        final_cands.append((seg[:-1] + "k", 0.0))
      if seg.endswith("Y") and len(seg) >= 3:
        final_cands.append((seg[:-1] + "n", 0.0))

      seen_w: set[str] = set()
      for w_c, pen in final_cands:
        if w_c in seen_w:
          continue
        seen_w.add(w_c)
        cost = _eval_word(w_c, pen)
        if cost is not None:
          out.append((end, "", w_c, cost))
      continue

    # Non-final position inside chunk
    if next_ch not in SLP_VOWELS:
      raw_in_pen = 2.0 if seg.endswith(("d", "q", "g", "b")) and len(seg) >= 2 else 0.1
      cost = _eval_word(seg, raw_in_pen)
      if cost is not None:
        out.append((end, "", seg, cost))
      # Velar nasal `N` (`ङ्`): before `n`/`m` -> `k` (`वाङ्निरुक्तो` -> `वाक्`, पा॰ ८.४.४५); before `k/K/g/G` -> `m`!
      if seg.endswith("N") and len(seg) >= 3:
        if next_ch in "nm":
          c_k = _eval_word(seg[:-1] + "k", 0.05)
          if c_k is not None:
            out.append((end, "", seg[:-1] + "k", c_k))
        elif next_ch in "kKgG":
          c_m = _eval_word(seg[:-1] + "m", 0.15)
          if c_m is not None:
            out.append((end, "", seg[:-1] + "m", c_m))
      # Palatal nasal `Y` (`ञ्`): before `c/C/j/J/S` -> `n` (`देवाञ्` -> `देवान्`, पा॰ ८.४.४०) OR `m` (`व्रतञ्च` -> `व्रतम्`)
      if seg.endswith("Y") and len(seg) >= 2 and next_ch in "cCjJS":
        c_n = _eval_word(seg[:-1] + "n", 0.12)
        if c_n is not None:
          out.append((end, "", seg[:-1] + "n", c_n))
        c_m = _eval_word(seg[:-1] + "m", 0.15)
        if c_m is not None:
          out.append((end, "", seg[:-1] + "m", c_m))
      if seg.endswith(("M", "R", "n", "m")) and len(seg) >= 2:
        c_m = _eval_word(seg[:-1] + "m", 0.15)
        if c_m is not None:
          out.append((end, "", seg[:-1] + "m", c_m))
        if seg[-1] in ("M", "n"):
          c_n = _eval_word(seg[:-1] + "n", 0.3)
          if c_n is not None:
            out.append((end, "", seg[:-1] + "n", c_n))
      if seg.endswith("g") and len(seg) >= 3:
        c_k = _eval_word(seg[:-1] + "k", 0.08)
        if c_k is not None:
          out.append((end, "", seg[:-1] + "k", c_k))
      if seg.endswith("q") and len(seg) >= 3:
        c_w = _eval_word(seg[:-1] + "w", 0.08)
        if c_w is not None:
          out.append((end, "", seg[:-1] + "w", c_w))
      if seg.endswith("b") and len(seg) >= 3:
        c_p = _eval_word(seg[:-1] + "p", 0.08)
        if c_p is not None:
          out.append((end, "", seg[:-1] + "p", c_p))
      if seg.endswith(("Ms", "MS", "Mz")) and len(seg) >= 4:
        c_n = _eval_word(seg[:-2] + "n", 0.15)
        if c_n is not None:
          out.append((end, "", seg[:-2] + "n", c_n))
      if seg.endswith("nt") and len(seg) >= 4 and next_ch == "s":
        c_n = _eval_word(seg[:-1], 0.1)
        if c_n is not None:
          out.append((end, "", seg[:-1], c_n))
      if seg.endswith(("d", "c", "j", "l", "n")) and len(seg) >= 2:
        c_t = _eval_word(seg[:-1] + "t", 0.12)
        if c_t is not None:
          out.append((end, "", seg[:-1] + "t", c_t))
          if seg.endswith("c") and next_ch == "C":
            out.append((end + 1, "S", seg[:-1] + "t", c_t + 0.05))
          if seg.endswith("d") and next_ch == "D":
            out.append((end + 1, "h", seg[:-1] + "t", c_t + 0.05))
      # Degeminated `t + S -> C` (e.g. Weber `तछकेयं` = `तत् + शकेयम्`)
      if next_ch == "C" and seg in ("ta", "ya", "eta"):
        c_t = _eval_word(seg + "t", 0.2)
        if c_t is not None:
          out.append((end + 1, "S", seg + "t", c_t))
      if seg.endswith("o") and len(seg) >= 2 and next_ch in "gGNjJYqQRdDnbBmyrlvh":
        c_v = _eval_word(seg[:-1] + "aH", 0.12)
        if c_v is not None:
          out.append((end, "", seg[:-1] + "aH", c_v))
      if seg.endswith(("r", "S", "z", "s")) and len(seg) >= 2:
        c_v = _eval_word(seg[:-1] + "H", 0.12)
        if c_v is not None:
          out.append((end, "", seg[:-1] + "H", c_v))
      if seg.endswith("A") and len(seg) >= 3 and next_ch in "gGNjJYqQRdDnbBmyrlvh":
        c_v = _eval_word(seg + "H", 0.35)
        if c_v is not None:
          out.append((end, "", seg + "H", c_v))
      if seg in ("sa", "eza"):
        c_v = _eval_word(seg + "H", 0.12)
        if c_v is not None:
          out.append((end, "", seg + "H", c_v))
    else:
      if seg[-1] not in SLP_VOWELS:
        for w_c, pen in _prevocalic_cons_restorations(seg, next_ch=next_ch):
          c = _eval_word(w_c, pen)
          if c is not None:
            out.append((end, "", w_c, c))
      if seg == "vA":
        c = _eval_word("vE", 0.05)
        if c is not None:
          out.append((end, "", "vE", c))
      elif seg.endswith(("I", "U", "e", "o")):
        c = _eval_word(seg, 0.25)
        if c is not None:
          out.append((end, "", seg, c))

    # Inverse vowel-sandhi merger AT `slp[end - 1]`!
    last_ch = slp[end - 1]
    if last_ch in _INV_VOWEL_SANDHI and len(seg) >= 2:
      base_pre = seg[:-1]
      for lv, rv in _INV_VOWEL_SANDHI[last_ch]:
        w_c = base_pre + lv
        if len(w_c) == 1 and w_c not in ("A", "u"):
          continue
        v_pen = 0.25
        # Penalize vocative-only `-a` stem (`उपहूत`) when fem. nom.sg. `-A` (`उपहूता`) is valid (`उपहूतेडा`)!
        if lv == "a" and w_c not in SB_FUNCTION_WORDS_SLP and len(w_c) >= 4:
          wm = lex.analyze_morph(_slp_to_deva(w_c))
          if wm["voc_possible"] and not wm["has_non_voc_subanta"] and not wm["is_avyaya"] and not wm["is_tinanta"]:
            v_pen += 2.0
        c = _eval_word(w_c, v_pen)
        if c is not None:
          out.append((end, rv, w_c, c))

    # Inverse *abhinihita* `e'` / `o'`
    if next_ch == "'" and last_ch in ("e", "o"):
      if last_ch == "o":
        c_v = _eval_word(seg[:-1] + "aH", 0.05)
        if c_v is not None:
          out.append((end + 1, "a", seg[:-1] + "aH", c_v))
      c_e = _eval_word(seg, 0.05)
      if c_e is not None:
        out.append((end + 1, "a", seg, c_e))

  return out


def _prevocalic_cons_restorations(seg: str, *, next_ch: str = "") -> list[tuple[str, float]]:
  """Restore consonant-final word endings before a following vowel inside a fused chunk."""
  out: list[tuple[str, float]] = [(seg, 0.1)]
  c = seg[-1]
  if c == "y" and len(seg) >= 2:
    out.append((seg[:-1] + "i", 0.05))
    out.append((seg[:-1] + "I", 0.35))
  elif c == "v":
    if seg == "v":
      # `यद्वेव` (`v` before `e`) = `उ + एव` (0.0); before `A` (`वाग्नीध्रो`) prefer `vA + A` over `u + A`!
      out.append(("u", 0.45 if next_ch in ("A", "E", "a") else 0.0))
    else:
      out.append((seg[:-1] + "u", 0.05))
      out.append((seg[:-1] + "U", 0.35))
      if seg.endswith("Av") and len(seg) >= 3:
        out.append((seg[:-2] + "O", 0.05))
      if seg.endswith("av") and len(seg) >= 3:
        out.append((seg[:-2] + "o", 0.25))
  elif c == "d" and len(seg) >= 2:
    out.append((seg[:-1] + "t", 0.05))
  elif c == "r" and len(seg) >= 3:
    out.append((seg[:-1] + "H", 0.08))
  elif c == "g" and len(seg) >= 3:
    out.append((seg[:-1] + "k", 0.15))
  elif c == "q" and len(seg) >= 3:
    out.append((seg[:-1] + "w", 0.15))
  elif seg.endswith("nn") and len(seg) >= 4:
    out.append((seg[:-1], 0.05))
  elif seg.endswith("NN") and len(seg) >= 4:
    out.append((seg[:-1], 0.05))
  elif seg.endswith("Ay") and len(seg) >= 4:
    out.append((seg[:-2] + "E", 0.2))
  return out


def split_chunk_to_padas_dp(
  chunk_deva: str,
  lex: UnifiedVedicLexicon,
  *,
  next_tok_deva: str = "",
  is_end_of_clause: bool = False,
  leading_avagraha: bool = False,
) -> list[str]:
  """Split one space-separated Devanagari saṁhitā chunk into normalized bare padapāṭha words."""
  raw = chunk_deva.strip()
  if not raw or not _DEVANAGARI_RE.search(raw):
    return []

  # Preserve already-hyphenated clean single words when valid (e.g. `पवित्र-पूतो`, `व्रत-पतिः`)
  if "-" in raw and "ऽ" not in raw:
    parts = [p for p in raw.split("-") if p]
    if len(parts) >= 2 and all(_DEVANAGARI_RE.search(p) for p in parts):
      # Only restore final sandhi on the whole compound!
      whole_slp = _deva_to_slp(raw.replace("-", ""))
      restored_last = split_chunk_to_padas_dp(
        parts[-1],
        lex,
        next_tok_deva=next_tok_deva,
        is_end_of_clause=is_end_of_clause,
        leading_avagraha=False,
      )
      if len(restored_last) == 1:
        cand = "-".join(parts[:-1] + restored_last)
        # Ensure it's not a prefixed finite verb
        if _strip_leading_upasargas_tinanta(whole_slp, lex) is None:
          return [cand]

  # Convert chunk to SLP1 keeping internal avagraha `'`
  clean_d = accent.strip_accents(raw).replace("-", "")
  if clean_d.startswith("ऽ"):
    leading_avagraha = True
    clean_d = clean_d.lstrip("ऽ")
  slp = _deva_to_slp(clean_d)
  slp = re.sub(r"[^a-zA-Z']", "", slp)
  if not slp:
    return []

  next_slp = ""
  if next_tok_deva:
    nt = accent.strip_accents(next_tok_deva).replace("-", "")
    next_slp = _deva_to_slp(nt)
  next_is_av = next_tok_deva.startswith("ऽ")
  next_starts_v = bool(next_slp and next_slp[0] in SLP_VOWELS)
  next_starts_voiced = bool(next_slp and next_slp[0] in "gGNjJYqQRdDnbBmyrlvh")
  next_starts_nasal = bool(next_slp and next_slp[0] in "nmNR")

  # Special fast path for single non-fused word with leading avagraha (`ऽधः`, `ऽग्निम्`)
  init_prefix = "a" if leading_avagraha else ""
  L = len(slp)

  # DP: dp[(pos, req_prefix)] = (cost, prev_state, word_slp)
  dp: dict[tuple[int, str], tuple[float, tuple[int, str] | None, str]] = {
    (0, init_prefix): (0.0, None, "")
  }
  # Process states ordered by `pos` (strictly increasing in every transition!)
  by_pos: list[list[tuple[int, str]]] = [[] for _ in range(L + 1)]
  by_pos[0].append((0, init_prefix))

  for pos in range(L):
    # Prune beam at each position to top-8 states for guaranteed linear-time splitting
    states = sorted(set(by_pos[pos]), key=lambda st: dp[st][0])[:8]
    for st in states:
      cur_cost = dp[st][0]
      _, req_pf = st
      trans = _generate_chunk_transitions(
        slp, pos, req_pf, lex, next_starts_v, next_starts_voiced, next_is_av, is_end_of_clause,
        next_tok_starts_nasal=next_starts_nasal,
      )
      for nxt_pos, nxt_pf, w_slp, t_cost in trans:
        nc = cur_cost + t_cost
        # Penalize clubbing forbidden left words (e.g., `nAtra` -> `na + atra` strongly beats `nAtra`)
        nxt_st = (nxt_pos, nxt_pf)
        if nxt_st not in dp or nc < dp[nxt_st][0]:
          if nxt_st not in dp:
            by_pos[nxt_pos].append(nxt_st)
          dp[nxt_st] = (nc, st, w_slp)

  # Close chunk-final pragṛhya `ओत्` (`नो` -> `न + उ`, `तथो` -> `तथा + उ`, `तेनो` -> `तेन + उ`)
  if (L, "u") in dp:
    u_cost = dp[(L, "u")][0] + 2.0
    if (L, "") not in dp or u_cost < dp[(L, "")][0]:
      dp[(L, "")] = (u_cost, (L, "u"), "u")

  goal = (L, "")
  if goal not in dp:
    # Fallback: keep the normalized whole token as a single pada (preserving clean Devanagari orthography)
    fb = ("अ" + clean_d) if leading_avagraha else clean_d
    return [_clean_pada_orthography(fb)]

  # Backtrack word sequence in SLP1
  words_slp: list[str] = []
  cur: tuple[int, str] | None = goal
  while cur is not None and dp[cur][1] is not None:
    words_slp.append(dp[cur][2])
    cur = dp[cur][1]
  words_slp.reverse()

  # Post-process every word:
  # 1. Separate upasargas from finite tiṅantas (Rule #1 — BOTH main and subordinate clauses!)
  # 2. Hyphenate compounds / gatikṛdantas
  final_padas: list[str] = []
  for w_slp in words_slp:
    split_tin = _strip_leading_upasargas_tinanta(w_slp, lex)
    if split_tin is not None:
      final_padas.extend(split_tin)
    else:
      w_deva = _slp_to_deva(w_slp)
      final_padas.append(_hyphenate_compound_pada(w_deva, lex))
  return final_padas


def _split_vp_with_diagnostics(
  vp_clean: str, lex: UnifiedVedicLexicon
) -> tuple[list[str], list[int], set[int], list[str]]:
  """Split ``vp_clean`` into ``(padas, clause_ids, minor_breaks, morph_sandhi_ambigs)``."""
  txt = re.sub(r"\+\+\+.*?\+\+\+", " ", vp_clean, flags=re.S)
  txt = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", txt)
  txt = _ALL_ACCENT_MARKS_RE.sub("", txt)
  txt = re.sub(r"(?<=[\u0900-\u097f])-(?=\s|$)", " —", txt)
  txt = re.sub(r"(?:^|(?<=\s))-(?=[\u0900-\u097f])", "— ", txt)

  tokens = re.findall(r"[।॥,;:—–\"“”]+|[\u0900-\u0963\u0971-\u097f\-ऽ]+", txt)
  padas: list[str] = []
  clause_ids: list[int] = []
  minor_breaks: set[int] = set()
  morph_ambigs: list[str] = []
  cur_clause = 0
  pending_minor = False
  n = len(tokens)
  for i, tok in enumerate(tokens):
    if not _DEVANAGARI_RE.search(tok):
      if any(p in tok for p in ("।", "॥", "\"", "“", "”")):
        cur_clause += 1
        pending_minor = False
      elif any(p in tok for p in (",", ";", "—", "–")):
        pending_minor = True
      continue
    tok = tok.strip("-")
    if not tok or not _DEVANAGARI_RE.search(tok):
      continue
    nxt_tok = ""
    end_clause = True
    if i + 1 < n:
      if _DEVANAGARI_RE.search(tokens[i + 1]):
        nxt_tok = tokens[i + 1].strip("-")
        end_clause = False
      elif any(p in tokens[i + 1] for p in ("।", "॥")):
        end_clause = True
      else:
        for j in range(i + 1, n):
          if any(p in tokens[j] for p in ("।", "॥")):
            end_clause = True
            break
          if _DEVANAGARI_RE.search(tokens[j]):
            nxt_tok = tokens[j].strip("-")
            end_clause = False
            break
    chunk_padas = split_chunk_to_padas_dp(
      tok, lex, next_tok_deva=nxt_tok, is_end_of_clause=end_clause
    )
    if pending_minor and chunk_padas:
      minor_breaks.add(len(padas))
      pending_minor = False

    # Detect morphological external-sandhi ambiguity on chunk-final `-आ` (sg vs pl `-आः`) and `-अ` before vowel (`-अः` vs `-ए`)!
    if chunk_padas and nxt_tok and not end_clause:
      tok_slp = _deva_to_slp(tok.replace("-", "").lstrip("ऽ"))
      nxt_slp = _deva_to_slp(nxt_tok.replace("-", ""))
      nxt_v = bool(nxt_slp and nxt_slp[0] in SLP_VOWELS)
      nxt_voiced = bool(nxt_slp and nxt_slp[0] in "gGNjJYqQRdDnbBmyrlvh")
      last_pd = chunk_padas[-1]
      last_slp = _deva_to_slp(_normalize_lookup_key(last_pd))
      p_idx = len(padas) + len(chunk_padas) - 1
      # Case 1: Surface `-आ` before voiced C (`निः-उक्ता` vs `निः-उक्ताः`, `पञ्चावत्ता` vs `पञ्चावत्ताः`, `या` vs `याः`, `उत्तरा` vs `उत्तराः`)
      if tok_slp.endswith("A") and nxt_voiced and len(tok_slp) >= 2 and last_slp.endswith(("A", "AH")):
        base_a = last_slp[:-1] if last_slp.endswith("AH") else last_slp
        # Exclude unambiguous masc. plurals, always-sg indeclinables, and instrumental `-इना`/`-उना` (`अग्निना`, `मनुना`)
        if (
          base_a not in (
            "sA", "ezA", "vA", "mA", "taTA", "yaTA", "yadA", "tadA", "BUtvA", "hotA", "yozA", "vfzA", "brahmA",
            "devA", "lokA", "gfhA", "ApA", "meDyA", "sarvA", "etA", "tA", "imA", "anuzWyA",
          )
          and not base_a.endswith(("tvA", "inA", "unA", "eRA", "enA"))
        ):
          m_sg = lex.analyze_morph(_slp_to_deva(base_a))
          m_pl = lex.analyze_morph(_slp_to_deva(base_a + "H"))
          if (m_sg["is_stri_prathama_eka"] or base_a == "yA") and m_pl["has_non_voc_subanta"]:
            morph_ambigs.append(f"morph_aa_aah@{p_idx}:{last_pd}")
      # Case 2: Surface `-अ` before vowel (`र᳓णे-रण इति` -> `-अः` vs `-ए` पा॰ ८.३.१९)
      elif tok_slp.endswith("a") and nxt_v and len(tok_slp) >= 3 and last_slp.endswith(("aH", "e")):
        base_a = last_slp[:-2] if last_slp.endswith("aH") else last_slp[:-1]
        # Exclude unambiguous `-भ्यः` dat/abl pl and `-तः` adverbs (`ततः`, `अतः`, `यतः`, `इतः`, `सर्वतः`)
        if (
          base_a + "a" not in ("apa", "sa", "eza", "ca", "na", "aTa", "eva", "iva", "tata", "ata", "yata", "ita", "kuta", "aBita", "parita", "sarvata")
          and not (base_a + "a").endswith(("Bya", "ata"))
        ):
          m_vis = lex.analyze_morph(_slp_to_deva(base_a + "aH"))
          m_e = lex.analyze_morph(_slp_to_deva(base_a + "e"))
          if (m_vis["has_non_voc_subanta"] or m_vis["is_tinanta"]) and (m_e["has_non_voc_subanta"] or m_e["is_tinanta"]):
            morph_ambigs.append(f"morph_ah_e@{p_idx}:{last_pd}")

    for pd in chunk_padas:
      padas.append(pd)
      clause_ids.append(cur_clause)
      if _normalize_lookup_key(pd) == "इति":
        cur_clause += 1
  return padas, clause_ids, minor_breaks, morph_ambigs


def split_vp_to_padas_with_clauses(
  vp_clean: str, lex: UnifiedVedicLexicon
) -> tuple[list[str], list[int]]:
  """Split a clean unaccented ``विश्वास-प्रस्तुतिः`` into ``(padas, clause_ids)``."""
  padas, clause_ids, _, _ = _split_vp_with_diagnostics(vp_clean, lex)
  return padas, clause_ids


def split_vp_to_padas(vp_clean: str, lex: UnifiedVedicLexicon) -> list[str]:
  """Split a clean unaccented ``विश्वास-प्रस्तुतिः`` string into normalized bare padapāṭha words."""
  padas, _ = split_vp_to_padas_with_clauses(vp_clean, lex)
  return padas


# ---------------------------------------------------------------------------
# Component 3: Candidate Generator + 3-State Viterbi ŚB Accent Decoder
# ---------------------------------------------------------------------------


_CORPUS_TIE_ORDER: dict[str, int] = {"VS": 0, "TS": 1, "RV": 2, "AV": 3, "TB": 4, "TA": 5}
_CORPUS_NAMES: frozenset[str] = frozenset(_CORPUS_TIE_ORDER.keys())
_DICT_ORDER: tuple[str, ...] = ("Whitney", "Macdonell", "Lanman", "MW_SB", "MW")


def _aggregate_corpus_counts(srcs: dict[str, int]) -> dict[str, int]:
  """Merge disjoint ``TB``/``TB_VP`` and ``TA``/``TA_VP`` counts and sort by ``(-count, VS>TS>RV>AV>TB>TA)``."""
  totals: dict[str, int] = {}
  for s, f in srcs.items():
    if f <= 0:
      continue
    if s in _CORPUS_NAMES:
      totals[s] = totals.get(s, 0) + int(f)
    elif s == "TB_VP":
      totals["TB"] = totals.get("TB", 0) + int(f)
    elif s == "TA_VP":
      totals["TA"] = totals.get("TA", 0) + int(f)
  ordered = sorted(totals.items(), key=lambda kv: (-kv[1], _CORPUS_TIE_ORDER[kv[0]]))
  return {k: v for k, v in ordered if v > 0}


def _format_corpus_prov(srcs: dict[str, int]) -> str:
  """Format provenance tags with exact Vedic corpus counts (e.g. ``*TS*-12, *RV*-2, *TB*-2``).

  Vedic corpora (``VS``, ``TS``, ``RV``, ``AV``, ``TB``, ``TA``) are ordered by count
  descending with tie-break ``VS > TS > RV > AV > TB > TA``. Non-corpus dictionaries
  and grammars (``*Whitney*``, ``*Macdonell*``, ``*Lanman*``, ``*MW* ŚBr.``, ``*MW*``)
  follow uncounted.
  """
  tags: list[str] = []
  for corp, cnt in _aggregate_corpus_counts(srcs).items():
    tags.append(f"*{corp}*-{cnt}")
  seen: set[str] = set()
  for d in _DICT_ORDER:
    if d in srcs and srcs[d] > 0:
      lbl = "*MW* ŚBr." if d == "MW_SB" else f"*{d}*"
      if lbl not in seen:
        seen.add(lbl)
        tags.append(lbl)
  return ", ".join(tags)


def lookup_corpus_counts(lex: UnifiedVedicLexicon, pada_us: str) -> dict[str, int]:
  """Return exact per-corpus occurrence counts ``{corpus: count}`` for a US-accented padapāṭha word.

  Keys are a subset of ``{'VS', 'TS', 'RV', 'AV', 'TB', 'TA'}`` with strictly positive integer
  counts, ordered by count descending (tie-break ``VS > TS > RV > AV > TB > TA``).
  """
  if not pada_us or not _DEVANAGARI_RE.search(pada_us):
    return {}
  clean = re.sub(r"\*+", "", pada_us).strip()
  key = _normalize_lookup_key(clean)
  if not key:
    return {}
  scanned = _fast_scan_deva_syllables(_join_virama_vowels(clean.replace("-", "")))
  if not scanned:
    return {}
  marks = tuple("S" if US_SVARITA in m else ("U" if US_UDATTA in m else "") for m, _ in scanned)
  srcs = lex.form_accents.get(key, {}).get(marks, {})
  return _aggregate_corpus_counts(srcs)


_CORPUS_TAG_NO_REF_RE = re.compile(
  r"\*(VS|TS|RV|AV|TB|TA)\*(?:-\d+)?(?![ \t]+[\d०-९])"
)


def enrich_padapatha_corpus_counts(lex: UnifiedVedicLexicon, pada_us: str, just: str) -> str:
  """Deterministically enrich a padapāṭha justification string with exact ``*CORPUS*-N`` counts.

  - Replaces any bare or previously counted Vedic corpus tags (``*VS*``, ``*TS*``, ``*RV*``,
    ``*AV*``, ``*TB*``, ``*TA*`` without an explicit verse citation like ``*VS* 1.5``) with
    the exact attested corpus counts for ``pada_us`` ordered by count descending
    (``VS > TS > RV > AV > TB > TA``).
  - Preserves explicit verse references (e.g. ``*VS* 1.5``, ``*RV* 6.16.15``), Pāṇini sūtras,
    dictionary tags (``*MW*``, ``*Macdonell*``, ``*Lanman*``, ``*Whitney*``), and editorial
    notes (``व्यत्यस्तः``, ``श्रीधरादि-पाठः``, ``Weber``) verbatim.
  - Never emits ``-0`` or hallucinated counts.
  """
  if not just:
    counts = lookup_corpus_counts(lex, pada_us)
    return ", ".join(f"*{c}*-{n}" for c, n in counts.items())

  # Normalize deprecated `पा\u0966` -> `पा\u0970` (Devanagari abbreviation sign)
  just = just.replace("पा\u0966", "पा\u0970")
  counts = lookup_corpus_counts(lex, pada_us)
  formatted_corpora = ", ".join(f"*{c}*-{n}" for c, n in counts.items())

  # Split top-level `;` clauses so editorial suffixes (e.g. `; श्रीधरादि-पाठः`) stay cleanly separated
  semi_parts = [p.strip() for p in just.split(";")]
  new_semi_parts: list[str] = []
  inserted = False
  for part in semi_parts:
    if not part:
      continue
    items_c = [c.strip() for c in part.split(",")]
    kept: list[str] = []
    had_plain_corpus = False
    for seg in items_c:
      if not seg:
        continue
      # Check if segment is purely a bare/counted corpus tag (no verse number after it)
      if _CORPUS_TAG_NO_REF_RE.fullmatch(seg):
        had_plain_corpus = True
        continue
      # Check if segment embeds a bare corpus tag alongside prose (e.g. `व्यत्यस्तः *TS*`)
      if _CORPUS_TAG_NO_REF_RE.search(seg):
        def _sub_inline(m: re.Match) -> str:
          cname = m.group(1)
          return f"*{cname}*-{counts[cname]}" if cname in counts else m.group(0)
        seg = _CORPUS_TAG_NO_REF_RE.sub(_sub_inline, seg)
      kept.append(seg)
    if had_plain_corpus and not inserted:
      if formatted_corpora:
        # Place counted corpora where corpus citations belong (after leading sūtra/rule if present)
        kept.append(formatted_corpora)
      inserted = True
    if kept:
      new_semi_parts.append(", ".join(kept))

  # If `just` had no bare corpus tag yet, append exact corpus counts when attested (unless already citing a verse of every attested corpus)
  if not inserted and formatted_corpora:
    if new_semi_parts:
      new_semi_parts[0] = f"{new_semi_parts[0]}, {formatted_corpora}"
    else:
      new_semi_parts.append(formatted_corpora)
  return "; ".join(new_semi_parts) if new_semi_parts else just


def _derive_paninian_tinanta_accent(
  word_deva: str, morph: dict, *, sub_rule: str
) -> list[tuple[tuple[str, ...], str]]:
  """Derive accented finite verb syllable marks via Pāṇinian rules (with sūtra provenance)."""
  bare = _normalize_lookup_key(word_deva)
  slp = morph["slp"]
  n_syl = _fast_syllable_count(bare)
  if n_syl == 0:
    return []

  out: dict[tuple[str, ...], str] = {}
  ks: list[tuple[str, str]] | None = None

  def _add(idx: int, sutra: str) -> None:
    if 0 <= idx < n_syl:
      mks = tuple("U" if i == idx else "" for i in range(n_syl))
      if mks not in out:
        out[mks] = f"{sub_rule}, {sutra}" if sutra else sub_rule

  # 1. Augmented tenses (लङ्, लुङ्, लृङ्): पा॰ ६.४.७१ लुङ्लङ्लृङ्क्ष्वडुदात्तः / ६.४.७२ आडजादीनाम्
  for t in morph["tin_entries"]:
    lak = t["lakara"]
    gana = t["gana"]
    prayoga = t["prayoga"]
    sanadi = t["sanadi"]

    if lak in ("la~N", "lu~N", "lf~N") and bare[0] in ("अ", "आ", "ऐ", "औ"):
      _add(0, "पा॰ ६.४.७१")
      continue
    # 2. Passive `यक्` (पा॰ ३.१.६७, पा॰ ३.१.३): accent on `-य-`
    if prayoga in ("karmaRi", "BAve") and lak in ("la~w", "lo~w", "viDili~N"):
      if ks is None:
        ks, _ = syllables_with_marks(bare)
      for idx in range(n_syl - 1, -1, -1):
        if "य" in ks[idx][0]:
          _add(idx, "यक् पा॰ ३.१.६७, पा॰ ३.१.३")
          break
      continue
    # 3. Causative `णिच्` / चुरादि (पा॰ ३.१.२६, पा॰ ३.१.३): accent on `-अय-` (`साद᳓यति`, `साद᳓येत्`, `आप᳓यति`)
    if any("Ric" in s for s in sanadi) or gana == "curAdi":
      # Locate `-ay-` syllable before ending
      if n_syl >= 3:
        _add(n_syl - 3, "णिच् पा॰ ३.१.३")
      if n_syl >= 2 and slp.endswith(("et", "eyuH", "eta", "eran", "eH", "em", "ema")):
        _add(n_syl - 2, "णिच् पा॰ ३.१.३")
      continue
    # 4. Future `स्य` (पा॰ ३.१.३३, पा॰ ३.१.३)
    if lak == "lf~w":
      if ks is None:
        ks, _ = syllables_with_marks(bare)
      for idx in range(n_syl - 1, -1, -1):
        if "स" in ks[idx][0] or "य" in ks[idx][0]:
          _add(idx, "स्यतासी पा॰ ३.१.३३, पा॰ ३.१.३")
          break
      continue
    # 5. Athematic optative `-यात्` (पा॰ ३.४.१०३ लिङ्सलोपौ)
    if lak == "viDili~N" and slp.endswith(("yAt", "yAtAm", "yuH", "yAH", "yAm", "yAma")):
      _add(n_syl - 1, "लिङ्सलोपौ पा॰ ३.४.१०३")
      continue
    # 6. Gaṇa-specific present/imperative/optative accent (ONLY on sārvadhātuka `la~w`/`lo~w`/`viDili~N`, NEVER `li~w` perfects!)
    if lak in ("la~w", "lo~w", "viDili~N"):
      if gana == "BvAdi":
        _add(0, "शप् अनुदात्त पा॰ ३.१.४")
      elif gana == "tudAdi":
        # तुदादिभ्यः शः (पा॰ ३.१.७७, पा॰ ३.१.३): `-ए-` optative (`स्पृशे᳓त्`) = `n_syl-1`; `-अति` = `n_syl-2`
        if lak == "viDili~N" and slp.endswith(("et", "eH", "em", "eta", "eyuH", "eran")):
          _add(n_syl - 1 if slp.endswith(("et", "eH", "em")) else max(0, n_syl - 2), "तुदादिभ्यः शः पा॰ ३.१.७७")
        else:
          _add(max(0, n_syl - 2), "तुदादिभ्यः शः पा॰ ३.१.७७")
      elif gana == "divAdi":
        _add(0, "दिवादिभ्यः श्यन् पा॰ ३.१.६९, पा॰ ६.१.१९७")
      elif gana == "kryAdi":
        # क्र्यादिभ्यः श्ना (पा॰ ३.१.८१): udātta on `-ना-`/`-ण-` or ending
        _add(max(0, n_syl - 2), "क्र्यादिभ्यः श्ना पा॰ ३.१.८१")
        _add(n_syl - 1, "क्र्यादिभ्यः श्ना पा॰ ३.१.८१")
      elif gana in ("svAdi", "tanAdi"):
        _add(max(0, n_syl - 2), "स्वादिभ्यः श्नुः पा॰ ३.१.७३, पा॰ ३.१.३")
        _add(n_syl - 1, "पा॰ ३.१.३")
      elif gana == "ruDAdi":
        # रुधादिभ्यः श्नम् (पा॰ ३.१.७८, पा॰ ३.१.३): strong sg active `युन᳓क्ति`/`पिन᳓ष्टि`/`हिन᳓स्ति` = `n_syl-2`; weak = `n_syl-1`
        if t["vacana"] == "eka" and slp.endswith(("ti", "zi", "si", "mi", "tu", "wi", "Di", "hi")):
          _add(max(0, n_syl - 2), "रुधादिभ्यः श्नम् पा॰ ३.१.७८, पा॰ ३.१.३")
        _add(n_syl - 1, "पा॰ ३.१.३")
      elif gana in ("adAdi", "juhotyAdi"):
        _add(0, "पा॰ ६.१.१८६")
        _add(n_syl - 1, "पा॰ ३.१.३")

  # Vedic लेट् / thematic fallback (`चरान्` -> `च᳓रान्`, `स्पृशति` -> `स्पृश᳓ति`)
  if not out and slp.endswith(("An", "At", "Ati")):
    _add(0, "लेट् पा॰ ३.४.९४")
  return list(out.items())


def _derive_paninian_krdanta_and_compound_accents(
  pada_deva: str, lex: UnifiedVedicLexicon
) -> list[tuple[tuple[str, ...], str]]:
  """Generate solid Pāṇinian compound/kṛdanta accent candidates (``पा॰ ६.१.१९३``, ``६.२.१``, ``६.२.२``, ``६.२.४९``, ``६.२.१३९``, ``६.२.१७२``, ``६.१.२२३``)."""
  bare = _normalize_lookup_key(pada_deva)
  n_syl = _fast_syllable_count(pada_deva)
  if n_syl < 2:
    return []

  out: dict[tuple[str, ...], str] = {}
  morph = lex.analyze_morph(bare)
  slp = morph["slp"]

  # 1. Gerunds: ल्यप् (पा॰ ६.१.१९३ लिति — udātta on root syllable right before `-य`), क्त्वा (पा॰ ३.१.३)
  for k in morph["krt_entries"]:
    krt = k["krt"]
    if "ktvA" in krt:
      if k["prefixes"] and slp.endswith("ya") and n_syl >= 2:
        mks = tuple("U" if i == n_syl - 2 else "" for i in range(n_syl))
        out.setdefault(mks, "लिति पा॰ ६.१.१९३")
      elif slp.endswith(("tvA", "tvI")):
        mks = tuple("U" if i == n_syl - 1 else "" for i in range(n_syl))
        out.setdefault(mks, "क्त्वा पा॰ ३.१.३")
    elif "tumun" in krt or "tumu~n" in krt:
      # तुमुन् = नित् (पा॰ ६.१.१९७ आद्युदात्त): if prefixed (`उ᳓द्-यन्तुम्`) or simplex (`क᳓र्तुम्`)
      mks = tuple("U" if i == 0 else "" for i in range(n_syl))
      out.setdefault(mks, "नित् आद्युदात्तम् पा॰ ६.१.१९७")
    elif "kta" in krt and k["prefixes"]:
      # गतिरनन्तरः पा॰ ६.२.४९: the LAST gati immediately preceding `क्त` keeps its prakṛtisvara!
      # Compute syllable offset of any earlier prefixes (e.g. `अभि + अ᳓नु + उक्तम्` -> offset = syls(`अभि`) = 2)
      pref_list = k["prefixes"]
      last_pf = pref_list[-1]
      last_norm = "A" if last_pf == "AN" else ("ut" if last_pf == "ud" else ("niH" if last_pf in ("nir", "nis") else ("duH" if last_pf in ("dur", "dus") else last_pf)))
      p_last = UPASARGA_SLP_TO_DEVA.get(last_pf, UPASARGA_SLP_TO_DEVA.get(last_norm, ""))
      if p_last in UPASARGA_ACCENT_MARKS:
        g_mks = UPASARGA_ACCENT_MARKS[p_last]
        prev_offset = 0
        for earlier_pf in pref_list[:-1]:
          e_norm = "A" if earlier_pf == "AN" else ("ut" if earlier_pf == "ud" else ("niH" if earlier_pf in ("nir", "nis") else ("duH" if earlier_pf in ("dur", "dus") else earlier_pf)))
          ep = UPASARGA_SLP_TO_DEVA.get(earlier_pf, UPASARGA_SLP_TO_DEVA.get(e_norm, ""))
          if ep:
            prev_offset += _fast_syllable_count(ep)
        # Note internal yaṇ merger between prefixes (`अभि + अनु -> अभ्यनु`) reduces offset by 1
        for off in (prev_offset, max(0, prev_offset - 1)) if prev_offset > 0 else (0,):
          if off + len(g_mks) <= n_syl:
            mks = tuple("" for _ in range(off)) + g_mks + tuple("" for _ in range(n_syl - off - len(g_mks)))
            out.setdefault(mks, "गतिरनन्तरः पा॰ ६.२.४९")
    elif "kta" in krt and not k["prefixes"]:
      # Unprefixed `क्त` participle (`गृहीत᳓म्`): प्रत्ययस्वर पा॰ ३.१.३ on stem-final syllable
      end_idx = _stem_final_syl_idx(bare, n_syl)
      out.setdefault(tuple("U" if i == end_idx else "" for i in range(n_syl)), "क्तः प्रत्ययस्वरः पा॰ ३.१.३")
    elif "tfc" in krt or "tfn" in krt:
      # तृच् (`अपहन्ता᳓रम्`): प्रत्ययस्वर पा॰ ३.१.३ on `-तृ-/-तार्-` syllable
      if n_syl >= 2:
        t_idx = n_syl - 2 if slp.endswith(("tAram", "tAraH", "tArO", "tfBiH", "tfByaH", "tFRAm")) else n_syl - 1
        out.setdefault(tuple("U" if i == t_idx else "" for i in range(n_syl)), "तृच् प्रत्ययस्वरः पा॰ ३.१.३")
    elif ("SAnac" in krt or "Satf" in krt) and k["prayoga"] in ("karmaRi", "BAve"):
      # Passive participle (`चर्य᳓माणम्`): यक् पा॰ ३.१.६७, पा॰ ३.१.३
      ks, _ = _fast_syllables_with_marks(pada_deva)
      for idx in range(n_syl - 1, -1, -1):
        if "य" in ks[idx][0]:
          mks = tuple("U" if i == idx else "" for i in range(n_syl))
          out.setdefault(mks, "यक् पा॰ ३.१.६७, पा॰ ३.१.३")
          break
    elif "Satf" in krt and not k["prefixes"] and k["gana"] in ("BvAdi", "divAdi"):
      # Active present participle of bhvādi/divādi (`श्रा᳓म्यन्तः`): root udātta पा॰ ३.१.४ / ६.१.१९७
      out.setdefault(tuple("U" if i == 0 else "" for i in range(n_syl)), "शतृ पा॰ ३.१.४ / ६.१.१९७")

  # 1b. Pāṇini ५.३.३५ एनप् directional adverbs (`दक्षिणे᳓न`, `उत्तरे᳓ण`, `पूर्वे᳓ण`, `अपरे᳓ण`, `अधरे᳓ण`)
  if bare in ("दक्षिणेन", "उत्तरेण", "पूर्वेण", "अपरेण", "अधरेण", "अन्तरेण") and n_syl >= 2:
    out.setdefault(tuple("U" if i == n_syl - 2 else "" for i in range(n_syl)), "एनप् पा॰ ५.३.३५, पा॰ ३.१.३")
  # 1c. Pāṇini ५.३.५७ ईयसुन् comparatives (`पा᳓पीयांसः`, `व᳓सीयांसः`, `श्रे᳓यांसः`): नित् आद्युदात्त पा॰ ६.१.१९७
  if slp.endswith(("IyAMsaH", "IyAMsam", "IyasaH", "IyasA", "IyasI", "IyAn")) and n_syl >= 3:
    out.setdefault(tuple("U" if i == 0 else "" for i in range(n_syl)), "ईयसुन् नित् आद्युदात्तम् पा॰ ६.१.१९७")

  # 2. Hyphenated compound rules (`p0 - p1 ...`)
  if "-" in pada_deva:
    parts = [p for p in pada_deva.split("-") if p]
    if len(parts) >= 2:
      p0, p_rest = parts[0], "-".join(parts[1:])
      n0 = _fast_syllable_count(p0)
      # (a) नञ् compound (`अ-`, `अन्-`): पा॰ ६.२.२ (ādyudātta) vs पा॰ ६.२.१७२ (bahuvrīhi antodātta)
      if p0 in ("अ", "अन्"):
        mks_init = tuple("U" if i == 0 else "" for i in range(n_syl))
        out.setdefault(mks_init, "नञ्तत्पुरुषे पूर्वपदप्रकृतिस्वरः पा॰ ६.२.२")
        end_idx = _stem_final_syl_idx(bare, n_syl)
        mks_end = tuple("U" if i == end_idx else "" for i in range(n_syl))
        out.setdefault(mks_end, "नञ्सुभ्याम् पा॰ ६.२.१७२")
      # (b) गतिकृदन्त (`उप-एष्यन्`, `अभि-ईक्षमाणः`, `उप-यन्तम्`, `प्र-जननम्`): पा॰ ६.२.१३९
      elif p0 in UPASARGA_ACCENT_MARKS:
        rest_bare = _normalize_lookup_key(p_rest)
        r_hits = lex.lookup_form(rest_bare)
        if not r_hits:
          for r_mks, r_prov, _ in lex.project_stem_accents(rest_bare):
            r_hits[r_mks] = {"_stem": 1}
        for r_mks in r_hits:
          if sum(1 for m in r_mks if m) == 1 and len(r_mks) <= n_syl:
            shift = n_syl - len(r_mks)
            full_mks = tuple("" for _ in range(shift)) + r_mks
            out.setdefault(full_mks, "गतिकारकोपपदात् कृत् पा॰ ६.२.१३९")
        # गतिरनन्तरः पा॰ ६.२.४९ ONLY for true `क्त` past participles (NEVER prefixed perfects `-ईधे`/`-एधे`/`-रे` or `शानच्`/`शतृ`!)
        is_kta_like = any("kta" in k["krt"] for k in morph["krt_entries"]) or (
          not morph["is_tinanta"]
          and not bare.endswith(("ईधे", "एधे", "रे", "इरे", "ऊचे", "आहे", "आते"))
          and not any(s in bare for s in ("माण", "मान", "ष्यन्", "ष्यत्", "यन्त"))
          and re.search(r"(?:त|न|ण|ढ|ष्ट|प्त|क्त|ग्ध)(?:ः|म्|े|ौ|ाः|ान्|ै|ा|ाम्|स्य|ेन|ेण|ाय|ात्|ेषु|ेभ्यः|ानाम्)?$", bare) is not None
        )
        if is_kta_like:
          # Accent the LAST upasarga immediately preceding the `क्त` participle (`अभि-अनु-उक्तम्` -> `अ᳓नु`)!
          last_g_idx = 0
          off = 0
          for pi_idx, part in enumerate(parts[:-1]):
            if part in UPASARGA_ACCENT_MARKS:
              last_g_idx = pi_idx
          for part in parts[:last_g_idx]:
            off += _fast_syllable_count(part)
          g_mks = UPASARGA_ACCENT_MARKS[parts[last_g_idx]]
          for cand_off in (off, max(0, off - 1)) if off > 0 else (0,):
            if cand_off + len(g_mks) <= n_syl:
              out.setdefault(
                tuple("" for _ in range(cand_off)) + g_mks + tuple("" for _ in range(n_syl - cand_off - len(g_mks))),
                "गतिरनन्तरः पा॰ ६.२.४९",
              )
      else:
        # (c) General samāsa:
        # - पा॰ ६.१.२२३ समासस्य (antodātta on uttarapada stem-final syllable)
        end_idx = _stem_final_syl_idx(bare, n_syl)
        out.setdefault(tuple("U" if i == end_idx else "" for i in range(n_syl)), "समासस्य पा॰ ६.१.२२३")
        # - पा॰ ६.२.१ / ६.२.२ pūrvapada prakṛtisvara (from attested p0!)
        p0_hits = lex.lookup_stem(p0) or lex.lookup_form(p0)
        if p0_hits:
          top_p0_mks = max(p0_hits.items(), key=lambda kv: sum(kv[1].values()))[0]
          if len(top_p0_mks) <= n_syl and sum(1 for m in top_p0_mks if m) == 1:
            out.setdefault(
              top_p0_mks + tuple("" for _ in range(n_syl - len(top_p0_mks))),
              "पूर्वपदप्रकृतिस्वरः पा॰ ६.२.१/६.२.२",
            )
        # - पा॰ ६.२.१८ पत्यावैश्वर्ये (`व्रत᳓-पतिः`, `प्रजा᳓-पतिः`)
        if bare.endswith(("पतिः", "पतिम्", "पतेः", "पत्ये", "पतौ")) and n0 >= 1 and n0 <= n_syl:
          p0_hits2 = lex.lookup_stem(p0) or lex.lookup_form(p0)
          if p0_hits2:
            top_p0 = max(p0_hits2.items(), key=lambda kv: sum(kv[1].values()))[0]
            if len(top_p0) <= n_syl and sum(1 for m in top_p0 if m) == 1:
              out[top_p0 + tuple("" for _ in range(n_syl - len(top_p0)))] = "पत्यावैश्वर्ये पा॰ ६.२.१८"
  return list(out.items())


def _stem_final_syl_idx(bare_deva: str, n_syl: int) -> int:
  """Return the stem-final syllable index for antodātta ``पा॰ ६.१.२२३`` / ``६.२.१७२``."""
  slp = _deva_to_slp(bare_deva)
  # Disyllabic endings where stem-final vowel is penultimate (`-asya`, `-ena`, `-Aya`, `-AnAm`, `-ezu`, `-eByaH`, `-ayoH`, `-Ani`)
  if slp.endswith(("asya", "ena", "eRa", "Aya", "AnAm", "ARAm", "ezu", "Asu", "eByaH", "AByaH", "ABiH", "AByAm", "ayoH", "Ani", "ARi", "ayA")) and n_syl >= 2:
    return n_syl - 2
  return n_syl - 1


def _detect_clause_contexts(
  padas_bare: Sequence[str],
  vp_clean: str,
  lex: UnifiedVedicLexicon,
  clause_ids: Sequence[int] | None = None,
  minor_breaks: set[int] | None = None,
) -> list[dict]:
  """Compute exact per-pada clause features: ``is_clause_start``, ``in_subordinate``, ``sub_rule``, ``is_amredita``."""
  ctx: list[dict] = []
  sub_rule = ""
  in_sub = False
  last_trig_idx = -1
  m_breaks = minor_breaks or set()
  for i, pd in enumerate(padas_bare):
    bare = _normalize_lookup_key(pd)
    prev_bare = _normalize_lookup_key(padas_bare[i - 1]) if i > 0 else ""
    if clause_ids is not None and len(clause_ids) == len(padas_bare):
      is_start = (i == 0) or (clause_ids[i] != clause_ids[i - 1])
    else:
      is_start = (i == 0) or (prev_bare == "इति")
    if is_start:
      in_sub = False
      sub_rule = ""
      last_trig_idx = -1

    if bare in YAD_VRTTA_TRIGGERS:
      in_sub = True
      sub_rule = "यद्वृत्तान्नित्यम् पा॰ ८.१.६६"
      last_trig_idx = i
    elif bare in NIPATA_8130_TRIGGERS:
      in_sub = True
      sub_rule = "निपातैर्यद्यदिहन्तकुविन्नेच्चेच्चण्कच्चिद्यत्रयुक्तम् पा॰ ८.१.३०"
      last_trig_idx = i
    elif bare in HI_8134_TRIGGERS:
      if not in_sub:
        in_sub = True
        sub_rule = "हि च पा॰ ८.१.३४"
        last_trig_idx = i
    elif in_sub and i > last_trig_idx >= 0:
      had_sub_verb = any(c.get("seen_verb_in_sub") for c in ctx[last_trig_idx + 1 : i])
      if (had_sub_verb or i in m_breaks) and (
        bare in CORRELATIVE_STOPS
        or (had_sub_verb and (
          bare in ("न", "सम्", "प्र", "उप", "उत्", "वि", "आ", "अभि", "निः", "प्रति", "परि")
          or ctx[i - 1].get("seen_verb_in_sub")
        ))
      ):
        in_sub = False
        sub_rule = ""
        last_trig_idx = -1

    nxt_bare = _normalize_lookup_key(padas_bare[i + 1]) if i + 1 < len(padas_bare) else ""
    is_amredita = False
    if (
      i > 0
      and not is_start
      and bare == prev_bare
      and bare not in ALWAYS_ANUDATTA_ENCLITICS
      and nxt_bare not in ("वै", "ह", "हि", "वा", "तु", "उ", "इव", "एव")
    ):
      probe = bare[: min(3, len(bare))]
      if not re.search(rf"{re.escape(probe)}[^\s,।॥—–]*[,;।॥—–]\s*{re.escape(probe)}", vp_clean):
        is_amredita = True
    morph = lex.analyze_morph(bare)
    is_non_verb_func = (
      bare in UPASARGA_DEVA_SET
      or bare in ALWAYS_ANUDATTA_ENCLITICS
      or bare in AMBIGUOUS_ENCLITICS
      or bare in YAD_VRTTA_TRIGGERS
      or bare in NIPATA_8130_TRIGGERS
      or bare in HI_8134_TRIGGERS
      or bare in CORRELATIVE_STOPS
      or bare in ("वै", "एव", "न", "इति", "अपः", "आपः", "अपि", "अत्र", "एतत्", "इदम्", "अस्य", "सविता", "देव", "होता", "पोता", "नेष्टा", "प्रशास्ता")
    )
    # Recognize clear finite verbs (`तरति`, `चरति`, `भवति`, `दधाति`, etc.) EVEN when `vidyut` also parses them as loc-sg `Satf`!
    is_verb_like = (not is_non_verb_func) and (
      bare in _COMMON_VEDIC_VERBS_DEVA
      or (morph["is_tinanta"] and not morph["is_subanta"])
      or (
        bool(morph["tin_entries"])
        and bare.endswith(("ति", "ते", "न्ति", "न्ते", "मि", "सि", "यात्", "येत्", "ईत्", "ध्वे", "ताम्", "न्तु", "स्यति", "स्यते"))
      )
    )
    eff_in_sub = in_sub or (is_verb_like and nxt_bare == "हि")
    eff_sub_rule = ("हि च पा॰ ८.१.३४" if (not in_sub and is_verb_like and nxt_bare == "हि") else (sub_rule or "यद्वृत्तान्नित्यम् पा॰ ८.१.६६"))
    ctx.append({
      "is_clause_start": is_start,
      "in_subordinate": eff_in_sub,
      "sub_rule": eff_sub_rule,
      "is_amredita": is_amredita,
      "seen_verb_in_sub": in_sub and is_verb_like,
    })
  return ctx


_NOT_VOCATIVE_DEVA: frozenset[str] = frozenset({
  "सः", "सा", "तत्", "तम्", "ते", "ताः", "तानि", "यः", "या", "यत्", "यम्", "ये", "याः",
  "एषः", "एषा", "एतत्", "एतम्", "अयम्", "इयम्", "इदम्", "अहम्", "त्वम्", "कः", "किम्",
  "सत्", "असत्", "सर्वम्", "अन्यत्", "एकम्", "द्वयम्", "सत्यम्", "अनृतम्", "व्रतम्", "यज्ञः",
  "पवित्रम्", "मिथुनम्", "वीर्यम्", "वज्रम्", "हविः", "मनः", "यशः",
  "वै", "एव", "हि", "ह", "नु", "उ", "च", "वा", "न", "अथ", "इति", "मा", "सु", "अपि",
  "तु", "चेत्", "नेत्", "अत्र", "तत्र", "यत्र", "एवम्", "तथा", "यथा", "अहो", "उत", "स्म", "इव",
})


def _can_be_vocative(bare: str, morph: dict) -> bool:
  """Return True only for genuine vocative morphology (blocking particles, avyayas, pronouns, and nom-sg abuse)."""
  if not morph["voc_possible"] or morph["is_avyaya"] or bare in _NOT_VOCATIVE_DEVA:
    return False
  if bare.endswith(("म्", "ः", "त्", "न्")) and not bare.endswith(("देवाः", "मरुतः", "आदित्याः", "विश्वे", "अश्विना", "ब्रह्मन्", "राजन्", "आत्मन्")):
    return False
  return True


def generate_pada_candidates(
  pada_deva: str,
  ctx: dict,
  next_pada_deva: str,
  lex: UnifiedVedicLexicon,
  *,
  expected_n_syl: int | None = None,
) -> list[PadaCandidate]:
  """Generate all grammatically valid US-accented candidates for ``pada_deva`` with provenance & priors."""
  bare = _normalize_lookup_key(pada_deva)
  n_syl = _fast_syllable_count(pada_deva)
  if expected_n_syl is not None and n_syl != expected_n_syl:
    ks_exact, _ = syllables_with_marks(pada_deva)
    n_syl = len(ks_exact)
  if n_syl == 0:
    return []
  zero_marks = tuple("" for _ in range(n_syl))
  cands: dict[tuple[tuple[str, ...], str], PadaCandidate] = {}

  def _add(marks: tuple[str, ...], prov: str, role: str, prior_cost: float) -> None:
    if len(marks) != n_syl:
      return
    try:
      ref = _fast_apply_us_marks(pada_deva, marks)
    except ValueError:
      return
    solid = (
      is_solid_provenance(prov)
      or is_solid_provenance(prov.replace("पा\u0970", "पा\u0966"))
      or ("*MW* ŚBr." in prov)
      or ("*Whitney*" in prov)
    )
    key = (marks, role)
    existing = cands.get(key)
    if existing is None or prior_cost < existing.prior_cost:
      cands[key] = PadaCandidate(
        ref=ref, marks=marks, prov=prov, role=role, solid=solid, prior_cost=prior_cost
      )

  form_hits = lex.lookup_form(bare)
  morph = lex.analyze_morph(bare)

  # 1. Always-unaccented enclitics (पा॰ ८.१.१८)
  if bare in ALWAYS_ANUDATTA_ENCLITICS:
    src_note = _format_corpus_prov(form_hits.get(zero_marks, {}))
    prov = f"अनुदात्तम्, पा॰ ८.१.१८{', ' + src_note if src_note else ''}"
    _add(zero_marks, prov, "enclitic", 0.0)
    return list(cands.values())

  # 2. Ambiguous enclitics (`वा`, `ते`, `मा`, `वाम्`, `नौ`)
  if bare in AMBIGUOUS_ENCLITICS:
    acc_mks, _ = AMBIGUOUS_ENCLITICS[bare]
    src_a = _format_corpus_prov(form_hits.get(zero_marks, {}))
    src_u = _format_corpus_prov(form_hits.get(acc_mks, {}))
    prov_a = f"अनुदात्तम्, पा॰ ८.१.१८{', ' + src_a if src_a else ''}"
    _add(zero_marks, prov_a, "enclitic", 0.1 if not ctx["is_clause_start"] else 50.0)
    if bare != "वा" and src_u:  # `वा` is enclitic 'or' (prevocalic `वै᳓` was already restored to `वै`)
      _add(acc_mks, src_u, "nominal", 0.15)
    return list(cands.values())

  # 3. Upasarga / gati (`प्र`, `उप`, `उत्`, `सम्`, `अभि`, `आ`, `वि`, `नि`, `अति`, `अव`, `प्रति`, `परि`, `निः`, etc.)
  if bare in UPASARGA_DEVA_SET:
    u_mks = UPASARGA_ACCENT_MARKS[bare]
    src_u = _format_corpus_prov(form_hits.get(u_mks, {})) or "उपसर्गः, पा॰ १.४.५९"
    _add(u_mks, src_u, "gati_main", 0.05)
    # Subordinate-clause anudātta upasarga (पा॰ ८.१.७१ तिङि चोदात्तवति) — constrained by Viterbi transition!
    _add(zero_marks, "तिङि चोदात्तवति पा॰ ८.१.७१", "gati_sub", 0.15 if ctx["in_subordinate"] else 0.8)
    # Main-clause chained gati (पा॰ ८.१.७० गतिर्गतावत्) — constrained by Viterbi transition!
    if next_pada_deva and _normalize_lookup_key(next_pada_deva) in UPASARGA_DEVA_SET:
      _add(zero_marks, "गतिर्गतावत् पा॰ ८.१.७०", "gati_chain", 0.05)
    return list(cands.values())

  # 4. Anvādeśa pronouns (`अस्य`, `अस्मै`, `एतत्`, `एनम्`, etc.)
  if bare in ANVADESHA_2434:
    src_a = _format_corpus_prov(form_hits.get(zero_marks, {}))
    _add(zero_marks, f"अन्वादेशे अनुदात्तम्, पा॰ २.४.३४{', ' + src_a if src_a else ''}", "anvadesha", 0.05)
    return list(cands.values())
  if bare in ANVADESHA_2432:
    src_a = _format_corpus_prov(form_hits.get(zero_marks, {}))
    _add(zero_marks, f"अन्वादेशे अनुदात्तम्, पा॰ २.४.३२{', ' + src_a if src_a else ''}", "anvadesha", 0.4)

  # 5. Finite verbs (`तिङन्त`): BOTH main-clause anudātta (पा॰ ८.१.२८) AND accented (subordinate/pādādi)
  # Exclude `-तः` directional adverbs (`उत्तरतः`, `अन्तरतः`), clear nouns (`आपः`/`अपः`/`सविता`/`देव`/`प्रियाः`/`होता`),
  # periphrastic future `lu~w` on `-तृ` nouns, and 2nd-person dual `maDyama`+`dvi` (`उपवसथः`, `एतम्`) while keeping 3du verbs (`भवतः`, `स्तः`)!
  is_non_tin_nominal = (
    bare in ("आपः", "अपः", "उलूखल-मुसले", "दृषद्-उपले", "सविता", "देव", "प्रियाः", "होता", "पोता", "नेष्टा", "प्रशास्ता", "अच्छावाक", "धर्ता", "भर्ता", "हन्ता", "कर्ता", "दाता", "भोक्ता", "वक्ता")
    or bare.endswith(("उत्तरतः", "अन्तरतः", "दक्षिणतः", "पुरतः", "पृष्ठतः", "अभितः", "परितः", "सर्वतः", "उभयतः", "अन्यतः", "अग्रतः", "मध्यतः"))
    or morph["slp"] in _PRONOMINAL_NEVER_SPLIT_SLP
    or (
      morph["is_subanta"]
      and bool(morph["tin_entries"])
      and all(
        (t["purusha"] == "maDyama" and t["vacana"] == "dvi") or t["lakara"] == "lu~w"
        for t in morph["tin_entries"]
      )
      and bare not in _COMMON_VEDIC_VERBS_DEVA
    )
  )
  is_tin = (not is_non_tin_nominal) and (morph["is_tinanta"] or bare in _COMMON_VEDIC_VERBS_DEVA)
  if is_tin:
    src_zero = _format_corpus_prov(form_hits.get(zero_marks, {}))
    p_main = f"तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८{', ' + src_zero if src_zero else ''}"
    main_cost = 0.05 if (not ctx["in_subordinate"] and not ctx["is_clause_start"]) else 1.2
    _add(zero_marks, p_main, "tinanta_main", main_cost)

    # Accented finite verb candidates (Pāṇinian verb derivation + clean corpus attestations)
    sub_rule = "वाक्यादिः तिङन्तम्, पा॰ ८.१.१८" if ctx["is_clause_start"] else ctx["sub_rule"]
    sub_cost_base = 0.05 if (ctx["in_subordinate"] or ctx["is_clause_start"]) else 1.4
    pan_verb_cands = _derive_paninian_tinanta_accent(bare, morph, sub_rule=sub_rule)
    pan_verb_marks = {mks for mks, _ in pan_verb_cands}

    # (a) Corpus-attested accented forms of this verb (only padapāṭha sources; reject 1-count glitches contradicting Pāṇini!)
    verb_pp_srcs = frozenset({"RV", "TS", "AV", "TA", "TB", "Whitney", "Lanman", "MW", "MW_SB"})
    verb_acc_hits = [
      (mks, {s: f for s, f in srcs.items() if s in verb_pp_srcs})
      for mks, srcs in form_hits.items()
      if any(mks)
    ]
    verb_acc_hits = [(mks, s) for mks, s in verb_acc_hits if s]
    max_vf = max((sum(s.values()) for _, s in verb_acc_hits), default=0)
    max_vsrcs = max((len(s) for _, s in verb_acc_hits), default=0)
    for mks, srcs in verb_acc_hits:
      tot_v = sum(srcs.values())
      if max_vf >= 20 and tot_v < max(2, int(max_vf * 0.02)):
        continue
      # Drop 1-count single-source corpus glitch (e.g. AV `यच्छति᳓ (1)`) when Pāṇinian gaṇa or multi-source accent disagrees!
      if tot_v == 1 and len(srcs) == 1 and (
        (pan_verb_marks and mks not in pan_verb_marks) or max_vsrcs >= 2 or max_vf >= 3
      ):
        continue
      src_s = _format_corpus_prov(srcs)
      _add(mks, f"{sub_rule}, {src_s}", "tinanta_sub", sub_cost_base)
    # (b) Pāṇinian verb accent rules
    for mks, prov in pan_verb_cands:
      _add(mks, prov, "tinanta_sub", sub_cost_base + 0.15)

  # 6. Attested inflected corpus forms (nominals, particles, pronouns, adverbs, kṛdantas)
  # Suppress spurious `nominal` duplicates (like loc-sg `शतृ` `भवति`, `एति`, `वदति`, `स्पृशति`) for clear finite verbs!
  is_clear_finite_verb = is_tin and (
    bare in _COMMON_VEDIC_VERBS_DEVA
    or (not morph["is_subanta"] and not morph["is_avyaya"])
    or (
      bool(morph["tin_entries"])
      and bare.endswith(("ति", "ते", "न्ति", "न्ते", "मि", "सि", "यात्", "येत्", "ईत्", "ध्वे", "ताम्", "न्तु", "स्यति", "स्यते"))
    )
  )
  nonzero_form_hits = [(mks, srcs) for mks, srcs in form_hits.items() if any(mks)]
  max_form_freq = max((sum(s.values()) for _, s in nonzero_form_hits), default=0)
  for mks, srcs in nonzero_form_hits:
    if is_clear_finite_verb:
      continue
    tot = sum(srcs.values())
    # Filter rare corpus OCR/variant noise (`< 2%` when `>= 25`, `< 3%` when `>= 100` unless VS/multi-primary-samhita)
    if max_form_freq >= 100 and tot < int(max_form_freq * 0.03) and "VS" not in srcs:
      continue
    if max_form_freq >= 25 and tot < max(2, int(max_form_freq * 0.02)):
      continue
    prov = _format_corpus_prov(srcs)
    bonus = 0.0
    if "VS" in srcs:
      bonus -= 0.12
    if sum(1 for k in ("RV", "TS", "AV", "TB", "TA") if k in srcs) >= 2:
      bonus -= 0.1
    prior = 0.15 - min(math.log1p(tot) * 0.04, 0.2) + bonus
    _add(mks, prov, "nominal", prior)

  # 7. Stem-projected accents (MW, Macdonell, Lanman)
  # Skip stem homographs when the exact inflected form is already strongly attested in Vedic corpora (>= 50x, e.g. `एव᳓` vs MW `ए᳓व`)!
  if not is_clear_finite_verb and max_form_freq < 50:
    for mks, prov, _ in lex.project_stem_accents(bare):
      prior = 0.35 if ("*Macdonell*" in prov or "*Lanman*" in prov or "*MW* ŚBr." in prov) else 0.55
      _add(mks, prov, "nominal", prior)

  # 8. Pāṇinian kṛdanta & compound rules (`पा॰ ६.१.१९३`, `६.२.१/२/१८/४९/१३९/१७२`, `६.१.२२३`)
  if not is_clear_finite_verb:
    for mks, prov in _derive_paninian_krdanta_and_compound_accents(pada_deva, lex):
      _add(mks, prov, "compound", 0.45)

  # 9. Vocative candidates (`आमन्त्रित`: पा॰ ६.१.१९८ initial vs पा॰ ८.१.१९ non-initial)
  if _can_be_vocative(bare, morph) and not is_tin:
    voc_init_mks = tuple("U" if i == 0 else "" for i in range(n_syl))
    _add(voc_init_mks, "पादादिः आमन्त्रितम् आद्युदात्तम्, पा॰ ६.१.१९८", "voc_init", 1.8 if ctx["is_clause_start"] else 8.0)
    _add(zero_marks, "अपादादिः आमन्त्रितम् अनुदात्तम्, पा॰ ८.१.१९", "voc_noninit", 8.0 if ctx["is_clause_start"] else 4.5)

  # 10. Āmreḍita (`पा॰ ८.१.३ अनुदात्तं च`)
  if ctx["is_amredita"]:
    _add(zero_marks, "आम्रेडितम् अनुदात्तम्, पा॰ ८.१.३", "amredita", 0.1)

  # 11. Fallback (unattested single-accent candidates marked non-solid -> NEVER allowed in AUTO_CLEAN!)
  if not cands:
    for idx in range(n_syl):
      mks = tuple("U" if i == idx else "" for i in range(n_syl))
      _add(mks, "अनाम्नातम् (अनुमानम्)", "guess", 3.0)

  return list(cands.values())


_COMMON_VEDIC_VERBS_DEVA: frozenset[str] = frozenset({
  "अस्ति", "अस्मि", "असि", "सन्ति", "आसीत्", "आसन्", "स्यात्", "स्युः",
  "भवति", "भवन्ति", "भवतु", "भवेत्", "अभवत्", "अभवन्", "बभूव",
  "एति", "एमि", "यन्ति", "इयात्", "अयानि", "आगात्", "अगात्", "अगन्",
  "आह", "आहुः", "उवाच", "ऊचुः", "ब्रूयात्", "ब्रवीति", "अब्रवीत्", "अब्रुवन्",
  "करोति", "कुर्वन्ति", "कुर्यात्", "अकरोत्", "अकुर्वन्", "चकार", "क्रियते", "क्रियन्ते",
  "स्पृशति", "स्पृशन्ति", "वदति", "वदेत्", "चरति", "चरन्ति", "चरिष्यामि", "अचारिषम्",
  "शकेयम्", "अशकत्", "अशकम्", "शक्नोति", "राध्यताम्", "अराधि", "सृजते", "सृजेत",
  "मेने", "जानन्ति", "विदुः", "यक्ष्यते", "यक्ष्यध्वे", "गच्छन्ति", "वसन्ति",
  "अश्नाति", "अश्नीयात्", "गृह्णन्ति", "गृह्णाति", "पचत", "शयीत", "शेते", "वर्तते",
  "पद्यते", "नयति", "णयति", "नीयन्ते", "णीयन्ते", "तनोति", "तनुते", "अतन्वत",
  "युनक्ति", "आप्नोति", "आपयति", "आपयेत्", "ररक्षुः", "अरक्षन्", "ददृशुः",
  "तिष्ठति", "तिष्ठन्ते", "दहन्ति", "यच्छति", "अयच्छन्", "सादयति", "सादयेत्",
  "शृणाति", "हिनस्ति", "स्तृणाति", "हरति", "पादयति", "रभेते", "चरेयुः", "चरान्",
  "वर्धयेत्", "कल्पते", "दधाति", "धत्ते", "जुहोति", "हूयते", "उच्यते",
})


def _sb_step_cost(
  cur_u: str,
  nxt_u: str | None,
  act_w: str | None,
  act_s: str | None,
  *,
  is_last: bool = False,
) -> tuple[float, bool]:
  """Score predicted ŚB marks for ``(cur_u, nxt_u)`` against actual ``(act_w, act_s)``.

  Returns ``(cost, both_disagree_bool)``.
  """
  if nxt_u == "S":
    ew, es = "G", "H"
  elif cur_u == "U" and (nxt_u == "" or nxt_u is None):
    ew, es = "H", "H"
  else:
    ew, es = "", ""

  if is_last and nxt_u is None:
    w_ok = None if act_w is None else (
      act_w == ew
      or (cur_u == "U" and act_w in ("H", ""))
      or (cur_u == "" and act_w in ("", "G", "H"))
      or (cur_u == "S" and act_w in ("", "G"))
    )
    s_ok = None if act_s is None else (
      act_s == es
      or (cur_u == "U" and act_s in ("H", ""))
      or (cur_u == "" and act_s in ("", "H"))
      or (cur_u == "S" and act_s in ("", "H"))
    )
  else:
    w_ok = None if act_w is None else (act_w == ew)
    s_ok = None if act_s is None else (act_s == es)

  if w_ok is None and s_ok is None:
    return 0.0, False
  if (w_ok is True) and (s_ok is True or s_ok is None):
    return 0.0, False
  if (s_ok is True) and (w_ok is None):
    return 0.0, False
  if w_ok is True and s_ok is False:
    return 0.35, False
  if s_ok is True and w_ok is False:
    return 0.40, False
  # BOTH Weber and Śrīdharādi disagree!
  return 12.0, True


def _transition_syntax_cost(prev_c: PadaCandidate, cur_c: PadaCandidate) -> float:
  """Syntactic grammar constraint cost between adjacent pada candidates."""
  # `gati_sub` (पा॰ ८.१.७१) MUST immediately precede another `gati_sub` or an accented verb (`tinanta_sub`)
  if prev_c.role == "gati_sub":
    if cur_c.role not in ("gati_sub", "tinanta_sub"):
      return 1000.0
    return 0.0
  # `gati_chain` (पा॰ ८.१.७०) MUST immediately precede `gati_main` or `gati_chain`
  if prev_c.role == "gati_chain":
    if cur_c.role not in ("gati_main", "gati_chain"):
      return 1000.0
    return 0.0
  # Two consecutive upasargas in a main clause MUST de-accent the first via पा॰ ८.१.७० (`उत् + आ᳓`, `अभि + स᳓म्`)!
  if prev_c.role == "gati_main" and cur_c.role in ("gati_main", "gati_chain"):
    return 80.0
  # Accented `gati_main` immediately before an accented `tinanta_sub` violates पा॰ ८.१.७१
  if prev_c.role == "gati_main" and cur_c.role == "tinanta_sub":
    return 80.0
  # `gati_main` immediately before `tinanta_main` is canonical पा॰ ८.१.२८
  if prev_c.role == "gati_main" and cur_c.role == "tinanta_main":
    return -0.2
  return 0.0


def _decode_sb_accents_viterbi_full(
  vp_clean: str,
  padas_bare: Sequence[str],
  weber_text: str,
  shri_text: str,
  lex: UnifiedVedicLexicon,
  *,
  next_first_mark: str | None = None,
  clause_ids: Sequence[int] | None = None,
  minor_breaks: set[int] | None = None,
) -> tuple[list[PadapathaItem], list[dict], list[tuple[str, int]], dict]:
  """Internal 3-state Viterbi ŚB accent decoder returning items plus alignment diagnostics."""
  if not padas_bare:
    return [], [], [], {}

  dummy_items = [
    PadapathaItem(ar=p, ref=p, prov="", vyat=False, solid=False) for p in padas_bare
  ]
  vp_pieces = _fast_extract_vp_pieces(vp_clean)
  pp_keys, pp_meta, pp_starts, pp_pada_syl_counts = _fast_flatten_pp_and_starts(padas_bare)
  vp_keys = [kv for pc in vp_pieces for kv in pc["keys"]]
  vp_meta = [(pi, si) for pi, pc in enumerate(vp_pieces) for si in range(len(pc["keys"]))]
  pc_syl_sources = _map_pp_to_vp_syllables(
    vp_clean, vp_pieces, pp_keys, pp_meta, vp_keys, vp_meta, pp_starts
  )

  weber_syls = _fast_extract_sb_syllables(weber_text, source="weber") if weber_text else []
  shri_syls = _fast_extract_sb_syllables(shri_text, source="shri") if shri_text else []
  vp_to_w = _align_key_sequences(vp_keys, [s.key for s in weber_syls]) if weber_syls else {}
  vp_to_s = _align_key_sequences(vp_keys, [s.key for s in shri_syls]) if shri_syls else {}

  # Build flat VP syllable descriptors: which pada(s) determine each VP syllable `v`
  n_vp = len(vp_keys)
  act_w: list[str | None] = [weber_syls[vp_to_w[v]].mark if v in vp_to_w else None for v in range(n_vp)]
  act_s: list[str | None] = [shri_syls[vp_to_s[v]].mark if v in vp_to_s else None for v in range(n_vp)]

  vp_syl_info: list[dict] = []
  unmapped: list[tuple[str, int]] = []
  flat_v = 0
  for pi, pc in enumerate(vp_pieces):
    next_starts_av = (
      pi + 1 < len(vp_pieces)
      and vp_pieces[pi + 1]["old"].startswith("ऽ")
      and _no_punct_between(vp_clean, pc, vp_pieces[pi + 1])
    )
    for vsi, srcs in enumerate(pc_syl_sources[pi]):
      if not srcs:
        unmapped.append((pc["old"], vsi))
        vp_syl_info.append({"kind": "unmapped", "owner": -1})
      else:
        src = srcs[0]
        if len(src) == 1:
          pp_si = src[0]
          ii, si = pp_meta[pp_si]
          skip_av = _skip_elided_avagraha_lead(pc, dummy_items[ii], si)
          vp_syl_info.append({
            "kind": "single",
            "owner": ii,
            "pada": ii,
            "syl": si,
            "skip_av": skip_av,
          })
        else:
          s1, s2 = src[0], src[1]
          i1, si1 = pp_meta[s1]
          i2, si2 = pp_meta[s2]
          vp_syl_info.append({
            "kind": "merge",
            "owner": max(i1, i2),
            "p1": i1,
            "s1": si1,
            "p2": i2,
            "s2": si2,
            "pp_s1": s1,
            "pp_s2": s2,
            "pc": pc,
            "vsi": vsi,
            "next_starts_av": next_starts_av,
          })
      flat_v += 1

  P = len(padas_bare)
  owned_by_pada: list[list[int]] = [[] for _ in range(P)]
  for v, info in enumerate(vp_syl_info):
    ow = info["owner"]
    if 0 <= ow < P:
      owned_by_pada[ow].append(v)

  ctxs = _detect_clause_contexts(
    padas_bare, vp_clean, lex, clause_ids=clause_ids, minor_breaks=minor_breaks
  )
  all_cands: list[list[PadaCandidate]] = []
  for i in range(P):
    nxt_p = padas_bare[i + 1] if i + 1 < P else ""
    c_list = generate_pada_candidates(
      padas_bare[i], ctxs[i], nxt_p, lex, expected_n_syl=pp_pada_syl_counts[i] or None
    )
    if not c_list:
      zm = tuple("" for _ in range(max(1, pp_pada_syl_counts[i])))
      c_list = [PadaCandidate(ref=padas_bare[i], marks=zm, prov="अनाम्नातम् (अनुमानम्)", role="guess", solid=False, prior_cost=5.0)]
    all_cands.append(c_list)

  def _eval_vp_syl_mark(v: int, prev_c: PadaCandidate | None, cur_c: PadaCandidate, prev_vp_u: str) -> str:
    info = vp_syl_info[v]
    if info["kind"] == "unmapped":
      return ""
    if info["kind"] == "single":
      if info["skip_av"]:
        return ""
      if info["pada"] == cur_i:
        si = info["syl"]
        return cur_c.marks[si] if si < len(cur_c.marks) else ""
      return ""
    # Merged syllable `(p1, s1) + (p2, s2)`
    p1, s1, p2, s2 = info["p1"], info["s1"], info["p2"], info["s2"]
    r1 = (
      (cur_c.marks[s1] if s1 < len(cur_c.marks) else "")
      if p1 == cur_i
      else ((prev_c.marks[s1] if s1 < len(prev_c.marks) else "") if prev_c is not None else "")
    )
    r2 = (
      (cur_c.marks[s2] if s2 < len(cur_c.marks) else "")
      if p2 == cur_i
      else ((prev_c.marks[s2] if s2 < len(prev_c.marks) else "") if prev_c is not None else "")
    )
    # Use Weber `G` cue or Shri `H` on preceding anudātta/svarita for ŚB पा॰ ८.२.६ svarita
    prev_cue = False
    if v > 0:
      if act_w[v - 1] == "G":
        prev_cue = True
      elif act_s[v - 1] == "H" and prev_vp_u in ("", "S"):
        prev_cue = True
    # Build tiny local dict/array for `_merged_valid_marks`
    local_refs = [""] * len(pp_keys)
    local_refs[info["pp_s1"]] = r1
    local_refs[info["pp_s2"]] = r2
    _, pref = _merged_valid_marks(
      local_refs,
      pp_keys,
      info["pc"],
      info["vsi"],
      info["pp_s1"],
      info["pp_s2"],
      info["next_starts_av"],
      allow_8_2_6_ekadesha_svarita=True,
      prefer_8_2_6_svarita=prev_cue,
      is_pAdAdi_s2=(s2 == 0),
    )
    return pref

  # Exact 3-state Viterbi DP!
  # State at step `i`: `(cand_idx, last_vp_u)` where `last_vp_u` is US mark of the latest VP syllable emitted <= i.
  # Value: `(total_cost, sb_mismatch_cost, prev_state)`
  dp: list[dict[tuple[int, str], tuple[float, float, tuple[int, str] | None]]] = [{} for _ in range(P)]

  for cur_i in range(P):
    v_list = owned_by_pada[cur_i]
    cands_i = all_cands[cur_i]
    if cur_i == 0:
      for k, c in enumerate(cands_i):
        # Enforce no gati_sub/gati_chain end-violation handled on transition; forbid enclitic at i == 0
        init_pen = 1000.0 if c.role == "enclitic" else 0.0
        sb_c = 0.0
        last_u = ""
        last_v = -1
        for v in v_list:
          u_v = _eval_vp_syl_mark(v, None, c, last_u)
          if last_v >= 0:
            sc, _ = _sb_step_cost(last_u, u_v, act_w[last_v], act_s[last_v])
            sb_c += sc
          last_u = u_v
          last_v = v
        tot = c.prior_cost + init_pen + sb_c
        st = (k, last_u)
        if st not in dp[0] or tot < dp[0][st][0]:
          dp[0][st] = (tot, sb_c, None)
    else:
      prev_v_last = -1
      for back in range(cur_i - 1, -1, -1):
        if owned_by_pada[back]:
          prev_v_last = owned_by_pada[back][-1]
          break
      cands_prev = all_cands[cur_i - 1]
      for (pk, prev_u), (p_tot, p_sb, _) in dp[cur_i - 1].items():
        pcand = cands_prev[pk]
        for k, c in enumerate(cands_i):
          syn_c = _transition_syntax_cost(pcand, c)
          if syn_c >= 900.0:
            continue
          sb_c = 0.0
          last_u = prev_u
          last_v = prev_v_last
          for v in v_list:
            u_v = _eval_vp_syl_mark(v, pcand, c, last_u)
            if last_v >= 0:
              sc, _ = _sb_step_cost(last_u, u_v, act_w[last_v], act_s[last_v])
              sb_c += sc
            last_u = u_v
            last_v = v
          tot = p_tot + c.prior_cost + syn_c + sb_c
          st = (k, last_u)
          if st not in dp[cur_i] or tot < dp[cur_i][st][0]:
            dp[cur_i][st] = (tot, p_sb + sb_c, (pk, prev_u))

  # Finalize last syllable emission and pick best terminal state
  last_vp_idx = n_vp - 1
  best_end_st: tuple[int, str] | None = None
  best_end_tot = float("inf")
  for (k, last_u), (tot, sb_c, prev_st) in dp[P - 1].items():
    # Forbid dangling gati_sub / gati_chain at very end of kaṇḍikā
    if all_cands[P - 1][k].role in ("gati_sub", "gati_chain"):
      continue
    end_sb, _ = _sb_step_cost(
      last_u, next_first_mark, act_w[last_vp_idx] if last_vp_idx >= 0 else None,
      act_s[last_vp_idx] if last_vp_idx >= 0 else None, is_last=True
    ) if last_vp_idx >= 0 else (0.0, False)
    if tot + end_sb < best_end_tot:
      best_end_tot = tot + end_sb
      best_end_st = (k, last_u)

  if best_end_st is None:
    # Fallback if hard constraints eliminated all terminal states
    chosen = [cands[0] for cands in all_cands]
  else:
    chosen_idxs: list[int] = [0] * P
    st = best_end_st
    for i in range(P - 1, -1, -1):
      chosen_idxs[i] = st[0]
      nxt_st = dp[i][st][2]
      if nxt_st is None:
        break
      st = nxt_st
    chosen = [all_cands[i][chosen_idxs[i]] for i in range(P)]

  # Consecutive-udātta / tie ambiguity check (ensures ZERO silent errors on AUTO_CLEAN!)
  ambiguous_padas, base_us, total_base_bd, viterbi_disagree = _find_masked_ambiguous_padas(
    chosen, all_cands, owned_by_pada, vp_syl_info, act_w, act_s, pp_keys, next_first_mark
  )

  items = [
    PadapathaItem(
      ar=c.ref,
      ref=c.ref,
      prov=c.prov,
      vyat=False,
      solid=c.solid,
    )
    for c in chosen
  ]
  unaligned_cnt = sum(1 for aw, as_ in zip(act_w, act_s) if aw is None and as_ is None)
  diag = {
    "ctxs": ctxs,
    "vp_pieces": vp_pieces,
    "base_us": base_us,
    "both_disagree_count": total_base_bd,
    "unaligned_count": unaligned_cnt,
    "disagree_indices": viterbi_disagree,
    "act_w": act_w,
    "act_s": act_s,
    "vp_syl_info": vp_syl_info,
    "vp_meta": vp_meta,
  }
  return items, ambiguous_padas, unmapped, diag


def decode_sb_accents_viterbi(
  vp_clean: str,
  padas_bare: Sequence[str],
  weber_text: str,
  shri_text: str,
  lex: UnifiedVedicLexicon,
  *,
  next_first_mark: str | None = None,
  clause_ids: Sequence[int] | None = None,
) -> tuple[list[PadapathaItem], list[dict], list[tuple[str, int]]]:
  """Run exact 3-state Viterbi ŚB accent decoding over ``padas_bare`` against Weber & Śrīdharādi.

  Returns ``(padapatha_items, ambiguous_padas, unmapped_vp_syllables)``.
  """
  items, ambig, unmapped, _ = _decode_sb_accents_viterbi_full(
    vp_clean, padas_bare, weber_text, shri_text, lex,
    next_first_mark=next_first_mark, clause_ids=clause_ids,
  )
  return items, ambig, unmapped


def _find_masked_ambiguous_padas(
  chosen: Sequence[PadaCandidate],
  all_cands: Sequence[Sequence[PadaCandidate]],
  owned_by_pada: Sequence[Sequence[int]],
  vp_syl_info: Sequence[dict],
  act_w: Sequence[str | None],
  act_s: Sequence[str | None],
  pp_keys: Sequence[tuple[str, str]],
  next_first_mark: str | None,
) -> tuple[list[dict], list[str], int, list[int]]:
  """Detect padas where an alternative accent candidate achieves equal ŚB-mark fit in O(P) local delta time."""
  P = len(chosen)
  n_vp = len(vp_syl_info)
  if P == 0 or n_vp == 0:
    return [], [], 0, []

  def _eval_v(v: int, seq: Sequence[PadaCandidate], prev_u: str) -> str:
    info = vp_syl_info[v]
    if info["kind"] == "unmapped":
      return ""
    if info["kind"] == "single":
      if info["skip_av"]:
        return ""
      mks_p = seq[info["pada"]].marks
      return mks_p[info["syl"]] if info["syl"] < len(mks_p) else ""
    m1 = seq[info["p1"]].marks
    m2 = seq[info["p2"]].marks
    r1 = m1[info["s1"]] if info["s1"] < len(m1) else ""
    r2 = m2[info["s2"]] if info["s2"] < len(m2) else ""
    prev_cue = False
    if v > 0:
      if act_w[v - 1] == "G":
        prev_cue = True
      elif act_s[v - 1] == "H" and prev_u in ("", "S"):
        prev_cue = True
    local_refs = [""] * len(pp_keys)
    local_refs[info["pp_s1"]] = r1
    local_refs[info["pp_s2"]] = r2
    _, pref = _merged_valid_marks(
      local_refs, pp_keys, info["pc"], info["vsi"], info["pp_s1"], info["pp_s2"],
      info["next_starts_av"], allow_8_2_6_ekadesha_svarita=True,
      prefer_8_2_6_svarita=prev_cue, is_pAdAdi_s2=(info["s2"] == 0),
    )
    return pref

  # Compute baseline US marks and per-syllable ŚB costs ONCE (O(n_vp))!
  base_us: list[str] = [""] * n_vp
  for v in range(n_vp):
    base_us[v] = _eval_v(v, chosen, base_us[v - 1] if v > 0 else "")

  base_sc: list[float] = [0.0] * n_vp
  base_bd: list[int] = [0] * n_vp
  disagree_indices: list[int] = []
  for v in range(n_vp):
    nxt = base_us[v + 1] if v + 1 < n_vp else next_first_mark
    sc, bd = _sb_step_cost(base_us[v], nxt, act_w[v], act_s[v], is_last=(v == n_vp - 1))
    base_sc[v] = sc
    base_bd[v] = 1 if bd else 0
    if bd:
      disagree_indices.append(v)

  total_base_sb = sum(base_sc)
  total_base_bd = sum(base_bd)

  # Map each pada `i` to the narrow range of VP syllables affected by changing pada `i`
  pada_vp_range: list[tuple[int, int] | None] = [None] * P
  for v, info in enumerate(vp_syl_info):
    touched = []
    if info["kind"] == "single":
      touched.append(info["pada"])
    elif info["kind"] == "merge":
      touched.append(info["p1"])
      touched.append(info["p2"])
    for pi in touched:
      if 0 <= pi < P:
        rng = pada_vp_range[pi]
        pada_vp_range[pi] = (v, v) if rng is None else (min(rng[0], v), max(rng[1], v))

  ambig: list[dict] = []
  trial = list(chosen)
  for i in range(P):
    rng = pada_vp_range[i]
    if rng is None:
      continue
    v_lo, v_hi = rng
    # Changing `us[v_lo..v_hi]` can also affect `v_hi + 1` if it uses `prev_u` cue, and ŚB step at `v_lo - 1 .. v_hi + 1`
    u_hi = min(n_vp - 1, v_hi + 1)
    s_lo = max(0, v_lo - 1)
    s_hi = u_hi

    best_c = chosen[i]
    alt_seen: set[tuple[str, ...]] = {best_c.marks}
    alts: list[dict] = []
    for cand in all_cands[i]:
      if cand.marks in alt_seen:
        continue
      if i > 0 and _transition_syntax_cost(chosen[i - 1], cand) >= 50.0:
        continue
      if i + 1 < P and _transition_syntax_cost(cand, chosen[i + 1]) >= 50.0:
        continue
      if cand.role == "enclitic" and cand.prior_cost >= 10.0:
        continue
      if cand.role in ("voc_init", "voc_noninit") and cand.prior_cost >= 1.0:
        continue
      if cand.role == "guess":
        continue

      trial[i] = cand
      local_u: dict[int, str] = {}
      for v in range(v_lo, u_hi + 1):
        pu = local_u[v - 1] if (v - 1) in local_u else (base_us[v - 1] if v > 0 else "")
        local_u[v] = _eval_v(v, trial, pu)

      delta_sb = 0.0
      delta_bd = 0
      for v in range(s_lo, s_hi + 1):
        cu = local_u.get(v, base_us[v])
        nu = local_u.get(v + 1, base_us[v + 1]) if v + 1 < n_vp else next_first_mark
        sc, bd = _sb_step_cost(cu, nu, act_w[v], act_s[v], is_last=(v == n_vp - 1))
        delta_sb += sc - base_sc[v]
        delta_bd += (1 if bd else 0) - base_bd[v]

      trial_bd = total_base_bd + delta_bd
      trial_sb = total_base_sb + delta_sb
      if trial_bd == 0 and trial_sb <= total_base_sb + 0.05:
        if cand.role == "compound" and best_c.role == "nominal" and best_c.prior_cost <= 0.15:
          continue
        # NEVER bypass masked `tinanta_main` vs `tinanta_sub` ambiguity!
        # Only skip when `best_c` is genuinely a non-ambiguous main-clause verb (`tinanta_main` anudātta in non-subordinate clause)
        # AND `cand` is a subordinate verb? NO: even a masked `tinanta_sub` vs `tinanta_main` MUST be caught if `best_c` is `tinanta_sub`!
        if best_c.role == "tinanta_main" and cand.role == "tinanta_sub" and (cand.prior_cost - best_c.prior_cost) >= 1.2:
          # Only skip if `best_c` is anudātta in a main clause where `tinanta_sub` has high prior (`>= 1.4`) —
          # NEVER skip when `best_c` is accented (`tinanta_sub`) and anudātta `tinanta_main` fits equally well!
          continue
        alt_seen.add(cand.marks)
        alts.append({"ref": cand.ref, "role": cand.role, "prov": cand.prov, "sb_cost": round(trial_sb, 2)})
    trial[i] = best_c
    if alts:
      ambig.append({
        "pada_idx": i,
        "chosen": best_c.ref,
        "chosen_role": best_c.role,
        "chosen_prov": best_c.prov,
        "alternatives": alts,
      })
  return ambig, base_us, total_base_bd, disagree_indices


# ---------------------------------------------------------------------------
# Component 4: Self-Certifying Classifier & Adjudication Queue Exporter
# ---------------------------------------------------------------------------


def solve_kandika(
  cluster: KandikaCluster,
  lex: UnifiedVedicLexicon,
  *,
  kandika_id: str = "",
  next_first_mark: str | None = None,
  fast_pass1: bool = False,
) -> SolveResult:
  """Solve, verify, and self-certify one Śatapatha Brāhmaṇa kaṇḍikā."""
  kid = kandika_id or cluster.key

  # Skip non-mantra unaccented intro blocks (e.g. `हरिः-ओ३म्।`, `१०.6.३`)
  if not cluster.weber and not cluster.shri:
    return SolveResult(
      kandika_id=kid, heading=cluster.heading, sub_idx=cluster.sub_idx,
      status="SKIPPED", vp_clean=cluster.vp_body, vp_summary=cluster.vp_summary,
      vp_accented=cluster.vp_body, items=[], padapatha_block="",
      preserve_vp=True, reasons=["no_weber_or_shri"],
    )

  # 1. Clean VP base (or stripped existing US VP when preserving already-US VP verbatim!)
  if cluster.is_already_us:
    vp_clean = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", cluster.vp_body)
    vp_clean = re.sub(r"\+\+\+.*?\+\+\+", " ", vp_clean, flags=re.S)
    vp_clean = accent.strip_accents(vp_clean).strip()
    preserve_vp = True
  else:
    vp_clean, _ = build_clean_vp_base(cluster.weber, cluster.shri, cluster.visvara)
    preserve_vp = False

  # 2. Split into normalized bare padapāṭha words (with clause IDs, minor breaks, and morphological sandhi ambiguities)
  padas_bare, clause_ids, minor_breaks, morph_ambigs = _split_vp_with_diagnostics(vp_clean, lex)
  if not padas_bare:
    return SolveResult(
      kandika_id=kid, heading=cluster.heading, sub_idx=cluster.sub_idx,
      status="NEEDS_ADJUDICATION", vp_clean=vp_clean, vp_summary=cluster.vp_summary,
      vp_accented="", items=[], padapatha_block="", preserve_vp=preserve_vp,
      reasons=["empty_padas"],
    )

  # 3. 3-State Viterbi ŚB accent decoding (with precomputed fast alignment & diagnostics!)
  items, ambiguous_padas, viterbi_unmapped, vdiag = _decode_sb_accents_viterbi_full(
    vp_clean, padas_bare, cluster.weber, cluster.shri, lex,
    next_first_mark=next_first_mark, clause_ids=clause_ids, minor_breaks=minor_breaks,
  )
  pp_block = format_padapatha_block(items)

  # 4. Fast pre-checks BEFORE calling slow `build_sb_vp_from_padapatha` + `audit_padapatha_against_sb` + validator!
  padas_ref = [it.ref for it in items]
  ok_vp, fail_vp, win_vp, _ = verify_mantra_sandhi(padas_ref, vp_clean)
  w_ref_clean = normalize_sb_orthography(strip_weber_footnotes(cluster.weber)) if cluster.weber else ""
  s_ref_clean = _clean_shri_geminates(normalize_sb_orthography(strip_shri_pratika(cluster.shri))) if cluster.shri else ""
  ok_w, fail_w, win_w, _ = (
    verify_mantra_sandhi(padas_ref, w_ref_clean)
    if w_ref_clean else (False, 0, "", "")
  )
  ok_s, fail_s, win_s, _ = (
    verify_mantra_sandhi(padas_ref, s_ref_clean)
    if s_ref_clean else (False, 0, "", "")
  )
  # Require strict 2-of-3 witness consensus (W+S, or W+V, or S+V) so solo Weber/Shri typos (`अनिरुक्तौ`) NEVER certify AUTO_CLEAN!
  ok_2of3 = ok_w and ok_s
  if not ok_2of3 and (ok_w or ok_s) and cluster.visvara:
    v_sandhi_ref = _clean_visvara_for_sandhi(cluster.visvara, w_ref_clean or s_ref_clean)
    if v_sandhi_ref:
      ok_v, _, _, _ = verify_mantra_sandhi(padas_ref, v_sandhi_ref)
      ok_2of3 = ok_v and (ok_w or ok_s)

  reasons: list[str] = []
  if not ok_vp:
    reasons.append(f"sandhi_vp_fail@{fail_vp}:{win_vp}")
  if not ok_2of3:
    reasons.append(f"sandhi_mula_fail(W={fail_w},S={fail_s})")
  if morph_ambigs:
    reasons.extend(morph_ambigs[:4])
  if viterbi_unmapped:
    reasons.append(f"unmapped:{len(viterbi_unmapped)}")
  if vdiag["both_disagree_count"] > 0:
    reasons.append(f"disagree_syls:{vdiag['both_disagree_count']}")
  if vdiag["unaligned_count"] > 0:
    reasons.append(f"unaligned_syls:{vdiag['unaligned_count']}")

  weak_padas = [i for i, it in enumerate(items) if not it.solid or "अनाम्नातम्" in it.prov]
  if weak_padas:
    reasons.append(f"weak_prov:{weak_padas[:6]}")
  if ambiguous_padas:
    reasons.append(f"ambiguous_padas:{[a['pada_idx'] for a in ambiguous_padas[:6]]}")
  if not cluster.weber or not cluster.shri:
    reasons.append("missing_one_sb_source")

  ctxs_check = vdiag["ctxs"]
  _DANGLING_LYAP_TAILS = frozenset({"धाय", "हृत्य", "कृत्य", "गत्य", "एत्य", "दाय", "स्थाय", "नीय", "भूय", "श्रुत्य"})
  for i, it in enumerate(items):
    bare_it = _normalize_lookup_key(it.ref)
    if "-" in it.ref and any(t in it.prov for t in ("८.१.२८", "८.१.६६", "८.१.३०", "८.१.३४", "८.१.७१")):
      reasons.append(f"compound_upasarga_tinanta@{i}:{it.ref}")
    if bare_it.startswith(("वषट्कुर्य", "वषट्करो", "वषट्कुर्व", "तिरस्करो", "पुरस्करो", "प्रादुर्भव", "अस्तमे", "अन्वाह", "प्राह", "उपाह", "समीधे")):
      reasons.append(f"compound_upasarga_tinanta@{i}:{it.ref}")
    if "८.१.१९" in it.prov:
      reasons.append(f"vocative_noninit_review@{i}:{it.ref}")
    if bare_it in _DANGLING_LYAP_TAILS:
      reasons.append(f"dangling_lyap_tail@{i}:{it.ref}")
    slp_p = _deva_to_slp(bare_it)
    if slp_p in _NEVER_SINGLE_PADA_SLP:
      reasons.append(f"fused_sandhi_pada@{i}:{it.ref}")
    if ctxs_check[i]["in_subordinate"] and not has_us_accents(it.ref) and "८.१.२८" in it.prov:
      reasons.append(f"subordinate_verb_anudatta@{i}:{it.ref}")
    if (
      not ctxs_check[i]["in_subordinate"]
      and not ctxs_check[i]["is_clause_start"]
      and any(t in it.prov for t in ("८.१.६६", "८.१.३०", "८.१.३४"))
    ):
      reasons.append(f"main_clause_verb_accented@{i}:{it.ref}")

  # 5. Full official build + audit + validator + reconciler on EVERY candidate passing fast gates
  # (skipped in `fast_pass1=True` since `solve_sb_file` Pass 2 runs full official verification once with `next_first_mark`!).
  audit: SbAuditReport | None = None
  v_issues: list[str] = []
  rec_logs: list[str] = []
  if not reasons and not fast_pass1:
    if preserve_vp:
      vp_sum = cluster.vp_summary
      vp_acc = cluster.vp_body
      unmapped = viterbi_unmapped
    else:
      vp_sum, vp_acc, unmapped = build_sb_vp_from_padapatha(
        vp_clean, items, weber_text=cluster.weber, shri_text=cluster.shri,
        orig_summary=cluster.vp_summary,
      )
    audit = audit_padapatha_against_sb(
      vp_clean, items, cluster.weber, cluster.shri, next_first_mark=next_first_mark
    )
    if unmapped:
      reasons.append(f"unmapped:{len(unmapped)}")
    disagree_syls = [s for s in audit.syllables if s.status == "both_disagree"]
    if disagree_syls:
      reasons.append(f"disagree_syls:{len(disagree_syls)}")
    unaligned_syls = [s for s in audit.syllables if s.status == "unaligned"]
    if unaligned_syls:
      reasons.append(f"unaligned_syls:{len(unaligned_syls)}")
    if audit.unflagged_vyatyasta_padas:
      reasons.append(f"unflagged_vyat:{audit.unflagged_vyatyasta_padas}")
    if audit.possibly_spurious_vyatyasta_padas:
      reasons.append(f"spurious_vyat:{audit.possibly_spurious_vyatyasta_padas}")
    if not reasons:
      assembled = (
        f"## {cluster.heading}\n\n"
        f"<details open><summary>{vp_sum}</summary>\n\n{vp_acc}\n</details>\n\n"
        + (f"<details><summary>मूलम् - श्रीधरादि</summary>\n\n{cluster.shri}\n</details>\n\n" if cluster.shri else "")
        + (f"<details><summary>मूलम् - Weber</summary>\n\n{cluster.weber}\n</details>\n\n" if cluster.weber else "")
        + f"{pp_block}\n"
      )
      v_issues = [f"{vi.kind}: {vi.message} ({vi.line})" for vi in validate_accented_markdown(assembled)]
      _, rec_logs = reconcile_markdown_blocks(assembled)
      if v_issues:
        reasons.append(f"val_issues:{len(v_issues)}")
      if rec_logs:
        reasons.append(f"rec_logs:{len(rec_logs)}")
  else:
    if preserve_vp:
      vp_sum = cluster.vp_summary
      vp_acc = cluster.vp_body
    else:
      vp_sum = cluster.vp_summary or "विश्वास-प्रस्तुतिः"
      if "स्वराङ्कित" not in vp_sum:
        vp_sum = "विश्वास-प्रस्तुतिः (स्वराङ्किता)"
      vp_acc = _fast_apply_vp_marks(vp_clean, vdiag["vp_pieces"], vdiag["base_us"])
    unmapped = viterbi_unmapped

  status = "AUTO_CLEAN" if not reasons else "NEEDS_ADJUDICATION"

  lex_hits: list[str] = []
  fast_disagree: list[dict] = []
  if status == "NEEDS_ADJUDICATION":
    lex_hits = _summarize_lexicon_hits(padas_bare, lex)
    if audit is None and vdiag:
      vp_pcs = vdiag["vp_pieces"]
      vp_mt = vdiag["vp_meta"]
      b_us = vdiag["base_us"]
      aw_l = vdiag["act_w"]
      as_l = vdiag["act_s"]
      sinfo = vdiag["vp_syl_info"]
      for v in vdiag["disagree_indices"]:
        pi_t, _ = vp_mt[v]
        tok_s = vp_pcs[pi_t]["old"]
        info = sinfo[v]
        p_idxs = [info["pada"]] if info["kind"] == "single" else ([info["p1"], info["p2"]] if info["kind"] == "merge" else [])
        nxt_u = b_us[v + 1] if v + 1 < len(b_us) else next_first_mark
        exp_w = "G" if nxt_u == "S" else ("H" if b_us[v] == "U" and nxt_u != "U" else "")
        exp_s = "H" if (nxt_u == "S" or (b_us[v] == "U" and nxt_u != "U")) else ""
        fast_disagree.append({
          "syl_idx": v,
          "token": tok_s,
          "us": b_us[v],
          "exp_w": exp_w,
          "exp_s": exp_s,
          "act_w": aw_l[v],
          "act_s": as_l[v],
          "padas": [items[pi].ref for pi in p_idxs if 0 <= pi < len(items)],
        })

  return SolveResult(
    kandika_id=kid,
    heading=cluster.heading,
    sub_idx=cluster.sub_idx,
    status=status,
    vp_clean=vp_clean,
    vp_summary=vp_sum,
    vp_accented=vp_acc,
    items=items,
    padapatha_block=pp_block,
    preserve_vp=preserve_vp,
    reasons=reasons,
    audit=audit,
    ambiguous_padas=ambiguous_padas,
    validation_issues=v_issues,
    reconciler_logs=rec_logs,
    sandhi_ok=(ok_vp, ok_w, ok_s),
    unmapped=unmapped,
    lexicon_hits=lex_hits,
    disagree_details=fast_disagree,
  )


def _summarize_lexicon_hits(padas_bare: Sequence[str], lex: UnifiedVedicLexicon, limit: int = 35) -> list[str]:
  """Collect concise retrieved lexicon hits for adjudication queue records."""
  seen: set[str] = set()
  hits: list[str] = []
  for p in padas_bare:
    key = _normalize_lookup_key(p)
    if key in seen or len(key) < 2:
      continue
    seen.add(key)
    parts: list[str] = []
    f_hits = lex.lookup_form(key)
    if f_hits:
      top = sorted(f_hits.items(), key=lambda kv: -sum(kv[1].values()))[:3]
      for mks, srcs in top:
        try:
          acc = _fast_apply_us_marks(key, mks)
        except ValueError:
          continue
        parts.append(f"{acc} ({_format_corpus_prov(srcs)})")
    else:
      for mks, prov, _ in lex.project_stem_accents(key)[:2]:
        try:
          acc = _fast_apply_us_marks(key, mks)
        except ValueError:
          continue
        parts.append(f"{acc} ({prov})")
    if parts:
      hits.append(f"{key}: " + " | ".join(parts))
      if len(hits) >= limit:
        break
  return hits


def solve_sb_file(
  md_path: str,
  lex: UnifiedVedicLexicon,
  *,
  rel_root: str = "",
) -> list[SolveResult]:
  """Solve and self-certify all kaṇḍikās in one Śatapatha Brāhmaṇa Markdown file."""
  txt = open(md_path, encoding="utf-8").read()
  clusters = parse_sb_markdown_clusters(txt)
  rel = os.path.relpath(md_path, rel_root) if rel_root else os.path.basename(md_path)

  # Pass 1: fast solve each kaṇḍikā (skipping official audit/validator on non-final kaṇḍikās since Pass 2 runs them once with `next_first_mark`!)
  n_cl = len(clusters)
  prelim = [
    solve_kandika(
      cl, lex, kandika_id=f"{rel}::{cl.key}", next_first_mark=None,
      fast_pass1=(idx + 1 < n_cl),
    )
    for idx, cl in enumerate(clusters)
  ]
  first_marks: list[str | None] = []
  for r in prelim:
    if r.vp_accented:
      scanned = _fast_scan_deva_syllables(r.vp_accented[:32])
      if scanned:
        s0 = scanned[0][0]
        first_marks.append("S" if US_SVARITA in s0 else ("U" if US_UDATTA in s0 else ""))
      else:
        first_marks.append(None)
    else:
      first_marks.append(None)

  # Pass 2: run full official certification with `next_first_mark` on EVERY AUTO_CLEAN candidate
  # (and on near-clean kaṇḍikās whose sole disagreement was on the final syllable!).
  results: list[SolveResult] = []
  for idx, (cl, r) in enumerate(zip(clusters, prelim)):
    nxt_m = first_marks[idx + 1] if idx + 1 < n_cl else None
    need_recheck = (
      r.status != "SKIPPED"
      and (
        (r.status == "AUTO_CLEAN" and idx + 1 < n_cl)
        or (
          nxt_m is not None
          and len(r.reasons) == 1
          and r.reasons[0] == "disagree_syls:1"
          and r.disagree_details
          and r.disagree_details[0]["syl_idx"] == _fast_syllable_count(r.vp_clean) - 1
        )
      )
    )
    if need_recheck:
      r = solve_kandika(cl, lex, kandika_id=f"{rel}::{cl.key}", next_first_mark=nxt_m, fast_pass1=False)
    results.append(r)
  return results


def export_adjudication_jsonl(
  file_results: Sequence[tuple[str, Sequence[KandikaCluster], Sequence[SolveResult]]],
  out_jsonl_path: str,
) -> int:
  """Export all ``NEEDS_ADJUDICATION`` kaṇḍikās into a compact JSONL adjudication queue."""
  os.makedirs(os.path.dirname(out_jsonl_path), exist_ok=True)
  written = 0
  with open(out_jsonl_path, "w", encoding="utf-8") as f:
    for md_path, clusters, results in file_results:
      for cl, res in zip(clusters, results):
        if res.status != "NEEDS_ADJUDICATION":
          continue
        disagree_details = []
        if res.audit:
          for s in res.audit.syllables:
            if s.status in ("both_disagree", "unaligned"):
              disagree_details.append({
                "syl_idx": s.vp_syl_idx,
                "token": s.token,
                "us": s.us_mark,
                "exp_w": s.exp_weber,
                "exp_s": s.exp_shri,
                "act_w": s.act_weber,
                "act_s": s.act_shri,
                "padas": [res.items[pi].ref for pi in s.pada_indices if pi < len(res.items)],
              })
        elif res.disagree_details:
          disagree_details = list(res.disagree_details)
        rec = {
          "id": res.kandika_id,
          "file": md_path,
          "heading": cl.heading,
          "sub_idx": cl.sub_idx,
          "preserve_vp": res.preserve_vp,
          "reasons": res.reasons,
          "weber": cl.weber,
          "shri": cl.shri,
          "visvara": cl.visvara,
          "sayana_excerpt": cl.sayana[:1200],
          "harisvami_excerpt": cl.harisvami[:800],
          "eggeling_excerpt": cl.eggeling[:1000],
          "draft_vp": res.vp_accented,
          "draft_vp_clean": res.vp_clean,
          "draft_padapatha": [
            f"- {it.ref} ({it.prov})" for it in res.items
          ],
          "disagree_syllables": disagree_details,
          "ambiguous_padas": res.ambiguous_padas,
          "validation_issues": res.validation_issues,
          "reconciler_logs": res.reconciler_logs,
          "sandhi_ok": list(res.sandhi_ok),
          "unmapped": res.unmapped,
          "lexicon_hits": res.lexicon_hits,
        }
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        written += 1
  return written
