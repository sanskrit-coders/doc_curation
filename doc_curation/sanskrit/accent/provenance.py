"""Vedic corpus occurrence counting and ``पद-पाठः (यान्त्रिकः)`` provenance formatting.

Computes exact per-corpus occurrence counts (e.g. ``सर्व᳓तः (*TS*-12, *RV*-2, *TB*-3)``)
across all accented Vedic corpora hosted locally (`TS`, `RV`, `TB`, `TK`, `AV`,
`ŚB` / `SB-M`, `SB-K`, `VS-M` / legacy `VS`, `VS-K`, `KS`, `MS`), and normalizes Pāṇinian abbreviation signs
to canonical ``पा॰`` (``U+0970``, ``DEVANAGARI ABBREVIATION SIGN``).
"""

from __future__ import annotations

import functools
import glob
import os
import pickle
import re
from collections import defaultdict
from typing import Sequence

from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.accent.reconciler import (
  DETAILS_RE,
  US_SVARITA,
  US_UDATTA,
  find_js_include_spans,
  has_us_accents,
  is_solid_provenance,
  parse_padapatha_items,
)
from doc_curation.sanskrit.accent.shatapatha_solver import (
  DEFAULT_DICT_ROOT,
  _DEVANAGARI_RE,
  _VS_DETAILS_RE,
  _fast_scan_deva_syllables,
  _is_dual_accent_word,
  _join_virama_vowels,
  _normalize_lookup_key,
  classical_padapatha_to_us,
  us_padasvara_to_entry,
)

PROVENANCE_CACHE_VERSION = 12
DEFAULT_PROVENANCE_CACHE_PATH = os.path.expanduser(
  "~/.cache/doc_curation/vedic_corpus_counts_v1.pkl"
)

CORPUS_TAGS: tuple[str, ...] = (
  "TS",
  "RV",
  "TB",
  "TK",
  "AV",
  "ŚB",
  "SB-M",
  "SB-K",
  "VS-M",
  "VS-K",
  "VS",
  "KS",
  "MS",
)
CORPUS_TAG_SET: frozenset[str] = frozenset(CORPUS_TAGS)
MAJOR_AUTO_CORPORA: tuple[str, ...] = ("TS", "RV", "TB", "TK", "AV", "SB-M", "SB-K", "VS-M", "VS-K")
FORBIDDEN_CORPUS_TAGS: tuple[str, ...] = ("TA", "EK")
_CORPUS_ALIASES: dict[str, str] = {
  "ŚB": "SB-M",
  "SB-M": "ŚB",
  "VS": "VS-M",
  "VS-M": "VS",
}

DEFAULT_CORPUS_DIRS: dict[str, str] = {
  "TS": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/saMhitA/sarva-prastutiH",
  "RV": "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH",
  "TB": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/brAhmaNam/sarva-prastutiH",
  "TK": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/kAThakam/sarva-prastutiH",
  "ŚB": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH",
  "SB-M": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH",
  "SB-K": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/kANvam/shatapatha-brAhmaNam/sarva-prastutiH",
  "VS-M": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/saMhitA/sarva-prastutiH",
  "VS-K": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/kANvam/saMhitA",
  "VS": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/saMhitA/sarva-prastutiH",
  "AV": "/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/shaunakam/rUDha-saMhitA/sarva-prastutiH",
  "KS": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/kaTha-kapiShTalAH/saMhitA/mUlam/schroeder",
  "MS": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/maitrAyaNIyam",
}

_PRAGRHYA_O_WORDS: frozenset[str] = frozenset({
  "अथो", "उतो", "मो", "नो", "आहो", "उताहो", "ओ", "भो", "अहो",
})

# Metalanguage words inside (...) provenance that are NOT Sanskrit target padas
_METALANGUAGE_BARE: frozenset[str] = frozenset({
  "पा", "पुं", "नपुं", "स्त्री", "क्ली", "सर्वत्र", "वा", "च", "अपि", "तु", "एव", "इव", "इति",
  "अनुदात्तम्", "अनुदात्तः", "अनुदात्ता", "उदात्तः", "उदात्तम्", "आद्युदात्तम्", "आद्युदात्तः",
  "अन्तोदात्तम्", "अन्तोदात्तः", "मध्योदात्तम्", "मध्योदात्तः", "स्वरितः", "स्वरितम्", "सर्वानुदात्तम्",
  "तिङन्तम्", "तिङन्तः", "निपातः", "आमन्त्रितम्", "अपादादौ", "पादादौ", "पादादावामन्त्रितम्",
  "पादादावामन्त्रिते", "पादादिः", "वाक्यादौ", "वाक्यादिः", "अन्वादेशे", "अन्वादेशेऽनुदात्तम्",
  "द्विर्वचने", "परस्यानुदात्तत्वम्", "वीप्सायाम्", "प्रश्ने", "प्लुतः", "निपात",
  "प्रातिपदिकम्", "तुल्यम्", "वारम्", "अत्र", "मूलेऽत्र", "मूले", "श्रेयः", "श्रेयान्", "श्रेयसी",
  "समासस्य", "समासस्वरः", "बहुव्रीहौ", "तत्पुरुषः", "तत्पुरुषे", "षष्ठीतत्पुरुषः", "षष्ठीतत्पुरुषे",
  "नञ्", "नञ्सुभ्याम्", "कर्मधारयः", "द्वन्द्वः", "देवताद्वन्द्वे", "अव्ययीभावः",
  "गतिरनन्तरः", "गतिकृदन्तः", "गतिकारकोपपदात्कृत्", "यद्वृत्तान्नित्यम्", "तिङि", "चोदात्तवति",
  "क्विप्", "क्तः", "क्त", "क्त्वा", "ल्यप्", "शतृ", "शानच्", "आनच्", "क्वसुः", "ल्युट्", "घञ्",
  "क्तिन्", "तृच्", "णिनिः", "अच्", "कः", "खः", "ण्यत्", "यत्", "तवै", "तुमुन्", "मतुप्", "वतुप्",
  "वृषादिः", "अभ्यस्तानामादिः", "फिषोऽन्तः", "धातोः", "प्रत्ययस्वरः", "लसार्वधातुकानुदात्तत्वम्",
  "हरदत्तः", "भास्करः", "सायणः", "महीधरः", "उवटः", "भट्टभास्करः", "रङ्गरामानुजः",
})

_ZERO_ABBREV_RE = re.compile(r"([\u0905-\u0939][\u093e-\u094d\u0901-\u0903]*)\u0966")
_CORPUS_TAG_PAT = "|".join(re.escape(t) for t in CORPUS_TAGS)
_COUNT_OPT_PAT = r"(?:-\d+(?:/\d+)?)?"
_TAG_TOKEN_RE = re.compile(rf"\*({_CORPUS_TAG_PAT})\*(?:-(\d+)(?:/(\d+))?)?")
_FORBIDDEN_TAG_PAT = "|".join(re.escape(t) for t in FORBIDDEN_CORPUS_TAGS)
_FORBIDDEN_SOURCE_RE = re.compile(rf"\*({_FORBIDDEN_TAG_PAT})\*(?:-(\d+)(?:/(\d+))?)?")
_TOK_SCAN_RE = re.compile(r"[\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\-]+")

_DEGEM_PAIRS: tuple[tuple[str, str], ...] = (
  ("र्द्ध", "र्ध"),
  ("र्त्त", "र्त"),
  ("र्म्म", "र्म"),
  ("र्व्व", "र्व"),
  ("र्ग्ग", "र्ग"),
  ("र्ण्ण", "र्ण"),
  ("र्ब्ब", "र्ब"),
  ("र्च्च", "र्च"),
  ("र्ज्ज", "र्ज"),
  ("र्ल्ल", "र्ल"),
  ("द्ध्व", "ध्व"),
  ("द्ध्य", "ध्य"),
  ("त्त्व", "त्व"),
  ("ब्ध्व", "ब्ध"),
  ("ङ्क्त", "ङ्क्"),
  ("ळ्ह", "ढ"),
  ("ळ", "ड"),
)


def normalize_panini_abbreviations(text: str) -> str:
  """Replace Devanagari letter + digit-zero ``०`` (``U+0966``) abbreviations with ``॰`` (``U+0970``).

  Converts ``पा०`` → ``पा॰``, ``पुं०`` → ``पुं॰``, ``नपुं०`` → ``नपुं॰``, ``उणा०`` → ``उणा॰``
  while leaving multi-digit Devanagari numerals (``१०``, ``२०``, ``१०८``) untouched.
  """
  return _ZERO_ABBREV_RE.sub(r"\1॰", text)


@functools.lru_cache(maxsize=65536)
def _canonical_allograph_key(norm_key: str) -> str:
  """Normalize recensional gemination after ``र्``, ``ळ/ड``, and final stop voicing for fallback matching."""
  w = norm_key
  for src, dst in _DEGEM_PAIRS:
    if src in w:
      w = w.replace(src, dst)
  if w.endswith(("स्", "र्", "श्", "ष्")) and len(w) >= 3:
    w = w[:-2] + "ः"
  elif w.endswith("द्") and len(w) >= 3:
    w = w[:-2] + "त्"
  elif w.endswith("ग्") and len(w) >= 3:
    w = w[:-2] + "क्"
  elif w.endswith("ड्") and len(w) >= 3:
    w = w[:-2] + "ट्"
  elif w.endswith("ब्") and len(w) >= 3:
    w = w[:-2] + "प्"
  return w


_PADAPATHA_INTERNAL_SANDHI_PAIRS: tuple[tuple[re.Pattern[str], str], ...] = (
  (re.compile(r"प्(?=[भधदगघजझब])"), "द्"),
  (re.compile(r"त्(?=[भधदगघब])"), "द्"),
  (re.compile(r"क्(?=[भधदगघब])"), "ग्"),
  (re.compile(r"([िीुूृेोौ])ः([कखपफ])"), r"\1ष्\2"),
  (re.compile(r"ः([कखपफ])"), r"स्\1"),
  (re.compile(r"ःअ"), "र"),
  (re.compile(r"ःआ"), "रा"),
  (re.compile(r"ःइ"), "रि"),
  (re.compile(r"ःई"), "री"),
  (re.compile(r"ःउ"), "रु"),
  (re.compile(r"ःऊ"), "रू"),
  (re.compile(r"ःऋ"), "रृ"),
  (re.compile(r"ःए"), "रे"),
  (re.compile(r"ःओ"), "रो"),
  (re.compile(r"ः(?=[गघदधबभयवरलहजझम])"), "र्"),
)


def _padapatha_avagraha_sandhi_key(raw_with_avagraha: str) -> str | None:
  """Join internal ``ऽ`` seams with standard compound sandhi (e.g. ``अप्ऽभिः`` → ``अद्भिः``, ``निःऽऋतिम्`` → ``निरृतिम्``)."""
  if "ऽ" not in raw_with_avagraha:
    return None
  bare = re.sub(r"[\u0951-\u0957\u1cd0-\u1cff]", "", raw_with_avagraha).strip("।॥,. ;:+")
  parts = [p for p in bare.split("ऽ") if p]
  if len(parts) < 2:
    return None
  joined = parts[0]
  for nxt in parts[1:]:
    merged = joined + nxt
    for pat, rep in _PADAPATHA_INTERNAL_SANDHI_PAIRS:
      merged_new = pat.sub(rep, merged)
      if merged_new != merged:
        merged = merged_new
        break
    joined = merged
  return _normalize_lookup_key(joined)


@functools.lru_cache(maxsize=65536)
def word_to_key_and_marks(word: str) -> tuple[str, tuple[str, ...]] | None:
  """Convert a US-accented, classical-accented, or unaccented Devanagari word to ``(norm_key, marks)``."""
  s = word.strip().strip(".,;:?!()[]*\"' ")
  if not s or not _DEVANAGARI_RE.search(s):
    return None
  # Remove pluta numeral 3 (`हा३᳓` -> `हा᳓`) and normalize Taittirīya `[वयलर]्ँ` -> `ं` BEFORE syllable scanning
  # so a trailing US accent mark (`मेधाव्ँ᳓`) stays attached to the preceding vowel instead of being skipped!
  s_clean = re.sub(r"[३3]", "", s)
  s_clean = re.sub(r"[वयलर]्ँ", "ं", s_clean).replace("\ua8f3", "ं")
  # Apply internal compound sandhi across `-` (`उत्-धृतः` -> `उद्धृतः`, `उत्-मुच्य` -> `उन्मुच्य`)
  if "-" in s_clean:
    bare_parts = [re.sub(r"[\u0951-\u0957\u1cd0-\u1cff]", "", p) for p in s_clean.split("-") if p]
    if len(bare_parts) >= 2:
      sandhi_joined = bare_parts[0]
      for nxt in bare_parts[1:]:
        cand = sandhi_joined + nxt
        if sandhi_joined.endswith("त्") and nxt.startswith("म"):
          cand = sandhi_joined[:-2] + "न्" + nxt
        else:
          for pat, rep in _PADAPATHA_INTERNAL_SANDHI_PAIRS:
            c2 = pat.sub(rep, cand)
            if c2 != cand:
              cand = c2
              break
        sandhi_joined = cand
      norm_key_override: str | None = _normalize_lookup_key(sandhi_joined)
    else:
      norm_key_override = None
  else:
    norm_key_override = None

  if ("\u0951" in s_clean or "\u0952" in s_clean) and not has_us_accents(s_clean):
    # Saṁhitā classical citations (e.g. `अहोरा॒त्राणि॑`, `निमे॒षा`, `अप॒घ्नन्`) omit `॒` on leading anudātta syllables,
    # so `accent.to_US_accents` is exact for >=2-syllable words that are not all-`॒`, while `classical_padapatha_to_us`
    # handles isolated monosyllables and all-`॒` sarvānudātta words.
    scanned_dep = _fast_scan_deva_syllables(_join_virama_vowels(s_clean.replace("-", "").replace("ऽ", "")))
    if len(scanned_dep) >= 2 and not all("\u0952" in m for m, _ in scanned_dep):
      s_clean = accent.to_US_accents(s_clean, pauses=r"[।॥,;]+")
    else:
      conv = classical_padapatha_to_us(s_clean)
      if conv is not None:
        return (norm_key_override or conv[0]), conv[1]
      s_clean = accent.to_US_accents(s_clean, pauses=r"[।॥,;]+")
  norm_key = norm_key_override or _normalize_lookup_key(s_clean)
  if not norm_key:
    return None
  joined = _join_virama_vowels(s_clean.replace("-", "").replace("ऽ", ""))
  scanned = _fast_scan_deva_syllables(joined)
  if not scanned:
    return None
  marks = tuple(
    "S" if US_SVARITA in mks else ("U" if US_UDATTA in mks else "")
    for mks, _ in scanned
  )
  # When a classical saṁhitā snippet (e.g. `अप॒घ्नन्`, `प्रथम॒जाः`, `संविदा॒नः`, `पृत॒ना॒ऽजित॑म्`)
  # is cited in isolation, leading anudātta syllables before `॒` carry no `॒` mark (inherited from the
  # preceding word in saṁhitā), causing `to_US_accents` to mark them `U` as well. For non-dual-accent words,
  # only the final `U`/`S` (the syllable licensed by `॒`) is genuine.
  if (
    ("\u0951" in s or "\u0952" in s)
    and not has_us_accents(s)
    and sum(1 for mk in marks if mk) > 1
    and not _is_dual_accent_word(norm_key)
  ):
    last_idx = max(i for i, mk in enumerate(marks) if mk)
    marks = tuple(mk if i == last_idx else "" for i, mk in enumerate(marks))
  return norm_key, marks


def _strip_spans(text: str, spans: Sequence[tuple[int, int]]) -> str:
  """Remove sorted ``(start, end)`` spans from ``text`` in O(len(spans))."""
  if not spans:
    return text
  parts: list[str] = []
  last = 0
  for a, b in sorted(spans):
    if a > last:
      parts.append(text[last:a])
    if b > last:
      last = b
  parts.append(text[last:])
  return "".join(parts)


def _samhita_surface_keys(norm_key: str) -> list[str]:
  """Return ``norm_key`` plus pre-sandhi visarga normalizations for saṁhitā-only corpora (TB/TK/KS/MS)."""
  keys = [norm_key]
  if norm_key.endswith(("र्", "स्", "श्", "ष्")) and len(norm_key) >= 3:
    vis = norm_key[:-2] + "ः"
    if vis not in keys:
      keys.append(vis)
  elif norm_key.endswith("ो") and norm_key not in _PRAGRHYA_O_WORDS and len(norm_key) >= 2:
    vis = norm_key[:-1] + "ः"
    if vis not in keys:
      keys.append(vis)
  return keys


