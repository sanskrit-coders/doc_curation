"""Vedic corpus occurrence counting and ``पद-पाठः (यान्त्रिकः)`` provenance formatting.

Computes exact per-corpus occurrence counts (e.g. ``सर्व᳓तः (*TS*-12, *RV*-2, *TB*-3)``)
across all ten accented Vedic corpora hosted locally (`TS`, `RV`, `TB`, `TK`, `AV`,
`ŚB`, `VS`, `TA`, `KS`, `MS`), and normalizes Pāṇinian abbreviation signs to canonical
``पा॰`` (``U+0970``, ``DEVANAGARI ABBREVIATION SIGN``).
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
)

PROVENANCE_CACHE_VERSION = 3
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
  "VS",
  "TA",
  "KS",
  "MS",
)
CORPUS_TAG_SET: frozenset[str] = frozenset(CORPUS_TAGS)

DEFAULT_CORPUS_DIRS: dict[str, str] = {
  "TS": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/saMhitA/sarva-prastutiH",
  "RV": "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH",
  "TB": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/brAhmaNam/sarva-prastutiH",
  "TK": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/kAThakam/sarva-prastutiH",
  "TA": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/AraNyakam/sarva-prastutiH",
  "ŚB": "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH",
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
_TAG_TOKEN_RE = re.compile(rf"\*({_CORPUS_TAG_PAT})\*(?:-(\d+))?")
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
  (re.compile(r"ः([कखपफ])"), r"ष्\1"),
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
  s_clean = re.sub(r"[वयलर]्ँ", "ं", s_clean)
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
  """Cached exact occurrence counter across all 10 Vedic corpora (`TS`, `RV`, `TB`, `TK`, `AV`, `ŚB`, `VS`, `TA`, `KS`, `MS`)."""

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

  def _add(
    self,
    corpus: str,
    key: str,
    marks: tuple[str, ...],
    freq: int = 1,
    *,
    mode: str = "sum",
  ) -> None:
    if not key or not marks or freq <= 0:
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

    # 1. Padasvara Babylon dictionaries (exact padapāṭha frequencies for RV, TS, AV)
    for tag, rel in (
      ("RV", "kAvya/rv-padasvara-dev/rv-padasvara-dev.babylon"),
      ("TS", "kAvya/kyv-ts-padasvara/kyv-ts-padasvara.babylon"),
      ("AV", "kAvya/av-padasvara/av-padasvara.babylon"),
    ):
      bpath = os.path.join(dict_root, rel)
      if os.path.isfile(bpath):
        counter._ingest_babylon(bpath, tag)

    # 2. Supplement TS from local US-accented `विश्वास-प्रस्तुतिः` (`mode="max"` so babylon exact counts win when present;
    # note TS `<summary>पद-पाठः</summary>` is unaccented so we never run `classical_padapatha_to_us` on unaccented blocks!)
    ts_dir = dirs.get("TS", "")
    if ts_dir and os.path.isdir(ts_dir):
      counter._ingest_us_vp_supplement(ts_dir, "TS")

    # 3. VS: prefer `<summary>पदपाठः - दयानन्दादि</summary>` per section, fallback to US/classical tokens
    vs_dir = dirs.get("VS", "")
    if vs_dir and os.path.isdir(vs_dir):
      counter._ingest_vs_dir(vs_dir)

    # 4. TB, TK, TA, ŚB: deduplicated per section (`पद-पाठः` > `पद-पाठः (यान्त्रिकः...)` > `विश्वास-प्रस्तुतिः`)
    for tag in ("TB", "TK", "TA", "ŚB"):
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
      self._add(corpus, conv[0], conv[1], freq=freq, mode="sum")
      if "ऽ" in form_raw:
        sk = _padapatha_avagraha_sandhi_key(form_raw)
        if sk and sk != conv[0] and len(_fast_scan_deva_syllables(sk)) == len(conv[1]):
          self._add(corpus, sk, conv[1], freq=freq, mode="max")
      elif conv[0] in ("ऊम्", "उम्") and conv[1] == ("",):
        # Śākala RV/AV padapāṭha writes pragṛhya particle `उ` as `ऊँ॒` / `उं॒`
        self._add(corpus, "उ", ("",), freq=freq, mode="max")

  def _ingest_us_vp_supplement(self, root_dir: str, corpus: str) -> None:
    """Supplement ``corpus`` with US-accented ``विश्वास-प्रस्तुतिः`` tokens only where ``exact_counts`` is 0."""
    local: dict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
    for fp in sorted(glob.glob(os.path.join(root_dir, "**", "*.md"), recursive=True)):
      if fp.endswith("_index.md"):
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
      if fp.endswith("_index.md"):
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

  def _ingest_vs_dir(self, vs_dir: str) -> None:
    for fp in sorted(glob.glob(os.path.join(vs_dir, "**", "*.md"), recursive=True)):
      if fp.endswith("_index.md"):
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
              self._add("VS", conv[0], conv[1], freq=1, mode="sum")
          continue
        mula_body = next((b for h, b in blocks if "मूलम्" in h and ("\u0951" in b or "\u0952" in b)), "")
        if not mula_body:
          continue
        clean = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]|<[^>]+>", " ", mula_body, flags=re.S)
        us_txt = accent.to_US_accents(clean, pauses=r"[।॥,;]+")
        self._ingest_us_samhita_tokens(us_txt, "VS")

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
      if base == "_index.md" and corpus != "TA":
        continue
      txt = open(fp, encoding="utf-8", errors="ignore").read()
      inc = find_js_include_spans(txt)
      if inc:
        txt = _strip_spans(txt, inc)
      sections = re.split(r"(?=\n##[ \t]+)", txt)
      for sec in sections:
        blocks = [(m.group(1).strip(), m.group(2)) for m in DETAILS_RE.finditer(sec)]
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
            for it in parse_padapatha_items(body):
              if "?" in it.ref or not _DEVANAGARI_RE.search(it.ref):
                continue
              km = word_to_key_and_marks(it.ref)
              if km is not None:
                self._add(corpus, km[0], km[1], freq=1, mode="sum")
        elif vp_blocks:
          for body in vp_blocks:
            clean = re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]", " ", body, flags=re.S)
            clean = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", clean)
            if accent.detect_fake_US_accents(clean):
              continue
            self._ingest_us_samhita_tokens(clean, corpus)
        elif corpus == "ŚB":
          weber_blocks = [b for h, b in blocks if h == "मूलम् - Weber"]
          for body in weber_blocks:
            w_clean = re.sub(r"\[\^?[^\]]*\]|\([^)]*\)", " ", body)
            # Restore Weber prevocalic visarga-lopa before avagraha (`शारीर᳘ ऽआत्मा᳘` -> `शारीर᳘ः आत्मा᳘`)
            w_clean = re.sub(r"([\u0905-\u0939][\u093e-\u094c]?[\u1cd8\u1cda\u0957]*)\s+(?=ऽ)", r"\1ः ", w_clean)
            w_us = w_clean.replace("\u1cd8", US_UDATTA).replace("\u1cda", US_UDATTA)
            self._ingest_us_samhita_tokens(w_us, "ŚB")

  def _ingest_samhita_or_pp_dir(self, root_dir: str, corpus: str, *, mode: str = "sum") -> None:
    local: dict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
    for fp in sorted(glob.glob(os.path.join(root_dir, "**", "*.md"), recursive=True)):
      if fp.endswith("_index.md"):
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
  # Reject numerals / sūtra refs like १०.१९०.२ or ६.१.१९८
  if re.search(r"[०-९0-9]", clean):
    return False
  bare = re.sub(r"[^\u0900-\u097f]", "", accent.strip_accents(clean)).rstrip("॰")
  if not bare or bare in _METALANGUAGE_BARE:
    return False
  return True


# Pattern A: `WORD (*TAG1*, *TAG2*, ...)` nested parens immediately after a Sanskrit word
_NESTED_MEMBER_PAREN_RE = re.compile(
  r"([\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\u0951\u0952\-]+)(\s*\([^()]*\*(?:"
  + _CORPUS_TAG_PAT
  + r")\*[^()]*\))"
)

# Pattern B: `*TAG1*(?:-\d+)?(?:,\s*\*TAG2\*(?:-\d+)?)*(?:\s+[०-९\d.]+)?\s+ACCENTED_WORD`
_TAG_GROUP_WITH_EXAMPLE_RE = re.compile(
  r"((?:\*(?:"
  + _CORPUS_TAG_PAT
  + r")\*(?:-\d+)?(?:\s*,\s*)?)+)"
  r"(\s+(?:[०-९\d]+(?:\.[०-९\d]+)+\s+)?)"
  r"([\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\u0951\u0952\-]+)"
)


def _annotate_clause(
  clause: str,
  default_ref: str,
  is_alt_clause: bool,
  counter: VedicCorpusCounter,
  unresolved: list[tuple[str, str]],
) -> str:
  # Clean redundant `*AV* १४.१.४५, *AV* १५ वारम्` -> `*AV* १४.१.४५` before annotating counts
  clause = re.sub(
    r"\*(" + _CORPUS_TAG_PAT + r")\*(\s+[०-९\d.]+),\s*\*\1\*\s*[०-९\d]+\s*वारम्",
    r"*\1*\2",
    clause,
  )

  # Track character spans already annotated by Pattern A or Pattern B so we don't double-process
  protected_spans: list[tuple[int, int]] = []
  replacements: list[tuple[int, int, str]] = []

  def _fmt_tag(tag: str, target_word: str) -> str:
    cnt = counter.count(target_word, tag)
    if cnt > 0:
      return f"*{tag}*-{cnt}"
    unresolved.append((tag, target_word))
    return f"*{tag}*"

  # 1. Pattern A: Nested `WORD (*TS*, *RV*)`
  for m in _NESTED_MEMBER_PAREN_RE.finditer(clause):
    w_tok, paren_grp = m.group(1), m.group(2)
    if not _is_sanskrit_example_word(w_tok):
      continue
    new_paren = _TAG_TOKEN_RE.sub(lambda tm: _fmt_tag(tm.group(1), w_tok), paren_grp)
    s, e = m.start(2), m.end(2)
    protected_spans.append((s, e))
    replacements.append((s, e, new_paren))

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
    grp_parts: list[str] = []
    g_last = 0
    for idx_t, tm in enumerate(tag_matches):
      grp_parts.append(m.group(1)[g_last : tm.start()])
      tname = tm.group(1)
      is_last = idx_t == len(tag_matches) - 1
      if is_last:
        grp_parts.append(_fmt_tag(tname, w_ex))
      else:
        # Earlier comma-separated tags (e.g. `*AV*` in `*AV*, *RV* वे᳓दः`) prefer `default_ref` if attested,
        # falling back to `w_ex` when `default_ref` itself is unattested (e.g. `*TS*, *RV*, *TB* सुम᳓नाः`).
        c_def = counter.count(default_ref, tname)
        if c_def > 0:
          grp_parts.append(f"*{tname}*-{c_def}")
        else:
          grp_parts.append(_fmt_tag(tname, w_ex))
      g_last = tm.end()
    grp_parts.append(m.group(1)[g_last:])
    protected_spans.append((s, e))
    replacements.append((s, e, "".join(grp_parts)))

  # 3. Determine fallback target for remaining `*TAG*` tokens in this clause
  fallback_word = default_ref
  if is_alt_clause:
    def_bare = _normalize_lookup_key(default_ref)
    def_km = word_to_key_and_marks(default_ref)
    for tok in re.findall(r"[\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\u0951\u0952\-]+", clause):
      if any(ch in tok for ch in (US_UDATTA, US_SVARITA, "\u0951", "\u0952")) and _is_sanskrit_example_word(tok):
        t_km = word_to_key_and_marks(tok)
        if t_km is not None and t_km != def_km:
          # Prefer a same-stem alternative accent if present, otherwise first accented word in alt clause
          fallback_word = tok
          if _normalize_lookup_key(tok) == def_bare:
            break

  for tm in _TAG_TOKEN_RE.finditer(clause):
    s, e = tm.start(), tm.end()
    if any(not (e <= ps or s >= pe) for ps, pe in protected_spans):
      continue
    replacements.append((s, e, _fmt_tag(tm.group(1), fallback_word)))

  if not replacements:
    return clause
  out: list[str] = []
  last = 0
  for s, e, rep in sorted(replacements, key=lambda x: x[0]):
    out.append(clause[last:s])
    out.append(rep)
    last = e
  out.append(clause[last:])
  return "".join(out)


def _prune_bare_corpus_tags_if_solid(prov: str) -> str:
  """Remove uncounted bare standalone ``*CORPUS*`` comma-segments when the remaining provenance stays solid."""
  bare_seg_re = re.compile(rf"^\*(?:{_CORPUS_TAG_PAT})\*$")
  clauses = _split_top_level_semicolons(prov)
  pruned_clauses: list[str] = []
  for cl in clauses:
    # Do not touch clauses with nested parens (`सप्त᳓ (*TS*-74)`)
    if "(" in cl or ")" in cl:
      pruned_clauses.append(cl)
      continue
    segs = [s.strip() for s in cl.split(",")]
    kept = [s for s in segs if s and not bare_seg_re.fullmatch(s)]
    if kept:
      pruned_clauses.append(", ".join(kept))
    elif cl.strip():
      pruned_clauses.append(cl.strip())
  cand = "; ".join(pruned_clauses)
  # Only accept pruning if solid provenance is preserved AND at least one counted tag or sūtra remains
  if cand and is_solid_provenance(cand):
    return cand
  return prov


def annotate_padapatha_line_counts(
  line: str,
  counter: VedicCorpusCounter,
  *,
  prune_unverified_standalone_tags: bool = False,
) -> tuple[str, list[tuple[str, str]]]:
  """Annotate ``*CORPUS*-N`` occurrence counts and normalize ``पा॰`` on one ``पद-पाठः`` bullet line.

  Returns ``(updated_line, unresolved_tag_word_pairs)``.
  """
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

  # Locate outer `(prov)` suffix matching `parse_padapatha_items`
  p_idx = stripped.find("(")
  if p_idx < 0 or not stripped.rstrip().endswith(")"):
    return normalize_panini_abbreviations(line), []
  r_end = stripped.rfind(")")
  head = stripped[:p_idx]
  prov_inner = normalize_panini_abbreviations(stripped[p_idx + 1 : r_end])
  tail = stripped[r_end + 1 :]

  unresolved: list[tuple[str, str]] = []
  clauses = _split_top_level_semicolons(prov_inner)
  new_clauses = [
    _annotate_clause(cl, it.ref, idx > 0, counter, unresolved)
    for idx, cl in enumerate(clauses)
  ]
  new_prov = ";".join(new_clauses)
  if prune_unverified_standalone_tags and unresolved:
    pruned = _prune_bare_corpus_tags_if_solid(new_prov)
    if pruned != new_prov:
      new_prov = pruned
      # Recompute remaining unresolved bare tags if any survived
      surviving_bare = set(re.findall(rf"\*({_CORPUS_TAG_PAT})\*(?!-\d)", new_prov))
      unresolved = [(tg, wd) for tg, wd in unresolved if tg in surviving_bare]
  return f"{indent}{head}({new_prov}){tail}", unresolved


def annotate_padapatha_markdown_counts(
  markdown_text: str,
  counter: VedicCorpusCounter,
  *,
  skip_js_includes: bool = True,
  prune_unverified_standalone_tags: bool = False,
) -> tuple[str, list[tuple[str, str, str]]]:
  """Annotate ``*CORPUS*-N`` counts and ``पा॰`` across all ``पद-पाठः (यान्त्रिकः...)`` blocks in ``markdown_text``.

  Returns ``(updated_markdown, unresolved_triples_of_(line, tag, target_word))``.
  """
  inc_spans = find_js_include_spans(markdown_text) if skip_js_includes else []
  all_unresolved: list[tuple[str, str, str]] = []

  def _sub_block(m: re.Match) -> str:
    if inc_spans and any(a <= m.start() < b for a, b in inc_spans):
      return m.group(0)
    full = m.group(0)
    hdr = m.group(1).strip()
    if not hdr.startswith("पद-पाठः (यान्त्रिकः"):
      # Also normalize पा० -> पा॰ inside editorial विश्वास-प्रस्तुतिः +++(...)+++ notes if any
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
        )
        for tg, wd in unres:
          all_unresolved.append((core.strip(), tg, wd))
        out_lines.append(updated_core + nl)
      else:
        out_lines.append(ln)
    return prefix + "".join(out_lines) + suffix

  updated = DETAILS_RE.sub(_sub_block, markdown_text)
  return updated, all_unresolved
