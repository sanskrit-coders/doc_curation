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
   across syllables and cross-pada ``पा० ८.२.४–६`` sandhi mergers, with
   ambiguity/consecutive-udātta masking detection.
4. Self-certifying batch classifier (``AUTO_CLEAN`` vs ``NEEDS_ADJUDICATION``)
   and compact JSONL adjudication queue exporter.
"""

from __future__ import annotations

import dataclasses
import difflib
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
  SbAuditReport,
  SbSyllable,
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

LEXICON_CACHE_VERSION = 1

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

# Always-unaccented enclitics (पा० ८.१.१८)
ALWAYS_ANUDATTA_ENCLITICS: frozenset[str] = frozenset({
  "च", "मे", "त्वा", "नः", "वः", "ह", "स्म", "उ", "इव", "चन", "चित्", "स्वित्", "अह", "ह्यः",
})
# Note: अह (particle 'indeed' in ŚB `तद् अह`, `एतद् अह` is enclitic? No, remove ह्यः; keep exact enclitics!)
ALWAYS_ANUDATTA_ENCLITICS = frozenset({
  "च", "मे", "त्वा", "नः", "वः", "ह", "स्म", "उ", "इव", "चन", "चित्",
})

# Homophones that can be EITHER enclitic anudātta (पा० ८.१.१८) OR accented
AMBIGUOUS_ENCLITICS: dict[str, tuple[tuple[str, ...], str]] = {
  "वा": (("U",), "*RV*, *TS*, *AV*"),       # enclitic 'or' (वा) vs prevocalic वै᳓ (handled separately)
  "ते": (("U",), "*RV*, *TS*, *AV*"),       # enclitic 'to thee' vs nom.pl. 'they' (ते᳓)
  "मा": (("U",), "*RV*, *TS*, *AV*"),       # enclitic 'me' vs prohibitive 'not' (मा᳓)
  "वाम्": (("U",), "*RV*, *TS*, *AV*"),     # enclitic 'you two' vs accented
  "नौ": (("U",), "*RV*, *TS*, *AV*"),       # enclitic 'us two' vs accented
  "त्वाम्": (("U",), "*RV*, *TS*, *AV*"),
}

# Anvādeśa pronouns (पा० २.४.३२ इदमोऽन्वादेशेऽशनुदात्तस्तृतीयादौ / पा० २.४.३४ द्वितीयाटौस्स्वेनः)
ANVADESHA_2432: frozenset[str] = frozenset({
  "अस्य", "अस्मै", "अस्मात्", "अस्मिन्", "अस्याः", "अस्यै", "अस्याम्",
  "अनेन", "अनया", "अयोः", "आभ्याम्", "एभिः", "एभ्यः", "एषाम्", "एषु",
  "आभिः", "आभ्यः", "आसाम्", "आसु", "एतत्", "एतम्", "एताम्", "एतेन",
  "एतस्य", "एतस्मै", "एतस्मात्", "एतस्मिन्", "एते", "एताः", "एतान्", "एतानि",
  "एतेषाम्", "एतेषु", "एतस्याः", "एतस्यै", "एतस्याम्", "एतया", "एतैः", "एतेभ्यः",
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
  sayana: str
  harisvami: str
  eggeling: str

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


# ---------------------------------------------------------------------------
# Accent conversion helpers (classical padapāṭha & IAST -> US)
# ---------------------------------------------------------------------------


def _normalize_lookup_key(word_deva: str) -> str:
  """Canonicalize a bare Devanagari pada for dictionary lookup (keeps `-म्`/`-ः`, normalizes `ँ`/parasavarṇa)."""
  w = accent.strip_accents(word_deva).replace("-", "").replace("ऽ", "").strip()
  for src, dst in (
    ("ᳫँ᳭", "ं"), ("ᳫं᳭", "ं"), ("ᳫँ", "ं"), ("ᳫं", "ं"), ("ᳫ", "ं"),
    ("᳭", ""), ("ᳮ", ""), ("᳟", ""),
    ("व्ँ", "ं"), ("य्ँ", "ं"), ("ल्ँ", "ं"), ("ँ", "ं"),
  ):
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


def _syllable_has_jatya_glide(word_deva: str, syl_idx: int) -> bool:
  """Return True if syllable ``syl_idx`` is immediately preceded by ``् + य/व`` (jātya svarita locus)."""
  syls = _fast_scan_deva_syllables(word_deva)
  return 0 <= syl_idx < len(syls) and syls[syl_idx][1]


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

  hyph_bare: str | None = None
  if "ऽ" in s:
    parts = [re.sub(r"[\u0951\u0952\u1cd0-\u1cff]", "", p) for p in s.split("ऽ") if p]
    if len(parts) >= 2 and all(_DEVANAGARI_RE.search(p) for p in parts):
      hyph_bare = "-".join(parts)

  clean_for_split = s.replace("ऽ", "").replace("-", "")
  scanned = _fast_scan_deva_syllables(clean_for_split)
  n_syl = len(scanned)
  if n_syl == 0:
    return None

  bare_key = _normalize_lookup_key(clean_for_split)
  if not bare_key:
    return None

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
  nfd = unicodedata.normalize("NFD", w.lower())
  if not any(ch in nfd for ch in ("\u0301", "\u0300", "\u0302")):
    return None
  if re.search(r"[^a-z\u0300-\u036f\-]", nfd):
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
  clean_iast = unicodedata.normalize("NFC", stripped_nfd)
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

  hyph_bare: str | None = None
  if len(parts) >= 2 and all(len(p) >= 2 or p in ("a", "ā") for p in parts):
    if len(parts[-1]) >= 3 or parts[-1] in ("ja", "da", "ga", "pa", "ha", "stha", "bhū", "vid", "kṛt", "jña"):
      d_parts = [sanscript.transliterate(p, sanscript.IAST, sanscript.DEVANAGARI) for p in parts]
      if all(_DEVANAGARI_RE.search(dp) for dp in d_parts) and not any(re.search(r"[a-zA-Z]", dp) for dp in d_parts):
        if _normalize_lookup_key("".join(d_parts)) == bare_key:
          hyph_bare = "-".join(d_parts)
  return bare_key, tuple(norm_marks), hyph_bare


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
  scanned = _fast_scan_deva_syllables(us_str.replace("-", ""))
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
  if len(hyph_parts) >= 2:
    clean_parts = [re.sub(r"[\u0951\u0952\u1cd0-\u1cff]", "", p).replace("ँ", "ं") for p in hyph_parts]
    if all(_DEVANAGARI_RE.search(p) for p in clean_parts) and _normalize_lookup_key("".join(clean_parts)) == bare_key:
      hyph_bare = "-".join(clean_parts)
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


def _kosha_get_slp(slp_word: str) -> list:
  kosha = get_vidyut_kosha()
  if kosha is None or not slp_word:
    return []
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
  return res


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
  ) -> None:
    self.form_accents: dict[str, dict[tuple[str, ...], dict[str, int]]] = form_accents or {}
    self.form_hyphens: dict[str, str] = form_hyphens or {}
    self.stem_accents: dict[str, dict[tuple[str, ...], dict[str, int]]] = stem_accents or {}
    self.stem_hyphens: dict[str, str] = stem_hyphens or {}
    self.slp_vocab: dict[str, int] = slp_vocab or {}
    self.vs_mantra_tokens: dict[str, dict[tuple[str, ...], int]] = vs_mantra_tokens or {}
    self._morph_cache: dict[str, dict] = {}

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
          )
      except Exception:
        pass

    lex = cls.build(dict_root=dict_root, vs_dir=vs_dir, tb_dir=tb_dir, ta_dir=ta_dir)
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

    # 5. Build fast SLP1 vocabulary lookup table from all attested inflected forms
    slp_vocab: dict[str, int] = {}
    for w_deva, by_marks in lex.form_accents.items():
      total_f = sum(sum(srcs.values()) for srcs in by_marks.values())
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
      for m in DETAILS_RE.finditer(txt):
        hdr, body = m.group(1), m.group(2)
        if "विश्वास-प्रस्तुतिः" not in hdr and "मूलम्" not in hdr:
          continue
        if "\u0951" not in body and "\u0952" not in body:
          continue
        clean = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]|<[^>]+>", " ", body, flags=re.S)
        us_txt = accent.to_US_accents(clean, pauses=r"[।॥,;]+")
        for tok in tok_re.findall(us_txt):
          if "ऽ" in tok or not _DEVANAGARI_RE.search(tok):
            continue
          bare = _normalize_lookup_key(tok)
          if not bare or len(bare) < 2:
            continue
          ks, mks = syllables_with_marks(tok)
          if not ks or len(ks) != len(syllables_with_marks(bare)[0]):
            continue
          n_acc = sum(1 for mk in mks if mk)
          if n_acc == 1 or (n_acc == 0 and bare in ALWAYS_ANUDATTA_ENCLITICS):
            self._add_form(bare, tuple(mks), "VS", freq=1)

  def _ingest_ta_tb_corpus(self, root_dir: str, tag: str) -> None:
    from doc_curation.sanskrit.accent.reconciler import parse_padapatha_items

    tok_re = re.compile(r"[\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\-]+")
    for fp in sorted(glob.glob(os.path.join(root_dir, "**", "*.md"), recursive=True)):
      if fp.endswith("_index.md"):
        continue
      txt = open(fp, encoding="utf-8", errors="ignore").read()
      for m in DETAILS_RE.finditer(txt):
        hdr, body = m.group(1).strip(), m.group(2)
        if hdr.startswith("पद-पाठः (यान्त्रिकः"):
          for it in parse_padapatha_items(body):
            if not it.solid or "?" in it.ref or not _DEVANAGARI_RE.search(it.ref):
              continue
            bare = _normalize_lookup_key(it.ref)
            ks, mks = syllables_with_marks(it.ref)
            if not ks or len(ks) != len(syllables_with_marks(bare)[0]):
              continue
            n_acc = sum(1 for mk in mks if mk)
            if n_acc > 1 and not _is_dual_accent_word(bare):
              continue
            hyph = accent.strip_accents(it.ref) if "-" in it.ref else None
            self._add_form(bare, tuple(mks), tag, freq=2, hyph=hyph)
        elif hdr == "पद-पाठः":
          for piece in re.split(r"[।॥\s]+", body):
            conv = classical_padapatha_to_us(piece)
            if conv is not None:
              key, marks, hyph = conv
              self._add_form(key, marks, tag, freq=1, hyph=hyph)
        elif hdr == "विश्वास-प्रस्तुतिः" and has_us_accents(body):
          if accent.detect_fake_US_accents(body):
            continue
          clean = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]", " ", body, flags=re.S)
          clean = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", clean)
          for tok in tok_re.findall(clean):
            if "ऽ" in tok or not _DEVANAGARI_RE.search(tok):
              continue
            bare = _normalize_lookup_key(tok)
            if not bare or len(bare) < 2:
              continue
            ks, mks = syllables_with_marks(tok)
            if not ks or len(ks) != len(syllables_with_marks(bare)[0]):
              continue
            n_acc = sum(1 for mk in mks if mk)
            if n_acc == 1:
              self._add_form(bare, tuple(mks), tag, freq=1)

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
      src_tag = "MW_SB" if "ŚBr." in body else "MW"
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

    slp = sanscript.transliterate(key, sanscript.DEVANAGARI, sanscript.SLP1)
    ents = _kosha_get_slp(slp)
    info: dict = {
      "slp": slp,
      "is_tinanta": False,
      "is_subanta": False,
      "is_krdanta": False,
      "is_avyaya": False,
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
        if str(e.vibhakti) == "samboDanam":
          info["voc_possible"] = True
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
            "vibhakti": str(e.vibhakti),
          })
          st = e.lemma
          if st and st not in seen_stems:
            seen_stems.add(st)
            info["sub_stems"].append(st)
        else:
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
    w_keys, _ = syllables_with_marks(key)
    n_w = len(w_keys)
    if n_w == 0:
      return []

    morph = self.analyze_morph(key)
    slp = morph["slp"]

    cand_stems_slp: list[str] = list(morph["sub_stems"])
    # Add stem-stripping fallbacks for Vedic/ŚB proper names and compounds not in vidyut.kosha
    for tail, fins in _DECLENSION_TAILS_SLP:
      if slp.endswith(tail) and len(slp) >= len(tail) + 2:
        pre = slp[: -len(tail)]
        for fin in fins:
          st = pre + fin
          if st not in cand_stems_slp:
            cand_stems_slp.append(st)
    if slp not in cand_stems_slp:
      cand_stems_slp.append(slp)

    results: dict[tuple[str, ...], tuple[set[str], str | None]] = {}
    for st_slp in cand_stems_slp:
      st_deva = sanscript.transliterate(st_slp, sanscript.SLP1, sanscript.DEVANAGARI)
      st_key = _normalize_lookup_key(st_deva)
      hits = self.stem_accents.get(st_key)
      if not hits:
        continue
      st_syls, _ = syllables_with_marks(st_key)
      n_st = len(st_syls)
      if n_st == 0 or n_st > n_w + 1:
        continue
      st_hyph = self.stem_hyphens.get(st_key)
      word_hyph: str | None = None
      if st_hyph and "-" in st_hyph:
        # Project stem hyphenation onto inflected word if prefix matches cleanly
        p0 = st_hyph.split("-", 1)[0]
        if key.startswith(p0) and len(key) > len(p0):
          word_hyph = p0 + "-" + key[len(p0) :]

      for st_marks, srcs in hits.items():
        # Find accented syllable(s) in stem
        acc_positions = [(idx, mk) for idx, mk in enumerate(st_marks) if mk]
        if len(acc_positions) != 1:
          continue
        acc_idx, acc_mk = acc_positions[0]
        if acc_idx < n_w:
          proj = tuple(acc_mk if i == acc_idx else "" for i in range(n_w))
          # Validate jātya svarita on projected syllable
          if acc_mk == "S" and not _syllable_has_jatya_glide(key, acc_idx):
            proj = tuple("U" if i == acc_idx else "" for i in range(n_w))
          src_set, old_h = results.setdefault(proj, (set(), word_hyph))
          src_set.update(srcs.keys())
          if word_hyph and not old_h:
            results[proj] = (src_set, word_hyph)
        # Weak-case oxytonic shift for consonant/monosyllabic stems (पा० ६.१.१६८ / ६.१.१७१)
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

  def word_score_slp(self, slp_w: str) -> int:
    """Fast frequency/validity score of an SLP1 token for the Sandhi-Inverting DP."""
    if not slp_w:
      return 0
    if slp_w in SB_FUNCTION_WORDS_SLP:
      return 1000
    sc = self.slp_vocab.get(slp_w, 0)
    if sc > 0:
      return sc + 20
    # Check stem + kosha
    ents = _kosha_get_slp(slp_w)
    if ents:
      return 15
    try:
      from doc_curation.sanskrit.hyphenator.lexicon import word_count_slp1
      wc = word_count_slp1(slp_w)
      if wc >= 2:
        return min(wc, 10)
    except Exception:
      pass
    return 0


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
  ("aMsaH", ("as", "yas")),
  ("AMsaH", ("as", "yas")),
  ("AMsO", ("as", "yas")),
  ("AMsi", ("as",)),
  ("asu", ("at", "as", "an")),
  ("atsu", ("at",)),
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
  ("uH", ("u",)),
  ("um", ("u",)),
  ("Un", ("u",)),
  ("eH", ("i",)),
  ("oH", ("u",)),
  ("A", ("a", "A")),
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


def build_clean_vp_base(weber: str, shri: str, visvara: str) -> tuple[str, str]:
  """Build a clean, orthographically normalized, sandhi-preserving unaccented ``विश्वास-प्रस्तुतिः`` base.

  Returns ``(vp_clean, base_source)`` where ``base_source`` is ``'visvara'``, ``'weber'``, or ``'shri'``.
  """
  # Remove leading `ॐ॥` from Weber if Śrīdharādi doesn't have it (e.g. Kāṇḍa 14 §01)
  w_clean = normalize_sb_orthography(strip_weber_footnotes(weber)) if weber else ""
  s_clean = normalize_sb_orthography(strip_shri_pratika(shri)) if shri else ""
  if w_clean.startswith("ॐ॥") and s_clean and not s_clean.startswith("ॐ"):
    w_clean = w_clean[2:].strip()

  ref_clean = w_clean or s_clean
  if visvara:
    v_trim = _strip_visvara_preamble(visvara, ref_clean)
    v_clean = normalize_sb_orthography(v_trim)
    v_slp = to_norm_slp(v_clean)
    w_slp = to_norm_slp(w_clean) if w_clean else ""
    s_slp = to_norm_slp(s_clean) if s_clean else ""
    if v_slp and (v_slp == w_slp or v_slp == s_slp):
      # Clean clause-breaking on `।` while preserving inline sandhi verbatim
      formatted = _format_vp_clauses(v_clean)
      return formatted, "visvara"
    # Allow tiny 1-char orthographic drift only if length matches closely AND ratio >= 0.992
    if v_slp and w_slp and abs(len(v_slp) - len(w_slp)) <= 1:
      if difflib.SequenceMatcher(None, v_slp, w_slp).ratio() >= 0.992:
        return _format_vp_clauses(v_clean), "visvara"

  if w_clean:
    return _format_vp_clauses(w_clean), "weber"
  return _format_vp_clauses(s_clean), "shri"


def _format_vp_clauses(text: str) -> str:
  """Normalize spaces and add two-space Markdown line breaks after ``।`` / ``॥`` pauses."""
  s = re.sub(r"\s+", " ", text).strip()
  # Keep avagraha attached nicely (`सो ऽग्निम्` or `सोऽग्निम्`)
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


def _strip_leading_upasargas_tinanta(slp_w: str, lex: UnifiedVedicLexicon) -> list[str] | None:
  """If ``slp_w`` is a prefixed finite verb (``तिङन्त``), split it into ``[upa_1, ..., verb]`` in Devanagari.

  Returns ``None`` if ``slp_w`` is a simplex verb, a nominal, or a ``गतिकृदन्त`` (participle/gerund/infinitive).
  """
  deva_w = sanscript.transliterate(slp_w, sanscript.SLP1, sanscript.DEVANAGARI)
  if deva_w in SIMPLEX_TINANTA_ALLOWLIST:
    return None

  morph = lex.analyze_morph(deva_w)
  tins = morph["tin_entries"]
  krts = morph["krt_entries"]

  # Prefer kṛdanta over rare conditional lṛṅ (e.g. `upEzyan` = Satf participle, not lṛṅ)
  if krts and tins and all(t["lakara"] == "lf~N" for t in tins):
    return None
  # If parsed ONLY as subanta/kṛdanta (gerund/participle/infinitive/action noun), NEVER split upasarga
  if morph["is_subanta"] and not tins:
    # Exception: Vedic prefixed finite verbs missing from classical vidyut.kosha (e.g. `visfjate`, `paristfRAti`, `saMcarAn`)
    if not _is_vedic_prefixed_tinanta_fallback(slp_w, lex):
      return None

  if tins:
    # If ANY tinanta parse is simplex (`prefixes == []`), do NOT split as prefixed
    if any(not t["prefixes"] for t in tins):
      return None
    # Pick shortest-prefix tinanta parse whose prefixes + verb reconstruct `slp_w` cleanly
    for t in sorted(tins, key=lambda x: len(x["prefixes"])):
      res = _split_by_prefix_list(slp_w, t["prefixes"], lex)
      if res is not None:
        return res

  # Fallback for Vedic prefixed finite verbs not in vidyut.kosha (e.g. `visfjate`, `paristfRAti`, `saMcarAn`)
  return _is_vedic_prefixed_tinanta_fallback(slp_w, lex)


def _split_by_prefix_list(slp_w: str, prefixes: Sequence[str], lex: UnifiedVedicLexicon) -> list[str] | None:
  """Peel exact ``vidyut`` upasarga prefixes off ``slp_w`` and return ``[upa_deva, ..., verb_deva]``."""
  if not prefixes:
    return None
  cur_slp = slp_w
  deva_upas: list[str] = []
  for idx, pf in enumerate(prefixes):
    pf_norm = "A" if pf == "AN" else ("ut" if pf == "ud" else ("niH" if pf in ("nir", "nis") else ("duH" if pf in ("dur", "dus") else pf)))
    upa_deva = UPASARGA_SLP_TO_DEVA.get(pf, UPASARGA_SLP_TO_DEVA.get(pf_norm))
    if not upa_deva:
      return None
    rem = _peel_one_upasarga_slp(cur_slp, pf_norm, is_last_prefix=(idx == len(prefixes) - 1), lex=lex)
    if rem is None:
      return None
    deva_upas.append(upa_deva)
    cur_slp = rem

  if len(cur_slp) < 2:
    return None
  verb_deva = sanscript.transliterate(cur_slp, sanscript.SLP1, sanscript.DEVANAGARI)
  # Verify forward sandhi round-trip!
  cands = deva_upas + [verb_deva]
  ok, _, _, _ = verify_mantra_sandhi(
    cands, sanscript.transliterate(slp_w, sanscript.SLP1, sanscript.DEVANAGARI)
  )
  if ok:
    return cands
  return None


def _peel_one_upasarga_slp(
  slp_w: str, pf: str, *, is_last_prefix: bool, lex: UnifiedVedicLexicon
) -> str | None:
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
    return None
  if not is_last_prefix:
    # Prefer candidate starting with a valid next prefix
    return cands[0]

  # Pick the best valid simplex verb form (preferring `vidyut.kosha` Tinanta or attested form!)
  best_cand: str | None = None
  best_score = -1
  for c in dict.fromkeys(cands):
    sc = 0
    ents = _kosha_get_slp(c)
    try:
      from vidyut.kosha import PadaEntry
      if any(isinstance(e, PadaEntry.Tinanta) and not e.dhatu_entry.dhatu.prefixes for e in ents):
        sc += 100
    except Exception:
      pass
    if c in lex.slp_vocab:
      sc += 20 + min(lex.slp_vocab[c], 50)
    # Prefer un-retroflexed `n`/`s` over `R`/`z` on ties
    if c.startswith(("n", "s")):
      sc += 2
    if sc > best_score:
      best_score = sc
      best_cand = c
  return best_cand


_VEDIC_FINITE_ENDINGS_SLP: tuple[str, ...] = (
  "ati", "ate", "anti", "ante", "asi", "ase", "Ami", "AmaH", "Amahe",
  "atu", "atAm", "antu", "antAm", "asva", "aDvam", "Ani",
  "et", "eta", "eyuH", "eran", "It", "yAt", "yAm", "yAma",
  "sya", "syati", "syate", "syanti", "syante", "syAmi", "syAmaH",
  "noti", "nute", "nuvanti", "nAti", "nIte", "nanti", "RAti", "RIte", "Ranti",
  "Ite", "Iyate", "Iyante", "yate", "yante",
  "aH", "at", "an", "ata", "anta", "An", "Am",
)


def _is_vedic_prefixed_tinanta_fallback(slp_w: str, lex: UnifiedVedicLexicon) -> list[str] | None:
  """Fallback splitter for Vedic prefixed finite verbs missing from classical ``vidyut.kosha``."""
  if len(slp_w) < 5 or not slp_w.endswith(_VEDIC_FINITE_ENDINGS_SLP):
    return None
  # Reject obvious nominal/kṛdanta endings
  if slp_w.endswith(("aH", "am", "ena", "eRa", "Aya", "asya", "ezu", "AnAm", "ARAm", "mARaH", "mARam", "mAnaH", "mAnam")):
    return None
  for pf in ("prati", "pari", "aBi", "aDi", "anu", "apa", "ava", "ati", "api", "upa", "parA", "sam", "pra", "niH", "duH", "ut", "vi", "ni", "A"):
    rem = _peel_one_upasarga_slp(slp_w, pf, is_last_prefix=True, lex=lex)
    if not rem or len(rem) < 3:
      continue
    rem_deva = sanscript.transliterate(rem, sanscript.SLP1, sanscript.DEVANAGARI)
    # Require the stripped verb to be a genuine simplex Tinanta or Vedic subjunctive/finite form!
    rem_m = lex.analyze_morph(rem_deva)
    is_simplex_tin = any(not t["prefixes"] for t in rem_m["tin_entries"])
    is_vedic_let = rem.endswith(("An", "At", "Ati", "As")) and len(rem) >= 4 and (
      any(not t["prefixes"] for t in lex.analyze_morph(sanscript.transliterate(rem[:-2] + "ati", sanscript.SLP1, sanscript.DEVANAGARI))["tin_entries"])
    )
    if is_simplex_tin or is_vedic_let or rem in ("sfjate", "sfjante", "stfRAti", "stfRanti", "Sete", "Serate", "yanti", "eti", "emi", "iyAt", "ayAni"):
      upa_deva = UPASARGA_SLP_TO_DEVA[pf]
      ok, _, _, _ = verify_mantra_sandhi(
        [upa_deva, rem_deva], sanscript.transliterate(slp_w, sanscript.SLP1, sanscript.DEVANAGARI)
      )
      if ok:
        return [upa_deva, rem_deva]
  return None


def _hyphenate_compound_pada(deva_w: str, lex: UnifiedVedicLexicon) -> str:
  """Insert canonical compound ``-`` hyphens inside a single nominal/kṛdanta pada (never splitting into 2 bullets)."""
  bare = _normalize_lookup_key(deva_w)
  if "-" in deva_w:
    return deva_w
  # 1. Canonical attested padapāṭha hyphenation (RV/AV ऽ, TA पद-पाठः)
  ch = lex.get_canonical_hyphenation(bare)
  if ch and "-" in ch:
    return ch
  # 2. Stem hyphenation from MW / Macdonell
  for _, _, h in lex.project_stem_accents(bare):
    if h and "-" in h:
      ok, _, _, _ = verify_mantra_sandhi([h], bare)
      if ok:
        return h
  # 3. Prefixed kṛdanta from vidyut.kosha (`उप-एष्यन्`, `अभि-ईक्षमाणः`, `सं-स्थिते`, `उत्-सिच्य`, `अति-हृत्य`, `उद्-यन्तुम्`)
  morph = lex.analyze_morph(bare)
  if morph["krt_entries"]:
    pref_krt = [k for k in morph["krt_entries"] if k["prefixes"]]
    if pref_krt and not any(not k["prefixes"] for k in morph["krt_entries"]):
      slp = morph["slp"]
      for k in sorted(pref_krt, key=lambda x: len(x["prefixes"])):
        parts = _split_by_prefix_list(slp, k["prefixes"], lex)
        if parts and len(parts) >= 2:
          cand = "-".join(parts)
          ok, _, _, _ = verify_mantra_sandhi([cand], bare)
          if ok:
            return cand
  return bare


def _generate_chunk_transitions(
  slp: str,
  pos: int,
  req_prefix: str,
  lex: UnifiedVedicLexicon,
  next_tok_starts_vowel: bool,
  next_tok_starts_voiced: bool,
  next_tok_is_avagraha: bool,
  is_end_of_clause: bool,
) -> list[tuple[int, str, str, float]]:
  """Generate candidate inverse-sandhi word transitions from ``(pos, req_prefix)`` in SLP1 chunk ``slp``.

  Returns list of ``(next_pos, next_req_prefix, cand_word_slp, transition_cost)``.
  """
  L = len(slp)
  out: list[tuple[int, str, str, float]] = []

  def _eval_word(w_slp: str, extra_pen: float = 0.0) -> float | None:
    if not w_slp or len(w_slp) == 0:
      return None
    if len(w_slp) == 1 and w_slp not in ("A", "u"):
      return None
    sc = lex.word_score_slp(w_slp)
    if sc <= 0:
      # Check prefixed finite verb!
      if len(w_slp) >= 5 and _strip_leading_upasargas_tinanta(w_slp, lex) is not None:
        sc = 40
      else:
        return None
    # Higher score -> lower cost; prefer fewer splits via per-word base cost
    return 3.0 - math.log1p(sc) * 0.55 + extra_pen

  # Scan ending positions `end` from pos+1..L
  max_end = min(L, pos + 28)
  for end in range(pos + 1, max_end + 1):
    seg = req_prefix + slp[pos:end]
    at_chunk_end = end == L
    next_ch = slp[end] if end < L else ""

    # 1. Exact segment (no boundary mutation)
    if at_chunk_end:
      # Handle chunk-final sandhi restorations
      final_cands: list[tuple[str, float]] = [(seg, 0.0)]
      if seg.endswith("M") and len(seg) >= 2:
        final_cands.append((seg[:-1] + "m", 0.0))
        final_cands.append((seg[:-1] + "n", 0.3))
      if seg.endswith("o") and len(seg) >= 2:
        if next_tok_is_avagraha or next_tok_starts_voiced:
          final_cands.append((seg[:-1] + "aH", 0.05))
        else:
          final_cands.append((seg[:-1] + "aH", 0.6))
      if seg.endswith("r") and len(seg) >= 3:
        final_cands.append((seg[:-1] + "H", 0.05))
      if seg.endswith(("S", "z", "s")) and len(seg) >= 2 and not is_end_of_clause:
        final_cands.append((seg[:-1] + "H", 0.05))
      if seg.endswith("d") and len(seg) >= 2:
        final_cands.append((seg[:-1] + "t", 0.05))
      if seg.endswith(("c", "j", "l", "n")) and len(seg) >= 2 and not is_end_of_clause:
        final_cands.append((seg[:-1] + "t", 0.25))
      if seg.endswith("nn") and len(seg) >= 4 and next_tok_starts_vowel:
        final_cands.append((seg[:-1], 0.05))
      if seg.endswith("NN") and len(seg) >= 4 and next_tok_starts_vowel:
        final_cands.append((seg[:-1], 0.05))
      if seg.endswith("y") and len(seg) >= 2 and next_tok_starts_vowel:
        final_cands.append((seg[:-1] + "i", 0.1))
        final_cands.append((seg[:-1] + "I", 0.3))
      if seg.endswith("v") and len(seg) >= 2 and next_tok_starts_vowel:
        final_cands.append((seg[:-1] + "u", 0.1))
        final_cands.append((seg[:-1] + "U", 0.3))
      if seg == "vA" and next_tok_starts_vowel:
        final_cands.append(("vE", 0.0))
      if seg == "sa" and not is_end_of_clause:
        final_cands.append(("saH", 0.05))
      if seg == "eza" and not is_end_of_clause:
        final_cands.append(("ezaH", 0.05))
      if seg.endswith("A") and len(seg) >= 3 and (next_tok_starts_vowel or next_tok_starts_voiced):
        final_cands.append((seg + "H", 0.15))
        if next_tok_starts_vowel and seg.endswith("smA"):
          final_cands.append((seg[:-1] + "E", 0.05))
      if seg.endswith("a") and len(seg) >= 2 and next_tok_starts_vowel:
        final_cands.append((seg + "H", 0.2))
      if seg.endswith("Ms") and len(seg) >= 4:
        final_cands.append((seg[:-2] + "n", 0.1))
      if seg.endswith("MS") and len(seg) >= 4:
        final_cands.append((seg[:-2] + "n", 0.1))
      if seg.endswith("nt") and len(seg) >= 4:
        final_cands.append((seg[:-1], 0.15))
      if seg.endswith("q") and len(seg) >= 3:
        final_cands.append((seg[:-1] + "w", 0.1))
      if seg.endswith("g") and len(seg) >= 3:
        final_cands.append((seg[:-1] + "k", 0.1))
      if seg.endswith("e") and next_tok_is_avagraha:
        final_cands.append((seg, 0.0))

      seen_w: set[str] = set()
      for w_c, pen in final_cands:
        if w_c in seen_w:
          continue
        seen_w.add(w_c)
        cost = _eval_word(w_c, pen)
        if cost is not None:
          out.append((end, "", w_c, cost))
      continue

    # Non-final position inside chunk: check sandhi boundaries!
    # A. Direct consonant/vowel boundary (no merger at `end - 1`)
    if next_ch not in SLP_VOWELS:
      # Raw word ending in vowel or consonant before consonant
      cost = _eval_word(seg, 0.1)
      if cost is not None:
        out.append((end, "", seg, cost))
      # Nasal assimilation: M / homorganic nasal -> m or n
      if seg.endswith(("M", "N", "Y", "R", "n", "m")) and len(seg) >= 2:
        c_m = _eval_word(seg[:-1] + "m", 0.15)
        if c_m is not None:
          out.append((end, "", seg[:-1] + "m", c_m))
        if seg[-1] in ("M", "n"):
          c_n = _eval_word(seg[:-1] + "n", 0.35)
          if c_n is not None:
            out.append((end, "", seg[:-1] + "n", c_n))
      # n -> Ms/MS before t/c
      if seg.endswith(("Ms", "MS", "Mz")) and len(seg) >= 4:
        c_n = _eval_word(seg[:-2] + "n", 0.2)
        if c_n is not None:
          out.append((end, "", seg[:-2] + "n", c_n))
      # Stop assimilation: d/c/j/l/n/t -> t
      if seg.endswith(("d", "c", "j", "l", "n")) and len(seg) >= 2:
        c_t = _eval_word(seg[:-1] + "t", 0.15)
        if c_t is not None:
          out.append((end, "", seg[:-1] + "t", c_t))
          # Special: `cC` -> `t + S` (`तच्छकेयम्` -> `तत्` + `शकेयम्`)
          if seg.endswith("c") and next_ch == "C":
            out.append((end + 1, "S", seg[:-1] + "t", c_t + 0.05))
          # Special: `dD` -> `t + h` (`एतद्ध` -> `एतत्` + `ह`, `अशकद्ध्येतत्` -> `अशकत्` + `हि`)
          if seg.endswith("d") and next_ch == "D":
            out.append((end + 1, "h", seg[:-1] + "t", c_t + 0.05))
      # Visarga sandhi before consonant: o -> aH, r/S/z/s -> H, A -> AH
      if seg.endswith("o") and len(seg) >= 2 and next_ch in "gGNjJYqQRdDnbBmyrlvh":
        c_v = _eval_word(seg[:-1] + "aH", 0.15)
        if c_v is not None:
          out.append((end, "", seg[:-1] + "aH", c_v))
      if seg.endswith(("r", "S", "z", "s")) and len(seg) >= 2:
        c_v = _eval_word(seg[:-1] + "H", 0.15)
        if c_v is not None:
          out.append((end, "", seg[:-1] + "H", c_v))
      if seg.endswith("A") and len(seg) >= 3 and next_ch in "gGNjJYqQRdDnbBmyrlvh":
        c_v = _eval_word(seg + "H", 0.35)
        if c_v is not None:
          out.append((end, "", seg + "H", c_v))
      if seg in ("sa", "eza"):
        c_v = _eval_word(seg + "H", 0.15)
        if c_v is not None:
          out.append((end, "", seg + "H", c_v))
    else:
      # `next_ch` IS a vowel!
      # Consonant-final word before vowel (`व्रतमुपैष्यन्` -> `vratam` + `upEzyan`, `अन्तरेणाहवनीयम्` handled below)
      if seg[-1] not in SLP_VOWELS:
        for w_c, pen in _prevocalic_cons_restorations(seg):
          c = _eval_word(w_c, pen)
          if c is not None:
            out.append((end, "", w_c, c))
        # Special: `dD` + `y` / vowel? Already handled when next_ch == 'D'.
      # Hiatus after `e`/`I`/`U`/`o`/`a`/`A` (e.g. `vA` -> `vE`, `apa` -> `apaH`, `te` -> `te`)
      if seg == "vA":
        c = _eval_word("vE", 0.1)
        if c is not None:
          out.append((end, "", "vE", c))
      elif seg.endswith(("I", "U", "e", "o")):
        c = _eval_word(seg, 0.25)
        if c is not None:
          out.append((end, "", seg, c))

    # B. Inverse vowel-sandhi merger AT `slp[end - 1]`!
    last_ch = slp[end - 1]
    if last_ch in _INV_VOWEL_SANDHI and len(seg) >= 2:
      base_pre = seg[:-1]
      for lv, rv in _INV_VOWEL_SANDHI[last_ch]:
        w_c = base_pre + lv
        # Avoid degenerate 1-letter `a` / `i` splits unless valid upasarga/particle (`A`, `u`)
        if len(w_c) == 1 and w_c not in ("A", "u"):
          continue
        c = _eval_word(w_c, 0.25)
        if c is not None:
          out.append((end, rv, w_c, c))

    # C. Inverse *abhinihita* `e'` / `o'` (explicit avagraha inside chunk e.g. `सोऽग्निम्`)
    if next_ch == "'" and last_ch in ("e", "o"):
      if last_ch == "o":
        c_v = _eval_word(seg[:-1] + "aH", 0.05)
        if c_v is not None:
          out.append((end + 1, "a", seg[:-1] + "aH", c_v))
      c_e = _eval_word(seg, 0.05)
      if c_e is not None:
        out.append((end + 1, "a", seg, c_e))

  return out


def _prevocalic_cons_restorations(seg: str) -> list[tuple[str, float]]:
  """Restore consonant-final word endings before a following vowel inside a fused chunk."""
  out: list[tuple[str, float]] = [(seg, 0.1)]
  c = seg[-1]
  if c == "y" and len(seg) >= 2:
    out.append((seg[:-1] + "i", 0.1))
    out.append((seg[:-1] + "I", 0.35))
  elif c == "v" and len(seg) >= 2:
    out.append((seg[:-1] + "u", 0.1))
    out.append((seg[:-1] + "U", 0.35))
    # Ayādi: `Av` -> `O` (`व्रीहियवावेव` -> `vrIhiyavO` + `eva`, `तावेतौ` -> `tO` + `etO`)
    if seg.endswith("Av") and len(seg) >= 3:
      out.append((seg[:-2] + "O", 0.1))
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
      whole_slp = sanscript.transliterate(raw.replace("-", ""), sanscript.DEVANAGARI, sanscript.SLP1)
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
  slp = sanscript.transliterate(clean_d, sanscript.DEVANAGARI, sanscript.SLP1)
  slp = re.sub(r"[^a-zA-Z']", "", slp)
  if not slp:
    return []

  next_slp = ""
  if next_tok_deva:
    nt = accent.strip_accents(next_tok_deva).replace("-", "")
    next_slp = sanscript.transliterate(nt, sanscript.DEVANAGARI, sanscript.SLP1)
  next_is_av = next_tok_deva.startswith("ऽ")
  next_starts_v = bool(next_slp and next_slp[0] in SLP_VOWELS)
  next_starts_voiced = bool(next_slp and next_slp[0] in "gGNjJYqQRdDnbBmyrlvh")

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
    # Prune beam at each position to top-12 states for speed
    states = sorted(set(by_pos[pos]), key=lambda st: dp[st][0])[:12]
    for st in states:
      cur_cost = dp[st][0]
      _, req_pf = st
      trans = _generate_chunk_transitions(
        slp, pos, req_pf, lex, next_starts_v, next_starts_voiced, next_is_av, is_end_of_clause
      )
      for nxt_pos, nxt_pf, w_slp, t_cost in trans:
        nc = cur_cost + t_cost
        # Penalize clubbing forbidden left words (e.g., `nAtra` -> `na + atra` strongly beats `nAtra`)
        nxt_st = (nxt_pos, nxt_pf)
        if nxt_st not in dp or nc < dp[nxt_st][0]:
          if nxt_st not in dp:
            by_pos[nxt_pos].append(nxt_st)
          dp[nxt_st] = (nc, st, w_slp)

  goal = (L, "")
  if goal not in dp:
    # Fallback: keep the normalized whole token as a single pada
    fb = ("अ" + clean_d) if leading_avagraha else clean_d
    return [_normalize_lookup_key(fb)]

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
      w_deva = sanscript.transliterate(w_slp, sanscript.SLP1, sanscript.DEVANAGARI)
      final_padas.append(_hyphenate_compound_pada(w_deva, lex))
  return final_padas


def split_vp_to_padas(vp_clean: str, lex: UnifiedVedicLexicon) -> list[str]:
  """Split a clean unaccented ``विश्वास-प्रस्तुतिः`` string into normalized bare padapāṭha words."""
  # Strip editorial +++(...)+++ and [[OLD|NEW]] -> NEW if present
  txt = re.sub(r"\+\+\+.*?\+\+\+", " ", vp_clean, flags=re.S)
  txt = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", txt)
  txt = accent.strip_accents(txt)

  # Tokenize preserving punctuation boundaries so we know pause/clause ends!
  tokens = re.findall(r"[।॥,;:—–]+|[\u0900-\u0963\u0971-\u097f\-ऽ]+", txt)
  padas: list[str] = []
  n = len(tokens)
  for i, tok in enumerate(tokens):
    if not _DEVANAGARI_RE.search(tok):
      continue
    nxt_tok = ""
    end_clause = True
    if i + 1 < n:
      if _DEVANAGARI_RE.search(tokens[i + 1]):
        nxt_tok = tokens[i + 1]
        end_clause = False
      elif any(p in tokens[i + 1] for p in ("।", "॥")):
        end_clause = True
      else:
        # Comma / dash: find next Devanagari token (external sandhi often crosses `,` in VP!)
        for j in range(i + 1, n):
          if any(p in tokens[j] for p in ("।", "॥")):
            end_clause = True
            break
          if _DEVANAGARI_RE.search(tokens[j]):
            nxt_tok = tokens[j]
            end_clause = False
            break
    # Merge short vowelless yaṇ fragment (`ध्य्`, `व्`, `त्य्`) onto next token before DP!
    # Wait: handled seamlessly if we check `tok` ends with virāma + `य्`/`व्` and `nxt_tok` starts with vowel!
    chunk_padas = split_chunk_to_padas_dp(
      tok, lex, next_tok_deva=nxt_tok, is_end_of_clause=end_clause
    )
    padas.extend(chunk_padas)
  return padas


# ---------------------------------------------------------------------------
# Component 3: Candidate Generator + 3-State Viterbi ŚB Accent Decoder
# ---------------------------------------------------------------------------


def _format_corpus_prov(srcs: dict[str, int]) -> str:
  """Format concise standard corpus provenance tags from a ``{source: freq}`` dict."""
  order = ("VS", "RV", "TS", "AV", "TB", "TA", "Whitney", "Macdonell", "Lanman", "MW_SB", "MW")
  tags: list[str] = []
  for s in order:
    if s in srcs:
      if s == "MW_SB":
        tags.append("*MW* ŚBr.")
      else:
        tags.append(f"*{s}*")
  return ", ".join(tags)


def _derive_paninian_tinanta_accent(
  word_deva: str, morph: dict, *, sub_rule: str
) -> list[tuple[tuple[str, ...], str]]:
  """Derive accented finite verb syllable marks via Pāṇinian rules (with sūtra provenance)."""
  bare = _normalize_lookup_key(word_deva)
  slp = morph["slp"]
  ks, _ = syllables_with_marks(bare)
  n_syl = len(ks)
  if n_syl == 0:
    return []

  out: dict[tuple[str, ...], str] = {}

  def _add(idx: int, sutra: str) -> None:
    if 0 <= idx < n_syl:
      mks = tuple("U" if i == idx else "" for i in range(n_syl))
      if mks not in out:
        out[mks] = f"{sub_rule}, {sutra}" if sutra else sub_rule

  # 1. Augmented tenses (लङ्, लुङ्, लृङ्): पा० ६.४.७१ लुङ्लङ्लृङ्क्ष्वडुदात्तः / ६.४.७२ आडजादीनाम्
  for t in morph["tin_entries"]:
    lak = t["lakara"]
    gana = t["gana"]
    prayoga = t["prayoga"]
    sanadi = t["sanadi"]

    if lak in ("la~N", "lu~N", "lf~N") and bare[0] in ("अ", "आ", "ऐ", "औ"):
      _add(0, "पा० ६.४.७१")
      continue
    # 2. Passive `यक्` (पा० ३.१.६७, पा० ३.१.३): accent on `-य-`
    if prayoga in ("karmaRi", "BAve") and lak in ("la~w", "lo~w", "viDili~N"):
      for idx in range(n_syl - 1, -1, -1):
        if "य" in ks[idx][0]:
          _add(idx, "यक् पा० ३.१.६७, पा० ३.१.३")
          break
      continue
    # 3. Causative `णिच्` / चुरादि (पा० ३.१.२६, पा० ३.१.३): accent on `-अय-` (`साद᳓यति`, `साद᳓येत्`, `आप᳓यति`)
    if any("Ric" in s for s in sanadi) or gana == "curAdi":
      # Locate `-ay-` syllable before ending
      if n_syl >= 3:
        _add(n_syl - 3, "णिच् पा० ३.१.३")
      if n_syl >= 2 and slp.endswith(("et", "eyuH", "eta", "eran", "eH", "em", "ema")):
        _add(n_syl - 2, "णिच् पा० ३.१.३")
      continue
    # 4. Future `स्य` (पा० ३.१.३३, पा० ३.१.३)
    if lak == "lf~w":
      for idx in range(n_syl - 1, -1, -1):
        if "स" in ks[idx][0] or "य" in ks[idx][0]:
          _add(idx, "स्यतासी पा० ३.१.३३, पा० ३.१.३")
          break
      continue
    # 5. Athematic optative `-यात्` (पा० ३.४.१०३ लिङ्सलोपौ)
    if lak == "viDili~N" and slp.endswith(("yAt", "yAtAm", "yuH", "yAH", "yAm", "yAma")):
      _add(n_syl - 1, "लिङ्सलोपौ पा० ३.४.१०३")
      continue
    # 6. Gaṇa-specific present/imperative/optative accent
    if gana == "BvAdi":
      _add(0, "शप् अनुदात्त पा० ३.१.४")
    elif gana == "tudAdi":
      # तुदादिभ्यः शः (पा० ३.१.७७, पा० ३.१.३): udātta on thematic vowel before ending
      _add(max(0, n_syl - 2), "तुदादिभ्यः शः पा० ३.१.७७")
    elif gana == "divAdi":
      _add(0, "दिवादिभ्यः श्यन् पा० ३.१.६९, पा० ६.१.१९७")
    elif gana == "kryAdi":
      # क्र्यादिभ्यः श्ना (पा० ३.१.८१): udātta on `-ना-`/`-ण-` or ending
      _add(max(0, n_syl - 2), "क्र्यादिभ्यः श्ना पा० ३.१.८१")
      _add(n_syl - 1, "क्र्यादिभ्यः श्ना पा० ३.१.८१")
    elif gana in ("svAdi", "tanAdi"):
      _add(max(0, n_syl - 2), "स्वादिभ्यः श्नुः पा० ३.१.७३, पा० ३.१.३")
      _add(n_syl - 1, "पा० ३.१.३")
    elif gana in ("adAdi", "juhotyAdi", "ruDAdi"):
      _add(0, "पा० ६.१.१८६")
      _add(n_syl - 1, "पा० ३.१.३")

  # Vedic लेट् / thematic fallback (`चरान्` -> `च᳓रान्`, `स्पृशति` -> `स्पृश᳓ति`)
  if not out and slp.endswith(("An", "At", "Ati")):
    _add(0, "लेट् पा० ३.४.९४")
  return list(out.items())


def _derive_paninian_krdanta_and_compound_accents(
  pada_deva: str, lex: UnifiedVedicLexicon
) -> list[tuple[tuple[str, ...], str]]:
  """Generate solid Pāṇinian compound/kṛdanta accent candidates (``पा० ६.१.१९३``, ``६.२.१``, ``६.२.२``, ``६.२.४९``, ``६.२.१३९``, ``६.२.१७२``, ``६.१.२२३``)."""
  bare = _normalize_lookup_key(pada_deva)
  ks, _ = syllables_with_marks(bare)
  n_syl = len(ks)
  if n_syl < 2:
    return []

  out: dict[tuple[str, ...], str] = {}
  morph = lex.analyze_morph(bare)
  slp = morph["slp"]

  # 1. Gerunds: ल्यप् (पा० ६.१.१९३ लिति — udātta on root syllable right before `-य`), क्त्वा (पा० ३.१.३)
  for k in morph["krt_entries"]:
    krt = k["krt"]
    if "ktvA" in krt:
      if k["prefixes"] and slp.endswith("ya") and n_syl >= 2:
        mks = tuple("U" if i == n_syl - 2 else "" for i in range(n_syl))
        out.setdefault(mks, "लिति पा० ६.१.१९३")
      elif slp.endswith(("tvA", "tvI")):
        mks = tuple("U" if i == n_syl - 1 else "" for i in range(n_syl))
        out.setdefault(mks, "क्त्वा पा० ३.१.३")
    elif "tumun" in krt:
      # तुमुन् = नित् (पा० ६.१.१९७ आद्युदात्त): if prefixed (`उ᳓द्-यन्तुम्`) or simplex (`क᳓र्तुम्`)
      mks = tuple("U" if i == 0 else "" for i in range(n_syl))
      out.setdefault(mks, "नित् आद्युदात्तम् पा० ६.१.१९७")
    elif "kta" in krt and k["prefixes"]:
      # गतिरनन्तरः पा० ६.२.४९: gati keeps its prakṛtisvara!
      p0 = UPASARGA_SLP_TO_DEVA.get(k["prefixes"][-1], "")
      if p0 in UPASARGA_ACCENT_MARKS:
        g_mks = UPASARGA_ACCENT_MARKS[p0]
        if len(g_mks) <= n_syl:
          mks = g_mks + tuple("" for _ in range(n_syl - len(g_mks)))
          out.setdefault(mks, "गतिरनन्तरः पा० ६.२.४९")
    elif ("SAnac" in krt or "Satf" in krt) and k["prayoga"] in ("karmaRi", "BAve"):
      # Passive participle (`चर्य᳓माणम्`): यक् पा० ३.१.६७, पा० ३.१.३
      for idx in range(n_syl - 1, -1, -1):
        if "य" in ks[idx][0]:
          mks = tuple("U" if i == idx else "" for i in range(n_syl))
          out.setdefault(mks, "यक् पा० ३.१.६७, पा० ३.१.३")
          break

  # 2. Hyphenated compound rules (`p0 - p1 ...`)
  if "-" in pada_deva:
    parts = [p for p in pada_deva.split("-") if p]
    if len(parts) >= 2:
      p0, p_rest = parts[0], "-".join(parts[1:])
      p0_ks, _ = syllables_with_marks(p0)
      n0 = len(p0_ks)
      # (a) नञ् compound (`अ-`, `अन्-`): पा० ६.२.२ (ādyudātta) vs पा० ६.२.१७२ (bahuvrīhi antodātta)
      if p0 in ("अ", "अन्"):
        mks_init = tuple("U" if i == 0 else "" for i in range(n_syl))
        out.setdefault(mks_init, "नञ्तत्पुरुषे पूर्वपदप्रकृतिस्वरः पा० ६.२.२")
        # Antodātta (stem-final syllable) for नञ्-बहुव्रीहि पा० ६.२.१७२
        end_idx = _stem_final_syl_idx(bare, n_syl)
        mks_end = tuple("U" if i == end_idx else "" for i in range(n_syl))
        out.setdefault(mks_end, "नञ्सुभ्याम् पा० ६.२.१७२")
      # (b) गतिकृदन्त (`उप-एष्यन्`, `अभि-ईक्षमाणः`, `उप-यन्तम्`, `प्र-जननम्`): पा० ६.२.१३९
      elif p0 in UPASARGA_ACCENT_MARKS:
        # Check attested accent of uttarapada `p_rest`!
        rest_bare = _normalize_lookup_key(p_rest)
        rest_ks, _ = syllables_with_marks(rest_bare)
        # Note internal vowel merger may reduce total syllable count by 1 (e.g. `उप`+`एष्यन्` = 4 pp syls -> 3 surface syls)
        # Project uttarapada accent aligned from the right!
        r_hits = lex.lookup_form(rest_bare)
        if not r_hits:
          for r_mks, r_prov, _ in lex.project_stem_accents(rest_bare):
            r_hits[r_mks] = {"_stem": 1}
        for r_mks in r_hits:
          if sum(1 for m in r_mks if m) == 1 and len(r_mks) <= n_syl:
            shift = n_syl - len(r_mks)
            full_mks = tuple("" for _ in range(shift)) + r_mks
            out.setdefault(full_mks, "गतिकारकोपपदात् कृत् पा० ६.२.१३९")
        # Also गतिरनन्तरः पा० ६.२.४९
        g_mks = UPASARGA_ACCENT_MARKS[p0]
        if len(g_mks) <= n_syl:
          out.setdefault(g_mks + tuple("" for _ in range(n_syl - len(g_mks))), "गतिरनन्तरः पा० ६.२.४९")
      else:
        # (c) General samāsa:
        # - पा० ६.१.२२३ समासस्य (antodātta on uttarapada stem-final syllable)
        end_idx = _stem_final_syl_idx(bare, n_syl)
        out.setdefault(tuple("U" if i == end_idx else "" for i in range(n_syl)), "समासस्य पा० ६.१.२२३")
        # - पा० ६.२.१ / ६.२.२ pūrvapada prakṛtisvara (from attested p0!)
        p0_hits = lex.lookup_stem(p0) or lex.lookup_form(p0)
        if p0_hits:
          top_p0_mks = max(p0_hits.items(), key=lambda kv: sum(kv[1].values()))[0]
          if len(top_p0_mks) <= n_syl and sum(1 for m in top_p0_mks if m) == 1:
            out.setdefault(
              top_p0_mks + tuple("" for _ in range(n_syl - len(top_p0_mks))),
              "पूर्वपदप्रकृतिस्वरः पा० ६.२.१/६.२.२",
            )
        # - पा० ६.२.१८ पत्यावैश्वर्ये (`व्रत᳓-पतिः`, `प्रजा᳓-पतिः`)
        if bare.endswith(("पतिः", "पतिम्", "पतेः", "पत्ये", "पतौ")) and n0 >= 1 and n0 <= n_syl:
          p0_hits2 = lex.lookup_stem(p0) or lex.lookup_form(p0)
          if p0_hits2:
            top_p0 = max(p0_hits2.items(), key=lambda kv: sum(kv[1].values()))[0]
            if len(top_p0) <= n_syl and sum(1 for m in top_p0 if m) == 1:
              out[top_p0 + tuple("" for _ in range(n_syl - len(top_p0)))] = "पत्यावैश्वर्ये पा० ६.२.१८"
  return list(out.items())


def _stem_final_syl_idx(bare_deva: str, n_syl: int) -> int:
  """Return the stem-final syllable index for antodātta ``पा० ६.१.२२३`` / ``६.२.१७२``."""
  slp = sanscript.transliterate(bare_deva, sanscript.DEVANAGARI, sanscript.SLP1)
  # Disyllabic endings where stem-final vowel is penultimate (`-asya`, `-ena`, `-Aya`, `-AnAm`, `-ezu`, `-eByaH`, `-ayoH`, `-Ani`)
  if slp.endswith(("asya", "ena", "eRa", "Aya", "AnAm", "ARAm", "ezu", "Asu", "eByaH", "AByaH", "ABiH", "AByAm", "ayoH", "Ani", "ARi", "ayA")) and n_syl >= 2:
    return n_syl - 2
  return n_syl - 1


def _detect_clause_contexts(
  padas_bare: Sequence[str], vp_clean: str, lex: UnifiedVedicLexicon
) -> list[dict]:
  """Compute per-pada clause features: ``is_clause_start``, ``in_subordinate``, ``sub_rule``, ``is_amredita``."""
  n = len(padas_bare)
  # Approximate pause boundaries using VP `।`/`॥` mapping via syllable counts
  vp_segs = [s.strip() for s in re.split(r"[।॥]+", vp_clean) if _DEVANAGARI_RE.search(s)]
  pause_syl_bounds: set[int] = {0}
  cum = 0
  for seg in vp_segs:
    cum += len(syllables_with_marks(seg)[0])
    pause_syl_bounds.add(cum)

  # Map each pada to cumulative syllable offset
  ctx: list[dict] = []
  sub_rule = ""
  in_sub = False
  cum_pp = 0
  for i, pd in enumerate(padas_bare):
    bare = _normalize_lookup_key(pd)
    # Approximate clause start: index 0, right after `इति`, or near a `।`/`॥` boundary
    prev_bare = _normalize_lookup_key(padas_bare[i - 1]) if i > 0 else ""
    is_start = (i == 0) or (prev_bare == "इति") or any(abs(cum_pp - b) <= 1 for b in pause_syl_bounds)
    if is_start:
      in_sub = False
      sub_rule = ""

    # Track subordinate triggers within clause
    if bare in YAD_VRTTA_TRIGGERS:
      in_sub = True
      sub_rule = "यद्वृत्तान्नित्यम् पा० ८.१.६६"
    elif bare in NIPATA_8130_TRIGGERS:
      in_sub = True
      sub_rule = "निपातैर्यद्यदिहन्तकुविन्नेच्चेच्चण्कच्चिद्यत्रयुक्तम् पा० ८.१.३०"
    elif bare in HI_8134_TRIGGERS and not in_sub:
      in_sub = True
      sub_rule = "हि च पा० ८.१.३४"
    elif bare in CORRELATIVE_STOPS and in_sub and i > 0:
      # Correlative closes a relative clause unless immediately preceded by `यद्` (`तद् यद्`, `स यद्`)
      if prev_bare not in ("तत्", "सः", "ते", "ताः"):
        # Only reset if a verb already occurred or we're past the relative pronoun
        if any(c.get("seen_verb_in_sub") for c in ctx[max(0, i - 8) : i]):
          in_sub = False
          sub_rule = ""

    is_amredita = i > 0 and bare == prev_bare and bare not in ALWAYS_ANUDATTA_ENCLITICS
    morph = lex.analyze_morph(bare)
    is_verb_like = morph["is_tinanta"] and not (morph["is_subanta"] and not morph["tin_entries"])
    ctx.append({
      "is_clause_start": is_start,
      "in_subordinate": in_sub,
      "sub_rule": sub_rule or "यद्वृत्तान्नित्यम् पा० ८.१.६६",
      "is_amredita": is_amredita,
      "seen_verb_in_sub": in_sub and is_verb_like,
    })
    cum_pp += len(syllables_with_marks(pd)[0])
  return ctx


def generate_pada_candidates(
  pada_deva: str,
  ctx: dict,
  next_pada_deva: str,
  lex: UnifiedVedicLexicon,
) -> list[PadaCandidate]:
  """Generate all grammatically valid US-accented candidates for ``pada_deva`` with provenance & priors."""
  bare = _normalize_lookup_key(pada_deva)
  ks, _ = syllables_with_marks(pada_deva)
  n_syl = len(ks)
  if n_syl == 0:
    return []
  zero_marks = tuple("" for _ in range(n_syl))
  cands: dict[tuple[tuple[str, ...], str], PadaCandidate] = {}

  def _add(marks: tuple[str, ...], prov: str, role: str, prior_cost: float) -> None:
    if len(marks) != n_syl:
      return
    try:
      ref = apply_marks_to_token(pada_deva, marks)
    except ValueError:
      return
    solid = is_solid_provenance(prov) or ("*MW* ŚBr." in prov) or ("*Whitney*" in prov)
    key = (marks, role)
    existing = cands.get(key)
    if existing is None or prior_cost < existing.prior_cost:
      cands[key] = PadaCandidate(
        ref=ref, marks=marks, prov=prov, role=role, solid=solid, prior_cost=prior_cost
      )

  form_hits = lex.lookup_form(bare)
  morph = lex.analyze_morph(bare)

  # 1. Always-unaccented enclitics (पा० ८.१.१८)
  if bare in ALWAYS_ANUDATTA_ENCLITICS:
    src_note = _format_corpus_prov(form_hits.get(zero_marks, {}))
    prov = f"अनुदात्तम्, पा० ८.१.१८{', ' + src_note if src_note else ''}"
    _add(zero_marks, prov, "enclitic", 0.0)
    return list(cands.values())

  # 2. Ambiguous enclitics (`वा`, `ते`, `मा`, `वाम्`, `नौ`)
  if bare in AMBIGUOUS_ENCLITICS:
    acc_mks, default_src = AMBIGUOUS_ENCLITICS[bare]
    src_a = _format_corpus_prov(form_hits.get(zero_marks, {})) or default_src
    src_u = _format_corpus_prov(form_hits.get(acc_mks, {})) or default_src
    _add(zero_marks, f"अनुदात्तम्, पा० ८.१.१८, {src_a}", "enclitic", 0.1 if not ctx["is_clause_start"] else 50.0)
    if bare != "वा":  # `वा` is enclitic 'or' (prevocalic `वै᳓` was already restored to `वै`)
      _add(acc_mks, src_u, "nominal", 0.15)
    return list(cands.values())

  # 3. Upasarga / gati (`प्र`, `उप`, `उत्`, `सम्`, `अभि`, `आ`, `वि`, `नि`, `अति`, `अव`, `प्रति`, `परि`, `निः`, etc.)
  if bare in UPASARGA_DEVA_SET:
    u_mks = UPASARGA_ACCENT_MARKS[bare]
    src_u = _format_corpus_prov(form_hits.get(u_mks, {})) or "*RV*, *TS*, *AV*"
    _add(u_mks, src_u, "gati_main", 0.05)
    # Subordinate-clause anudātta upasarga (पा० ८.१.७१ तिङि चोदात्तवति) — constrained by Viterbi transition!
    _add(zero_marks, "तिङि चोदात्तवति पा० ८.१.७१", "gati_sub", 0.15 if ctx["in_subordinate"] else 0.8)
    # Main-clause chained gati (पा० ८.१.७० गतिर्गतावत्) — constrained by Viterbi transition!
    if next_pada_deva and _normalize_lookup_key(next_pada_deva) in UPASARGA_DEVA_SET:
      _add(zero_marks, "गतिर्गतावत् पा० ८.१.७०", "gati_chain", 0.05)
    return list(cands.values())

  # 4. Anvādeśa pronouns (`अस्य`, `अस्मै`, `एतत्`, `एनम्`, etc.)
  if bare in ANVADESHA_2434:
    src_a = _format_corpus_prov(form_hits.get(zero_marks, {}))
    _add(zero_marks, f"अन्वादेशे अनुदात्तम्, पा० २.४.३४{', ' + src_a if src_a else ''}", "anvadesha", 0.05)
    return list(cands.values())
  if bare in ANVADESHA_2432:
    src_a = _format_corpus_prov(form_hits.get(zero_marks, {}))
    _add(zero_marks, f"अन्वादेशे अनुदात्तम्, पा० २.४.३२{', ' + src_a if src_a else ''}", "anvadesha", 0.4)

  # 5. Finite verbs (`तिङन्त`): BOTH main-clause anudātta (पा० ८.१.२८) AND accented (subordinate/pādādi)
  is_tin = morph["is_tinanta"] or bare in _COMMON_VEDIC_VERBS_DEVA
  if is_tin:
    src_zero = _format_corpus_prov(form_hits.get(zero_marks, {}))
    p_main = f"तिङन्तम् अनुदात्तम्, पा० ८.१.२८{', ' + src_zero if src_zero else ''}"
    main_cost = 0.05 if (not ctx["in_subordinate"] and not ctx["is_clause_start"]) else 1.2
    _add(zero_marks, p_main, "tinanta_main", main_cost)

    # Accented finite verb candidates (from corpus attestations + Pāṇinian verb derivation)
    sub_rule = "वाक्यादिः तिङन्तम्, पा० ८.१.१८" if ctx["is_clause_start"] else ctx["sub_rule"]
    sub_cost_base = 0.05 if (ctx["in_subordinate"] or ctx["is_clause_start"]) else 1.4
    # (a) Corpus-attested accented forms of this verb
    for mks, srcs in form_hits.items():
      if any(mks):
        src_s = _format_corpus_prov(srcs)
        _add(mks, f"{sub_rule}, {src_s}", "tinanta_sub", sub_cost_base)
    # (b) Pāṇinian verb accent rules
    for mks, prov in _derive_paninian_tinanta_accent(bare, morph, sub_rule=sub_rule):
      _add(mks, prov, "tinanta_sub", sub_cost_base + 0.15)

  # 6. Attested inflected corpus forms (nominals, particles, pronouns, adverbs, kṛdantas)
  # Filter out low-freq 1-off corpus typos when a dominant attestation exists (>= 10x frequency)
  nonzero_form_hits = [(mks, srcs) for mks, srcs in form_hits.items() if any(mks)]
  max_form_freq = max((sum(s.values()) for _, s in nonzero_form_hits), default=0)
  for mks, srcs in nonzero_form_hits:
    # Skip if this word is purely a finite verb (already added above as tinanta_sub!)
    if is_tin and not morph["is_subanta"] and not morph["is_avyaya"]:
      continue
    tot = sum(srcs.values())
    # Skip rare 1-count corpus glitch if another accent has >= 25 occurrences across >= 2 corpora
    if tot == 1 and max_form_freq >= 25 and len(srcs) == 1:
      continue
    prov = _format_corpus_prov(srcs)
    # Prefer forms attested in VS / RV / TS / AV with higher frequency
    bonus = 0.0
    if "VS" in srcs:
      bonus -= 0.12
    if sum(1 for k in ("RV", "TS", "AV", "TB", "TA") if k in srcs) >= 2:
      bonus -= 0.1
    prior = 0.15 - min(math.log1p(tot) * 0.04, 0.2) + bonus
    _add(mks, prov, "nominal", prior)

  # 7. Stem-projected accents (MW, Macdonell, Lanman)
  if not (is_tin and not morph["is_subanta"]):
    for mks, prov, _ in lex.project_stem_accents(bare):
      prior = 0.35 if ("*Macdonell*" in prov or "*Lanman*" in prov or "*MW* ŚBr." in prov) else 0.55
      _add(mks, prov, "nominal", prior)

  # 8. Pāṇinian kṛdanta & compound rules (`पा० ६.१.१९३`, `६.२.१/२/१८/४९/१३९/१७२`, `६.१.२२३`)
  if not (is_tin and not morph["is_subanta"]):
    for mks, prov in _derive_paninian_krdanta_and_compound_accents(pada_deva, lex):
      _add(mks, prov, "compound", 0.45)

  # 9. Vocative candidates (`आमन्त्रित`: पा० ६.१.१९८ initial vs पा० ८.१.१९ non-initial)
  if morph["voc_possible"] and not is_tin:
    voc_init_mks = tuple("U" if i == 0 else "" for i in range(n_syl))
    _add(voc_init_mks, "पादादिः आमन्त्रितम् आद्युदात्तम्, पा० ६.१.१९८", "voc_init", 0.5 if ctx["is_clause_start"] else 4.0)
    _add(zero_marks, "अपादादिः आमन्त्रितम् अनुदात्तम्, पा० ८.१.१९", "voc_noninit", 4.0 if ctx["is_clause_start"] else 1.1)

  # 10. Āmreḍita (`पा० ८.१.३ अनुदात्तं च`)
  if ctx["is_amredita"]:
    _add(zero_marks, "आम्रेडितम् अनुदात्तम्, पा० ८.१.३", "amredita", 0.1)

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
      act_w == ew or (cur_u == "U" and act_w in ("H", "")) or (cur_u == "" and act_w in ("", "G", "H"))
    )
    s_ok = None if act_s is None else (
      act_s == es or (cur_u == "U" and act_s in ("H", "")) or (cur_u == "" and act_s in ("", "H"))
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
  # `gati_sub` (पा० ८.१.७१) MUST immediately precede another `gati_sub` or an accented verb (`tinanta_sub`)
  if prev_c.role == "gati_sub":
    if cur_c.role not in ("gati_sub", "tinanta_sub"):
      return 1000.0
    return 0.0
  # `gati_chain` (पा० ८.१.७०) MUST immediately precede `gati_main` or `gati_chain`
  if prev_c.role == "gati_chain":
    if cur_c.role not in ("gati_main", "gati_chain"):
      return 1000.0
    return 0.0
  # Accented `gati_main` immediately before an accented `tinanta_sub` violates पा० ८.१.७१
  if prev_c.role == "gati_main" and cur_c.role == "tinanta_sub":
    return 80.0
  # `gati_main` immediately before `tinanta_main` is canonical पा० ८.१.२८
  if prev_c.role == "gati_main" and cur_c.role == "tinanta_main":
    return -0.2
  return 0.0


def decode_sb_accents_viterbi(
  vp_clean: str,
  padas_bare: Sequence[str],
  weber_text: str,
  shri_text: str,
  lex: UnifiedVedicLexicon,
  *,
  next_first_mark: str | None = None,
) -> tuple[list[PadapathaItem], list[dict], list[tuple[str, int]]]:
  """Run exact 3-state Viterbi ŚB accent decoding over ``padas_bare`` against Weber & Śrīdharādi.

  Returns ``(padapatha_items, ambiguous_padas, unmapped_vp_syllables)``.
  """
  if not padas_bare:
    return [], [], []

  dummy_items = [
    PadapathaItem(ar=p, ref=p, prov="", vyat=False, solid=False) for p in padas_bare
  ]
  vp_pieces = _extract_vp_pieces(vp_clean)
  pp_keys, pp_meta, _, _ = _flatten_pp_syllables(dummy_items)
  vp_keys = [kv for pc in vp_pieces for kv in pc["keys"]]
  vp_meta = [(pi, si) for pi, pc in enumerate(vp_pieces) for si in range(len(pc["keys"]))]
  pc_syl_sources = _map_pp_to_vp_syllables(
    vp_clean, vp_pieces, pp_keys, pp_meta, vp_keys, vp_meta, _pp_member_starts(dummy_items)
  )

  weber_syls = extract_sb_syllables(weber_text, source="weber") if weber_text else []
  shri_syls = extract_sb_syllables(shri_text, source="shri") if shri_text else []
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

  # Group VP syllables owned by each pada `i` (i.e. completed as soon as pada `i` is chosen)
  P = len(padas_bare)
  owned_by_pada: list[list[int]] = [[] for _ in range(P)]
  for v, info in enumerate(vp_syl_info):
    ow = info["owner"]
    if 0 <= ow < P:
      owned_by_pada[ow].append(v)

  # Generate candidates for each pada
  ctxs = _detect_clause_contexts(padas_bare, vp_clean, lex)
  all_cands: list[list[PadaCandidate]] = []
  for i in range(P):
    nxt_p = padas_bare[i + 1] if i + 1 < P else ""
    all_cands.append(generate_pada_candidates(padas_bare[i], ctxs[i], nxt_p, lex))

  def _eval_vp_syl_mark(v: int, prev_c: PadaCandidate | None, cur_c: PadaCandidate, prev_vp_u: str) -> str:
    info = vp_syl_info[v]
    if info["kind"] == "unmapped":
      return ""
    if info["kind"] == "single":
      if info["skip_av"]:
        return ""
      if info["pada"] == cur_i:
        return cur_c.marks[info["syl"]]
      return ""
    # Merged syllable `(p1, s1) + (p2, s2)`
    p1, s1, p2, s2 = info["p1"], info["s1"], info["p2"], info["s2"]
    r1 = cur_c.marks[s1] if p1 == cur_i else (prev_c.marks[s1] if prev_c is not None else "")
    r2 = cur_c.marks[s2] if p2 == cur_i else (prev_c.marks[s2] if prev_c is not None else "")
    # Use Weber `G` cue or Shri `H` on preceding anudātta for ŚB पा० ८.२.६ svarita
    prev_cue = False
    if v > 0:
      if act_w[v - 1] == "G":
        prev_cue = True
      elif act_s[v - 1] == "H" and prev_vp_u == "":
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
  ambiguous_padas = _find_masked_ambiguous_padas(
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
  return items, ambiguous_padas, unmapped


def _find_masked_ambiguous_padas(
  chosen: Sequence[PadaCandidate],
  all_cands: Sequence[Sequence[PadaCandidate]],
  owned_by_pada: Sequence[Sequence[int]],
  vp_syl_info: Sequence[dict],
  act_w: Sequence[str | None],
  act_s: Sequence[str | None],
  pp_keys: Sequence[tuple[str, str]],
  next_first_mark: str | None,
) -> list[dict]:
  """Detect padas where an alternative accent candidate achieves equal ŚB-mark fit (e.g., masked by following udātta)."""
  P = len(chosen)
  n_vp = len(vp_syl_info)
  if P == 0 or n_vp == 0:
    return []

  def _project_sequence(seq: Sequence[PadaCandidate]) -> tuple[list[str], float, int]:
    us: list[str] = [""] * n_vp
    for v, info in enumerate(vp_syl_info):
      if info["kind"] == "unmapped":
        us[v] = ""
      elif info["kind"] == "single":
        us[v] = "" if info["skip_av"] else seq[info["pada"]].marks[info["syl"]]
      else:
        r1 = seq[info["p1"]].marks[info["s1"]]
        r2 = seq[info["p2"]].marks[info["s2"]]
        prev_cue = False
        if v > 0:
          if act_w[v - 1] == "G":
            prev_cue = True
          elif act_s[v - 1] == "H" and us[v - 1] == "":
            prev_cue = True
        local_refs = [""] * len(pp_keys)
        local_refs[info["pp_s1"]] = r1
        local_refs[info["pp_s2"]] = r2
        _, pref = _merged_valid_marks(
          local_refs, pp_keys, info["pc"], info["vsi"], info["pp_s1"], info["pp_s2"],
          info["next_starts_av"], allow_8_2_6_ekadesha_svarita=True,
          prefer_8_2_6_svarita=prev_cue, is_pAdAdi_s2=(info["s2"] == 0),
        )
        us[v] = pref
    sb_cost = 0.0
    disagrees = 0
    for v in range(n_vp):
      nxt = us[v + 1] if v + 1 < n_vp else next_first_mark
      sc, bd = _sb_step_cost(us[v], nxt, act_w[v], act_s[v], is_last=(v == n_vp - 1))
      sb_cost += sc
      if bd:
        disagrees += 1
    return us, sb_cost, disagrees

  _, base_sb, _ = _project_sequence(chosen)
  ambig: list[dict] = []

  for i in range(P):
    best_c = chosen[i]
    # Check distinct alternative accent patterns for pada `i`
    alt_seen: set[tuple[str, ...]] = {best_c.marks}
    alts: list[dict] = []
    for cand in all_cands[i]:
      if cand.marks in alt_seen:
        continue
      # Skip syntactically illegal transitions
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
      # Skip strongly dispreferred alternatives (e.g. anvādeśa vs accented pronoun when prior gap is huge? No, check!)
      # Actually `anvadesha` (`अस्य` vs `अस्य᳓`) masked before udātta IS genuinely ambiguous in ŚB — MUST flag!
      # Whereas `tinanta_main` vs `tinanta_sub` in a clear non-subordinate main clause has a 1.35 prior gap;
      # wait: if both match ŚB equally (e.g. verb at end before udātta? Usually verb doesn't end before udātta,
      # OR monosyllabic `ते᳓` vs `ते` before `अ᳓त्र`!).
      trial = list(chosen)
      trial[i] = cand
      _, trial_sb, trial_bd = _project_sequence(trial)
      if trial_bd == 0 and trial_sb <= base_sb + 0.05:
        # Ignore purely mechanical compound-rule fallbacks when the chosen form is strongly corpus-attested
        if cand.role == "compound" and best_c.role == "nominal" and best_c.prior_cost <= 0.15:
          continue
        # Ignore `tinanta_sub` when clearly in main clause and `tinanta_main` is chosen (prior gap >= 1.0)
        if best_c.role == "tinanta_main" and cand.role == "tinanta_sub" and (cand.prior_cost - best_c.prior_cost) >= 1.0:
          continue
        if best_c.role == "tinanta_sub" and cand.role == "tinanta_main" and (cand.prior_cost - best_c.prior_cost) >= 1.0:
          continue
        alt_seen.add(cand.marks)
        alts.append({"ref": cand.ref, "role": cand.role, "prov": cand.prov, "sb_cost": round(trial_sb, 2)})
    if alts:
      ambig.append({
        "pada_idx": i,
        "chosen": best_c.ref,
        "chosen_role": best_c.role,
        "chosen_prov": best_c.prov,
        "alternatives": alts,
      })
  return ambig


# ---------------------------------------------------------------------------
# Component 4: Self-Certifying Classifier & Adjudication Queue Exporter
# ---------------------------------------------------------------------------


def solve_kandika(
  cluster: KandikaCluster,
  lex: UnifiedVedicLexicon,
  *,
  kandika_id: str = "",
  next_first_mark: str | None = None,
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

  # 2. Split into normalized bare padapāṭha words
  padas_bare = split_vp_to_padas(vp_clean, lex)
  if not padas_bare:
    return SolveResult(
      kandika_id=kid, heading=cluster.heading, sub_idx=cluster.sub_idx,
      status="NEEDS_ADJUDICATION", vp_clean=vp_clean, vp_summary=cluster.vp_summary,
      vp_accented="", items=[], padapatha_block="", preserve_vp=preserve_vp,
      reasons=["empty_padas"],
    )

  # 3. 3-State Viterbi ŚB accent decoding
  items, ambiguous_padas, viterbi_unmapped = decode_sb_accents_viterbi(
    vp_clean, padas_bare, cluster.weber, cluster.shri, lex, next_first_mark=next_first_mark
  )

  # 4. Build US-accented VP and padapāṭha block
  if preserve_vp:
    vp_sum = cluster.vp_summary
    vp_acc = cluster.vp_body
    unmapped = viterbi_unmapped
  else:
    vp_sum, vp_acc, unmapped = build_sb_vp_from_padapatha(
      vp_clean, items, weber_text=cluster.weber, shri_text=cluster.shri,
      orig_summary=cluster.vp_summary,
    )
  pp_block = format_padapatha_block(items)

  # 5. Full self-certification suite!
  padas_ref = [it.ref for it in items]
  ok_vp, fail_vp, win_vp, _ = verify_mantra_sandhi(padas_ref, vp_clean)
  ok_w, fail_w, win_w, _ = (
    verify_mantra_sandhi(padas_ref, strip_weber_footnotes(cluster.weber))
    if cluster.weber else (True, -1, "", "")
  )
  ok_s, fail_s, win_s, _ = (
    verify_mantra_sandhi(padas_ref, strip_shri_pratika(cluster.shri))
    if cluster.shri else (True, -1, "", "")
  )

  audit = audit_padapatha_against_sb(
    vp_clean, items, cluster.weber, cluster.shri, next_first_mark=next_first_mark
  )

  # Assemble synthetic section to run validator + reconciler identically to final file!
  assembled = (
    f"## {cluster.heading}\n\n"
    f"<details open><summary>{vp_sum}</summary>\n\n{vp_acc}\n</details>\n\n"
    + (f"<details><summary>मूलम् - श्रीधरादि</summary>\n\n{cluster.shri}\n</details>\n\n" if cluster.shri else "")
    + (f"<details><summary>मूलम् - Weber</summary>\n\n{cluster.weber}\n</details>\n\n" if cluster.weber else "")
    + f"{pp_block}\n"
  )
  v_issues = [f"{vi.kind}: {vi.message} ({vi.line})" for vi in validate_accented_markdown(assembled)]
  _, rec_logs = reconcile_markdown_blocks(assembled)

  # Strict AUTO_CLEAN certification gate (zero tolerance for silent errors!)
  reasons: list[str] = []
  if not ok_vp:
    reasons.append(f"sandhi_vp_fail@{fail_vp}:{win_vp}")
  if not (ok_w or ok_s):
    reasons.append(f"sandhi_mula_fail(W={fail_w},S={fail_s})")
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
  if v_issues:
    reasons.append(f"val_issues:{len(v_issues)}")
  if rec_logs:
    reasons.append(f"rec_logs:{len(rec_logs)}")

  # Check 100% solid provenance (no guesses, no bare weak MW-only without ŚBr.)
  weak_padas = [i for i, it in enumerate(items) if not it.solid or "अनाम्नातम्" in it.prov]
  if weak_padas:
    reasons.append(f"weak_prov:{weak_padas[:6]}")
  # Check no masked consecutive-udātta ambiguities
  if ambiguous_padas:
    reasons.append(f"ambiguous_padas:{[a['pada_idx'] for a in ambiguous_padas[:6]]}")
  # Require both Weber and Śrīdharādi present for AUTO_CLEAN (single-source clusters need review!)
  if not cluster.weber or not cluster.shri:
    reasons.append("missing_one_sb_source")

  # Check no compound upasarga+tiṅanta slipped through
  for i, it in enumerate(items):
    if "-" in it.ref and any(t in it.prov for t in ("८.१.२८", "८.१.६६", "८.१.३०", "८.१.३४", "८.१.७१")):
      reasons.append(f"compound_upasarga_tinanta@{i}:{it.ref}")

  status = "AUTO_CLEAN" if not reasons else "NEEDS_ADJUDICATION"

  lex_hits: list[str] = []
  if status == "NEEDS_ADJUDICATION":
    lex_hits = _summarize_lexicon_hits(padas_bare, lex)

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
          acc = apply_marks_to_token(key, mks)
        except ValueError:
          continue
        parts.append(f"{acc} ({_format_corpus_prov(srcs)})")
    else:
      for mks, prov, _ in lex.project_stem_accents(key)[:2]:
        try:
          acc = apply_marks_to_token(key, mks)
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

  # Pass 1: solve each kaṇḍikā to obtain first-syllable US mark of kaṇḍikā k+1
  # (needed for cross-kaṇḍikā boundary auditing on the final syllable of kaṇḍikā k!).
  prelim = [
    solve_kandika(cl, lex, kandika_id=f"{rel}::{cl.key}", next_first_mark=None)
    for cl in clusters
  ]
  first_marks: list[str | None] = []
  for r in prelim:
    if r.vp_accented:
      _, mks = syllables_with_marks(r.vp_accented)
      first_marks.append(mks[0] if mks else None)
    else:
      first_marks.append(None)

  # Pass 2: re-solve only kaṇḍikās where next_first_mark is known and matters (final syllable)
  results: list[SolveResult] = []
  for idx, (cl, r) in enumerate(zip(clusters, prelim)):
    nxt_m = first_marks[idx + 1] if idx + 1 < len(clusters) else None
    if nxt_m is not None and r.status != "SKIPPED":
      r = solve_kandika(cl, lex, kandika_id=f"{rel}::{cl.key}", next_first_mark=nxt_m)
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