class VedicCorpusCounter:
  """Cached exact occurrence counter across Vedic corpora (`TS`, `RV`, `TB`, `TK`, `AV`, `SB-M`/`ŚB`, `SB-K`, `VS-M`/`VS`, `VS-K`, `KS`, `MS`; excludes dubious `TA`/`EK`)."""

  def __init__(
    self,
    exact_counts: dict[str, dict[tuple[str, tuple[str, ...]], int]] | None = None,
    allograph_counts: dict[str, dict[tuple[str, tuple[str, ...]], int]] | None = None,
    stem_prefix_counts: dict[str, dict[tuple[str, tuple[str, ...]], int]] | None = None,
  ) -> None:
    self.exact_counts: dict[str, dict[tuple[str, tuple[str, ...]], int]] = (
      exact_counts or {c: {} for c in CORPUS_TAGS}
    )
    self.allograph_counts: dict[str, dict[tuple[str, tuple[str, ...]], int]] = (
      allograph_counts or {c: {} for c in CORPUS_TAGS}
    )
    self.stem_prefix_counts: dict[str, dict[tuple[str, tuple[str, ...]], int]] = (
      stem_prefix_counts or {c: {} for c in CORPUS_TAGS}
    )
    self._paradigm_cache: dict[str, frozenset[tuple[str, tuple[str, ...]]]] = {}

  def _add(
    self,
    corpus: str,
    key: str,
    marks: tuple[str, ...],
    freq: int = 1,
    *,
    mode: str = "sum",
  ) -> None:
    if not key or not marks or freq <= 0 or corpus in FORBIDDEN_CORPUS_TAGS:
      return
    ex = self.exact_counts.setdefault(corpus, {})
    pair = (key, marks)
    if mode == "max":
      if freq > ex.get(pair, 0):
        ex[pair] = freq
    else:
      ex[pair] = ex.get(pair, 0) + freq

  def _finalize_secondary_tables(self) -> None:
    self.allograph_counts = {c: {} for c in CORPUS_TAGS}
    self.stem_prefix_counts = {c: {} for c in CORPUS_TAGS}
    self._paradigm_cache = {}
    for corpus, table in self.exact_counts.items():
      allo_tbl = self.allograph_counts[corpus]
      stem_tbl = self.stem_prefix_counts[corpus]
      for (key, marks), freq in table.items():
        ak = _canonical_allograph_key(key)
        allo_tbl[(ak, marks)] = allo_tbl.get((ak, marks), 0) + freq
        # Also index svarita->udatta equivalence for jātya monosyllables/stems (`स्वः᳙` <-> `सु᳓वः` handled separately)
        if "S" in marks:
          u_marks = tuple("U" if m == "S" else m for m in marks)
          allo_tbl[(ak, u_marks)] = allo_tbl.get((ak, u_marks), 0) + freq
        # Stem prefix index for explicit stem citations like `*TS* ब्राह्मण᳓`, `शत᳓ (*TS*, *RV*)`, or `अङ्गिरस्`
        if len(ak) >= 3:
          for trim in (1, 2):
            if len(ak) - trim >= 2 and ak.endswith(("ः", "म्", "न्", "त्", "ाः", "ान्")):
              base = ak[:-trim]
              if len(marks) >= 1:
                stem_tbl[(base, marks)] = stem_tbl.get((base, marks), 0) + freq

  @classmethod
  def load_or_build(
    cls,
    *,
    cache_path: str = DEFAULT_PROVENANCE_CACHE_PATH,
    dict_root: str = DEFAULT_DICT_ROOT,
    corpus_dirs: dict[str, str] | None = None,
    force_rebuild: bool = False,
  ) -> "VedicCorpusCounter":
    if not force_rebuild and cache_path and os.path.isfile(cache_path):
      try:
        with open(cache_path, "rb") as f:
          payload = pickle.load(f)
        if isinstance(payload, dict) and payload.get("version") == PROVENANCE_CACHE_VERSION:
          obj = cls(exact_counts=payload["exact_counts"])
          obj._finalize_secondary_tables()
          return obj
      except Exception:
        pass

    obj = cls.build(dict_root=dict_root, corpus_dirs=corpus_dirs)
    if cache_path:
      os.makedirs(os.path.dirname(cache_path), exist_ok=True)
      tmp = cache_path + ".tmp"
      with open(tmp, "wb") as f:
        pickle.dump(
          {"version": PROVENANCE_CACHE_VERSION, "exact_counts": obj.exact_counts},
          f,
          protocol=pickle.HIGHEST_PROTOCOL,
        )
      os.replace(tmp, cache_path)
    return obj

  @classmethod
  def build(
    cls,
    *,
    dict_root: str = DEFAULT_DICT_ROOT,
    corpus_dirs: dict[str, str] | None = None,
  ) -> "VedicCorpusCounter":
    dirs = dict(DEFAULT_CORPUS_DIRS)
    if corpus_dirs:
      dirs.update(corpus_dirs)
    counter = cls()

    # 1. Padasvara Babylon dictionaries (exact padapāṭha frequencies for RV, TS, TB, TK, AV, VS-M)
    for tag, rel in (
      ("RV", "stardict-sanskrit-kAvya/rv-padasvara-dev/rv-padasvara-dev.babylon"),
      ("TS", "stardict-sanskrit-kAvya/kyv-ts-padasvara/kyv-ts-padasvara.babylon"),
      ("TB", "stardict-sanskrit-kAvya/kyv-tb-pada-svara/kyv-tb-pada-svara.babylon"),
      ("TK", "stardict-sanskrit-kAvya/kyv-tk-pada-svara/kyv-tk-pada-svara.babylon"),
      ("AV", "stardict-sanskrit-kAvya/av-padasvara/av-padasvara.babylon"),
      ("VS-M", "stardict-sanskrit-kAvya/syv-ms-padasvara/syv-ms-padasvara.babylon"),
    ):
      bpath = os.path.join(dict_root, rel)
      if os.path.isfile(bpath):
        counter._ingest_babylon(bpath, tag)

    # 2. Supplement TS from local US-accented `विश्वास-प्रस्तुतिः` (`mode="max"` so babylon exact counts win when present;
    # note TS `<summary>पद-पाठः</summary>` is unaccented so we never run `classical_padapatha_to_us` on unaccented blocks!)
    ts_dir = dirs.get("TS", "")
    if ts_dir and os.path.isdir(ts_dir):
      counter._ingest_us_vp_supplement(ts_dir, "TS")

    # 3. VS-M (Mādhyandina; legacy alias `VS`): fallback to local markdown dir if syv-ms-padasvara.babylon wasn't loaded
    vs_m_dir = dirs.get("VS-M") or dirs.get("VS", "")
    if not counter.exact_counts.get("VS-M") and vs_m_dir and os.path.isdir(vs_m_dir):
      counter._ingest_vs_dir(vs_m_dir, corpus="VS-M")
    vs_dir = dirs.get("VS", "")
    if vs_dir and vs_dir == vs_m_dir:
      counter.exact_counts["VS"] = dict(counter.exact_counts.get("VS-M", {}))
    elif vs_dir and os.path.isdir(vs_dir):
      counter._ingest_vs_dir(vs_dir, corpus="VS")

    # 3b. VS-K (Kāṇva Saṁhitā): US-accented `विश्वास-प्रस्तुतिः` (fallback to classical `मूलम्`)
    vs_k_dir = dirs.get("VS-K", "")
    if vs_k_dir and os.path.isdir(vs_k_dir):
      counter._ingest_us_markdown_corpus(vs_k_dir, "VS-K")

    # 4. TB, TK, ŚB / SB-M, SB-K: deduplicated per section (`पद-पाठः` > `पद-पाठः (यान्त्रिकः...)` > `विश्वास-प्रस्तुतिः`)
    # Skip TB/TK markdown crawl if their padasvara Babylon dictionaries were already loaded in step 1.
    for tag in ("TB", "TK", "ŚB", "SB-M", "SB-K"):
      if tag in ("TB", "TK") and counter.exact_counts.get(tag):
        continue
      if tag == "SB-M" and dirs.get("SB-M") and dirs.get("SB-M") == dirs.get("ŚB"):
        counter.exact_counts["SB-M"] = dict(counter.exact_counts.get("ŚB", {}))
        continue
      cdir = dirs.get(tag, "")
      if cdir and os.path.isdir(cdir):
        counter._ingest_us_markdown_corpus(cdir, tag)

    # 5. KS & MS
    for tag in ("KS", "MS"):
      cdir = dirs.get(tag, "")
      if cdir and os.path.isdir(cdir):
        counter._ingest_samhita_or_pp_dir(cdir, tag, mode="sum")

    counter._finalize_secondary_tables()
    return counter

  def _ingest_babylon(self, path: str, corpus: str) -> None:
    with open(path, encoding="utf-8", errors="ignore") as f:
      raw = f.read()
    is_us = US_UDATTA in raw or US_SVARITA in raw
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
      conv = us_padasvara_to_entry(form_raw) if is_us else classical_padapatha_to_us(form_raw)
      if conv is None and is_us and corpus == "VS-M":
        # `syv-ms-padasvara.babylon` inherits unmarked pre-avagraha syllables before `॒` as a spurious leading `᳓`
        # on compounds (`सु᳓-प्रजाः᳓`, `पु᳓ष्टि-व᳓र्धनः`); recover the true final accent on non-dual compounds.
        joined_vs = _join_virama_vowels(form_raw.replace("-", "").replace("ऽ", ""))
        scanned_vs = _fast_scan_deva_syllables(joined_vs)
        nk_vs = _normalize_lookup_key(form_raw)
        if scanned_vs and nk_vs and not _is_dual_accent_word(nk_vs):
          mks_vs = tuple(
            "S" if US_SVARITA in ms else ("U" if US_UDATTA in ms else "") for ms, _ in scanned_vs
          )
          if sum(1 for x in mks_vs if x) > 1:
            last_i = max(i for i, x in enumerate(mks_vs) if x)
            conv = (nk_vs, tuple(x if i == last_i else "" for i, x in enumerate(mks_vs)), None)
      if conv is None:
        continue
      bare_key, marks = conv[0], conv[1]
      self._add(corpus, bare_key, marks, freq=freq, mode="sum")
      if "ऽ" in form_raw or (is_us and "-" in form_raw):
        sep_src = form_raw.replace("-", "ऽ") if is_us and "-" in form_raw else form_raw
        sk = _padapatha_avagraha_sandhi_key(sep_src)
        if sk and sk != bare_key and len(_fast_scan_deva_syllables(sk)) == len(marks):
          self._add(corpus, sk, marks, freq=freq, mode="max")
      if is_us and "-" in form_raw:
        # Also index syllable-aligned sandhi headword aliases (e.g. `अँहोमुचे`, `अभिमातिषाहम्`, `निषद्य`, `अद्भिः`)
        # while skipping `build_visvara_headwords` trimmed stems (`ः`/`म्` dropped).
        for hw in head.split("|"):
          if not _DEVANAGARI_RE.search(hw):
            continue
          hb = _normalize_lookup_key(hw)
          if (
              hb
              and hb != bare_key
              and len(_fast_scan_deva_syllables(hb)) == len(marks)
              and (not bare_key.endswith(("ः", "्")) or hb.endswith(("ः", "्")))
          ):
            self._add(corpus, hb, marks, freq=freq, mode="max")
      elif bare_key in ("ऊम्", "उम्") and marks == ("",):
        # Śākala RV/AV padapāṭha writes pragṛhya particle `उ` as `ऊँ॒` / `उं॒`
        self._add(corpus, "उ", ("",), freq=freq, mode="max")

  def _ingest_us_vp_supplement(self, root_dir: str, corpus: str) -> None:
    """Supplement ``corpus`` with US-accented ``विश्वास-प्रस्तुतिः`` tokens only where ``exact_counts`` is 0."""
    local: dict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
    for fp in sorted(glob.glob(os.path.join(root_dir, "**", "*.md"), recursive=True)):
      if os.path.basename(fp) in ("_index.md", "file_list.md"):
        continue
      txt = open(fp, encoding="utf-8", errors="ignore").read()
      if US_UDATTA not in txt and US_SVARITA not in txt:
        continue
      inc = find_js_include_spans(txt)
      if inc:
        txt = _strip_spans(txt, inc)
      for m in DETAILS_RE.finditer(txt):
        if m.group(1).strip().startswith("विश्वास-प्रस्तुतिः") and has_us_accents(m.group(2)):
          clean = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]", " ", m.group(2), flags=re.S)
          clean = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", clean)
          self._ingest_us_samhita_tokens(clean, corpus, target_dict=local)
    ex = self.exact_counts.setdefault(corpus, {})
    for pair, freq in local.items():
      if pair not in ex:
        ex[pair] = freq

  def _ingest_classical_padapatha_dir(self, root_dir: str, corpus: str, *, mode: str = "max") -> None:
    local: dict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
    for fp in sorted(glob.glob(os.path.join(root_dir, "**", "*.md"), recursive=True)):
      if os.path.basename(fp) in ("_index.md", "file_list.md"):
        continue
      txt = open(fp, encoding="utf-8", errors="ignore").read()
      if "पद-पाठः</summary>" not in txt:
        continue
      inc = find_js_include_spans(txt)
      for m in DETAILS_RE.finditer(txt):
        if any(a <= m.start() < b for a, b in inc):
          continue
        if m.group(1).strip() != "पद-पाठः":
          continue
        body = m.group(2)
        if "\u0951" not in body and "\u0952" not in body:
          continue
        for piece in re.split(r"[।॥\s]+", body):
          conv = classical_padapatha_to_us(piece)
          if conv is not None:
            local[(conv[0], conv[1])] += 1
    for (k, mks), freq in local.items():
      self._add(corpus, k, mks, freq=freq, mode=mode)

  def _ingest_vs_dir(self, vs_dir: str, corpus: str = "VS-M") -> None:
    for fp in sorted(glob.glob(os.path.join(vs_dir, "**", "*.md"), recursive=True)):
      if os.path.basename(fp) in ("_index.md", "file_list.md"):
        continue
      txt = open(fp, encoding="utf-8", errors="ignore").read()
      sections = re.split(r"(?=\n##[ \t]+)", txt)
      for sec in sections:
        blocks = [(m.group(1).strip(), m.group(2)) for m in _VS_DETAILS_RE.finditer(sec)]
        pp_bodies = [b for h, b in blocks if "पदपाठः" in h or "पद-पाठः" in h]
        if pp_bodies:
          for piece in re.split(r"[।॥\s]+", pp_bodies[0]):
            conv = classical_padapatha_to_us(piece)
            if conv is not None:
              self._add(corpus, conv[0], conv[1], freq=1, mode="sum")
          continue
        mula_body = next((b for h, b in blocks if "मूलम्" in h and ("\u0951" in b or "\u0952" in b)), "")
        if not mula_body:
          continue
        clean = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]|<[^>]+>", " ", mula_body, flags=re.S)
        us_txt = accent.to_US_accents(clean, pauses=r"[।॥,;]+")
        self._ingest_us_samhita_tokens(us_txt, corpus)

  def _ingest_us_samhita_tokens(
    self,
    us_txt: str,
    corpus: str,
    *,
    target_dict: dict[tuple[str, tuple[str, ...]], int] | None = None,
  ) -> None:
    for tok in _TOK_SCAN_RE.findall(us_txt):
      if "ऽ" in tok or not _DEVANAGARI_RE.search(tok):
        continue
      km = word_to_key_and_marks(tok)
      if km is None:
        continue
      norm_key, mks = km
      n_acc = sum(1 for mk in mks if mk)
      if n_acc > 1 and not _is_dual_accent_word(norm_key):
        continue
      for sk in _samhita_surface_keys(norm_key):
        if target_dict is not None:
          target_dict[(sk, mks)] += 1
        else:
          self._add(corpus, sk, mks, freq=1, mode="sum")

  def _ingest_us_markdown_corpus(self, root_dir: str, corpus: str) -> None:
    for fp in sorted(glob.glob(os.path.join(root_dir, "**", "*.md"), recursive=True)):
      base = os.path.basename(fp)
      if base in ("_index.md", "file_list.md"):
        continue
      txt = open(fp, encoding="utf-8", errors="ignore").read()
      if corpus != "VS-K":
        inc = find_js_include_spans(txt)
        if inc:
          txt = _strip_spans(txt, inc)
      details_rx = _VS_DETAILS_RE if corpus == "VS-K" else DETAILS_RE
      sections = re.split(r"(?=\n##[ \t]+)", txt)
      for sec in sections:
        blocks = [(m.group(1).strip(), m.group(2)) for m in details_rx.finditer(sec)]
        if not blocks:
          continue
        pp_trad = [b for h, b in blocks if h == "पद-पाठः" and ("\u0951" in b or "\u0952" in b)]
        pp_mech = [b for h, b in blocks if h.startswith("पद-पाठः (यान्त्रिकः")]
        vp_blocks = [b for h, b in blocks if h.startswith("विश्वास-प्रस्तुतिः") and has_us_accents(b)]
        if pp_trad:
          for body in pp_trad:
            for piece in re.split(r"[।॥\s]+", body):
              conv = classical_padapatha_to_us(piece)
              if conv is not None:
                self._add(corpus, conv[0], conv[1], freq=1, mode="sum")
        elif pp_mech:
          for body in pp_mech:
            items = parse_padapatha_items(body)
            if items:
              for it in items:
                if "?" in it.ref or not _DEVANAGARI_RE.search(it.ref):
                  continue
                km = word_to_key_and_marks(it.ref)
                if km is not None:
                  self._add(corpus, km[0], km[1], freq=1, mode="sum")
            else:
              for piece in re.split(r"[।॥\s]+", body):
                if not piece or "?" in piece or not _DEVANAGARI_RE.search(piece):
                  continue
                km = word_to_key_and_marks(piece)
                if km is not None:
                  self._add(corpus, km[0], km[1], freq=1, mode="sum")
        elif vp_blocks:
          for body in vp_blocks:
            clean = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]", " ", body, flags=re.S)
            clean = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", clean)
            if accent.detect_fake_US_accents(clean):
              continue
            self._ingest_us_samhita_tokens(clean, corpus)
        elif corpus == "VS-K":
          mula_blocks = [b for h, b in blocks if h in ("मूलम्", "मूलम् - काण्वम्") and ("\u0951" in b or "\u0952" in b)]
          for body in mula_blocks:
            clean = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]|<[^>]+>", " ", body, flags=re.S)
            us_txt = accent.to_US_accents(clean, pauses=r"[।॥,;]+")
            self._ingest_us_samhita_tokens(us_txt, corpus)
        elif corpus in ("ŚB", "SB-M"):
          weber_blocks = [b for h, b in blocks if h == "मूलम् - Weber"]
          for body in weber_blocks:
            w_clean = re.sub(r"\[\^?[^\]]*\]|\([^)]*\)", " ", body)
            # Restore Weber prevocalic visarga-lopa before avagraha (`शारीर᳘ ऽआत्मा᳘` -> `शारीर᳘ः आत्मा᳘`)
            w_clean = re.sub(r"([\u0905-\u0939][\u093e-\u094c]?[\u1cd8\u1cda\u0957]*)\s+(?=ऽ)", r"\1ः ", w_clean)
            w_us = w_clean.replace("\u1cd8", US_UDATTA).replace("\u1cda", US_UDATTA)
            self._ingest_us_samhita_tokens(w_us, corpus)

  def _ingest_samhita_or_pp_dir(self, root_dir: str, corpus: str, *, mode: str = "sum") -> None:
    local: dict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
    for fp in sorted(glob.glob(os.path.join(root_dir, "**", "*.md"), recursive=True)):
      if os.path.basename(fp) in ("_index.md", "file_list.md"):
        continue
      txt = open(fp, encoding="utf-8", errors="ignore").read()
      inc = find_js_include_spans(txt)
      if inc:
        txt = _strip_spans(txt, inc)
      blocks = [(m.group(1).strip(), m.group(2)) for m in DETAILS_RE.finditer(txt)]
      if blocks:
        chosen = [b for h, b in blocks if h.startswith("विश्वास-प्रस्तुतिः") and has_us_accents(b)]
        if not chosen:
          chosen = [
            accent.to_US_accents(re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]", " ", b, flags=re.S), pauses=r"[।॥,;]+")
            for h, b in blocks
            if h.startswith("मूलम्") and ("\u0951" in b or "\u0952" in b)
          ]
        for u_b in chosen:
          self._ingest_us_samhita_tokens(u_b, corpus, target_dict=local)
      else:
        body = txt.split("+++", 2)[2] if txt.startswith("+++") and txt.count("+++") >= 2 else txt
        if has_us_accents(body):
          self._ingest_us_samhita_tokens(body, corpus, target_dict=local)
        elif "\u0951" in body or "\u0952" in body:
          u_b = accent.to_US_accents(body, pauses=r"[।॥,;]+")
          self._ingest_us_samhita_tokens(u_b, corpus, target_dict=local)
    for (k, mks), freq in local.items():
      self._add(corpus, k, mks, freq=freq, mode=mode)

  def count(self, word: str, corpus: str) -> int:
    """Return the occurrence count of ``word`` (with its US/classical accent) in ``corpus``."""
    if corpus not in CORPUS_TAG_SET:
      return 0
    km = word_to_key_and_marks(word)
    if km is None:
      return 0
    norm_key, marks = km

    # 1. Exact (norm_key, marks)
    exact = self.exact_counts.get(corpus, {}).get((norm_key, marks), 0)
    if exact > 0:
      return exact

    # 2. Allograph / degemination / jātya svarita-udātta equivalence
    ak = _canonical_allograph_key(norm_key)
    allo_tbl = self.allograph_counts.get(corpus, {})
    allo = allo_tbl.get((ak, marks), 0)
    if allo > 0:
      return allo
    if "S" in marks:
      u_marks = tuple("U" if m == "S" else m for m in marks)
      allo_u = allo_tbl.get((ak, u_marks), 0)
      if allo_u > 0:
        return allo_u

    # 3. Taittirīya vyūha (`सु᳓वः` <-> `स्वः᳙`, `त्र्य्-` <-> `त्रि-`, `-न्` <-> `-म्` parasavarṇa)
    if ak == "स्वः" and marks in (("S",), ("U",)):
      c_suv = allo_tbl.get(("सुवः", ("U", "")), 0)
      if c_suv > 0:
        return c_suv
    elif ak == "सुवः" and marks == ("U", ""):
      c_sv = allo_tbl.get(("स्वः", ("S",)), 0) + allo_tbl.get(("स्वः", ("U",)), 0)
      if c_sv > 0:
        return c_sv

    if ak.endswith("न्") and len(ak) >= 3:
      c_m = allo_tbl.get((ak[:-2] + "म्", marks), 0)
      if c_m > 0:
        return c_m
    elif ak.endswith("म्") and len(ak) >= 3:
      c_n = allo_tbl.get((ak[:-2] + "न्", marks), 0)
      if c_n > 0:
        return c_n

    # 3b. Śākala RV/AV padapāṭha de-retroflexion across explicit `-` compound seams (`प्र᳓-णेतः` -> `प्रनेतः`, `परि-ष्व᳓जे` -> `परिस्वजे`, `शत्रु-ह᳓णः` -> `शत्रुहनः`)
    if "-" in word:
      deretro = ak
      for r_src, r_dst in (
        ("प्रण", "प्रन"),
        ("परिष", "परिस"),
        ("विष", "विस"),
        ("निष", "निस"),
        ("अभिष", "अभिस"),
        ("सुष", "सुस"),
        ("दुष", "दुस"),
        ("हण", "हन"),
      ):
        if r_src in deretro:
          deretro = deretro.replace(r_src, r_dst)
      if deretro != ak:
        c_dr = allo_tbl.get((deretro, marks), 0)
        if c_dr > 0:
          return c_dr
      retro = ak
      for r_src, r_dst in (("सुस", "सुष"), ("अभिस", "अभिष"), ("परिस", "परिष"), ("विस", "विष"), ("निस", "निष")):
        if r_src in retro:
          retro = retro.replace(r_src, r_dst)
      if retro != ak:
        c_rt = allo_tbl.get((retro, marks), 0)
        if c_rt > 0:
          return c_rt

    # 3c. Śākala RV/AV padapāṭha visarga retention vs saṁhitā sibilant before voiceless stops (`जास्पत्य᳓म्` <-> `जाःपत्यम्`, `विश्व᳓तस्पात्` <-> `विश्वतःपात्`)
    vis_de = re.sub(r"[सषश]्(?=[कखपफचछतथ])", "ः", ak)
    if vis_de != ak:
      c_vd = allo_tbl.get((vis_de, marks), 0)
      if c_vd > 0:
        return c_vd

    # 4. Stem citation fallback (when `word` is an uninflected stem like `ब्राह्मण᳓` or `अङ्गिरस्`)
    stem_c = self.stem_prefix_counts.get(corpus, {}).get((ak, marks), 0)
    if stem_c > 0:
      return stem_c
    # Unaccented stem citation (e.g. `अङ्गिरस् (*TS*, *RV*)`) -> sum all accented inflections of stem
    if not any(marks) and len(ak) >= 4:
      stem_any = sum(
        f for (sk, _), f in self.stem_prefix_counts.get(corpus, {}).items() if sk == ak
      )
      if stem_any > 0:
        return stem_any

    return 0

  def paradigm_forms(self, word: str) -> frozenset[tuple[str, tuple[str, ...]]]:
    """Return the set of ``(canonical_allograph_key, marks)`` case-inflected forms of ``word``'s nominal stem."""
    cached = self._paradigm_cache.get(word)
    if cached is not None:
      return cached
    km = word_to_key_and_marks(word)
    if km is None or not any(km[1]):
      res: frozenset[tuple[str, tuple[str, ...]]] = frozenset()
      self._paradigm_cache[word] = res
      return res
    ak = _canonical_allograph_key(km[0])
    marks = km[1]

    # 1. Closed heteroclite / suppletive / numeral / orthotonic-pronoun paradigms
    irreg_map = _get_irregular_paradigm_map()
    if (ak, marks) in irreg_map:
      res = irreg_map[(ak, marks)]
      self._paradigm_cache[word] = res
      return res

    # 2. Dual-accent पा॰ ६.२.१४० compounds (`वन᳓स्प᳓तिः`, `बृ᳓हस्प᳓तिः`, `वाचः᳓-प᳓तये`)
    acc_indices = [i for i, m in enumerate(marks) if m]
    if len(acc_indices) == 2 and "-" in word:
      parts = [p for p in word.split("-") if p]
      if len(parts) == 2:
        km1 = word_to_key_and_marks(parts[0])
        km2 = word_to_key_and_marks(parts[1])
        if km1 and km2 and any(km1[1]) and any(km2[1]):
          sub_forms = self.paradigm_forms(parts[1])
          if sub_forms:
            p1_raw = re.sub(r"[\u0951-\u0957\u1cd0-\u1cff]", "", parts[0])
            combined: set[tuple[str, tuple[str, ...]]] = {(ak, marks)}
            for sf_ak, sf_mks in sub_forms:
              joined_w = p1_raw + "-" + sf_ak
              j_km = word_to_key_and_marks(joined_w)
              if j_km and len(j_km[1]) == len(km1[1]) + len(sf_mks):
                combined.add((_canonical_allograph_key(j_km[0]), km1[1] + sf_mks))
            res = frozenset(combined)
            self._paradigm_cache[word] = res
            return res

    # 3. Productive Pāṇinian declensional classes scored against attested corpus paradigms
    cands = _infer_candidate_stems(ak, marks)
    if not cands:
      res = frozenset({(ak, marks)})
      self._paradigm_cache[word] = res
      return res

    vis_de = re.sub(r"[सषश]्(?=[कखपफचछतथ])", "ः", ak)
    word_ends_fem_a = ak.endswith(("ा", "ाम्", "या", "ायै", "ायाः", "ायाम्", "ाभिः", "ाभ्यः", "ासु", "ासाम्")) and not ak.endswith("ता")
    best_forms: set[tuple[str, tuple[str, ...]]] = {(ak, marks)}
    best_score = (-1, -1)
    for st, cls, stem_a in cands:
      include_fem = word_ends_fem_a
      if cls == "a" and not include_fem:
        fem_probes = _generate_nominal_paradigm(st, "a_fem_oblique", stem_a)
        include_fem = any(
          self.allograph_counts.get(cp, {}).get(fp, 0) > 0
          for cp in CORPUS_TAGS
          for fp in fem_probes
        )
        if not include_fem:
          # Also enable fem `-आ` when masc/neut `-ः`/`-म्` are unattested while fem `-ा`/`-ाम्` are attested (`स्थू᳓णा`)
          masc_probes = _generate_nominal_paradigm(st, "a_masc_nom_acc", stem_a)
          has_masc = any(
            self.allograph_counts.get(cp, {}).get(mp, 0) > 0
            for cp in CORPUS_TAGS
            for mp in masc_probes
          )
          if not has_masc:
            fem_na = _generate_nominal_paradigm(st, "a_fem_nom_acc", stem_a)
            include_fem = any(
              self.allograph_counts.get(cp, {}).get(fp, 0) > 0
              for cp in CORPUS_TAGS
              for fp in fem_na
            )
      if cls == "i" and not ak.endswith(("िः", "िम्", "िना", "िणा", "ये", "ेः", "यः", "ीन्", "िभिः", "िभ्यः", "िषु", "ि")):
        # Require at least one unambiguous `i`-stem inflection in corpora before preferring `i`-stem on ambiguous `-ौ`/`-ा`
        i_core = _generate_nominal_paradigm(st, "i_core", stem_a)
        if not any(
          self.allograph_counts.get(cp, {}).get(ic, 0) > 0
          for cp in CORPUS_TAGS
          for ic in i_core
        ):
          continue
      p_forms = _generate_nominal_paradigm(st, cls, stem_a, include_fem_a=include_fem)
      if (ak, marks) not in p_forms and (vis_de, marks) not in p_forms and "-" not in word:
        continue
      distinct_other = 0
      total_freq = 0
      for cp in CORPUS_TAGS:
        tbl = self.allograph_counts.get(cp, {})
        for pf in p_forms:
          c_val = tbl.get(pf, 0)
          if c_val > 0:
            total_freq += c_val
            if pf[0] != ak:
              distinct_other += 1
      score = (distinct_other, total_freq)
      if score > best_score:
        best_score = score
        best_forms = p_forms
    best_forms.add((ak, marks))
    res = frozenset(best_forms)
    self._paradigm_cache[word] = res
    return res

  def count_with_stem(
    self,
    word: str,
    corpus: str,
    *,
    allow_stem: bool = True,
  ) -> tuple[int, int]:
    """Return ``(exact_count, all_cases_stem_count)`` for ``word`` in ``corpus``."""
    if corpus not in CORPUS_TAG_SET:
      return 0, 0
    m = self.count(word, corpus)
    if not allow_stem or not is_declinable_nominal(word):
      return m, m
    p_forms = self.paradigm_forms(word)
    if not p_forms:
      return m, m
    allo_tbl = self.allograph_counts.get(corpus, {})
    has_hyphen = "-" in word
    n_sum = 0
    counted_keys: set[tuple[str, tuple[str, ...]]] = set()
    for pf_ak, pf_mks in p_forms:
      if (pf_ak, pf_mks) in counted_keys:
        continue
      val = allo_tbl.get((pf_ak, pf_mks), 0)
      if val > 0:
        n_sum += val
        counted_keys.add((pf_ak, pf_mks))
        continue
      # Taittirīya saṁhitā `-म्` -> `-न्` parasavarṇa (`उदक᳓म्` -> `उदक᳓न्` in TB)
      if pf_ak.endswith("म्") and len(pf_ak) >= 4:
        alt_n = pf_ak[:-2] + "न्"
        if (alt_n, pf_mks) not in counted_keys:
          n_val = allo_tbl.get((alt_n, pf_mks), 0)
          if n_val > 0:
            n_sum += n_val
            counted_keys.add((alt_n, pf_mks))
            continue
      if has_hyphen:
        vis_de = re.sub(r"[सषश]्(?=[कखपफचछतथ])", "ः", pf_ak)
        if vis_de != pf_ak and (vis_de, pf_mks) not in counted_keys:
          v_val = allo_tbl.get((vis_de, pf_mks), 0)
          if v_val > 0:
            n_sum += v_val
            counted_keys.add((vis_de, pf_mks))
            continue
        deretro = pf_ak
        for r_src, r_dst in (
          ("प्रण", "प्रन"), ("परिष", "परिस"), ("विष", "विस"), ("निष", "निस"),
          ("अभिष", "अभिस"), ("सुष", "सुस"), ("दुष", "दुस"), ("हण", "हन"),
        ):
          if r_src in deretro:
            deretro = deretro.replace(r_src, r_dst)
        if deretro != pf_ak and (deretro, pf_mks) not in counted_keys:
          d_val = allo_tbl.get((deretro, pf_mks), 0)
          if d_val > 0:
            n_sum += d_val
            counted_keys.add((deretro, pf_mks))
    return m, max(m, n_sum)


def format_corpus_count(corpus: str, m: int, n: int | None = None) -> str | None:
  """Format ``(exact, all_cases)`` counts as ``*CORPUS*-M/N`` when ``N > M``, else ``*CORPUS*-M``."""
  n_eff = m if n is None else n
  if m <= 0 and n_eff <= 0:
    return None
  if n_eff > m:
    return f"*{corpus}*-{m}/{n_eff}"
  return f"*{corpus}*-{m}"


_INDECLINABLE_BARE: frozenset[str] = frozenset({
  "च", "वा", "उ", "हि", "ह", "स्म", "वै", "एव", "इत्", "चित्", "चन", "नु", "सु", "कम्",
  "ईम्", "सीम्", "न", "मा", "इति", "इव", "नूनम्", "नाना", "सह", "साकम्", "सत्रा", "सदा",
  "कदा", "यदा", "तदा", "यत्र", "तत्र", "अत्र", "कुत्र", "कुह", "इह", "यथा", "तथा", "कथम्",
  "इत्थम्", "यदि", "नेत्", "चेत्", "कुवित्", "किला", "किल", "खलु", "नू", "आत्", "अथ", "अथो",
  "उत", "उतो", "अपि", "तु", "स्वित्", "अह", "हन्त", "ओम्", "स्वाहा", "स्वधा", "वषट्", "श्रौषट्",
  "वौषट्", "शम्", "योः", "स्वस्ति", "अद्धा", "मिथः", "मिथू", "मुहुः", "पुनः", "प्रातः",
  "सायाम्", "सायम्", "दिवा", "नक्तम्", "श्वः", "ह्यः", "अद्य", "सद्यः", "परुत्", "चिरम्",
  "उच्चा", "उच्चैः", "नीचैः", "शनैः", "शनकैः", "आरात्", "अन्तिके", "पुरः", "पुरस्तात्",
  "अधः", "अधस्तात्", "उपरि", "उपरिष्टात्", "अवः", "अवस्तात्", "परः", "परस्तात्", "तिरः",
  "बहिः", "अन्तः", "अन्तरा", "अन्तरेण", "ऋते", "विना", "पृथक्", "समया", "निकषा", "हा", "धिक्",
  "सम्", "प्र", "परा", "अप", "अनु", "अव", "नि", "निः", "दुः", "वि", "आ", "अधि", "अति",
  "उत्", "अभि", "प्रति", "परि", "उप", "अच्छा", "अच्छ", "भूः", "भुवः", "स्वः", "सुवः",
})

_AVYAYA_SUFFIX_RE = re.compile(r"(?:तः|त्र|था|धा|शः|सात्|त्वा|त्वाय|ध्यै|तवै)$")
_NON_SUBANTA_PROV_RE = re.compile(
  r"तिङन्त|आशीर्लिङ्|लिट्|लोट्|लङ्|लुङ्|विधिलिङ्|लेट्|८\.१\.२८|८\.१\.६६|८\.१\.३४|८\.१\.३०|८\.१\.५९|८\.१\.६३|८\.१\.७१|"
  r"यद्वृत्तान्नित्यम्|तिङि\s+चोदात्तवति|हि\s+च|आमन्त्रित|६\.१\.१९८|८\.१\.१९|८\.१\.१८|८\.१\.३\b|२\.४\.३[२३४]|"
  r"निपात|अव्यय(?![ीपूर्वपद])|उपसर्ग|क्त्वा\b|ल्यप्|तुमुन्|तवै\b"
)
_MATER_CHARS = frozenset("ािीुूृॄॢॣेैोौ्")


def is_declinable_nominal(word: str, prov: str = "") -> bool:
  """Return True if ``word`` is an accented declinable nominal (``सुबन्त``/stem), not an avyaya, tiṅanta, or vocative."""
  km = word_to_key_and_marks(word)
  if km is None or not any(km[1]):
    return False
  if prov and _NON_SUBANTA_PROV_RE.search(prov):
    return False
  ak = _canonical_allograph_key(km[0])
  if ak in _INDECLINABLE_BARE:
    return False
  if _AVYAYA_SUFFIX_RE.search(ak) and ak not in (
    "गात्र", "पात्र", "क्षेत्र", "मित्र", "गोत्र", "पुत्र", "नेत्र", "सूत्र", "स्तोत्र", "नक्षत्र", "मन्त्र", "तन्त्र", "यन्त्र", "छत्र", "वस्त्र", "शस्त्र", "अस्त्र", "रात्र",
    "कथा", "गाथा", "प्रथा", "व्यथा",
  ):
    if ak.endswith("तः") and ak not in (
      "सर्वतः", "विश्वतः", "अभितः", "परितः", "उभयतः", "अन्यतः", "एकतः", "इतः", "अतः", "ततः", "यतः", "कुतः",
      "अग्रतः", "पृष्ठतः", "दक्षिणतः", "उत्तरतः", "पुरतः", "अधस्ततः", "मत्तः", "त्वत्तः", "अस्मत्तः",
    ):
      return True
    return False
  return True


def _n_syls(k: str) -> int:
  return len(_fast_scan_deva_syllables(k))


def _ends_inherent_a(b: str) -> bool:
  return bool(b) and b[-1] not in _MATER_CHARS and "\u0905" <= b[-1] <= "\u0939"


@functools.lru_cache(maxsize=1)
def _get_irregular_paradigm_map() -> dict[tuple[str, tuple[str, ...]], frozenset[tuple[str, tuple[str, ...]]]]:
  groups: tuple[tuple[str, ...], ...] = (
    ("प᳓न्थाः", "प᳓न्थाम्", "प᳓न्थानम्", "पथा᳓", "पथे᳓", "पथः᳓", "पथि᳓", "प᳓न्थानः", "प᳓थाः", "पथि᳓भिः", "पथि᳓भ्याम्", "पथि᳓भ्यः", "पथा᳓म्", "पथीना᳓म्", "पथि᳓षु"),
    ("आ᳓पः", "अपः᳓", "अद्भिः᳓", "अद्भ्यः᳓", "अपा᳓म्", "अप्सु᳓"),
    ("गौः᳓", "गा᳓म्", "ग᳓वा", "ग᳓वे", "गोः᳓", "ग᳓वि", "गा᳓वौ", "गा᳓वा", "गो᳓भ्याम्", "ग᳓वोः", "गा᳓वः", "गाः᳓", "गो᳓भिः", "गो᳓भ्यः", "ग᳓वाम्", "गो᳓नाम्", "गोना᳓म्", "गो᳓षु"),
    ("द्यौः᳓", "द्या᳓म्", "दि᳓वम्", "दिवा᳓", "दिवे᳓", "दिवः᳓", "दिवि᳓", "द्यू᳓नि", "द्या᳓वा", "द्यु᳓भ्याम्", "दि᳓वः", "द्यु᳓भिः", "द्यु᳓भ्यः", "दिवा᳓म्", "द्यु᳓षु"),
    ("राः᳓", "रा᳓यम्", "राया᳓", "राये᳓", "रायः᳓", "रायि᳓", "रा᳓यः", "राया᳓म्", "रैभिः᳓", "रैभ्यः᳓"),
    ("स᳓खा", "स᳓खायम्", "स᳓ख्या", "स᳓ख्ये", "स᳓ख्युः", "स᳓खायौ", "स᳓खिभ्याम्", "स᳓ख्योः", "स᳓खायः", "स᳓खीन्", "स᳓खिभिः", "स᳓खिभ्यः", "स᳓खीनाम्", "स᳓खिषु"),
    ("प᳓तिः", "प᳓तिम्", "प᳓त्या", "प᳓त्ये", "प᳓त्युः", "प᳓त्यौ", "प᳓ती", "प᳓तिभ्याम्", "प᳓त्योः", "प᳓तयः", "प᳓तीन्", "प᳓तिभिः", "प᳓तिभ्यः", "प᳓तीनाम्", "प᳓तिषु"),
    ("स्त्री᳓", "स्त्रि᳓यम्", "स्त्री᳓म्", "स्त्रिया᳓", "स्त्रियै᳓", "स्त्रियाः᳓", "स्त्रिया᳓म्", "स्त्रि᳓यौ", "स्त्री᳓भ्याम्", "स्त्रि᳓यः", "स्त्रीः᳓", "स्त्री᳓भिः", "स्त्री᳓भ्यः", "स्त्रीणा᳓म्", "स्त्री᳓षु"),
    ("श्वा᳓", "श्वा᳓नम्", "शु᳓ना", "शु᳓ने", "शु᳓नः", "शु᳓नि", "श्वा᳓नौ", "श्व᳓भ्याम्", "श्वा᳓नः", "श्व᳓भिः", "श्व᳓भ्यः", "शु᳓नाम्", "श्व᳓सु"),
    ("यु᳓वा", "यु᳓वानम्", "यू᳓ना", "यू᳓ने", "यू᳓नः", "यू᳓नि", "यु᳓वानौ", "यु᳓वभ्याम्", "यु᳓वानः", "यु᳓वभिः", "यु᳓वभ्यः", "यू᳓नाम्", "यु᳓वसु"),
    ("मघ᳓वा", "मघ᳓वानम्", "मघो᳓ना", "मघो᳓ने", "मघो᳓नः", "मघ᳓वद्भिः", "मघ᳓वद्भ्यः", "मघो᳓नाम्", "मघ᳓वत्सु", "मघ᳓वानः"),
    ("पूषा᳓", "पूष᳓णम्", "पूष्णा᳓", "पूष्णे᳓", "पूष्णः᳓", "पूष्णि᳓", "पूष᳓णः"),
    ("अ᳓हः", "अ᳓ह्ना", "अ᳓ह्ने", "अ᳓ह्नः", "अ᳓हनि", "अ᳓ह्नि", "अ᳓हनी", "अ᳓होभ्याम्", "अ᳓ह्नोः", "अ᳓हानि", "अ᳓हा", "अ᳓होभिः", "अ᳓होभ्यः", "अ᳓ह्नाम्", "अ᳓हःसु", "अ᳓हस्सु"),
    ("अ᳓क्षि", "अक्ष्णा᳓", "अक्ष्णे᳓", "अक्ष्णः᳓", "अक्षि᳓णि", "अ᳓क्षिणी", "अक्षी᳓", "अ᳓क्षीणि", "अक्षि᳓भ्याम्", "अक्षि᳓भिः"),
    ("अ᳓स्थि", "अस्थ्ना᳓", "अस्थ्ने᳓", "अस्थ्नः᳓", "अ᳓स्थीनि", "अस्थि᳓भिः", "अस्थि᳓भ्यः", "अस्थ्ना᳓म्"),
    ("हृ᳓त्", "हृ᳓दम्", "हृदा᳓", "हृदे᳓", "हृदः᳓", "हृदि᳓", "हृद्भिः᳓", "हृद्भ्यः᳓", "हृदा᳓म्", "हृत्सु᳓"),
    ("पा᳓त्", "पा᳓दम्", "पदा᳓", "पदे᳓", "पदः᳓", "पदि᳓", "पा᳓दौ", "पद्भ्या᳓म्", "पा᳓दः", "पद्भिः᳓", "पद्भ्यः᳓", "पदा᳓म्", "पत्सु᳓"),
    ("अनड्वा᳓न्", "अनड्वा᳓हम्", "अनडु᳓हा", "अनडु᳓हे", "अनडु᳓हः", "अनडु᳓हि", "अनड्वा᳓हौ", "अनड्वा᳓हः", "अनडु᳓द्भिः"),
    ("द्वौ᳓", "द्वा᳓", "द्वे᳓", "द्वा᳓भ्याम्", "द्व᳓योः"),
    ("त्र᳓यः", "तिस्रः᳓", "त्री᳓णि", "त्री᳓", "त्री᳓न्", "त्रिभिः᳓", "तिसृ᳓भिः", "त्रिभ्यः᳓", "तिसृ᳓भ्यः", "त्रयाणा᳓म्", "त्रीणा᳓म्", "तिसृणा᳓म्", "त्रिषु᳓", "तिसृ᳓षु"),
    ("चत्वा᳓रः", "चत᳓स्रः", "चत्वा᳓रि", "च᳓तुरः", "चतु᳓र्भिः", "चत᳓सृभिः", "चतु᳓र्भ्यः", "चत᳓सृभ्यः", "चतुर्णा᳓म्", "चतसृणा᳓म्", "चतु᳓र्षु", "चत᳓सृषु"),
    ("प᳓ञ्च", "प᳓ञ्चभिः", "प᳓ञ्चभ्यः", "पञ्चा᳓नाम्", "पञ्चाना᳓म्", "प᳓ञ्चसु"),
    ("ष᳓ट्", "षड्भिः᳓", "षड्भ्यः᳓", "षण्णा᳓म्", "षट्सु᳓"),
    ("सप्त᳓", "सप्त᳓भिः", "सप्त᳓भ्यः", "सप्ताना᳓म्", "सप्त᳓सु"),
    ("अष्टौ᳓", "अष्टा᳓", "अष्ट᳓", "अष्टा᳓भिः", "अष्टा᳓भ्यः", "अष्टाना᳓म्", "अष्टा᳓सु"),
    ("न᳓व", "न᳓वभिः", "न᳓वभ्यः", "नवाना᳓म्", "न᳓वसु"),
    ("द᳓श", "द᳓शभिः", "द᳓शभ्यः", "दशाना᳓म्", "द᳓शसु"),
    ("सः᳓", "त᳓म्", "ते᳓न", "त᳓स्मै", "त᳓स्मात्", "त᳓स्य", "त᳓स्मिन्", "तौ᳓", "ता᳓भ्याम्", "त᳓योः", "ते᳓", "ता᳓न्", "तैः᳓", "ते᳓भिः", "ते᳓भ्यः", "ते᳓षाम्", "ते᳓षु", "सा᳓", "ता᳓म्", "त᳓या", "त᳓स्यै", "त᳓स्याः", "त᳓स्याम्", "ताः᳓", "ता᳓भिः", "ता᳓भ्यः", "ता᳓साम्", "ता᳓सु", "त᳓त्", "ता᳓नि"),
    ("यः᳓", "य᳓म्", "ये᳓न", "य᳓स्मै", "य᳓स्मात्", "य᳓स्य", "य᳓स्मिन्", "यौ᳓", "या᳓भ्याम्", "य᳓योः", "ये᳓", "या᳓न्", "यैः᳓", "ये᳓भिः", "ये᳓भ्यः", "ये᳓षाम्", "ये᳓षु", "या᳓", "या᳓म्", "य᳓या", "य᳓स्यै", "य᳓स्याः", "य᳓स्याम्", "याः᳓", "या᳓भिः", "या᳓भ्यः", "या᳓साम्", "या᳓सु", "य᳓त्", "या᳓नि"),
    ("कः᳓", "के᳓न", "क᳓स्मै", "क᳓स्मात्", "क᳓स्य", "क᳓स्मिन्", "कौ᳓", "का᳓भ्याम्", "क᳓योः", "के᳓", "का᳓न्", "कैः᳓", "के᳓भिः", "के᳓भ्यः", "के᳓षाम्", "के᳓षु", "का᳓", "का᳓म्", "क᳓या", "क᳓स्यै", "क᳓स्याः", "क᳓स्याम्", "काः᳓", "का᳓भिः", "का᳓भ्यः", "का᳓साम्", "का᳓सु", "कि᳓म्", "का᳓नि"),
    ("एषः᳓", "एत᳓म्", "एते᳓न", "एत᳓स्मै", "एत᳓स्मात्", "एत᳓स्य", "एत᳓स्मिन्", "एतौ᳓", "एता᳓भ्याम्", "एत᳓योः", "एते᳓", "एता᳓न्", "एतैः᳓", "एते᳓भिः", "एते᳓भ्यः", "एते᳓षाम्", "एते᳓षु", "एषा᳓", "एता᳓म्", "एत᳓या", "एत᳓स्यै", "एत᳓स्याः", "एत᳓स्याम्", "एताः᳓", "एता᳓भिः", "एता᳓भ्यः", "एता᳓साम्", "एता᳓सु", "एत᳓त्", "एता᳓नि"),
    ("अय᳓म्", "इम᳓म्", "अने᳓न", "अस्मै᳓", "अस्मा᳓त्", "अस्य᳓", "अस्मि᳓न्", "इमौ᳓", "आभ्या᳓म्", "अन᳓योः", "इमे᳓", "इमा᳓न्", "एभिः᳓", "एभ्यः᳓", "एषा᳓म्", "एषु᳓", "इय᳓म्", "इमा᳓म्", "अन᳓या", "अस्यै᳓", "अस्याः᳓", "अस्या᳓म्", "इमाः᳓", "आभिः᳓", "आभ्यः᳓", "आसा᳓म्", "आसु᳓", "इद᳓म्", "इमा᳓नि"),
    ("असौ᳓", "अमु᳓म्", "अमु᳓ना", "अमु᳓ष्मै", "अमु᳓ष्मात्", "अमु᳓ष्य", "अमु᳓ष्मिन्", "अमू᳓", "अमी᳓", "अमू᳓न्", "अमी᳓भिः", "अमी᳓भ्यः", "अमी᳓षाम्", "अमी᳓षु", "अमू᳓या", "अमूः᳓", "अमू᳓भिः", "अमू᳓भ्यः", "अमू᳓षाम्", "अमू᳓षु", "अदः᳓", "अमू᳓नि"),
    ("अह᳓म्", "मा᳓म्", "म᳓या", "म᳓ह्यम्", "म᳓त्", "म᳓म", "म᳓यि", "आवा᳓म्", "आवा᳓भ्याम्", "आव᳓योः", "वय᳓म्", "अस्मा᳓न्", "अस्मा᳓भिः", "अस्म᳓भ्यम्", "अस्म᳓त्", "अस्मा᳓कम्", "अस्मा᳓सु", "अस्मे᳓"),
    ("त्व᳓म्", "त्वा᳓म्", "त्व᳓या", "तु᳓भ्यम्", "त्व᳓त्", "त᳓व", "त्व᳓यि", "युवा᳓म्", "युवा᳓भ्याम्", "युव᳓योः", "यूय᳓म्", "युष्मा᳓न्", "युष्मा᳓भिः", "युष्म᳓भ्यम्", "युष्म᳓त्", "युष्मा᳓कम्", "युष्मा᳓सु", "युष्मे᳓"),
  )
  out: dict[tuple[str, tuple[str, ...]], frozenset[tuple[str, tuple[str, ...]]]] = {}
  for grp in groups:
    fset_items: set[tuple[str, tuple[str, ...]]] = set()
    for w in grp:
      km = word_to_key_and_marks(w)
      if km is not None:
        fset_items.add((_canonical_allograph_key(km[0]), km[1]))
    fset = frozenset(fset_items)
    for pair in fset:
      out[pair] = fset
  return out


def _generate_nominal_paradigm(
  stem: str,
  cls: str,
  acc_idx: int,
  *,
  include_fem_a: bool = False,
) -> set[tuple[str, tuple[str, ...]]]:
  """Generate ``(canonical_allograph_key, marks)`` case forms for ``(stem, cls, acc_idx)``."""
  forms: set[tuple[str, tuple[str, ...]]] = set()
  has_retro_trigger = any(ch in stem for ch in ("र", "ष", "ृ", "ॄ"))

  def _add_form(surface: str, a_idx: int, mark_char: str = "U") -> None:
    ak = _canonical_allograph_key(surface)
    n = _n_syls(ak)
    if 0 <= a_idx < n:
      mks = tuple(mark_char if i == a_idx else "" for i in range(n))
      forms.add((ak, mks))

  if cls == "a_fem_oblique":
    if not _ends_inherent_a(stem):
      return forms
    for sf in ("या", "ायै", "ायाः", "ायाम्", "ाभिः", "ाभ्यः", "ासु", "ासाम्"):
      _add_form(stem + sf, acc_idx)
    return forms

  if cls == "a_masc_nom_acc":
    if not _ends_inherent_a(stem):
      return forms
    for sf in ("ः", "म्", "ान्"):
      _add_form(stem + sf, acc_idx)
    return forms

  if cls == "a_fem_nom_acc":
    if not _ends_inherent_a(stem):
      return forms
    for sf in ("ा", "ाम्"):
      _add_form(stem + sf, acc_idx)
    return forms

  if cls == "i_core":
    if not stem.endswith("ि") or len(stem) < 2:
      return forms
    base = stem[:-1]
    for sf in ("िः", "िम्", "िना", "िणा", "ये", "ेः", "यः", "ीन्", "िभिः", "िभ्यः", "िषु"):
      _add_form(base + sf, acc_idx)
    return forms

  if cls == "a":
    K = _n_syls(stem)
    if K < 1 or not _ends_inherent_a(stem):
      return forms
    is_oxy = acc_idx == K - 1
    na = "ण" if has_retro_trigger else "न"
    sufs = [
      "ः", "म्", f"े{na}", "ाय", "ात्", "स्य", "े",
      "स्मै", "स्मात्", "स्मिन्",
      "ौ", "ाभ्याम्", "योः",
      "ाः", "ासः", "ान्", "ानि", f"ा{na}ि", "ैः", "ेभिः", "ेभ्यः",
      f"ा{na}ाम्", "ानाम्", "ेषाम्", "ेषु",
    ]
    if include_fem_a:
      sufs.extend(["ा", "ाम्", "या", "ायै", "स्यै", "ायाः", "स्याः", "ायाम्", "स्याम्", "ाभिः", "ाभ्यः", "ासाम्", "ासु"])
    for sf in sufs:
      w = stem + sf
      _add_form(w, acc_idx)
      if is_oxy and sf in (f"ा{na}ाम्", "ानाम्", "ासाम्", "ेषाम्"):
        _add_form(w, K)

  elif cls == "i":
    if not stem.endswith("ि") or len(stem) < 2:
      return forms
    base = stem[:-1]
    K = _n_syls(stem)
    is_oxy = acc_idx == K - 1
    na = "ण" if has_retro_trigger else "न"
    for sf in [
      "िः", "िम्", "ि", f"ि{na}ा", "िना", "ये", "ेः", "ौ", "्योः",
      "ी", "िभ्याम्",
      "यः", "ीन्", "ीः", "ीनि", f"ी{na}ि", "िभिः", "िभ्यः",
      f"ी{na}ाम्", "ीनाम्", "िषु",
      "्या", "्यै", "्याः", "्याम्",
    ]:
      w = base + sf
      if sf.startswith("्य"):
        if is_oxy and K >= 2:
          _add_form(w, K - 2, "S")
          _add_form(w, K - 2, "U")
        elif not is_oxy:
          _add_form(w, acc_idx)
      else:
        _add_form(w, acc_idx)
        if is_oxy and sf in (f"ी{na}ाम्", "ीनाम्"):
          _add_form(w, K)

  elif cls == "ii":
    if not stem.endswith("ी") or len(stem) < 2:
      return forms
    base = stem[:-1]
    K = _n_syls(stem)
    is_oxy = acc_idx == K - 1
    na = "ण" if has_retro_trigger else "न"
    for sf in [
      "ी", "ीः", "ीम्", "्या", "्यै", "्ये", "्याः", "्याम्",
      "्यौ", "ीभ्याम्", "्योः",
      "्यः", "ीभिः", "ीभ्यः", f"ी{na}ाम्", "ीनाम्", "ीषु",
    ]:
      w = base + sf
      if sf.startswith("्य"):
        if is_oxy and K >= 2:
          _add_form(w, K - 2, "S")
          _add_form(w, K - 2, "U")
        elif not is_oxy:
          _add_form(w, acc_idx)
      else:
        _add_form(w, acc_idx)
        if is_oxy and sf in (f"ी{na}ाम्", "ीनाम्"):
          _add_form(w, K)

  elif cls == "u":
    if not stem.endswith("ु") or len(stem) < 2:
      return forms
    base = stem[:-1]
    K = _n_syls(stem)
    is_oxy = acc_idx == K - 1
    na = "ण" if has_retro_trigger else "न"
    for sf in [
      "ुः", "ुम्", "ु", f"ु{na}ा", "ुना", "वे", "ोः", "ौ", "्वोः",
      "ू", "ुभ्याम्",
      "वः", "ून्", "ूः", "ूनि", f"ू{na}ि", "ुभिः", "ुभ्यः",
      f"ू{na}ाम्", "ूनाम्", "ुषु",
      "्वा", "्वै", "्वाः", "्वाम्",
    ]:
      w = base + sf
      if sf.startswith("्व"):
        if is_oxy and K >= 2:
          _add_form(w, K - 2, "S")
          _add_form(w, K - 2, "U")
        elif not is_oxy:
          _add_form(w, acc_idx)
      else:
        _add_form(w, acc_idx)
        if is_oxy and sf in (f"ू{na}ाम्", "ूनाम्"):
          _add_form(w, K)

  elif cls == "uu":
    if not stem.endswith("ू") or len(stem) < 2:
      return forms
    base = stem[:-1]
    K = _n_syls(stem)
    is_oxy = acc_idx == K - 1
    na = "ण" if has_retro_trigger else "न"
    for sf in [
      "ूः", "ूम्", "्वा", "्वै", "्वे", "्वाः", "्वाम्",
      "्वौ", "ूभ्याम्", "्वोः",
      "्वः", "ूभिः", "ूभ्यः", f"ू{na}ाम्", "ूनाम्", "ूषु",
    ]:
      w = base + sf
      if sf.startswith("्व"):
        if is_oxy and K >= 2:
          _add_form(w, K - 2, "S")
          _add_form(w, K - 2, "U")
        elif not is_oxy:
          _add_form(w, acc_idx)
      else:
        _add_form(w, acc_idx)
        if is_oxy and sf in (f"ू{na}ाम्", "ूनाम्"):
          _add_form(w, K)

  elif cls == "R":
    if not stem.endswith("ृ") or len(stem) < 2:
      return forms
    base = stem[:-1]
    K = _n_syls(stem)
    is_oxy = acc_idx == K - 1
    for sf in [
      "ा", "रम्", "ारम्", "्रा", "्रे", "ुः", "रि", "ारि",
      "रौ", "ारौ", "ृभ्याम्", "्रोः",
      "रः", "ारः", "ॄन्", "ॄः", "ृभिः", "ृभ्यः", "ॄणाम्", "ॄनाम्", "ृषु",
    ]:
      w = base + sf
      _add_form(w, acc_idx)
      if is_oxy and sf in ("ॄणाम्", "ॄनाम्"):
        _add_form(w, K)

  elif cls == "an":
    if not stem.endswith("न्") or len(stem) < 4:
      return forms
    base_a = stem[:-2]
    K = _n_syls(base_a)
    is_oxy = acc_idx == K - 1
    na = "ण" if has_retro_trigger else "न"
    for sf in [
      "ा", "", f"ा{na}म्", "ानम्", f"{na}म्", "नम्",
      f"{na}ा", "ना", f"{na}े", "ने", f"{na}ः", "नः", f"{na}ि", "नि", f"ा{na}ि", "ानि",
      f"ा{na}ौ", "ानौ", f"{na}ौ", "नौ", "भ्याम्", f"{na}ोः", "नोः",
      f"ा{na}ः", "ानः", "भिः", "भ्यः", f"{na}ाम्", "नाम्", "सु",
    ]:
      _add_form(base_a + sf, acc_idx)
    if len(base_a) >= 2:
      sync_base = base_a + "्"
      for sf in [f"{na}ा", "ना", f"{na}े", "ने", f"{na}ः", "नः", f"{na}ि", "नि", f"{na}ोः", "नोः", f"{na}ाम्", "नाम्"]:
        w = sync_base + sf
        if is_oxy and K >= 2:
          _add_form(w, K - 1)
        elif not is_oxy:
          _add_form(w, acc_idx)

  elif cls == "in":
    if not stem.endswith("िन्") or len(stem) < 4:
      return forms
    base = stem[:-3]
    na = "ण" if has_retro_trigger else "न"
    for sf in [
      "ी", "ि", f"ि{na}म्", "िनम्", f"ि{na}ा", "िना", f"ि{na}े", "िने",
      f"ि{na}ः", "िनः", f"ि{na}ि", "िनि",
      f"ि{na}ौ", "िनौ", "िभ्याम्", f"ि{na}ोः", "िनोः",
      f"ी{na}ि", "ीनि", "िभिः", "िभ्यः", f"ि{na}ाम्", "िनाम्", "िषु",
    ]:
      _add_form(base + sf, acc_idx)

  elif cls == "as":
    if not stem.endswith("स्") or len(stem) < 4:
      return forms
    base = stem[:-2]
    for sf in [
      "ः", "सम्", "ाम्", "सा", "से", "सः", "सि",
      "सी", "सौ", "आसौ", "ोभ्याम्", "सोः",
      "ांसि", "ाँसि", "आसः", "ोभिः", "ोभ्यः", "साम्", "ःसु", "स्सु",
    ]:
      if sf.startswith("आ"):
        _add_form(base + "ा" + sf[1:], acc_idx)
      else:
        _add_form(base + sf, acc_idx)

  elif cls in ("is", "us"):
    vow = "ि" if cls == "is" else "ु"
    lvow = "ीं" if cls == "is" else "ूं"
    base = stem[:-3]
    for sf in [
      f"{vow}ः", f"{vow}षा", f"{vow}षे", f"{vow}षः", f"{vow}षि",
      f"{vow}षी", f"{vow}र्भ्याम्", f"{vow}षोः",
      f"{lvow}षि", f"{vow}र्भिः", f"{vow}र्भ्यः", f"{vow}षाम्", f"{vow}ःषु", f"{vow}ष्षु",
    ]:
      _add_form(base + sf, acc_idx)

  elif cls == "mat":
    if not stem.endswith("त्") or len(stem) < 3:
      return forms
    base = stem[:-2]
    is_mahat = base.endswith("मह")
    nt = "ान्त" if is_mahat else "न्त"
    nm = "ान्" if is_mahat else ("ान्" if base.endswith(("म", "व")) else "न्")
    for sf in [
      nm, "न्", "त्", f"{nt}म्", "ता", "ते", "तः", "ति",
      f"{nt}ौ", "ती", "द्भ्याम्", "तोः",
      f"{nt}ः", "ान्ति" if is_mahat else "न्ति", "द्भिः", "द्भ्यः", "ताम्", "त्सु",
    ]:
      _add_form(base + sf, acc_idx)

  elif cls == "cons":
    if not stem.endswith("्") or len(stem) < 3:
      return forms
    K = _n_syls(stem)
    c_base = stem[:-1]
    is_mono = K == 1
    last_c = c_base[-1]
    if last_c in ("त", "थ", "द", "ध"):
      p_d, p_s = c_base[:-1] + "द्", c_base[:-1] + "त्"
    elif last_c in ("च", "ज"):
      p_d, p_s = c_base[:-1] + "ग्", c_base[:-1] + "क्"
    elif last_c in ("श", "ष", "ह"):
      p_d, p_s = c_base[:-1] + "ड्", c_base[:-1] + "ट्"
    elif last_c in ("प", "भ"):
      p_d, p_s = c_base[:-1] + "ब्", c_base[:-1] + "प्"
    else:
      p_d, p_s = c_base + "्", c_base + "्"

    _add_form(p_s, acc_idx)
    for sf, is_weak in [
      ("म्", False), ("ौ", False), ("ः", False),
      ("ा", True), ("े", True), ("ि", True), ("ोः", True), ("ाम्", True),
    ]:
      w = c_base + sf
      _add_form(w, acc_idx)
      if is_mono and is_weak:
        _add_form(w, 1)
    for sf in ("भ्याम्", "भिः", "भ्यः"):
      w = p_d + sf
      _add_form(w, acc_idx)
      if is_mono:
        _add_form(w, 1)
    w_su = (p_s[:-2] + "क्षु") if p_s.endswith("क्") else (p_s + "सु")
    _add_form(w_su, acc_idx)
    if is_mono:
      _add_form(w_su, 1)

  return forms


def _infer_candidate_stems(ak: str, marks: tuple[str, ...]) -> list[tuple[str, str, int]]:
  """Infer candidate ``(stem, cls, acc_idx)`` triples from ``(ak, marks)``."""
  acc_indices = [i for i, m in enumerate(marks) if m]
  if len(acc_indices) != 1:
    return []
  a_idx = acc_indices[0]
  cands: list[tuple[str, str, int]] = []

  def _try(stem: str, cls: str, stem_a: int) -> None:
    if len(stem) < 2:
      return
    ns = _n_syls(stem)
    if ns < 1 or not (0 <= stem_a < ns):
      return
    tup = (stem, cls, stem_a)
    if tup not in cands:
      cands.append(tup)

  for sf in (
    "िणम्", "िनम्", "िणा", "िना", "िणे", "िने", "िणः", "िनः", "िणि", "िनि",
    "िणौ", "िनौ", "िणोः", "िनोः", "िणाम्", "िनाम्", "ीणि", "ीनि", "िभ्याम्", "िभिः", "िभ्यः", "िषु", "ी",
  ):
    if ak.endswith(sf) and len(ak) > len(sf) + 1 and _ends_inherent_a(ak[: -len(sf)]):
      st = ak[: -len(sf)] + "िन्"
      if a_idx < _n_syls(st):
        _try(st, "in", a_idx)

  for sf in (
    "मान्", "वान्", "मन्तम्", "वन्तम्", "मन्तौ", "वन्तौ", "मन्तः", "वन्तः", "मन्ति", "वन्ति",
    "मता", "वता", "मते", "वते", "मतः", "वतः", "मति", "वति",
    "मद्भिः", "वद्भिः", "मद्भ्यः", "वद्भ्यः", "मताम्", "वताम्", "मत्सु", "वत्सु", "मत्", "वत्",
  ):
    if ak.endswith(sf) and len(ak) > len(sf):
      base = ak[: -len(sf)]
      if _ends_inherent_a(base) or base.endswith(("ि", "ु", "ी", "ू", "ृ")):
        st = base + sf[0] + "त्"
        if a_idx < _n_syls(st):
          _try(st, "mat", a_idx)

  for sf in ("ांसि", "ाँसि", "ोभ्याम्", "ोभिः", "ोभ्यः", "स्सु", "ःसु"):
    if ak.endswith(sf) and len(ak) > len(sf) and _ends_inherent_a(ak[: -len(sf)]):
      st = ak[: -len(sf)] + "स्"
      if a_idx < _n_syls(st):
        _try(st, "as", a_idx)
  for sf in ("सा", "से", "सः", "सि", "सोः", "साम्"):
    if ak.endswith(sf) and len(ak) > len(sf) + 1 and _ends_inherent_a(ak[: -len(sf)]):
      st = ak[: -len(sf)] + "स्"
      if a_idx < _n_syls(st):
        _try(st, "as", a_idx)
  for vow, cls_s in (("ि", "is"), ("ु", "us")):
    for sf in (
      f"{vow}षा", f"{vow}षे", f"{vow}षः", f"{vow}षि", f"{vow}षोः", f"{vow}षाम्",
      f"{vow}र्भिः", f"{vow}र्भ्याम्", f"{vow}र्भ्यः", f"{vow}ः",
    ):
      if ak.endswith(sf) and len(ak) > len(sf) and _ends_inherent_a(ak[: -len(sf)]):
        st = ak[: -len(sf)] + vow + "स्"
        if a_idx < _n_syls(st):
          _try(st, cls_s, a_idx)

  for sf in (
    "ानम्", "ाणम्", "ानौ", "ाणौ", "ानः", "ाणः",
    "णा", "णे", "णः", "णि", "णोः", "णाम्",
    "ना", "ने", "नः", "नि", "नोः", "नाम्", "ाणि", "ानि",
  ):
    if ak.endswith(sf) and len(ak) > len(sf) + 1 and _ends_inherent_a(ak[: -len(sf)]):
      st = ak[: -len(sf)] + "न्"
      if a_idx < _n_syls(st):
        _try(st, "an", a_idx)
  if _ends_inherent_a(ak) and _n_syls(ak) >= 2:
    _try(ak + "न्", "an", a_idx)
  if ak.endswith("ा") and _ends_inherent_a(ak[:-1]) and _n_syls(ak[:-1]) >= 2:
    _try(ak[:-1] + "न्", "an", a_idx)

  for sf in ("ीः", "ीम्", "ीभ्याम्", "ीभिः", "ीभ्यः", "ीनाम्", "ीणाम्", "ीषु", "ी"):
    if ak.endswith(sf) and len(ak) > len(sf) and _ends_inherent_a(ak[: -len(sf)]):
      st = ak[: -len(sf)] + "ी"
      K = _n_syls(st)
      if a_idx < K:
        _try(st, "ii", a_idx)
        _try(ak[: -len(sf)] + "ि", "i", a_idx)
      elif a_idx == K and sf in ("ीनाम्", "ीणाम्"):
        _try(st, "ii", K - 1)
        _try(ak[: -len(sf)] + "ि", "i", K - 1)
  for sf in ("्या", "्यै", "्याः", "्याम्", "्यौ", "्योः"):
    if ak.endswith(sf) and len(ak) > len(sf) and _ends_inherent_a(ak[: -len(sf)]):
      st_ii = ak[: -len(sf)] + "ी"
      K = _n_syls(st_ii)
      if marks[a_idx] == "S" or a_idx == K - 2:
        _try(st_ii, "ii", K - 1)
        _try(ak[: -len(sf)] + "ि", "i", K - 1)
      if a_idx < K - 1:
        _try(st_ii, "ii", a_idx)
        _try(ak[: -len(sf)] + "ि", "i", a_idx)

  for sf in ("िः", "िम्", "िना", "िणा", "ये", "ेः", "ौ", "ा", "यः", "ीन्", "िभ्याम्", "िभिः", "िभ्यः", "िषु", "ि"):
    if ak.endswith(sf) and len(ak) > len(sf) and _ends_inherent_a(ak[: -len(sf)]):
      st = ak[: -len(sf)] + "ि"
      if a_idx < _n_syls(st):
        _try(st, "i", a_idx)

  for sf in ("ुः", "ुम्", "ुना", "ुणा", "वे", "ोः", "ौ", "वः", "ून्", "ुभ्याम्", "ुभिः", "ुभ्यः", "ुषु", "ूनाम्", "ूणाम्", "ु", "ू"):
    if ak.endswith(sf) and len(ak) > len(sf) and _ends_inherent_a(ak[: -len(sf)]):
      st = ak[: -len(sf)] + "ु"
      K = _n_syls(st)
      if a_idx < K:
        _try(st, "u", a_idx)
      elif a_idx == K and sf in ("ूनाम्", "ूणाम्"):
        _try(st, "u", K - 1)
  for sf in ("ूः", "ूम्", "ूभ्याम्", "ूभिः", "ूभ्यः", "ूषु"):
    if ak.endswith(sf) and len(ak) > len(sf) and _ends_inherent_a(ak[: -len(sf)]):
      st = ak[: -len(sf)] + "ू"
      if a_idx < _n_syls(st):
        _try(st, "uu", a_idx)
        _try(ak[: -len(sf)] + "ु", "u", a_idx)

  for sf in ("ारम्", "रम्", "ारः", "रः", "ारौ", "रौ", "्रा", "्रे", "्रोः", "ुः", "ृभिः", "ृभ्याम्", "ृभ्यः", "ॄणाम्", "ृषु"):
    if ak.endswith(sf) and len(ak) > len(sf) and _ends_inherent_a(ak[: -len(sf)]):
      st = ak[: -len(sf)] + "ृ"
      K = _n_syls(st)
      if a_idx < K:
        _try(st, "R", a_idx)
      elif a_idx == K and sf == "ॄणाम्":
        _try(st, "R", K - 1)
  if ak.endswith("ता") and len(ak) >= 4:
    st_r = ak[:-1] + "ृ"
    if a_idx < _n_syls(st_r):
      _try(st_r, "R", a_idx)

  for sf in (
    "ाभ्याम्", "ेभिः", "ेभ्यः", "ाभिः", "ाभ्यः", "ानाम्", "ाणाम्", "ेषाम्", "ासाम्",
    "ायाः", "स्याः", "ायाम्", "स्याम्", "ायै", "स्यै", "स्मात्", "स्मिन्", "स्मै", "ासः",
    "ानि", "ाणि", "ेन", "ेण", "ाय", "ात्", "स्य", "योः", "ेषु", "ासु", "या",
    "ाः", "ान्", "ैः", "ाम्", "ौ", "े", "ा", "ः", "म्",
  ):
    if ak.endswith(sf) and len(ak) > len(sf):
      base = ak[: -len(sf)]
      if _ends_inherent_a(base) and _n_syls(base) >= 1:
        if _n_syls(base) == 1 and len(base) < 2:
          continue
        K = _n_syls(base)
        if a_idx < K:
          _try(base, "a", a_idx)
        elif a_idx == K and sf in ("ानाम्", "ाणाम्", "ेषाम्", "ासाम्"):
          _try(base, "a", K - 1)
  if _ends_inherent_a(ak) and _n_syls(ak) >= 2:
    _try(ak, "a", a_idx)
  if ak.endswith("ः") and _ends_inherent_a(ak[:-1]) and _n_syls(ak[:-1]) >= 2:
    _try(ak[:-1] + "स्", "as", a_idx)

  if ak.endswith("्") and _n_syls(ak) >= 2:
    _try(ak, "cons", a_idx)
  for sf in ("द्भिः", "द्भ्यः", "द्भ्याम्"):
    if ak.endswith(sf) and len(ak) > len(sf) and _ends_inherent_a(ak[: -len(sf)]):
      for c_end in ("त्", "द्", "ध्"):
        _try(ak[: -len(sf)] + c_end, "cons", a_idx)
  for sf in ("म्", "ा", "े", "ः", "ि", "ौ", "ोः", "ाम्"):
    if ak.endswith(sf) and len(ak) > len(sf) + 1 and _ends_inherent_a(ak[: -len(sf)]):
      c_cand = ak[: -len(sf)]
      if c_cand[-1] in ("च", "ज", "त", "द", "ध", "श", "ष", "ह", "प", "भ"):
        st = c_cand + "्"
        if a_idx < _n_syls(st):
          _try(st, "cons", a_idx)

  return cands


def _split_top_level_semicolons(prov: str) -> list[str]:
  """Split ``prov`` on ``;`` only at parenthesis depth 0."""
  parts: list[str] = []
  depth = 0
  start = 0
  for idx, ch in enumerate(prov):
    if ch == "(":
      depth += 1
    elif ch == ")" and depth > 0:
      depth -= 1
    elif ch == ";" and depth == 0:
      parts.append(prov[start:idx])
      start = idx + 1
  parts.append(prov[start:])
  return parts


def _is_sanskrit_example_word(tok: str) -> bool:
  clean = tok.strip(".,;:?!()[]*\"'—–- ")
  if not clean or not _DEVANAGARI_RE.search(clean):
    return False
  if re.search(r"[०-९0-9]", clean):
    return False
  bare = re.sub(r"[^\u0900-\u097f]", "", accent.strip_accents(clean)).rstrip("॰")
  if not bare or bare in _METALANGUAGE_BARE:
    return False
  return True


_NESTED_MEMBER_PAREN_RE = re.compile(
  r"([\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\u0951\u0952\-]+)(\s*\([^()]*\*(?:"
  + _CORPUS_TAG_PAT
  + r")\*[^()]*\))"
)

_PRECEDING_WORD_TAG_GROUP_RE = re.compile(
  r"([\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\u0951\u0952\-]+)"
  r"(\s+)(\*(?:"
  + _CORPUS_TAG_PAT
  + r")\*"
  + _COUNT_OPT_PAT
  + r"(?:\s*,\s*\*(?:"
  + _CORPUS_TAG_PAT
  + r")\*"
  + _COUNT_OPT_PAT
  + r")*)"
)

_TAG_GROUP_WITH_EXAMPLE_RE = re.compile(
  r"(\*(?:"
  + _CORPUS_TAG_PAT
  + r")\*"
  + _COUNT_OPT_PAT
  + r"(?:\s*,\s*\*(?:"
  + _CORPUS_TAG_PAT
  + r")\*"
  + _COUNT_OPT_PAT
  + r")*)"
  r"(\s+(?:[०-९\d]+(?:\.[०-९\d]+)+\s+)?)"
  r"([\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\u0951\u0952\-]+)"
)


def _enrich_tag_list_for_word(
  existing_tags: Sequence[str],
  target_word: str,
  counter: VedicCorpusCounter,
  unresolved: list[tuple[str, str]],
  *,
  allow_stem: bool,
  enrich_major: bool,
  zero_exact_tags: frozenset[str] = frozenset(),
  major_corpora: Sequence[str] = MAJOR_AUTO_CORPORA,
  skip_tags: frozenset[str] = frozenset(),
) -> list[str]:
  """Format ``existing_tags`` + (when ``enrich_major and allow_stem``) any other ``major_corpora`` with ``N > 0``."""
  seen: set[str] = set()
  formatted_by_tag: dict[str, str] = {}
  for tg in existing_tags:
    if tg in seen:
      continue
    seen.add(tg)
    if tg in skip_tags:
      formatted_by_tag[tg] = f"*{tg}*"
      continue
    m_c, n_c = counter.count_with_stem(target_word, tg, allow_stem=allow_stem)
    fmt = format_corpus_count(tg, m_c, n_c)
    if fmt is not None:
      formatted_by_tag[tg] = fmt
    elif tg in zero_exact_tags:
      # Drop stale `-0/N` auto-tags that evaluate to (0, 0)
      continue
    else:
      unresolved.append((tg, target_word))
      formatted_by_tag[tg] = f"*{tg}*"

  if enrich_major and allow_stem:
    for cp in major_corpora:
      if cp in seen or _CORPUS_ALIASES.get(cp) in seen or cp in skip_tags:
        continue
      m_c, n_c = counter.count_with_stem(target_word, cp, allow_stem=True)
      fmt = format_corpus_count(cp, m_c, n_c)
      if fmt is not None:
        seen.add(cp)
        formatted_by_tag[cp] = fmt

  if len(formatted_by_tag) != len(existing_tags):
    ordered = [formatted_by_tag[cp] for cp in CORPUS_TAGS if cp in formatted_by_tag]
    for tg in existing_tags:
      if tg not in CORPUS_TAG_SET and tg in formatted_by_tag:
        ordered.append(formatted_by_tag[tg])
    return ordered
  return [formatted_by_tag[tg] for tg in existing_tags if tg in formatted_by_tag]


def _annotate_clause(
  clause: str,
  default_ref: str,
  is_alt_clause: bool,
  counter: VedicCorpusCounter,
  unresolved: list[tuple[str, str]],
  *,
  allow_stem_default: bool = True,
  enrich_major_corpora: bool = True,
  major_corpora: Sequence[str] = MAJOR_AUTO_CORPORA,
  skip_tags: frozenset[str] = frozenset(),
) -> str:
  clause = re.sub(
    r"\*(" + _CORPUS_TAG_PAT + r")\*" + _COUNT_OPT_PAT + r"(\s+[०-९\d.]+),\s*\*\1\*\s*[०-९\d]+\s*वारम्",
    r"*\1*\2",
    clause,
  )

  protected_spans: list[tuple[int, int]] = []
  replacements: list[tuple[int, int, str]] = []
  default_paradigm = counter.paradigm_forms(default_ref) if allow_stem_default else frozenset()
  same_stem_covered_tags: set[str] = set()
  has_pattern_b = False

  def _fmt_tag(tag: str, target_word: str, *, allow_stem: bool) -> str:
    if tag in skip_tags:
      return f"*{tag}*"
    m_c, n_c = counter.count_with_stem(target_word, tag, allow_stem=allow_stem)
    fmt = format_corpus_count(tag, m_c, n_c)
    if fmt is not None:
      return fmt
    unresolved.append((tag, target_word))
    return f"*{tag}*"

  def _is_same_paradigm_word(w_cand: str) -> bool:
    if not default_paradigm:
      return False
    km_c = word_to_key_and_marks(w_cand)
    if km_c is None:
      return False
    return (_canonical_allograph_key(km_c[0]), km_c[1]) in default_paradigm

  # 1. Pattern A: Nested `WORD (*TS*, *RV*)`
  for m in _NESTED_MEMBER_PAREN_RE.finditer(clause):
    w_tok, paren_grp = m.group(1), m.group(2)
    if not _is_sanskrit_example_word(w_tok):
      continue
    w_allow = is_declinable_nominal(w_tok)
    t_matches = list(_TAG_TOKEN_RE.finditer(paren_grp))
    if _is_same_paradigm_word(w_tok):
      same_stem_covered_tags.update(tm.group(1) for tm in t_matches)
    inner_strip = paren_grp.strip()
    inner_body = inner_strip[1:-1].strip() if inner_strip.startswith("(") and inner_strip.endswith(")") else ""
    pure_list = bool(inner_body) and all(
      re.fullmatch(rf"\*(?:{_CORPUS_TAG_PAT})\*{_COUNT_OPT_PAT}|\*(?:MW|Macdonell|Lanman)\*", seg.strip())
      for seg in inner_body.split(",")
    )
    if pure_list and t_matches:
      ex_tags = [tm.group(1) for tm in t_matches]
      z_tags = frozenset(tm.group(1) for tm in t_matches if tm.group(2) == "0" and tm.group(3) is not None)
      lex_tags = [
        seg.strip()
        for seg in inner_body.split(",")
        if re.fullmatch(r"\*(?:MW|Macdonell|Lanman)\*", seg.strip())
      ]
      enriched = _enrich_tag_list_for_word(
        ex_tags,
        w_tok,
        counter,
        unresolved,
        allow_stem=w_allow,
        enrich_major=enrich_major_corpora,
        zero_exact_tags=z_tags,
        major_corpora=major_corpora,
        skip_tags=skip_tags,
      )
      lead_ws = paren_grp[: len(paren_grp) - len(paren_grp.lstrip())]
      new_paren = f"{lead_ws}({', '.join(enriched + lex_tags)})"
    else:
      new_paren = _TAG_TOKEN_RE.sub(lambda tm: _fmt_tag(tm.group(1), w_tok, allow_stem=w_allow), paren_grp)
    s, e = m.start(2), m.end(2)
    protected_spans.append((s, e))
    replacements.append((s, e, new_paren))

  # 1b. Pattern A2: `ACCENTED_WORD *TS*, *RV*`
  for m in _PRECEDING_WORD_TAG_GROUP_RE.finditer(clause):
    s_word, s, e = m.start(1), m.start(3), m.end(3)
    if any(not (e <= ps or s >= pe) for ps, pe in protected_spans):
      continue
    w_tok = m.group(1)
    has_explicit_acc = any(ch in w_tok for ch in (US_UDATTA, US_SVARITA, "\u0951", "\u0952"))
    if not (has_explicit_acc and _is_sanskrit_example_word(w_tok)):
      continue
    after_tags = clause[e : e + 40]
    m_after = re.match(
      r"^\s+(?:[०-९\d]+(?:\.[०-९\d]+)+\s+)?([\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\u0951\u0952\-]+)",
      after_tags,
    )
    if (
      m_after
      and any(ch in m_after.group(1) for ch in (US_UDATTA, US_SVARITA, "\u0951", "\u0952"))
      and _is_sanskrit_example_word(m_after.group(1))
    ):
      continue
    t_matches = list(_TAG_TOKEN_RE.finditer(m.group(3)))
    ex_tags = [tm.group(1) for tm in t_matches]
    before_w = clause[:s_word].strip()
    if (
      not is_alt_clause
      and "-" not in default_ref
      and not before_w
      and _is_same_paradigm_word(w_tok)
      and enrich_major_corpora
    ):
      promoted = _enrich_tag_list_for_word(
        ex_tags,
        default_ref,
        counter,
        unresolved,
        allow_stem=True,
        enrich_major=True,
        major_corpora=major_corpora,
        skip_tags=skip_tags,
      )
      same_stem_covered_tags.update(CORPUS_TAGS)
      protected_spans.append((s_word, e))
      replacements.append((s_word, e, ", ".join(promoted)))
      continue

    w_allow = is_declinable_nominal(w_tok)
    if _is_same_paradigm_word(w_tok):
      same_stem_covered_tags.update(ex_tags)
    z_tags = frozenset(tm.group(1) for tm in t_matches if tm.group(2) == "0" and tm.group(3) is not None)
    enriched = _enrich_tag_list_for_word(
      ex_tags,
      w_tok,
      counter,
      unresolved,
      allow_stem=w_allow,
      enrich_major=enrich_major_corpora,
      zero_exact_tags=z_tags,
      major_corpora=major_corpora,
      skip_tags=skip_tags,
    )
    protected_spans.append((s, e))
    replacements.append((s, e, ", ".join(enriched)))

  # 2. Pattern B: `*TS*, *RV* १०.१९०.२ अहोरा॒त्राणि॑` or `*AV*, *RV* वे᳓दः`
  for m in _TAG_GROUP_WITH_EXAMPLE_RE.finditer(clause):
    s, e = m.start(1), m.end(1)
    if any(not (e <= ps or s >= pe) for ps, pe in protected_spans):
      continue
    w_ex = m.group(3)
    has_explicit_acc = any(ch in w_ex for ch in (US_UDATTA, US_SVARITA, "\u0951", "\u0952"))
    if not (has_explicit_acc and _is_sanskrit_example_word(w_ex)):
      continue
    tag_matches = list(_TAG_TOKEN_RE.finditer(m.group(1)))
    if not tag_matches:
      continue
    has_pattern_b = True
    w_ex_allow = is_declinable_nominal(w_ex)
    ex_same_stem = _is_same_paradigm_word(w_ex)
    kept_b_parts: list[str] = []
    for idx_t, tm in enumerate(tag_matches):
      tname = tm.group(1)
      was_zero_slash = tm.group(2) == "0" and tm.group(3) is not None
      if ex_same_stem:
        same_stem_covered_tags.add(tname)
      is_last = idx_t == len(tag_matches) - 1
      if is_last:
        kept_b_parts.append(_fmt_tag(tname, w_ex, allow_stem=w_ex_allow))
      elif tname in skip_tags:
        kept_b_parts.append(f"*{tname}*")
      else:
        m_def, n_def = counter.count_with_stem(default_ref, tname, allow_stem=allow_stem_default)
        if m_def > 0 or (ex_same_stem and n_def > 0):
          same_stem_covered_tags.add(tname)
          kept_b_parts.append(format_corpus_count(tname, m_def, n_def) or f"*{tname}*")
        else:
          m_ex, n_ex = counter.count_with_stem(w_ex, tname, allow_stem=w_ex_allow)
          fmt_ex = format_corpus_count(tname, m_ex, n_ex)
          if fmt_ex is not None:
            kept_b_parts.append(fmt_ex)
          elif not was_zero_slash:
            unresolved.append((tname, w_ex))
            kept_b_parts.append(f"*{tname}*")
    protected_spans.append((s, e))
    replacements.append((s, e, ", ".join(kept_b_parts)))

  # 3. Top-level `*TAG*` tokens in this clause
  fallback_word = default_ref
  fallback_allow_stem = allow_stem_default
  if is_alt_clause:
    def_bare = _normalize_lookup_key(default_ref)
    def_km = word_to_key_and_marks(default_ref)
    for tok in re.findall(r"[\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\u0951\u0952\-]+", clause):
      if any(ch in tok for ch in (US_UDATTA, US_SVARITA, "\u0951", "\u0952")) and _is_sanskrit_example_word(tok):
        t_km = word_to_key_and_marks(tok)
        if t_km is not None and t_km != def_km:
          fallback_word = tok
          fallback_allow_stem = is_declinable_nominal(tok)
          if _normalize_lookup_key(tok) == def_bare:
            break

  top_tms = [
    tm
    for tm in _TAG_TOKEN_RE.finditer(clause)
    if not any(not (tm.end() <= ps or tm.start() >= pe) for ps, pe in protected_spans)
  ]
  top_tag_names = [tm.group(1) for tm in top_tms]

  can_merge_top_block = False
  if top_tms and not is_alt_clause and enrich_major_corpora and fallback_allow_stem:
    first_s, last_e = top_tms[0].start(), top_tms[-1].end()
    span_txt = clause[first_s:last_e]
    after_last = clause[last_e : last_e + 15]
    has_trailing_sec_num = bool(re.match(r"^\s+[०-९0-9]+\.[०-९0-9]", after_last))
    if not has_trailing_sec_num and re.fullmatch(
      rf"\*(?:{_CORPUS_TAG_PAT})\*{_COUNT_OPT_PAT}(?:\s*,\s*\*(?:{_CORPUS_TAG_PAT})\*{_COUNT_OPT_PAT})*",
      span_txt,
    ):
      can_merge_top_block = True

  if can_merge_top_block:
    zero_exact_top = frozenset(
      tm.group(1) for tm in top_tms if tm.group(2) == "0" and tm.group(3) is not None
    )
    merged_tags = _enrich_tag_list_for_word(
      top_tag_names,
      fallback_word,
      counter,
      unresolved,
      allow_stem=True,
      enrich_major=True,
      zero_exact_tags=zero_exact_top,
      major_corpora=major_corpora,
      skip_tags=skip_tags,
    )
    kept_merged: list[str] = []
    for fmt_item in merged_tags:
      m_t = _TAG_TOKEN_RE.match(fmt_item)
      t_nm = m_t.group(1) if m_t else ""
      if t_nm not in top_tag_names and t_nm in same_stem_covered_tags:
        continue
      kept_merged.append(fmt_item)
    if kept_merged:
      replacements.append((top_tms[0].start(), top_tms[-1].end(), ", ".join(kept_merged)))
    else:
      # All top-level tags were stale `-0/N` tags that evaluated to (0, 0); also consume trailing `, `
      end_del = top_tms[-1].end()
      m_comma = re.match(r"^\s*,\s*", clause[end_del:])
      if m_comma:
        end_del += m_comma.end()
      replacements.append((top_tms[0].start(), end_del, ""))
  else:
    for idx_tm, tm in enumerate(top_tms):
      s, e = tm.start(), tm.end()
      if tm.group(1) in skip_tags:
        rep_str = f"*{tm.group(1)}*"
      else:
        was_z = tm.group(2) == "0" and tm.group(3) is not None
        m_cur, n_cur = counter.count_with_stem(fallback_word, tm.group(1), allow_stem=fallback_allow_stem)
        fmt_cur = format_corpus_count(tm.group(1), m_cur, n_cur)
        if fmt_cur is None and was_z:
          s_del = s
          m_pre_comma = re.search(r",\s*$", clause[:s])
          if m_pre_comma:
            s_del = m_pre_comma.start()
          replacements.append((s_del, e, ""))
          continue
        rep_str = fmt_cur if fmt_cur is not None else _fmt_tag(tm.group(1), fallback_word, allow_stem=fallback_allow_stem)
      if (
        idx_tm == len(top_tms) - 1
        and not is_alt_clause
        and enrich_major_corpora
        and fallback_allow_stem
      ):
        covered_seen = set(top_tag_names) | same_stem_covered_tags
        extra_fmts: list[str] = []
        for cp in major_corpora:
          if cp in covered_seen or _CORPUS_ALIASES.get(cp) in covered_seen or cp in skip_tags:
            continue
          m_c, n_c = counter.count_with_stem(fallback_word, cp, allow_stem=True)
          fmt = format_corpus_count(cp, m_c, n_c)
          if fmt is not None:
            extra_fmts.append(fmt)
        if extra_fmts:
          m_sec = re.match(r"^(\s+[०-९0-9]+(?:\.[०-९0-9]+)+)", clause[e:])
          if m_sec:
            sec_end = e + m_sec.end()
            replacements.append((s, sec_end, rep_str + m_sec.group(1) + ", " + ", ".join(extra_fmts)))
            continue
          if clause[e:].lstrip().startswith("/"):
            rep_str = ", ".join(extra_fmts) + ", " + rep_str
          else:
            rep_str = rep_str + ", " + ", ".join(extra_fmts)
      replacements.append((s, e, rep_str))

  if replacements:
    out_parts: list[str] = []
    last = 0
    for s, e, rep in sorted(replacements, key=lambda x: x[0]):
      out_parts.append(clause[last:s])
      out_parts.append(rep)
      last = e
    out_parts.append(clause[last:])
    clause_out = "".join(out_parts)
  else:
    clause_out = clause

  # 4. If main clause had NO top-level corpus tags at all (and no Pattern B tag list), surface `major_corpora` where `N > 0`
  if not top_tms and not has_pattern_b and not is_alt_clause and enrich_major_corpora and fallback_allow_stem:
    extra_lead: list[str] = []
    for cp in major_corpora:
      if cp in same_stem_covered_tags or _CORPUS_ALIASES.get(cp) in same_stem_covered_tags or cp in skip_tags:
        continue
      m_c, n_c = counter.count_with_stem(fallback_word, cp, allow_stem=True)
      fmt = format_corpus_count(cp, m_c, n_c)
      if fmt is not None:
        extra_lead.append(fmt)
    if extra_lead:
      lead_ws = clause_out[: len(clause_out) - len(clause_out.lstrip())]
      rest = clause_out.lstrip()
      clause_out = f"{lead_ws}{', '.join(extra_lead)}, {rest}" if rest else f"{lead_ws}{', '.join(extra_lead)}"

  return clause_out


def _prune_bare_corpus_tags_if_solid(prov: str, *, skip_tags: frozenset[str] = frozenset()) -> str:
  """Remove uncounted bare standalone ``*CORPUS*`` comma-segments when the remaining provenance stays solid."""
  bare_seg_re = re.compile(rf"^\*({_CORPUS_TAG_PAT})\*$")
  clauses = _split_top_level_semicolons(prov)
  pruned_clauses: list[str] = []
  for cl in clauses:
    segs: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in cl:
      if ch == "(":
        depth += 1
      elif ch == ")" and depth > 0:
        depth -= 1
      if ch == "," and depth == 0:
        segs.append("".join(cur).strip())
        cur = []
      else:
        cur.append(ch)
    segs.append("".join(cur).strip())
    kept = []
    for s in segs:
      if not s:
        continue
      m_b = bare_seg_re.fullmatch(s)
      if m_b and m_b.group(1) not in skip_tags:
        continue
      kept.append(s)
    if kept:
      pruned_clauses.append(", ".join(kept))
    elif cl.strip():
      pruned_clauses.append(cl.strip())
  cand = "; ".join(pruned_clauses)
  if cand and is_solid_provenance(cand):
    return cand
  return prov


def _strip_forbidden_sources_if_nonempty(prov: str) -> str:
  """Drop segments citing forbidden sources (``*TA*`` / ``*EK*``) when non-empty provenance remains."""
  if not _FORBIDDEN_SOURCE_RE.search(prov):
    return prov
  clauses = _split_top_level_semicolons(prov)
  kept_clauses: list[str] = []
  for cl in clauses:
    segs: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in cl:
      if ch == "(":
        depth += 1
      elif ch == ")" and depth > 0:
        depth -= 1
      if ch == "," and depth == 0:
        segs.append("".join(cur).strip())
        cur = []
      else:
        cur.append(ch)
    segs.append("".join(cur).strip())
    kept_segs: list[str] = []
    for seg in segs:
      if not seg:
        continue
      if "(" not in seg:
        seg_clean = re.sub(
          rf"\s*/\s*\*(?:{_FORBIDDEN_TAG_PAT})\*{_COUNT_OPT_PAT}|\*(?:{_FORBIDDEN_TAG_PAT})\*{_COUNT_OPT_PAT}\s*/\s*",
          "",
          seg,
        ).strip()
        if seg_clean and not _FORBIDDEN_SOURCE_RE.search(seg_clean):
          kept_segs.append(seg_clean)
        continue
      if _FORBIDDEN_SOURCE_RE.search(seg):
        cleaned = re.sub(rf"(?:,\s*)?\*(?:{_FORBIDDEN_TAG_PAT})\*{_COUNT_OPT_PAT}", "", seg)
        cleaned = re.sub(r"\(\s*,\s*", "(", cleaned).strip()
        if re.search(r"\(\s*\)", cleaned):
          continue
        if cleaned and not _FORBIDDEN_SOURCE_RE.search(cleaned):
          kept_segs.append(cleaned)
      else:
        kept_segs.append(seg)
    if kept_segs:
      kept_clauses.append(", ".join(kept_segs))
  cand = "; ".join(kept_clauses)
  return cand if cand else prov


def annotate_padapatha_line_counts(
  line: str,
  counter: VedicCorpusCounter,
  *,
  prune_unverified_standalone_tags: bool = False,
  enrich_major_corpora: bool = True,
  major_corpora: Sequence[str] = MAJOR_AUTO_CORPORA,
  skip_tags: Sequence[str] | frozenset[str] = frozenset(),
) -> tuple[str, list[tuple[str, str]]]:
  """Annotate ``*CORPUS*-M`` / ``*CORPUS*-M/N`` occurrence counts and normalize ``पा॰`` on one ``पद-पाठः`` bullet line."""
  skip_set = frozenset(skip_tags)
  stripped = line.lstrip()
  if not stripped.startswith("- "):
    return line, []
  indent = line[: len(line) - len(stripped)]
  items = parse_padapatha_items(stripped)
  if not items:
    return normalize_panini_abbreviations(line), []
  it = items[0]
  if not it.prov or "?" in it.ref:
    return normalize_panini_abbreviations(line), []

  p_idx = stripped.find("(")
  if p_idx < 0 or not stripped.rstrip().endswith(")"):
    return normalize_panini_abbreviations(line), []
  r_end = stripped.rfind(")")
  head = stripped[:p_idx]
  prov_inner = normalize_panini_abbreviations(stripped[p_idx + 1 : r_end])
  prov_inner = _strip_forbidden_sources_if_nonempty(prov_inner)
  tail = stripped[r_end + 1 :]

  allow_stem_ref = is_declinable_nominal(it.ref, prov_inner)
  unresolved: list[tuple[str, str]] = []
  clauses = _split_top_level_semicolons(prov_inner)
  new_clauses = [
    _annotate_clause(
      cl,
      it.ref,
      idx > 0,
      counter,
      unresolved,
      allow_stem_default=allow_stem_ref,
      enrich_major_corpora=enrich_major_corpora,
      major_corpora=major_corpora,
      skip_tags=skip_set,
    )
    for idx, cl in enumerate(clauses)
  ]
  new_prov = ";".join(new_clauses)
  new_prov = _strip_forbidden_sources_if_nonempty(new_prov)
  if prune_unverified_standalone_tags and unresolved:
    pruned = _prune_bare_corpus_tags_if_solid(new_prov, skip_tags=skip_set)
    if pruned != new_prov:
      new_prov = pruned
      surviving_bare = set(re.findall(rf"\*({_CORPUS_TAG_PAT})\*(?!-\d)", new_prov))
      unresolved = [(tg, wd) for tg, wd in unresolved if tg in surviving_bare]
  for fm in _FORBIDDEN_SOURCE_RE.finditer(new_prov):
    unresolved.append((fm.group(1), it.ref))
  return f"{indent}{head}({new_prov}){tail}", unresolved


def annotate_padapatha_markdown_counts(
  markdown_text: str,
  counter: VedicCorpusCounter,
  *,
  skip_js_includes: bool = True,
  prune_unverified_standalone_tags: bool = False,
  enrich_major_corpora: bool = True,
  major_corpora: Sequence[str] = MAJOR_AUTO_CORPORA,
  skip_tags: Sequence[str] | frozenset[str] = frozenset(),
) -> tuple[str, list[tuple[str, str, str]]]:
  """Annotate ``*CORPUS*-M`` / ``*CORPUS*-M/N`` counts and ``पा॰`` across all ``पद-पाठः (यान्त्रिकः...)`` blocks."""
  skip_set = frozenset(skip_tags)
  inc_spans = find_js_include_spans(markdown_text) if skip_js_includes else []
  all_unresolved: list[tuple[str, str, str]] = []

  def _sub_block(m: re.Match) -> str:
    if inc_spans and any(a <= m.start() < b for a, b in inc_spans):
      return m.group(0)
    full = m.group(0)
    hdr = m.group(1).strip()
    if not hdr.startswith("पद-पाठः (यान्त्रिकः"):
      if hdr.startswith("विश्वास-प्रस्तुतिः") and "पा\u0966" in full:
        return full.replace("पा\u0966", "पा॰")
      return full
    open_end = full.find("</summary>") + len("</summary>")
    close_start = full.rfind("</details>")
    prefix = full[:open_end]
    body = full[open_end:close_start]
    suffix = full[close_start:]

    out_lines: list[str] = []
    for ln in body.splitlines(keepends=True):
      nl = "\n" if ln.endswith("\n") else ""
      core = ln[:-1] if nl else ln
      if core.lstrip().startswith("- "):
        updated_core, unres = annotate_padapatha_line_counts(
          core,
          counter,
          prune_unverified_standalone_tags=prune_unverified_standalone_tags,
          enrich_major_corpora=enrich_major_corpora,
          major_corpora=major_corpora,
          skip_tags=skip_set,
        )
        for tg, wd in unres:
          all_unresolved.append((core.strip(), tg, wd))
        out_lines.append(updated_core + nl)
      else:
        out_lines.append(ln)
    return prefix + "".join(out_lines) + suffix

  updated = DETAILS_RE.sub(_sub_block, markdown_text)
  return updated, all_unresolved


def _insert_backfill_tags_in_order(
  existing_tag_spans: Sequence[re.Match],
  target_word: str,
  counter: VedicCorpusCounter,
  corpora: Sequence[str],
  *,
  allow_stem: bool,
) -> list[str]:
  """Preserve every existing formatted tag outside ``corpora`` verbatim, inserting/updating ``corpora`` in canonical order."""
  order_idx = {cp: i for i, cp in enumerate(CORPUS_TAGS)}
  target_set = set(corpora)
  kept: list[tuple[str, str]] = []
  seen: set[str] = set()
  for tm in existing_tag_spans:
    tg = tm.group(1)
    if tg in seen:
      continue
    seen.add(tg)
    if tg in target_set:
      m_c, n_c = counter.count_with_stem(target_word, tg, allow_stem=allow_stem)
      fmt = format_corpus_count(tg, m_c, n_c)
      kept.append((tg, fmt if fmt is not None else tm.group(0)))
    else:
      kept.append((tg, tm.group(0)))

  additions: list[tuple[str, str]] = []
  for cp in corpora:
    if cp in seen or _CORPUS_ALIASES.get(cp) in seen:
      continue
    m_c, n_c = counter.count_with_stem(target_word, cp, allow_stem=allow_stem)
    fmt = format_corpus_count(cp, m_c, n_c)
    if fmt is not None:
      seen.add(cp)
      additions.append((cp, fmt))

  if not additions:
    return [txt for _, txt in kept]

  # Insert each new corpus tag right after the last existing tag that precedes it in CORPUS_TAGS order
  result = list(kept)
  for cp, fmt in sorted(additions, key=lambda kv: order_idx.get(kv[0], 999)):
    cp_ord = order_idx.get(cp, 999)
    ins_at = 0
    for idx_r, (r_tg, _) in enumerate(result):
      if order_idx.get(r_tg, 999) < cp_ord:
        ins_at = idx_r + 1
    result.insert(ins_at, (cp, fmt))
  return [txt for _, txt in result]


def backfill_corpora_in_padapatha_line(
  line: str,
  counter: VedicCorpusCounter,
  corpora: Sequence[str] = ("SB-K", "VS-K"),
) -> str:
  """Insert or update ONLY ``corpora`` counts on one ``पद-पाठः`` bullet line without modifying any other tag or prose."""
  stripped = line.lstrip()
  if not stripped.startswith("- "):
    return line
  indent = line[: len(line) - len(stripped)]
  items = parse_padapatha_items(stripped)
  if not items:
    return line
  it = items[0]
  if not it.prov or "?" in it.ref:
    return line
  p_idx = stripped.find("(")
  if p_idx < 0 or not stripped.rstrip().endswith(")"):
    return line
  r_end = stripped.rfind(")")
  head = stripped[:p_idx]
  prov_inner = stripped[p_idx + 1 : r_end]
  tail = stripped[r_end + 1 :]

  allow_stem_ref = is_declinable_nominal(it.ref, prov_inner)
  default_paradigm = counter.paradigm_forms(it.ref) if allow_stem_ref else frozenset()

  def _is_same_paradigm(w_cand: str) -> bool:
    if not default_paradigm:
      return False
    km = word_to_key_and_marks(w_cand)
    return km is not None and (_canonical_allograph_key(km[0]), km[1]) in default_paradigm

  clauses = _split_top_level_semicolons(prov_inner)
  new_clauses: list[str] = []
  for c_idx, clause in enumerate(clauses):
    is_alt = c_idx > 0
    protected: list[tuple[int, int]] = []
    reps: list[tuple[int, int, str]] = []
    same_stem_covered: set[str] = set()

    # 1. Pattern A: Nested `WORD (*TS*-..., *SB-M*-...)`
    for m in _NESTED_MEMBER_PAREN_RE.finditer(clause):
      w_tok, paren_grp = m.group(1), m.group(2)
      if not _is_sanskrit_example_word(w_tok):
        continue
      w_allow = is_declinable_nominal(w_tok)
      t_matches = list(_TAG_TOKEN_RE.finditer(paren_grp))
      if not t_matches:
        continue
      inner_strip = paren_grp.strip()
      inner_body = inner_strip[1:-1].strip() if inner_strip.startswith("(") and inner_strip.endswith(")") else ""
      pure_list = bool(inner_body) and all(
        re.fullmatch(rf"\*(?:{_CORPUS_TAG_PAT})\*{_COUNT_OPT_PAT}|\*(?:MW|Macdonell|Lanman)\*", seg.strip())
        for seg in inner_body.split(",")
      )
      if pure_list:
        lex_tags = [
          seg.strip()
          for seg in inner_body.split(",")
          if re.fullmatch(r"\*(?:MW|Macdonell|Lanman)\*", seg.strip())
        ]
        updated_tags = _insert_backfill_tags_in_order(
          t_matches, w_tok, counter, corpora, allow_stem=w_allow
        )
        if _is_same_paradigm(w_tok):
          same_stem_covered.update(corpora)
        lead_ws = paren_grp[: len(paren_grp) - len(paren_grp.lstrip())]
        new_paren = f"{lead_ws}({', '.join(updated_tags + lex_tags)})"
        s, e = m.start(2), m.end(2)
        protected.append((s, e))
        if new_paren != paren_grp:
          reps.append((s, e, new_paren))
      else:
        protected.append((m.start(2), m.end(2)))

    # 2. Pattern A2: `WORD *TS*-..., *SB-M*-...` (preserve WORD verbatim!)
    for m in _PRECEDING_WORD_TAG_GROUP_RE.finditer(clause):
      s, e = m.start(3), m.end(3)
      if any(not (e <= ps or s >= pe) for ps, pe in protected):
        continue
      w_tok = m.group(1)
      has_acc = any(ch in w_tok for ch in (US_UDATTA, US_SVARITA, "\u0951", "\u0952"))
      if not (has_acc and _is_sanskrit_example_word(w_tok)):
        continue
      after_tags = clause[e : e + 40]
      m_after = re.match(
        r"^\s+(?:[०-९\d]+(?:\.[०-९\d]+)+\s+)?([\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\u0951\u0952\-]+)",
        after_tags,
      )
      if (
        m_after
        and any(ch in m_after.group(1) for ch in (US_UDATTA, US_SVARITA, "\u0951", "\u0952"))
        and _is_sanskrit_example_word(m_after.group(1))
      ):
        continue
      t_matches = list(_TAG_TOKEN_RE.finditer(m.group(3)))
      if not t_matches:
        continue
      w_allow = is_declinable_nominal(w_tok)
      updated_tags = _insert_backfill_tags_in_order(
        t_matches, w_tok, counter, corpora, allow_stem=w_allow
      )
      if _is_same_paradigm(w_tok):
        same_stem_covered.update(corpora)
      protected.append((s, e))
      new_grp = ", ".join(updated_tags)
      if new_grp != m.group(3):
        reps.append((s, e, new_grp))

    # 3. Protect Pattern B (`*RV*-1 १०.८५.२५ WORD`) so top-level pass doesn't alter cited passages
    has_pattern_b = False
    for m in _TAG_GROUP_WITH_EXAMPLE_RE.finditer(clause):
      s, e = m.start(1), m.end(1)
      if any(not (e <= ps or s >= pe) for ps, pe in protected):
        continue
      w_ex = m.group(3)
      if any(ch in w_ex for ch in (US_UDATTA, US_SVARITA, "\u0951", "\u0952")) and _is_sanskrit_example_word(w_ex):
        has_pattern_b = True
        protected.append((s, e))

    # 4. Top-level tag block in main clause (clause 0)
    if not is_alt:
      top_tms = [
        tm
        for tm in _TAG_TOKEN_RE.finditer(clause)
        if not any(not (tm.end() <= ps or tm.start() >= pe) for ps, pe in protected)
      ]
      eff_corpora = tuple(cp for cp in corpora if cp not in same_stem_covered)
      if top_tms and eff_corpora:
        first_s, last_e = top_tms[0].start(), top_tms[-1].end()
        span_txt = clause[first_s:last_e]
        after_last = clause[last_e : last_e + 15]
        has_trailing_sec = bool(re.match(r"^\s+[०-९0-9]+\.[०-९0-9]", after_last))
        if not has_trailing_sec and re.fullmatch(
          rf"\*(?:{_CORPUS_TAG_PAT})\*{_COUNT_OPT_PAT}(?:\s*,\s*\*(?:{_CORPUS_TAG_PAT})\*{_COUNT_OPT_PAT})*",
          span_txt,
        ):
          updated_top = _insert_backfill_tags_in_order(
            top_tms, it.ref, counter, eff_corpora, allow_stem=allow_stem_ref
          )
          new_span = ", ".join(updated_top)
          if new_span != span_txt:
            reps.append((first_s, last_e, new_span))
        else:
          # Mixed top-level tags (e.g. `*VS-M*-91 १.५, *RV*-265, *TS*-157`): if a trailing contiguous pure tag run exists, update it; else append after last tag/ref.
          tail_start_idx = len(top_tms) - 1
          while tail_start_idx > 0:
            gap = clause[top_tms[tail_start_idx - 1].end() : top_tms[tail_start_idx].start()]
            if re.fullmatch(r"\s*,\s*", gap):
              tail_start_idx -= 1
            else:
              break
          tail_tms = top_tms[tail_start_idx:]
          tail_s, tail_e = tail_tms[0].start(), tail_tms[-1].end()
          tail_has_sec = bool(re.match(r"^\s+[०-९0-9]+\.[०-९0-9]", clause[tail_e : tail_e + 15]))
          if not tail_has_sec and tail_start_idx > 0 and all(
            not re.match(r"^\s+[०-९0-9]+\.[०-९0-9]", clause[tm.end() : tm.end() + 15]) for tm in tail_tms
          ):
            # Also include any preceding tags (like `*VS-M*-91` before `१.५`) in `seen` so we don't duplicate aliases, while preserving them verbatim.
            pre_names = {tm.group(1) for tm in top_tms[:tail_start_idx]}
            sub_corpora = tuple(cp for cp in eff_corpora if cp not in pre_names and _CORPUS_ALIASES.get(cp) not in pre_names)
            if sub_corpora:
              updated_tail = _insert_backfill_tags_in_order(
                tail_tms, it.ref, counter, sub_corpora, allow_stem=allow_stem_ref
              )
              new_span = ", ".join(updated_tail)
              if new_span != clause[tail_s:tail_e]:
                reps.append((tail_s, tail_e, new_span))
          else:
            existing_names = {tm.group(1) for tm in top_tms}
            extras: list[str] = []
            for cp in eff_corpora:
              if cp in existing_names or _CORPUS_ALIASES.get(cp) in existing_names:
                continue
              m_c, n_c = counter.count_with_stem(it.ref, cp, allow_stem=allow_stem_ref)
              fmt = format_corpus_count(cp, m_c, n_c)
              if fmt is not None:
                extras.append(fmt)
            if extras:
              s_last, e_last = top_tms[-1].start(), top_tms[-1].end()
              m_sec = re.match(r"^(\s+[०-९0-9]+(?:\.[०-९0-9]+)+)", clause[e_last:])
              if m_sec:
                sec_end = e_last + m_sec.end()
                reps.append((s_last, sec_end, clause[s_last:sec_end] + ", " + ", ".join(extras)))
              elif clause[e_last:].lstrip().startswith("/"):
                reps.append((s_last, e_last, ", ".join(extras) + ", " + clause[s_last:e_last]))
              else:
                reps.append((s_last, e_last, clause[s_last:e_last] + ", " + ", ".join(extras)))
      elif not top_tms and not has_pattern_b and eff_corpora:
        # Main clause had no top-level corpus tags at all: insert positive counts (prepending before *MW*/notes for declinables, appending after Pāṇini rules for indeclinables/verbs).
        extras = []
        for cp in eff_corpora:
          m_c, n_c = counter.count_with_stem(it.ref, cp, allow_stem=allow_stem_ref)
          fmt = format_corpus_count(cp, m_c, n_c)
          if fmt is not None:
            extras.append(fmt)
        if extras:
          if allow_stem_ref:
            lead_len = len(clause) - len(clause.lstrip())
            rest = clause[lead_len:]
            ins_txt = f"{', '.join(extras)}, " if rest else ", ".join(extras)
            reps.append((lead_len, lead_len, ins_txt))
          else:
            trail_len = len(clause.rstrip())
            # Place corpus counts after rules/prose and right before trailing *MW*/*Macdonell*/*Lanman*/*Whitney* if present
            m_lex = re.search(r",\s*(?:\*(?:MW|Macdonell|Lanman|Whitney)\*)", clause[:trail_len])
            if m_lex:
              ins_pos = m_lex.start()
              reps.append((ins_pos, ins_pos, f", {', '.join(extras)}"))
            elif clause[:trail_len].strip():
              reps.append((trail_len, trail_len, f", {', '.join(extras)}"))
            else:
              reps.append((trail_len, trail_len, ", ".join(extras)))

    if reps:
      out_p: list[str] = []
      last = 0
      for s, e, rep in sorted(reps, key=lambda x: x[0]):
        out_p.append(clause[last:s])
        out_p.append(rep)
        last = e
      out_p.append(clause[last:])
      new_clauses.append("".join(out_p))
    else:
      new_clauses.append(clause)

  new_prov = ";".join(new_clauses)
  if new_prov == prov_inner:
    return line
  return f"{indent}{head}({new_prov}){tail}"


def backfill_corpora_in_padapatha_markdown(
  markdown_text: str,
  counter: VedicCorpusCounter,
  corpora: Sequence[str] = ("SB-K", "VS-K"),
  *,
  skip_js_includes: bool = True,
) -> str:
  """Insert or update ONLY ``corpora`` counts across all ``पद-पाठः (यान्त्रिकः...)`` blocks without touching other tags."""
  inc_spans = find_js_include_spans(markdown_text) if skip_js_includes else []

  def _sub_block(m: re.Match) -> str:
    if inc_spans and any(a <= m.start() < b for a, b in inc_spans):
      return m.group(0)
    full = m.group(0)
    hdr = m.group(1).strip()
    if not hdr.startswith("पद-पाठः (यान्त्रिकः"):
      return full
    open_end = full.find("</summary>") + len("</summary>")
    close_start = full.rfind("</details>")
    prefix = full[:open_end]
    body = full[open_end:close_start]
    suffix = full[close_start:]
    out_lines: list[str] = []
    for ln in body.splitlines(keepends=True):
      nl = "\n" if ln.endswith("\n") else ""
      core = ln[:-1] if nl else ln
      if core.lstrip().startswith("- "):
        out_lines.append(backfill_corpora_in_padapatha_line(core, counter, corpora=corpora) + nl)
      else:
        out_lines.append(ln)
    return prefix + "".join(out_lines) + suffix

  return DETAILS_RE.sub(_sub_block, markdown_text)
