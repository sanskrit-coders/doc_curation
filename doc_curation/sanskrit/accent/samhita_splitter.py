"""Seam-aware Vedic Saṁhitā clause splitting, accent restoration, and validation.

Splits unsplit or partially split ``विश्वास-प्रस्तुतिः`` / ``मूलम्`` /
``पदपाठः`` sections along clause boundaries (typically translation-aligned),
resolving external sandhi, avagraha (``ऽ``), and conjunct splits at block
seams while keeping interior words verbatim. Also provides section parsing,
rendering, and integrity validation utilities.
"""

from __future__ import annotations

import dataclasses
import difflib
import functools
import re
import unicodedata
from typing import Mapping, Sequence

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.md.content_processor.details.common import (
  get_top_level_detail_spans,
  parse_top_level_details,
)
from doc_curation.sanskrit.accent.reconciler import US_SVARITA, US_UDATTA
from doc_curation.sanskrit.fixer import normalize_mAdhyandina

CONS_DEVA = frozenset("कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहळ")
VOW_INDEP = frozenset("अआइईउऊऋॠऌॡएऐओऔ")
MATRAS = frozenset("ािीुूृॄॢॣेैोौ")
MODIFIER_MARKS = frozenset("ँंः᳓᳙॒᳖॑ऽ")

ALL_VEDIC_ACCENTS_RE = re.compile(r"[\u1cd0-\u1cde\u1ce0-\u1cff\u0951\u0952\u1cf2\u1cf3]")
STRIP_COMBINING_RE = re.compile(r"[\u1cd0-\u1cde\u1ce0-\u1cff\u0951\u0952\u1cf2\u1cf3\u0300-\u036f′’']")
DEVA_STRIP_RE = re.compile(r"[\u1cd0-\u1cde\u1ce0-\u1cff\u0951\u0952\u1cf2\u1cf3\s।॥०-९0-9]+")

BAD_SEAM_START_CHARS = frozenset("ािीुूृॄॢॣेैोौ्ंःँ᳓᳙॒᳖॑ऽ")
REPHA_START_RE = re.compile(r"^र्[क-ह]")
INVALID_A_MATRA_RE = re.compile(r"अ[ािीुूृॄॢॣेैोौ]")
INVALID_CONS_ACCENT_ORDER_RE = re.compile(r"[क-ह][᳓᳙॒॑][ािीुूृॄॢॣेैोौ्]")

INLINE_MA_HAL_RE = re.compile(r"म्[ \t]+[क-ह]")
INLINE_TA_HAL_RE = re.compile(r"[दजचलन]्[ \t]+[क-ह]")
INLINE_HIATUS_RE = re.compile(r"[अ-औा-ौ][ \t]+[अआइईउऊऋएऐओऔ]")

_AKSHARA_RE = re.compile(
  r"[\u0915-\u0939\u0958-\u0961](?:\u094d[\u0915-\u0939\u0958-\u0961])*"
  r"[\u093e-\u094c\u0901-\u0903\u0951\u0952\u1cd0-\u1cff]*"
  r"|[\u0905-\u0914][\u0951\u0952\u1cd0-\u1cff]*"
  r"|[\u0951\u0952\u1cd0-\u1cff]+"
  r"|\S"
)

_MATRA_TO_INDEP: dict[str, str] = {
  "ा": "आ",
  "ि": "इ",
  "ी": "ई",
  "ु": "उ",
  "ू": "ऊ",
  "ृ": "ऋ",
  "ॄ": "ॠ",
  "ॢ": "ऌ",
  "ॣ": "ॡ",
  "े": "ए",
  "ै": "ऐ",
  "ो": "ओ",
  "ौ": "औ",
}
_VOW_TO_MATRA: dict[str, str] = {v: k for k, v in _MATRA_TO_INDEP.items()}
_VOICE_TO_VOICELESS: dict[str, str] = {"द": "त", "ग": "क", "ड": "ट", "ब": "प", "ज": "च"}

PADA_OCR_FIX_LOOKUP: dict[str, str] = {
  "अशानिम्": "अशनिम्",
  "उपायामगृहीतः": "उपयामगृहीतः",
  "उपायामगृहीत": "उपयामगृहीत",
  "तृणवध्मम्": "तूणवध्मम्",
  "उत्यतः": "उद्यतः",
  "उत्यासाय": "उद्यासाय",
}

DEFAULT_VP_TITLE = "विश्वास-प्रस्तुतिः"
DEFAULT_SARVA_TITLE = "सर्वाष् टीकाः"
DEFAULT_GRIFFITH_TITLE = "Griffith"
DEFAULT_MULA_TITLE = "मूलम्"
DEFAULT_PADA_TITLE = "पदपाठः - दयानन्दादि"

_ITI_RE = re.compile(r"(?:ऽ?(?:इति|इती)|[ेी]ति|[ेी]ती|[क-ह]िति|[क-ह]िती)$")
_ITI_INLINE_RE = re.compile(r"(.*?(?:ऽ?इति|ऽ?इती|इत्य|[ेी]ति|[ेी]ती|[ेी]त्य|[क-ह]िति|[क-ह]िती|[क-ह]ित्य))(.*)$")
_DIGRUN_RE = re.compile(r"^[।॥०-९0-9\s]+$")
_GLOSS_ITI_RE = re.compile("[िइ]ति")


@dataclasses.dataclass(frozen=True)
class ParsedSamhitaSection:
  """Parsed components of one saṁhitā mantra section (unsplit or interleaved)."""

  heading: str
  vps: list[str]
  griffiths: list[str]
  mulas: list[str]
  padas: list[str]
  residual_blocks: list[str]

  @property
  def head_full(self) -> str:
    return " ".join(self.vps)

  @property
  def griffith_full(self) -> str:
    return " ".join(g for g in self.griffiths if g)

  @property
  def mula_full(self) -> str:
    return " ".join(m for m in self.mulas if m)

  @property
  def pada_full(self) -> str:
    return " ".join(p for p in self.padas if p)


@dataclasses.dataclass(frozen=True)
class SamhitaSplitIssue:
  """One structural, sandhi, accent, or alignment validation issue."""

  kind: str
  message: str
  location: str = ""


def strip_vedic_accents(text: str) -> str:
  """Strip Vedic accent marks while preserving base Devanagari, virāma, anusvāra, and visarga."""
  return ALL_VEDIC_ACCENTS_RE.sub("", text)


def normalize_pada_geminates(word: str) -> str:
  """Collapse Dayānanda-style doubled consonant after repha (e.g. ``कर्म्मणे`` -> ``कर्मणे``)."""
  return re.sub(r"र्([क-ह])्\1", r"र्\1", word)


def strip_danda_number(text: str) -> str:
  """Strip trailing daṇḍas and Devanagari/ASCII verse numbers from a clause."""
  return re.sub(r"[।॥]+\s*[०-९0-9]*\s*[।॥]*\s*$", "", text.strip()).strip()


def split_aksharas(text: str) -> list[str]:
  """Split Devanagari text into orthographic akṣaras without breaking conjuncts."""
  return [m.group(0) for m in _AKSHARA_RE.finditer(text)]


def is_akshara_start(text: str, idx: int) -> bool:
  """Return True if ``idx`` in ``text`` begins a valid Devanagari akṣara or separator."""
  if idx <= 0 or idx >= len(text):
    return True
  ch = text[idx]
  if ch in (" ", "।", "॥", "ऽ"):
    return True
  prev = text[idx - 1]
  if prev in (" ", "।", "॥"):
    return True
  if prev == "्":
    return False
  return ch in CONS_DEVA or ch in VOW_INDEP


def normalize_devanagari_for_alignment(text: str) -> str:
  """Fold Devanagari text to accent-stripped, lowercase Latin keys for fuzzy alignment."""
  cleaned = STRIP_COMBINING_RE.sub("", text)
  cleaned = cleaned.replace("ऽ", "").replace("॥", "").replace("।", "")
  cleaned = re.sub(r"[०-९0-9]+", "", cleaned)
  iast = transliterate(cleaned, sanscript.DEVANAGARI, sanscript.IAST)
  nfkd = unicodedata.normalize("NFKD", iast)
  folded = "".join(c for c in nfkd if not unicodedata.combining(c))
  folded = folded.replace("~", "m")
  return re.sub(r"\s+", "", folded.lower())


def syllable_char_spans(word: str) -> list[tuple[int, int, str, str]]:
  """Return ``(start, end, vowel, us_marks)`` character spans per syllable in Devanagari ``word``."""
  out: list[tuple[int, int, str, str]] = []
  i, n = 0, len(word)
  while i < n:
    ch = word[i]
    if ch in VOW_INDEP:
      j = i + 1
      acc = ""
      while j < n and word[j] in MODIFIER_MARKS:
        if word[j] in (US_UDATTA, US_SVARITA):
          acc += word[j]
        j += 1
      out.append((i, j, ch, acc))
      i = j
    elif ch in CONS_DEVA:
      if i + 1 < n and word[i + 1] == "्":
        i += 2
        continue
      j = i + 1
      vowel = "अ"
      if j < n and word[j] in MATRAS:
        vowel = word[j]
        j += 1
      acc = ""
      while j < n and word[j] in MODIFIER_MARKS:
        if word[j] in (US_UDATTA, US_SVARITA):
          acc += word[j]
        j += 1
      out.append((i, j, vowel, acc))
      i = j
    else:
      i += 1
  return out


def iast_word_udattas(word: str) -> list[bool]:
  """Return per-syllable acute (``\\u0301``) accent flags for an accented IAST token."""
  s = re.sub(r"[|.\d\-\s'’+]+", "", unicodedata.normalize("NFD", word))
  out: list[bool] = []
  i, n = 0, len(s)
  base_vowels = frozenset("aiuṛḷeo")
  while i < n:
    ch = s[i].lower()
    if ch in ("r", "l") and i + 1 < n and s[i + 1] in ("\u0323", "\u0325"):
      j = i + 2
      acc = False
      while j < n and unicodedata.combining(s[j]):
        if s[j] == "\u0301":
          acc = True
        j += 1
      out.append(acc)
      i = j
      continue
    if ch in base_vowels:
      j = i + 1
      acc = False
      has_macron = False
      while j < n and unicodedata.combining(s[j]):
        if s[j] == "\u0301":
          acc = True
        elif s[j] == "\u0304":
          has_macron = True
        j += 1
      if ch == "a" and not has_macron and not acc and j < n and s[j].lower() in ("i", "u"):
        k = j + 1
        while k < n and unicodedata.combining(s[k]):
          if s[k] == "\u0301":
            acc = True
          k += 1
        out.append(acc)
        i = k
        continue
      out.append(acc)
      i = j
      continue
    i += 1
  return out


def dependent_to_us_preserving(text: str, pauses: str = r"[।॥,;]+") -> str:
  """Convert dependent Vedic accents (``॒``/``॑``) to US notation while keeping existing ``᳓``/``᳙``."""
  if US_UDATTA in text or US_SVARITA in text:
    syl_orig = [acc for _, _, _, acc in syllable_char_spans(text)]
    tmp = text.replace(US_SVARITA, "᳖").replace(US_UDATTA, "")
    if not any(x in tmp for x in ("॒", "॑", "᳖", "᳚", "᳛")):
      return text
    us = accent.to_US_accents(tmp, pauses=pauses)
    us_syls = syllable_char_spans(us)
    if len(us_syls) != len(syl_orig):
      return us
    out: list[str] = []
    prev = 0
    for (s, e, _, _), orig_acc in zip(us_syls, syl_orig):
      out.append(us[prev:s])
      seg = us[s:e]
      if US_SVARITA in orig_acc and US_SVARITA not in seg:
        seg = seg.replace(US_UDATTA, "") + US_SVARITA
      elif US_UDATTA in orig_acc and US_UDATTA not in seg:
        seg = seg.replace(US_SVARITA, "") + US_UDATTA
      out.append(seg)
      prev = e
    out.append(us[prev:])
    return "".join(out)
  if any(x in text for x in ("॒", "॑", "᳖", "᳚", "᳛")):
    return accent.to_US_accents(text, pauses=pauses)
  return text


def us_to_dependent_word(words_us: Sequence[str], take_idx: int) -> str:
  """Convert a US-accented seam context to classical dependent accents and return word ``take_idx``."""
  dep = accent.add_dependent_accents(" ".join(words_us), UDATTA_NEW="", DEP_SVARITA="॑")
  parts = dep.split(" ")
  return parts[take_idx] if len(parts) == len(words_us) else dep


def _coarse_phonetic_fold(s: str) -> str:
  """Coarse phonetic folding for fuzzy first/last-word matching in DP alignment."""
  for c in ("dh", "th", "d", "t", "ṭh", "ṭ", "ḍ", "ḍh"):
    s = s.replace(c, "t")
  for c in ("gh", "kh", "g", "k"):
    s = s.replace(c, "k")
  for c in ("bh", "ph", "b", "p"):
    s = s.replace(c, "p")
  for c in ("jh", "ch", "j", "c"):
    s = s.replace(c, "c")
  s = re.sub(r"[sśṣ]", "s", s)
  s = re.sub(r"[ṅñṇ]", "n", s)
  return s.replace("h", "s")


@functools.lru_cache(maxsize=16384)
def _seq_ratio(a: str, b: str) -> float:
  return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _collapse_runs(s: str) -> str:
  return re.sub(r"(.)\1+", r"\1", s)


def _iast_to_devanagari_clean(iast_word: str) -> str:
  # Protect ś/Ś from NFKD decomposing into s + combining acute!
  s = unicodedata.normalize("NFC", iast_word).replace("ś", "\ue001").replace("Ś", "\ue002")
  s = unicodedata.normalize("NFKD", s)
  s = "".join(c for c in s if c not in ("\u0301", "\u0300", "\u0302"))
  s = unicodedata.normalize("NFC", s).replace("\ue001", "ś").replace("\ue002", "Ś")
  s = s.replace("m̐", "ँ").replace("M̐", "ँ")
  return transliterate(s, sanscript.IAST, sanscript.DEVANAGARI)


def _add_us_udatta_first_syl(word_deva: str) -> str:
  syls = syllable_char_spans(word_deva)
  if not syls:
    return word_deva
  _, e0, _, acc0 = syls[0]
  if US_UDATTA in acc0 or US_SVARITA in acc0:
    return word_deva
  return word_deva[:e0] + US_UDATTA + word_deva[e0:]


def _drop_us_udatta_last_syl(word_deva: str) -> str:
  syls = syllable_char_spans(word_deva)
  if not syls:
    return word_deva
  sl, el, _, accl = syls[-1]
  if US_UDATTA not in accl:
    return word_deva
  return word_deva[:sl] + word_deva[sl:el].replace(US_UDATTA, "") + word_deva[el:]


def _coalesce_avagraha_to_match(cand_word: str, pre_ref: str) -> str:
  """Prefer ``pre_ref`` when ``cand_word`` splits internal compound sandhi via ``ऽ``."""
  if "ऽ" not in cand_word or not pre_ref:
    return cand_word.replace("ऽ", "")
  pb = normalize_pada_geminates(strip_vedic_accents(pre_ref))
  cb = strip_vedic_accents(cand_word)
  if re.search(r"ऽ[अआइईउऊऋएऐओऔ]", cb):
    pairs = (
      (r"([क-ह])ऽ[अआ]", r"\1ा"),
      (r"ाऽ[अआ]", "ा"),
      (r"([क-ह])ऽ[इई]", r"\1े"),
      (r"([क-ह])ऽ[उऊ]", r"\1ो"),
      (r"िऽ[इई]", "ी"),
      (r"िऽआ", "्या"),
      (r"िऽअ", "्य"),
      (r"िऽउ", "्यु"),
      (r"िऽऊ", "्यू"),
      (r"ुऽ[उऊ]", "ू"),
    )
    collapsed = cb
    for pat, rep in pairs:
      collapsed = re.sub(pat, rep, collapsed)
    collapsed = collapsed.replace("ऽ", "")
    pb_norm = _coarse_phonetic_fold(normalize_devanagari_for_alignment(pb.rstrip("्")))
    col_norm = _coarse_phonetic_fold(normalize_devanagari_for_alignment(collapsed.rstrip("्")))
    if col_norm == pb_norm:
      if pb.endswith("्") and collapsed.endswith("्"):
        return pb
      return pb + "्" if collapsed.endswith("्") else pb
  return cand_word.replace("ऽ", "")


def is_pada_gloss_quote(unit: str) -> bool:
  """Return True if daṇḍa-unit is an ``Xिति`` analytical quotation longer than bare ``इति``."""
  bare = re.sub(r"[।\s]+$", "", STRIP_COMBINING_RE.sub("", unit))
  return len(bare) > 3 and re.search(r"[िइ]ति$", bare) is not None


def extract_padapatha_words(pada_inner: str, *, keep_avagraha: bool = False) -> list[str]:
  """Extract sequential words from Dayānanda-style padapāṭha, resolving ``इति`` analyses."""
  units = [u.strip() for u in re.split(r"(?<=।)", pada_inner.strip()) if u.strip()]
  out: list[str] = []
  def _finish_word(w: str) -> str:
    return w if keep_avagraha else w.replace("ऽ", "")

  for unit in units:
    if is_pada_gloss_quote(unit):
      continue
    toks = [re.sub(r"[।॥०-९0-9]+", "", t).strip() for t in unit.split()]
    toks = [t for t in toks if t]
    if not toks:
      continue
    iti_idx = None
    for idx, tok in enumerate(toks):
      tb = strip_vedic_accents(tok)
      if _ITI_RE.search(tb) or re.search(r"(?:^इत्य|ऽइति|ऽइती|इति|इती|[ेी]त्य)", tb):
        iti_idx = idx
        break
      m_cy = re.match(r"^(.*?(?:[क-ह]ित्य|[ेी]ती|[क-ह]िती))(.+)$", tb)
      if m_cy and (
        "ऽ" in tb
        or (idx + 1 < len(toks) and "ऽ" in "".join(toks[idx + 1:]))
        or (not re.search(r"(?:दित्य|क्षित्य|चित्य)", tb) and len(m_cy.group(2)) >= 2 and "त्य" in m_cy.group(1))
      ):
        iti_idx = idx
        break
    if iti_idx is None:
      for tok in toks:
        w = _finish_word(tok)
        if w:
          out.append(w)
      continue

    pre_toks = list(toks[:iti_idx])
    tb_iti = strip_vedic_accents(toks[iti_idx])
    after_toks = list(toks[iti_idx + 1:])
    m_inl = _ITI_INLINE_RE.match(tb_iti)
    inline_pre_ref = None
    if m_inl:
      g1 = m_inl.group(1)
      if not pre_toks:
        inline_pre_ref = re.sub(r"(?:ऽ?इति|ऽ?इती|इत्य|[ेी]ति|[ेी]ती|[ेी]त्य|ित[िय]|िती|ित्य)$", "", g1)
      if m_inl.group(2) and not after_toks:
        aft = m_inl.group(2)
        if g1.endswith(("त्य", "त्य्")) and aft:
          if aft[0] in _MATRA_TO_INDEP:
            aft = _MATRA_TO_INDEP[aft[0]] + aft[1:]
          elif aft[0] not in VOW_INDEP:
            aft = "अ" + aft
        elif g1.endswith(("ती", "ती्")) and aft and aft[0] not in VOW_INDEP and aft[0] not in MATRAS:
          aft = "इ" + aft
        after_toks = [aft]

    if not pre_toks and after_toks:
      for ai, atok in enumerate(after_toks):
        if ai == 0 and inline_pre_ref:
          cand_word = (
            _coalesce_avagraha_to_match(atok, inline_pre_ref)
            if (not keep_avagraha or re.search(r"ऽ[अआइईउऊऋएऐओऔ]", strip_vedic_accents(atok)))
            else atok
          )
        else:
          cand_word = _finish_word(atok)
        if ai == 0 and out and _coarse_phonetic_fold(normalize_devanagari_for_alignment(out[-1])) == _coarse_phonetic_fold(normalize_devanagari_for_alignment(cand_word)):
          continue
        if cand_word:
          out.append(cand_word)
      continue

    if (
      len(pre_toks) == 1
      and out
      and _coarse_phonetic_fold(normalize_devanagari_for_alignment(out[-1]))
      == _coarse_phonetic_fold(normalize_devanagari_for_alignment(pre_toks[0]))
    ):
      continue

    if pre_toks and after_toks:
      if len(pre_toks) == 1:
        cand_word = (
          _coalesce_avagraha_to_match(after_toks[0], pre_toks[0])
          if (not keep_avagraha or re.search(r"ऽ[अआइईउऊऋएऐओऔ]", strip_vedic_accents(after_toks[0])))
          else after_toks[0]
        )
        if not (
          out
          and _coarse_phonetic_fold(normalize_devanagari_for_alignment(out[-1]))
          == _coarse_phonetic_fold(normalize_devanagari_for_alignment(cand_word))
        ):
          if cand_word:
            out.append(cand_word)
        for extra in after_toks[1:]:
          ew = _finish_word(extra)
          if ew:
            out.append(ew)
      else:
        out.extend(_finish_word(w) for w in pre_toks if _finish_word(w))
    elif pre_toks:
      out.extend(_finish_word(w) for w in pre_toks if _finish_word(w))
    elif after_toks:
      for atok in after_toks:
        cw = _finish_word(atok)
        if cw:
          out.append(cw)
  return out


def parse_pada_groups(pada_inner: str) -> list[str]:
  """Split padapāṭha text into daṇḍa-bounded groups, keeping ``Xिति`` gloss pairs intact."""
  units = [u.strip() for u in re.split(r"(?<=।)", pada_inner) if u.strip()]
  groups: list[str] = []
  i = 0
  while i < len(units):
    u = units[i]
    if is_pada_gloss_quote(u) and i + 1 < len(units):
      groups.append(u + " " + units[i + 1])
      i += 2
      continue
    groups.append(u)
    i += 1

  merged: list[str] = []
  for g in groups:
    if merged and _GLOSS_ITI_RE.search(g) and " " in g.strip() and not _GLOSS_ITI_RE.search(merged[-1]):
      bare = re.sub(r"[।\s]+$", "", STRIP_COMBINING_RE.sub("", merged[-1]))
      first = re.sub(r"[।\s]+$", "", STRIP_COMBINING_RE.sub("", g.split()[0])) if g.split() else ""
      head = re.sub(r"ऽ.*$", "", first)
      if bare and head and (
        head in bare
        or bare in head
        or _seq_ratio(normalize_devanagari_for_alignment(bare), normalize_devanagari_for_alignment(head)) > 0.6
      ):
        merged[-1] += " " + g
        continue
    merged.append(g)
  return merged


def extract_iast_words(iast_text: str) -> list[tuple[str, str]]:
  """Extract ``(raw_iast_token, folded_norm)`` pairs from an accented IAST string."""
  toks = [t for t in re.split(r"[\s|+]+", iast_text.strip()) if t and not re.fullmatch(r"[\d.\-]+", t)]
  out: list[tuple[str, str]] = []
  for tok in toks:
    cleaned = tok.replace("-", "")
    if cleaned:
      out.append((cleaned, normalize_devanagari_for_alignment(_iast_to_devanagari_clean(cleaned))))
  return out


def banded_monotonic_align(source_norm: str, target_norm: str, band: int = 32) -> list[int] | None:
  """Compute monotonic banded global alignment mapping prefix lengths of ``target_norm`` to ``source_norm``."""
  na, nb = len(source_norm), len(target_norm)
  if na == 0 or nb == 0:
    return None
  eff_band = max(band, abs(na - nb) + 24)
  neg = -10**9
  dp: dict[tuple[int, int], int] = {(0, 0): 0}
  bt: dict[tuple[int, int], int] = {}
  for j in range(1, min(nb, eff_band) + 1):
    dp[(0, j)] = -j
    bt[(0, j)] = 2
  for i in range(1, na + 1):
    center = round(i * nb / na)
    j_lo = max(0, center - eff_band)
    j_hi = min(nb, center + eff_band)
    if j_lo == 0:
      dp[(i, 0)] = -i
      bt[(i, 0)] = 1
      j_lo = 1
    ai = source_norm[i - 1]
    for j in range(j_lo, j_hi + 1):
      best, op = neg, 0
      v = dp.get((i - 1, j - 1), neg)
      if v != neg:
        sc = v + (2 if ai == target_norm[j - 1] else -1)
        if sc > best:
          best, op = sc, 0
      v = dp.get((i - 1, j), neg)
      if v != neg and v - 1 > best:
        best, op = v - 1, 1
      v = dp.get((i, j - 1), neg)
      if v != neg and v - 1 > best:
        best, op = v - 1, 2
      dp[(i, j)] = best
      bt[(i, j)] = op
  if (na, nb) not in dp:
    return None
  j_to_i = [0] * (nb + 1)
  i, j = na, nb
  while i > 0 or j > 0:
    j_to_i[j] = i
    op = bt[(i, j)]
    if op == 0:
      i -= 1
      j -= 1
    elif op == 1:
      i -= 1
    else:
      j -= 1
  j_to_i[0] = 0
  return j_to_i


def resolve_pausa_word_end(word_vp: str, word_pada_base: str) -> str:
  """Restore pausa ending on a left block-boundary token given its accent-free padapāṭha form."""
  if not word_pada_base or not word_vp:
    return word_vp
  base_vp = strip_vedic_accents(word_vp)
  wp = normalize_pada_geminates(strip_vedic_accents(word_pada_base))
  if wp.endswith("म्") and word_vp.endswith(("ं", "ँ")):
    return word_vp[:-1] + "म्"
  if wp.endswith("म्"):
    m = re.search(r"([ंँ])([᳓᳙]+)$", word_vp)
    if m:
      return word_vp[:m.start()] + m.group(2) + "म्"
  if wp.endswith("क्"):
    m = re.search(r"([गघङ]्)([᳓᳙]*)$", word_vp)
    if m:
      return word_vp[:m.start()] + "क्" + m.group(2)
  if wp.endswith("त्"):
    m = re.search(r"([दजचलन]्)([᳓᳙]*)$", word_vp)
    if m:
      return word_vp[:m.start()] + "त्" + m.group(2)
  if wp.endswith("ट्"):
    m = re.search(r"([डण]्)([᳓᳙]*)$", word_vp)
    if m:
      return word_vp[:m.start()] + "ट्" + m.group(2)
  if wp.endswith("न्"):
    m_nt = re.search(r"न्त्([᳓᳙]*)$", word_vp)
    if m_nt:
      return word_vp[:m_nt.start()] + "न्" + m_nt.group(1)
    m = re.search(r"([ँं]?)([᳓᳙]*)([ञशषस]्)([᳓᳙]*)$", word_vp)
    if m:
      return word_vp[:m.start()] + m.group(2) + m.group(4) + "न्"
  if wp.endswith("ः"):
    m_o = re.search(r"ो([᳓᳙]*)$", word_vp)
    if m_o and not wp.endswith("ोः"):
      return word_vp[:m_o.start()] + "ः" + m_o.group(1)
    m_r = re.search(r"र्([᳓᳙]*)$", word_vp)
    if m_r and not wp.endswith("र्"):
      return word_vp[:m_r.start()] + "ः" + m_r.group(1)
    m_s = re.search(r"[सशष]्([᳓᳙]*)$", word_vp)
    if m_s and not wp.endswith("स्"):
      return word_vp[:m_s.start()] + "ः" + m_s.group(1)
    if word_vp.endswith("ऽ") and (
      normalize_devanagari_for_alignment(base_vp[:-1]) + "h" == normalize_devanagari_for_alignment(wp)
      or base_vp[:-1].endswith(wp[:-1])
      or (wp.startswith("अ") and len(wp) == 3 and base_vp[:-1].endswith(wp[1:-1]))
    ):
      stem_tr = word_vp[:-1]
      m_tr = re.search(r"([᳓᳙]+)$", stem_tr)
      return (stem_tr[:m_tr.start()] + "ः" + m_tr.group(1)) if m_tr else (stem_tr + "ः")
    if not word_vp.endswith("ऽ") and not base_vp.endswith("ः") and (
      normalize_devanagari_for_alignment(base_vp) + "h" == normalize_devanagari_for_alignment(wp)
      or wp[:-1] == base_vp
    ):
      m_tr = re.search(r"([᳓᳙]+)$", word_vp)
      return (word_vp[:m_tr.start()] + "ः" + m_tr.group(1)) if m_tr else (word_vp + "ः")
  elif word_vp.endswith("ऽ") and base_vp[:-1].endswith(wp):
    return word_vp[:-1]
  if wp.endswith("ि") and word_vp.endswith("य्") and len(word_vp) >= 3 and word_vp[-3] == "्":
    return word_vp[:-3] + "ि"
  if wp.endswith("ु") and word_vp.endswith("व्") and len(word_vp) >= 3 and word_vp[-3] == "्":
    return word_vp[:-3] + "ु"
  if wp.endswith("ौ"):
    m_v = re.search(r"ाव्([᳓᳙]*)$", word_vp)
    if m_v:
      return word_vp[:m_v.start()] + "ौ" + m_v.group(1)
    if re.search(r"ाव[ेैोौ][᳓᳙]*$", word_vp):
      return re.sub(r"ाव[ेैोौ][᳓᳙]*$", "ौ", word_vp)
  if wp == "मे" and base_vp.rstrip("ऽ") == "म":
    return "मे" + re.sub(r"[ऽ]", "", word_vp[1:])
  return word_vp


def build_cut_lookup(
  full_text: str,
  pada_inner: str,
  iast_text: str = "",
  ocr_fix_lookup: Mapping[str, str] = PADA_OCR_FIX_LOOKUP,
):
  """Return a lookup closure ``get_at(cut_raw_idx) -> (pL, pR, iL, iR)`` anchored to ``full_text``."""
  raw_pwords = extract_padapatha_words(pada_inner)
  pwords = [ocr_fix_lookup.get(strip_vedic_accents(w), w) for w in raw_pwords]
  iwords = extract_iast_words(iast_text) if iast_text else []
  nh = normalize_devanagari_for_alignment(full_text)

  def _prepare(word_norms):
    if not word_norms:
      return None
    joined = "".join(wn for _, wn in word_norms)
    bounds = [0]
    acc = 0
    for _, wn in word_norms:
      acc += len(wn)
      bounds.append(acc)
    j_to_i = banded_monotonic_align(nh, joined)
    if j_to_i is not None:
      return word_norms, [j_to_i[b] for b in bounds], None, bounds
    sm = difflib.SequenceMatcher(None, nh, joined, autojunk=False)
    return word_norms, None, sm.get_opcodes(), bounds

  pw_prep = _prepare([(w, normalize_devanagari_for_alignment(w)) for w in pwords])
  iw_prep = _prepare([(orig, n) for orig, n in iwords])

  def _lookup(n_pos: int, prepped) -> tuple[str, str, int]:
    if not prepped:
      return "", "", 999
    word_norms, i_bounds, opcodes, bounds = prepped
    if i_bounds is not None:
      best_idx = min(range(len(i_bounds)), key=lambda idx: abs(i_bounds[idx] - n_pos))
      best_dist = abs(i_bounds[best_idx] - n_pos)
    else:
      target_j = 0
      for tag, i1, i2, j1, j2 in opcodes:
        if i1 <= n_pos <= i2:
          if tag == "equal":
            target_j = j1 + (n_pos - i1)
          elif i2 > i1:
            target_j = j1 + round((n_pos - i1) * (j2 - j1) / (i2 - i1))
          else:
            target_j = round((j1 + j2) / 2)
          break
        target_j = j2
      best_idx = min(range(len(bounds)), key=lambda idx: abs(bounds[idx] - target_j))
      best_dist = abs(bounds[best_idx] - target_j)
    w_l = word_norms[best_idx - 1][0] if best_idx > 0 else ""
    w_r = word_norms[best_idx][0] if best_idx < len(word_norms) else ""
    return w_l, w_r, best_dist

  def get_at(cut_ri: int) -> tuple[str, str, str, str]:
    n_pos = len(normalize_devanagari_for_alignment(full_text[:cut_ri]))
    p_l, p_r, pdist = _lookup(n_pos, pw_prep)
    i_l, i_r, _ = _lookup(n_pos, iw_prep)
    if pdist > 6:
      p_l, p_r = "", ""
    return p_l, p_r, i_l, i_r

  return get_at


def _deva_strip_with_map(text: str) -> tuple[str, list[int]]:
  chars: list[str] = []
  pos_map = [0]
  for i, ch in enumerate(text):
    if DEVA_STRIP_RE.match(ch):
      continue
    chars.append(ch)
    pos_map.append(i + 1)
  return "".join(chars), pos_map


def cut_text_to_slices(full_text: str, target_clauses: Sequence[str]) -> tuple[list[str], list[int], list[str]]:
  """Project ``target_clauses`` boundaries onto unsplit ``full_text`` at akṣara/word/halant edges."""
  if len(target_clauses) <= 1:
    return [full_text], [], []

  dh, h_map = _deva_strip_with_map(full_text)
  t_clean = [strip_danda_number(v) for v in target_clauses]
  t_strips = [DEVA_STRIP_RE.sub("", v) for v in t_clean]
  dt = "".join(t_strips)

  opcodes = difflib.SequenceMatcher(None, dt, dh, autojunk=False).get_opcodes()

  def _map_t_to_h(tx: int) -> int:
    for tag, i1, i2, j1, j2 in opcodes:
      if i1 <= tx <= i2:
        if tag == "equal":
          return j1 + (tx - i1)
        if i2 > i1:
          if i2 - tx <= 1 and j2 - j1 <= 3:
            return j2
          return j1 + round((tx - i1) * (j2 - j1) / (i2 - i1))
        return round((j1 + j2) / 2)
    return len(dh)

  raw_cuts = [0]
  acc_t = 0
  for k in range(len(t_clean) - 1):
    acc_t += len(t_strips[k])
    hj = max(0, min(len(dh), _map_t_to_h(acc_t)))
    ri = max(raw_cuts[-1], h_map[hj])
    while ri < len(full_text) and full_text[ri] in (US_UDATTA, US_SVARITA, "ं", "ः", "ँ", "॑", "॒"):
      ri += 1
    best_ri = ri
    while best_ri < len(full_text) and full_text[best_ri] in (" ", "।"):
      best_ri += 1
    is_exact_hal_seam = (
      0 < ri < len(full_text)
      and full_text[ri - 1] == "्"
      and full_text[ri] in CONS_DEVA
      and (
        t_strips[k].endswith("्")
        or normalize_devanagari_for_alignment(t_clean[k + 1][:1]) == normalize_devanagari_for_alignment(full_text[ri])
        or (t_strips[k + 1].startswith("श") and full_text[ri] == "छ")
      )
    )
    snapped = False
    if is_exact_hal_seam:
      best_ri = ri
      snapped = True
    else:
      for p in range(max(raw_cuts[-1] + 1, ri - 6), min(len(full_text), ri + 7)):
        if full_text[p - 1] == " ":
          nxt_t = normalize_devanagari_for_alignment(t_clean[k + 1][:10])
          nxt_h = normalize_devanagari_for_alignment(full_text[p:p + 10])
          if nxt_t[:3] == nxt_h[:3] and (len(nxt_t) < 4 or nxt_t[:4] == nxt_h[:4]):
            best_ri = p
            snapped = True
            break
    if not snapped and not is_akshara_start(full_text, best_ri):
      for delta in (1, -1, 2, -2, 3, -3):
        cand = best_ri + delta
        if raw_cuts[-1] < cand < len(full_text) and is_akshara_start(full_text, cand):
          best_ri = cand
          break
    raw_cuts.append(best_ri)
  raw_cuts.append(len(full_text))

  slices = [full_text[a:b].strip() for a, b in zip(raw_cuts, raw_cuts[1:])]
  return slices, raw_cuts[1:-1], []


def _can_trust_iast_left(cand_base_word: str, i_l: str, ia_l: Sequence[bool]) -> bool:
  if not (ia_l and i_l):
    return False
  il_n = normalize_devanagari_for_alignment(_iast_to_devanagari_clean(i_l))
  w_n = normalize_devanagari_for_alignment(cand_base_word)
  if abs(len(il_n) - len(w_n)) > 1:
    return False
  return il_n == w_n or (
    len(il_n) >= 3 and len(w_n) >= 3 and (il_n[:3] == w_n[:3] or il_n[-3:] == w_n[-3:])
  )


def _resolve_fused_right(
  r_frag: str,
  l_frag: str,
  w_r_base: str,
  i_r: str,
  ia_r: Sequence[bool],
  can_trust_ia_r: bool,
) -> str:
  if not w_r_base:
    return r_frag
  m_tail = re.search(r"([।॥०-९0-9\s]+)$", r_frag)
  r_punct = m_tail.group(1) if m_tail else ""
  r_core = r_frag[:len(r_frag) - len(r_punct)] if r_punct else r_frag
  rb_core = strip_vedic_accents(r_core)

  if normalize_devanagari_for_alignment(rb_core[:len(w_r_base)]) == normalize_devanagari_for_alignment(w_r_base):
    if r_core.startswith("ऽ") and len(r_core) > 1 and r_core[1] in VOW_INDEP:
      return r_core[1:] + r_punct
    return r_frag
  if r_core.startswith("ऽ") and len(r_core) > 1 and r_core[1] in VOW_INDEP:
    return r_core[1:] + r_punct
  if r_core.startswith("ऽ"):
    rest_r = "अ" + r_core[1:]
    if can_trust_ia_r and ia_r[0]:
      rest_r = _add_us_udatta_first_syl(rest_r)
    elif not can_trust_ia_r and w_r_base.startswith("अ") and l_frag.count(US_UDATTA) >= 2 and l_frag.endswith(US_UDATTA):
      rest_r = _add_us_udatta_first_syl(rest_r)
    return rest_r + r_punct
  if (
    rb_core.startswith("छ")
    and w_r_base.startswith("श")
    and len(w_r_base) >= 3
    and rb_core[1:].startswith(w_r_base[1:min(4, len(w_r_base))])
  ):
    return "श" + r_core[1:] + r_punct

  w_r_cands = [w_r_base]
  i_r_deva = normalize_pada_geminates(strip_vedic_accents(_iast_to_devanagari_clean(i_r))) if i_r else ""
  if i_r_deva and i_r_deva != w_r_base:
    w_r_cands.append(i_r_deva)
  for base_cand in list(w_r_cands):
    if len(base_cand) >= 3 and base_cand[-1] in ("उ", "ऊ"):
      w_r_cands.append(base_cand[:-1] + "्व")
    elif len(base_cand) >= 3 and base_cand[-1] in ("इ", "ई"):
      w_r_cands.append(base_cand[:-1] + "्य")

  for i_skip in range(min(6, len(rb_core))):
    rem_rb = rb_core[i_skip:]
    rem_rb_noava = rem_rb.replace("ऽ", "") if (i_skip == 0 and "ऽ" in rb_core[:3]) else None
    for wr_b in w_r_cands:
      if (
        rem_rb.startswith("छ")
        and wr_b.startswith("श")
        and len(wr_b) >= 3
        and rem_rb[1:].startswith(wr_b[1:min(4, len(wr_b))])
      ):
        raw_i = 0
        while raw_i < len(r_core) and len(strip_vedic_accents(r_core[:raw_i])) < i_skip:
          raw_i += 1
        while raw_i < len(r_core) and (ALL_VEDIC_ACCENTS_RE.match(r_core[raw_i]) or r_core[raw_i] == "्"):
          raw_i += 1
        if raw_i < len(r_core) and r_core[raw_i] == "छ":
          return "श" + r_core[raw_i + 1:] + r_punct

      max_woff = 2 if wr_b[0] in VOW_INDEP else 1
      for w_off in range(min(max_woff, len(wr_b))):
        w_suf = wr_b[w_off:]
        if not w_suf:
          continue
        w_lens = [len(w_suf), max(0, len(w_suf) - 1)]
        if w_suf.endswith(("म्", "ः", "त्", "न्")):
          w_lens.append(max(0, len(w_suf) - 2))
        if w_off == 1 and len(w_suf) >= 5:
          w_lens.extend([4, 3])
        for w_len in w_lens:
          allow_vow_c = (
            i_skip <= 2
            and w_off == 1
            and wr_b[0] in VOW_INDEP
            and len(wr_b) <= 4
            and w_len == 1
            and wr_b[1] in CONS_DEVA
          )
          if w_len < min(2, len(wr_b)) and not allow_vow_c:
            continue
          sub = w_suf[:w_len]
          if len(sub) == 2 and sub.endswith("्") and not allow_vow_c and len(wr_b) > 3:
            continue
          ava_hit = bool(rem_rb_noava and rem_rb_noava.startswith(sub) and len(sub) >= 2)
          if not (rem_rb.startswith(sub) or ava_hit):
            continue
          raw_i = 0
          while raw_i < len(r_core) and len(strip_vedic_accents(r_core[:raw_i])) < i_skip:
            raw_i += 1
          while raw_i < len(r_core) and ALL_VEDIC_ACCENTS_RE.match(r_core[raw_i]):
            raw_i += 1
          skipped_piece = r_core[:raw_i]
          tail_piece = r_core[raw_i:]
          if tail_piece and (tail_piece[0] in MATRAS or tail_piece[0] == "्" or tail_piece[0] in ("᳓", "᳙", "ं", "ः", "ँ")):
            continue
          new_prefix = wr_b[:w_off]
          if not new_prefix and i_skip == 0:
            return r_core + r_punct
          cand_p = new_prefix + tail_piece
          if (can_trust_ia_r and ia_r[0]) or (not can_trust_ia_r and i_skip > 0 and US_UDATTA in skipped_piece):
            cand_p = _add_us_udatta_first_syl(cand_p)
          return cand_p + r_punct
  return r_frag


def _try_left_match(l_frag: str, cand_base_word: str, i_l: str, ia_l: Sequence[bool]) -> str | None:
  lb_core = strip_vedic_accents(l_frag)
  trust_ia_l = _can_trust_iast_left(cand_base_word, i_l, ia_l)
  if lb_core.endswith(cand_base_word):
    res = resolve_pausa_word_end(l_frag, cand_base_word)
    if trust_ia_l and not ia_l[-1]:
      res = _drop_us_udatta_last_syl(res)
    elif not trust_ia_l and cand_base_word == "स्वाहा" and res.count(US_UDATTA) >= 2 and res.endswith("हा" + US_UDATTA):
      res = _drop_us_udatta_last_syl(res)
    return res

  tail_variants = [cand_base_word]
  if "ः" in cand_base_word[:-1]:
    tail_sub = cand_base_word.split("ः")[-1]
    if len(tail_sub) >= 3:
      tail_variants.append(tail_sub)
  base_cands = [lb_core]
  if lb_core.endswith("ऽ"):
    base_cands.insert(0, lb_core[:-1])
  for c_init in list(base_cands):
    if len(c_init) >= 2 and c_init[-1] in MATRAS:
      base_cands.append(c_init[:-1])
  for c_init in list(base_cands):
    if c_init.endswith("र") and cand_base_word.endswith("ः") and len(c_init) >= 2:
      base_cands.append(c_init[:-1])
    elif c_init.endswith("्य") and cand_base_word.endswith(("ि", "ी")) and len(c_init) >= 3:
      base_cands.append(c_init[:-2])
    elif c_init.endswith("्व") and cand_base_word.endswith(("ु", "ू")) and len(c_init) >= 3:
      base_cands.append(c_init[:-2])

  pref_list: list[tuple[str, str, bool]] = []
  for tv in tail_variants:
    min_plen = max(2, len(tv) - 4)
    for p_len in range(len(tv), min_plen - 1, -1):
      pref_list.append((tv[:p_len], tv[p_len:], False))
    if tv.startswith("अ") and len(tv) >= 3:
      for p_len in range(len(tv), max(2, len(tv) - 3) - 1, -1):
        pref_list.append((tv[1:p_len], tv[p_len:], True))
    elif tv and tv[0] in _VOW_TO_MATRA and len(tv) >= 3:
      m0 = _VOW_TO_MATRA[tv[0]]
      for p_len in range(len(tv), max(2, len(tv) - 3) - 1, -1):
        pref_list.append((m0 + tv[1:p_len], tv[p_len:], False))
    if tv and tv[0] in VOW_INDEP and len(tv) >= 3 and lb_core.endswith("ऽ" + tv[0]):
      pref_list.append((tv[0], tv[1:], False))

  for pref, rem_base, need_cons_before in pref_list:
    allow_short_vow_ava = len(pref) == 1 and pref in VOW_INDEP and lb_core.endswith("ऽ" + pref)
    allow_short_ah_c = need_cons_before and len(pref) == 1 and (
      (rem_base in ("ः", "म्", "त्", "न्") and (lb_core.endswith(pref + "ऽ") or lb_core.endswith(pref + "ो")))
      or (rem_base in ("ि", "ी") and lb_core.endswith(pref + "्य"))
    )
    if (len(pref) < 2 and not allow_short_ah_c and not allow_short_vow_ava) or (len(pref) < 3 and pref.endswith("्")):
      continue
    for cand_t in base_cands:
      cand_norm = cand_t
      voiced_fix = False
      if not cand_t.endswith(pref) and cand_t and cand_t[-1] in _VOICE_TO_VOICELESS:
        alt = cand_t[:-1] + _VOICE_TO_VOICELESS[cand_t[-1]]
        if alt.endswith(pref):
          cand_norm = alt
          voiced_fix = True
      elif not cand_t.endswith(pref) and pref.startswith("श") and len(cand_t) >= len(pref):
        pos_c = len(cand_t) - len(pref)
        if cand_t[pos_c] == "छ" and cand_t[pos_c + 1:] == pref[1:]:
          cand_norm = cand_t[:pos_c] + "श" + cand_t[pos_c + 1:]
      if not cand_norm.endswith(pref):
        continue
      if need_cons_before:
        b_idx = len(cand_t) - len(pref)
        if b_idx <= 0 or (
          cand_t[b_idx - 1] not in CONS_DEVA and cand_t[b_idx - 1] not in MATRAS and cand_t[b_idx - 1] != "ऽ"
        ):
          continue
      target_b = len(cand_t)
      end_raw = 0
      while end_raw < len(l_frag) and len(strip_vedic_accents(l_frag[:end_raw])) < target_b:
        end_raw += 1
      while end_raw < len(l_frag) and l_frag[end_raw] in ("᳓", "᳙", "ं", "ः", "ँ"):
        end_raw += 1
      prefix_kept = l_frag[:end_raw]
      dropped_acc = ""
      if rem_base and (rem_base[0] == "्" or rem_base[0] in MATRAS):
        m_acc = re.search(r"([᳓᳙॒॑]+)$", prefix_kept)
        if m_acc:
          if rem_base[0] in MATRAS:
            dropped_acc = m_acc.group(1)
          prefix_kept = prefix_kept[:m_acc.start()]
      if rem_base == "म्" and prefix_kept.endswith(("ं", "ँ")):
        prefix_kept = prefix_kept[:-1]
      if voiced_fix and rem_base == "्":
        prefix_kept = prefix_kept[:-1] + _VOICE_TO_VOICELESS.get(prefix_kept[-1], prefix_kept[-1])
      cand_l = resolve_pausa_word_end(prefix_kept + rem_base + dropped_acc, cand_base_word)
      if trust_ia_l:
        if not ia_l[-1]:
          cand_l = _drop_us_udatta_last_syl(cand_l)
        else:
          syls = syllable_char_spans(cand_l)
          if syls and US_UDATTA not in syls[-1][3]:
            _, el, _, _ = syls[-1]
            cand_l = cand_l[:el] + US_UDATTA + cand_l[el:]
      elif cand_base_word == "स्वाहा" and cand_l.count(US_UDATTA) >= 2 and cand_l.endswith("हा" + US_UDATTA):
        cand_l = _drop_us_udatta_last_syl(cand_l)
      return cand_l
  return None


def _resolve_fused_seam(l_frag: str, r_frag: str, p_l: str, p_r: str, i_l: str, i_r: str) -> tuple[str, str]:
  if not p_l and i_l:
    p_l = _iast_to_devanagari_clean(i_l)
  if not p_r and i_r:
    p_r = _iast_to_devanagari_clean(i_r)
  w_l_base = normalize_pada_geminates(strip_vedic_accents(p_l)) if p_l else ""
  w_r_base = normalize_pada_geminates(strip_vedic_accents(p_r)) if p_r else ""
  ia_l = iast_word_udattas(i_l) if i_l else []
  ia_r = iast_word_udattas(i_r) if i_r else []
  w_r_n = normalize_devanagari_for_alignment(w_r_base) if w_r_base else ""
  i_r_n = normalize_devanagari_for_alignment(_iast_to_devanagari_clean(i_r)) if i_r else ""
  can_trust_ia_r = bool(ia_r and i_r_n and w_r_n and i_r_n.startswith(w_r_n[:min(3, len(w_r_n))]))

  new_r = _resolve_fused_right(r_frag, l_frag, w_r_base, i_r, ia_r, can_trust_ia_r)

  new_l = l_frag
  if strip_vedic_accents(l_frag) == "मऽ" and (w_l_base in ("मे", "च") or i_l == "ma"):
    new_l = re.sub(r"^म([᳓᳙]*)ऽ$", r"मे\1", l_frag)
  elif w_l_base:
    got_l = _try_left_match(l_frag, w_l_base, i_l, ia_l)
    if got_l is None:
      pausa_l = resolve_pausa_word_end(l_frag, w_l_base)
      if pausa_l != l_frag:
        got_l = pausa_l
    if got_l is None and i_l:
      i_l_deva = normalize_pada_geminates(strip_vedic_accents(_iast_to_devanagari_clean(i_l)))
      pl_wrong = not (w_l_base and normalize_devanagari_for_alignment(w_l_base)[:2] in normalize_devanagari_for_alignment(l_frag))
      if i_l_deva and i_l_deva != w_l_base and (
        pl_wrong
        or len(normalize_devanagari_for_alignment(i_l_deva)) <= len(normalize_devanagari_for_alignment(w_l_base)) + 1
      ):
        got_l = _try_left_match(l_frag, i_l_deva, i_l, ia_l)
    new_l = resolve_pausa_word_end(got_l if got_l is not None else l_frag, w_l_base)
  if (
    not w_l_base.endswith("ः")
    and r_frag.startswith("ऽ")
    and re.search(r"ो([᳓᳙]*)$", new_l)
    and i_l
    and normalize_devanagari_for_alignment(_iast_to_devanagari_clean(i_l)).endswith("h")
  ):
    new_l = re.sub(r"ो([᳓᳙]*)$", r"ः\1", new_l)
    if ia_l and not ia_l[-1]:
      new_l = _drop_us_udatta_last_syl(new_l)
  return new_l, new_r


def _resolve_space_seam_edges(
  w_l: str,
  w_r: str,
  p_l: str,
  p_r: str,
  i_l: str,
  i_r: str,
  *,
  adjust_left_udatta: bool,
) -> tuple[str, str]:
  """Resolve space-separated boundary words across an inter-block seam (avagraha / ``छ->श`` / pausa)."""
  new_l, new_r = w_l, w_r
  ia_l = iast_word_udattas(i_l) if i_l else []
  ia_r = iast_word_udattas(i_r) if i_r else []
  can_trust_ia_l = bool(
    adjust_left_udatta
    and ia_l
    and p_l
    and i_l
    and len(normalize_devanagari_for_alignment(i_l)) <= len(normalize_devanagari_for_alignment(p_l)) + 2
  )
  if new_r.startswith("ऽ"):
    if len(new_r) > 1 and new_r[1] in VOW_INDEP:
      new_r = new_r[1:]
    else:
      rest_r = "अ" + new_r[1:]
      can_accent_r = (
        not adjust_left_udatta
        and ia_r
        and ia_r[0]
        and i_r
        and p_r
        and normalize_devanagari_for_alignment(_iast_to_devanagari_clean(i_r)).startswith(
          normalize_devanagari_for_alignment(strip_vedic_accents(p_r))[:3]
        )
      )
      if (adjust_left_udatta and ia_r and ia_r[0]) or can_accent_r:
        rest_r = _add_us_udatta_first_syl(rest_r)
      new_r = rest_r
      if can_trust_ia_l and not ia_l[-1]:
        new_l = _drop_us_udatta_last_syl(new_l)
  elif p_r:
    pr_b = normalize_pada_geminates(strip_vedic_accents(p_r))
    wr_b = strip_vedic_accents(new_r)
    if wr_b.startswith("छ") and pr_b.startswith("श") and len(pr_b) >= 3 and wr_b[1:].startswith(pr_b[1:min(4, len(pr_b))]):
      new_r = "श" + new_r[1:]
  if p_l:
    new_l = resolve_pausa_word_end(new_l, strip_vedic_accents(p_l) if not adjust_left_udatta else p_l)
    if can_trust_ia_l and not ia_l[-1] and w_r.startswith("ऽ") and not new_r.startswith("ऽ"):
      new_l = _drop_us_udatta_last_syl(new_l)
  return new_l, new_r


def resolve_seam_boundaries(
  slices: Sequence[str],
  full_text: str,
  cut_positions: Sequence[int],
  pada_inner: str,
  iast_text: str = "",
  ocr_fix_lookup: Mapping[str, str] = PADA_OCR_FIX_LOOKUP,
) -> tuple[list[str], list[tuple[str, str, str]]]:
  """Resolve external sandhi/avagraha/conjunct breaks at block seams of US-accented ``slices``."""
  if len(slices) <= 1:
    return list(slices), []
  out = list(slices)
  logs: list[tuple[str, str, str]] = []
  get_at = build_cut_lookup(full_text, pada_inner, iast_text, ocr_fix_lookup=ocr_fix_lookup)
  for k, ri in enumerate(cut_positions):
    tok_fused = 0 < ri < len(full_text) and full_text[ri - 1] not in (" ", "।") and full_text[ri] != " "
    p_l, p_r, i_l, i_r = get_at(ri)
    m_l = re.match(r"^(.*?)(\S+?)([।]*)$", out[k])
    m_r = re.match(r"^(\S+)(.*)$", out[k + 1])
    if not m_l or not m_r:
      continue
    pref_l, w_l, punct_l = m_l.groups()
    w_r, suf_r = m_r.groups()
    old_pair = f"{w_l}{punct_l} | {w_r}"
    if tok_fused:
      new_w_l, new_w_r = _resolve_fused_seam(w_l, w_r, p_l, p_r, i_l, i_r)
    else:
      new_w_l, new_w_r = _resolve_space_seam_edges(w_l, w_r, p_l, p_r, i_l, i_r, adjust_left_udatta=True)
    out[k] = pref_l + new_w_l + punct_l
    out[k + 1] = new_w_r + suf_r
    new_w_l_disp = out[k].split()[-1] if out[k].split() else ""
    new_w_r_disp = out[k + 1].split()[0] if out[k + 1].split() else ""
    new_pair = f"{new_w_l_disp} | {new_w_r_disp}"
    if old_pair != new_pair or tok_fused:
      logs.append((old_pair, new_pair, "FUSED" if tok_fused else "SPACE"))
  return out, logs


def _toks_norm_spans(toks: Sequence[str]) -> tuple[list[tuple[int, int, int, str, str]], int]:
  spans: list[tuple[int, int, int, str, str]] = []
  acc = 0
  for idx, tk in enumerate(toks):
    nt = normalize_devanagari_for_alignment(tk)
    spans.append((idx, acc, acc + len(nt), tk, nt))
    acc += len(nt)
  return spans, acc


def _compute_mula_ak_cuts(toks: Sequence[str], vps: Sequence[str]) -> tuple[list[tuple[int, int]], list[str]]:
  spans, total_m = _toks_norm_spans(toks)
  m_norm = "".join(s[4] for s in spans)
  vn = [normalize_devanagari_for_alignment(strip_danda_number(v)) for v in vps]
  v_norm = "".join(vn)
  opcodes = difflib.SequenceMatcher(None, v_norm, m_norm, autojunk=False).get_opcodes()

  def _map_v_to_m(vx: int) -> int:
    for tag, i1, i2, j1, j2 in opcodes:
      if i1 <= vx <= i2:
        if tag == "equal":
          return j1 + (vx - i1)
        if i2 > i1:
          return j1 + round((vx - i1) * (j2 - j1) / (i2 - i1))
        return round((j1 + j2) / 2)
    return len(m_norm)

  cut_m_coords: list[int] = []
  acc_v = 0
  for k in range(len(vps) - 1):
    acc_v += len(vn[k])
    mc = max(0, min(total_m, _map_v_to_m(acc_v)))
    if cut_m_coords and mc < cut_m_coords[-1]:
      mc = cut_m_coords[-1]
    cut_m_coords.append(mc)

  resolved_cuts: list[tuple[int, int]] = []
  for k, mc in enumerate(cut_m_coords):
    snapped_edge = None
    for idx, m1, _, _, nt in spans:
      if abs(m1 - mc) <= 2:
        nxt_v = vn[k + 1][:4] if vn[k + 1] else ""
        prv_v = vn[k][-4:] if vn[k] else ""
        if (nxt_v and nt.startswith(nxt_v[:2])) or (idx > 0 and prv_v and spans[idx - 1][4].endswith(prv_v[-2:])):
          snapped_edge = (idx, 0)
          break
    if not snapped_edge and abs(total_m - mc) <= 2:
      snapped_edge = (len(toks), 0)
    if snapped_edge:
      if resolved_cuts and snapped_edge < resolved_cuts[-1]:
        snapped_edge = resolved_cuts[-1]
      resolved_cuts.append(snapped_edge)
    else:
      t_hit = next((idx for idx, m1, m2, _, _ in spans if m1 < mc < m2), None)
      if t_hit is None:
        best_t = min(range(len(spans) + 1), key=lambda i: abs((spans[i][1] if i < len(spans) else total_m) - mc))
        resolved_cuts.append((best_t, 0))
      else:
        resolved_cuts.append((t_hit, -(mc - spans[t_hit][1])))

  by_tok: dict[int, list[tuple[int, int]]] = {}
  for k, (ti, off) in enumerate(resolved_cuts):
    if off < 0:
      by_tok.setdefault(ti, []).append((k, -off))

  ak_cuts = [(ti, 0 if co == 0 else -1) for ti, co in resolved_cuts]
  flags: list[str] = []
  for ti, items in by_tok.items():
    tk = toks[ti]
    ak = split_aksharas(tk)
    pieces_norm = [len(normalize_devanagari_for_alignment("".join(ak[:a_i]))) for a_i in range(len(ak) + 1)]
    last_edge = 0
    for k, rel_m in items:
      best_a = min(
        range(last_edge, len(ak) + 1),
        key=lambda a_i: (abs(pieces_norm[a_i] - rel_m), 1 if (a_i == 0 or a_i == len(ak)) else 0),
      )
      char_off = len("".join(ak[:best_a]))
      ak_cuts[k] = (ti, best_a)
      last_edge = best_a
      flags.append(f"mul_cut:{tk[:char_off]}|{tk[char_off:]}")
  return ak_cuts, flags


def _slice_from_ak_cuts(toks: Sequence[str], ak_cuts: Sequence[tuple[int, int]]) -> tuple[list[str], list[tuple[int, int]]]:
  char_cuts: list[tuple[int, int]] = []
  for ti, ai in ak_cuts:
    if ai <= 0 or ti >= len(toks):
      char_cuts.append((ti, 0))
    else:
      ak = split_aksharas(toks[ti])
      char_cuts.append((ti, len("".join(ak[:min(ai, len(ak))]))))
  pts = [(0, 0)] + char_cuts + [(len(toks), 0)]
  out: list[str] = []
  for (t1, c1), (t2, c2) in zip(pts, pts[1:]):
    if (t1, c1) == (t2, c2):
      out.append("")
      continue
    if t1 == t2:
      out.append(toks[t1][c1:c2])
    else:
      parts = []
      if c1 < len(toks[t1]):
        parts.append(toks[t1][c1:])
      for mid in range(t1 + 1, t2):
        parts.append(toks[mid])
      if t2 < len(toks) and c2 > 0:
        parts.append(toks[t2][:c2])
      out.append(" ".join(parts))
  return out, char_cuts


def slice_mula_verbatim(hmul: str, raw_slices: Sequence[str]) -> tuple[list[str], list[str]]:
  """Split ``hmul`` strictly monotonically at akṣara edges without modifying any character."""
  toks = re.findall(r"\S+", hmul)
  if len(raw_slices) <= 1:
    return [" ".join(toks)] if toks else [hmul], []
  ak_cuts, flags = _compute_mula_ak_cuts(toks, raw_slices)
  out_slices, _ = _slice_from_ak_cuts(toks, ak_cuts)
  if re.sub(r"\s+", "", "".join(out_slices)) != re.sub(r"\s+", "", "".join(toks)):
    raise ValueError("Verbatim मूलम् slice concatenation mismatch")
  return out_slices, flags


def resolve_mula_seams(
  hmul: str,
  raw_slices: Sequence[str],
  resolved_vps: Sequence[str],
  pada_inner: str,
  iast_text: str = "",
  ocr_fix_lookup: Mapping[str, str] = PADA_OCR_FIX_LOOKUP,
) -> list[str]:
  """Partition ``hmul`` per ``raw_slices`` while resolving sandhi and dependent accents only at seams.

  All interior non-seam words preserve original ``hmul`` orthography and dependent accents verbatim.
  """
  toks = re.findall(r"\S+", hmul)
  hm_norm_sp = " ".join(toks)
  if len(raw_slices) <= 1:
    return [hm_norm_sp] if toks else [hmul]

  hm_us = dependent_to_us_preserving(hm_norm_sp)
  toks_us = hm_us.split(" ")
  ak_cuts, _ = _compute_mula_ak_cuts(toks, raw_slices)
  dep_slices, _ = _slice_from_ak_cuts(toks, ak_cuts)
  if re.sub(r"\s+", "", "".join(dep_slices)) != re.sub(r"\s+", "", "".join(toks)):
    raise ValueError("मूलम् slice concatenation mismatch before seam fix")
  if len(toks_us) != len(toks):
    return dep_slices

  ak_cuts_u: list[tuple[int, int]] = []
  for ti, ai in ak_cuts:
    if ai > 0 and ti < len(toks) and len(split_aksharas(toks[ti])) != len(split_aksharas(toks_us[ti])):
      rel_m = len(normalize_devanagari_for_alignment("".join(split_aksharas(toks[ti])[:ai])))
      aku = split_aksharas(toks_us[ti])
      pu = [len(normalize_devanagari_for_alignment("".join(aku[:j]))) for j in range(len(aku) + 1)]
      ai_u = min(range(len(aku) + 1), key=lambda j: abs(pu[j] - rel_m))
      ak_cuts_u.append((ti, ai_u))
    else:
      ak_cuts_u.append((ti, ai))
  us_slices, char_cuts_u = _slice_from_ak_cuts(toks_us, ak_cuts_u)

  tok_starts_us: list[int] = []
  pos = 0
  for tok in toks_us:
    tok_starts_us.append(pos)
    pos += len(tok) + 1
  cuts_us = [tok_starts_us[ti] + co if ti < len(toks_us) else len(hm_us) for ti, co in char_cuts_u]
  get_at = build_cut_lookup(hm_us, pada_inner, iast_text, ocr_fix_lookup=ocr_fix_lookup)

  out_dep = list(dep_slices)
  out_us = list(us_slices)
  for k, ri in enumerate(cuts_us):
    tok_fused = 0 < ri < len(hm_us) and hm_us[ri - 1] not in (" ", "।") and hm_us[ri] != " "
    m_l = re.match(r"^(.*?)(\S+?)([।]*)$", out_us[k])
    m_r = re.match(r"^(\S+)(.*)$", out_us[k + 1])
    m_ld = re.match(r"^(.*?)(\S+?)([।]*)$", out_dep[k])
    m_rd = re.match(r"^(\S+)(.*)$", out_dep[k + 1])
    if not (m_l and m_r and m_ld and m_rd):
      continue
    pref_l, w_l_u, punc_l = m_l.groups()
    w_r_u, suf_r = m_r.groups()
    pref_ld, _, punc_ld = m_ld.groups()
    _, suf_rd = m_rd.groups()

    p_l, p_r, i_l, i_r = get_at(ri)
    vp_w_l = normalize_pada_geminates(strip_vedic_accents(resolved_vps[k].split()[-1].rstrip("।"))) if resolved_vps[k].split() else ""
    vp_w_r = normalize_pada_geminates(strip_vedic_accents(resolved_vps[k + 1].split()[0])) if resolved_vps[k + 1].split() else ""

    if tok_fused:
      new_w_l_u, new_w_r_u = _resolve_fused_seam(w_l_u, w_r_u, p_l, p_r, i_l, i_r)
      w_r_b = strip_vedic_accents(new_w_r_u)
      need_retry = (
        w_r_b.startswith(("र्", "ञ्", "न्त्", "न्न"))
        or (
          vp_w_r
          and normalize_devanagari_for_alignment(w_r_b)[:2] != normalize_devanagari_for_alignment(vp_w_r)[:2]
          and not normalize_devanagari_for_alignment(w_r_b).startswith("छ")
        )
        or (
          new_w_l_u == w_l_u
          and vp_w_l
          and normalize_devanagari_for_alignment(w_l_u)[-2:] != normalize_devanagari_for_alignment(vp_w_l)[-2:]
        )
      )
      if need_retry and (vp_w_l or vp_w_r):
        alt_l, alt_r = _resolve_fused_seam(w_l_u, w_r_u, vp_w_l or p_l, vp_w_r or p_r, i_l, i_r)
        if alt_r != new_w_r_u or new_w_r_u == w_r_u:
          new_w_r_u = alt_r
        if alt_l != new_w_l_u or new_w_l_u == w_l_u:
          new_w_l_u = alt_l
    else:
      new_w_l_u, new_w_r_u = _resolve_space_seam_edges(
        w_l_u,
        w_r_u,
        p_l or vp_w_l,
        p_r or vp_w_r,
        i_l,
        i_r,
        adjust_left_udatta=False,
      )

    if new_w_l_u != w_l_u:
      new_w_l_d = us_to_dependent_word(pref_l.strip().split()[-1:] + [new_w_l_u], -1)
      out_us[k] = pref_l + new_w_l_u + punc_l
      out_dep[k] = pref_ld + new_w_l_d + punc_ld
    if new_w_r_u != w_r_u:
      new_w_r_d = us_to_dependent_word([new_w_r_u] + suf_r.strip().split()[:1], 0)
      out_us[k + 1] = new_w_r_u + suf_r
      out_dep[k + 1] = new_w_r_d + suf_rd
  return out_dep


def partition_padapatha_dp(pada_inner: str, clauses: Sequence[str]) -> tuple[list[str] | None, list[str]]:
  """Partition ``pada_inner`` groups monotonically across ``clauses`` using DP alignment."""
  raw_groups = parse_pada_groups(pada_inner)
  if not raw_groups:
    return None, ["pada-empty"]

  groups: list[str] = []
  for g in raw_groups:
    if "इति" not in g and "ऽ" not in g and " " in g.strip() and not _DIGRUN_RE.match(g):
      parts_g = g.strip().split()
      if len(parts_g) >= 2 and not any(_DIGRUN_RE.match(p) for p in parts_g[:-1]):
        groups.extend(parts_g)
        continue
    groups.append(g)

  def _degloss(g: str) -> str:
    units = [u.strip() for u in re.split(r"(?<=।)", g) if u.strip()]
    if len(units) <= 1:
      return g
    kept = [u for u in units if not is_pada_gloss_quote(u)]
    return " ".join(kept) if kept else g

  g_deglossed = [_degloss(g) for g in groups]
  gn = [_collapse_runs(normalize_devanagari_for_alignment(gd)) for gd in g_deglossed]
  g0_fz: list[str] = []
  g_l_fz: list[str] = []
  g_dig: list[bool] = []
  for g, gd in zip(groups, g_deglossed):
    g_dig.append(bool(_DIGRUN_RE.match(g)))
    t0 = gd.split()
    g0_fz.append(_coarse_phonetic_fold(normalize_devanagari_for_alignment(t0[0])) if t0 else "")
    t_l = [t for t in t0 if not _DIGRUN_RE.match(t)]
    g_l_fz.append(_coarse_phonetic_fold(normalize_devanagari_for_alignment(t_l[-1])[-4:]) if t_l else "")

  vn = [_collapse_runs(normalize_devanagari_for_alignment(v)) for v in clauses]
  v0_fz: list[str] = []
  v_l_fz: list[str] = []
  for v in clauses:
    vw = [re.sub(r"[।॥०-९0-9]+", "", w) for w in v.split()]
    vw = [w for w in vw if w]
    v0_fz.append(_coarse_phonetic_fold(normalize_devanagari_for_alignment(vw[0])) if vw else "")
    v_l_fz.append(_coarse_phonetic_fold(normalize_devanagari_for_alignment(vw[-1])[-4:]) if vw else "")

  n, m = len(clauses), len(groups)

  @functools.lru_cache(maxsize=None)
  def _score(i: int, a: int, b: int) -> float:
    if a >= b:
      return 0.0
    if not vn[i]:
      return 1e-6 if all(g_dig[k] for k in range(a, b)) else -1e8
    vw0, g0 = v0_fz[i], g0_fz[a]
    if vw0 and g0:
      vw0_pref = vw0[:max(len(g0) + 3, 5)]
      if g0 not in vw0 and vw0 not in g0 and _seq_ratio(vw0_pref, g0) < 0.35 and _seq_ratio(vw0, g0) < 0.35:
        return -1e8
    rt = "".join(gn[a:b])
    if not rt:
      return -1e8
    r = _seq_ratio(vn[i], rt)
    m_score = r * (len(vn[i]) + len(rt)) / 2
    if m_score < min(1.5, max(1.0, 0.25 * len(vn[i]))):
      return -1e8
    bonus = 0.0
    vw_l, g_l = v_l_fz[i], g_l_fz[b - 1]
    if vw_l and g_l:
      if g_l in vw_l or vw_l in g_l or _seq_ratio(vw_l, g_l) >= 0.6:
        bonus += 1.5
      else:
        bonus -= 0.8
    excess_pen = 0.12 * max(0, len(rt) - len(vn[i])) + 0.02 * abs(len(rt) - len(vn[i]))
    return m_score + bonus - excess_pen

  neg = -1e9
  psum = [0]
  for g in gn:
    psum.append(psum[-1] + len(g))
  dp = [[neg] * (m + 1) for _ in range(n + 1)]
  bt: list[list[int | None]] = [[None] * (m + 1) for _ in range(n + 1)]
  dp[0][0] = 0.0
  valid_ks = [0]
  for i in range(1, n + 1):
    max_span = 1.8 * len(vn[i - 1]) + 100
    next_valid: list[int] = []
    for j in range(m + 1):
      best, bk = neg, None
      for k in valid_ks:
        if k > j:
          break
        if psum[j] - psum[k] > max_span:
          continue
        cand_s = dp[i - 1][k] + _score(i - 1, k, j)
        if cand_s > best:
          best, bk = cand_s, k
      dp[i][j] = best
      bt[i][j] = bk
      if best > neg / 2:
        next_valid.append(j)
    valid_ks = next_valid
  if dp[n][m] <= neg / 2:
    return None, ["pada-dp-fail"]

  bounds: list[int] = []
  j = m
  for i in range(n, 0, -1):
    k = bt[i][j]
    assert k is not None
    bounds.append(j)
    j = k
  bounds.reverse()
  out: list[str] = []
  prev = 0
  for b in bounds:
    out.append(" ".join(groups[prev:b]).strip())
    prev = b
  return out, []


def parse_samhita_section(
  section_text: str,
  *,
  vp_title: str = DEFAULT_VP_TITLE,
  sarva_title: str = DEFAULT_SARVA_TITLE,
  griffith_title: str = DEFAULT_GRIFFITH_TITLE,
  mula_title: str = DEFAULT_MULA_TITLE,
  pada_title: str = DEFAULT_PADA_TITLE,
) -> ParsedSamhitaSection:
  """Parse either an unsplit or interleaved saṁhitā mantra section using shared ``<details>`` parsers."""
  lines = section_text.splitlines()
  heading = lines[0] if lines else ""
  body = "\n".join(lines[1:])
  vps: list[str] = []
  griffiths: list[str] = []
  mulas: list[str] = []
  padas: list[str] = []
  residual_blocks: list[str] = []

  for _, _, title, inner in parse_top_level_details(body):
    if title == vp_title:
      vps.append(re.sub(r"\s+", " ", inner.strip()))
    elif title == sarva_title:
      spans = get_top_level_detail_spans(inner)
      children = parse_top_level_details(inner)
      for (s_pos, e_pos), (_, _, child_title, child_body) in zip(spans, children):
        if child_title == griffith_title:
          griffiths.append(child_body.strip())
        elif child_title == mula_title:
          mulas.append(child_body.strip())
        elif child_title == pada_title:
          padas.append(child_body.strip())
        else:
          residual_blocks.append(inner[s_pos:e_pos])

  return ParsedSamhitaSection(
    heading=heading,
    vps=vps,
    griffiths=griffiths,
    mulas=mulas,
    padas=padas,
    residual_blocks=residual_blocks,
  )


def render_interleaved_samhita_section(
  heading: str,
  vps: Sequence[str],
  griffiths: Sequence[str] | None,
  mulas: Sequence[str] | None,
  padas: Sequence[str] | None,
  residual_blocks: Sequence[str] = (),
  *,
  vp_title: str = DEFAULT_VP_TITLE,
  sarva_title: str = DEFAULT_SARVA_TITLE,
  griffith_title: str = DEFAULT_GRIFFITH_TITLE,
  mula_title: str = DEFAULT_MULA_TITLE,
  pada_title: str = DEFAULT_PADA_TITLE,
) -> str:
  """Render one mantra section with per-clause interleaved ``सर्वाष् टीकाः`` and optional residual block."""
  out: list[str] = [heading]
  vp_tag = f"<details open><summary>{vp_title}</summary>"
  sarva_tag = f"<details><summary>{sarva_title}</summary>"
  gr_tag = f"<details><summary>{griffith_title}</summary>"
  mul_tag = f"<details><summary>{mula_title}</summary>"
  pada_tag = f"<details><summary>{pada_title}</summary>"

  for i, vp_text in enumerate(vps):
    out.append(f"{vp_tag}\n\n{vp_text}\n</details>\n")
    out.append(sarva_tag)
    if griffiths and i < len(griffiths) and griffiths[i]:
      out.append(f"{gr_tag}\n\n{griffiths[i]}\n</details>\n")
    if mulas and i < len(mulas) and mulas[i]:
      out.append(f"{mul_tag}\n\n{mulas[i]}\n</details>\n")
    if padas and i < len(padas) and padas[i]:
      out.append(f"{pada_tag}\n\n{padas[i]}\n</details>\n")
    out[-1] = out[-1].rstrip("\n")
    out.append("</details>\n")
  if residual_blocks:
    out.append(sarva_tag)
    for rb in residual_blocks:
      out.append(rb)
    out.append("</details>\n")
  return "\n".join(out).rstrip() + "\n\n"


def count_inline_sandhi(vps: Sequence[str]) -> dict[str, int]:
  """Count intra-block sandhi violations (``म्+C``, coronal halant+``C``, and vowel hiatus)."""
  return {
    "ma_hal": sum(len(INLINE_MA_HAL_RE.findall(vp)) for vp in vps),
    "ta_hal": sum(len(INLINE_TA_HAL_RE.findall(vp)) for vp in vps),
    "hiatus": sum(len(INLINE_HIATUS_RE.findall(vp)) for vp in vps),
  }


def _check_non_pausa_halant(word_bare: str) -> bool:
  return word_bare.endswith(("न्त्", "ङ्", "ञ्", "ण्")) or (
    word_bare.endswith("्") and len(word_bare) >= 2 and word_bare[-2] not in ("क", "ट", "त", "प", "ङ", "न", "म")
  )


def _check_clause_text_issues(
  clauses: Sequence[str],
  label: str,
  section_id: str,
) -> list[SamhitaSplitIssue]:
  issues: list[SamhitaSplitIssue] = []
  total = len(clauses)
  for idx, clause in enumerate(clauses):
    loc = f"{section_id}[{idx + 1}]"
    if not clause:
      issues.append(SamhitaSplitIssue(f"empty_{label}", f"Empty {label} block", loc))
      continue
    if clause[0] in BAD_SEAM_START_CHARS:
      issues.append(SamhitaSplitIssue(f"bad_start_{label}", f"{label} starts with invalid sign {clause[:12]!r}", loc))
    if label == "mula" and idx > 0 and REPHA_START_RE.match(strip_vedic_accents(clause)):
      issues.append(SamhitaSplitIssue("repha_start_mula", f"Repha start in मूलम्: {clause[:15]!r}", loc))
    if INVALID_A_MATRA_RE.search(clause):
      issues.append(SamhitaSplitIssue("invalid_a_matra", f"Invalid अ+mātrā in {label}: {clause!r}", loc))
    if INVALID_CONS_ACCENT_ORDER_RE.search(clause):
      issues.append(SamhitaSplitIssue("invalid_accent_order", f"Invalid C+accent+matra in {label}: {clause!r}", loc))
    if idx < total - 1:
      if clause.rstrip("।").endswith("ऽ"):
        issues.append(SamhitaSplitIssue(f"trailing_avagraha_{label}", f"Trailing ऽ at internal seam in {label}", loc))
      last_w = strip_vedic_accents(clause.split()[-1].rstrip("।"))
      if _check_non_pausa_halant(last_w):
        issues.append(SamhitaSplitIssue(f"non_pausa_halant_{label}", f"Non-pausa halant end {last_w!r} in {label}", loc))
  return issues


def validate_samhita_section(
  section_text: str,
  section_id: str = "",
  *,
  original_section: str | None = None,
  original_mula_fixed: str | None = None,
  original_pada_fixed: str | None = None,
  check_griffith: bool = True,
  check_pada_concat: bool = True,
  allow_empty_pada: bool = False,
  vp_title: str = DEFAULT_VP_TITLE,
  sarva_title: str = DEFAULT_SARVA_TITLE,
  griffith_title: str = DEFAULT_GRIFFITH_TITLE,
  mula_title: str = DEFAULT_MULA_TITLE,
  pada_title: str = DEFAULT_PADA_TITLE,
) -> list[SamhitaSplitIssue]:
  """Validate structure, seam integrity, interior preservation, and parity of one saṁhitā section."""
  issues: list[SamhitaSplitIssue] = []
  if section_text.count("<details") != section_text.count("</details>") or section_text.count("<div") != section_text.count("</div>"):
    issues.append(SamhitaSplitIssue("tag_unbalanced", "Mismatched <details> or <div> tags", section_id))
    return issues

  if original_section is not None and "js_include" in original_section:
    if section_text != original_section:
      issues.append(SamhitaSplitIssue("js_include_altered", "js_include section was altered", section_id))
    return issues
  if "js_include" in section_text:
    return issues

  parsed = parse_samhita_section(
    section_text,
    vp_title=vp_title,
    sarva_title=sarva_title,
    griffith_title=griffith_title,
    mula_title=mula_title,
    pada_title=pada_title,
  )
  body = "\n".join(section_text.splitlines()[1:])
  top_parsed = parse_top_level_details(body)
  i = 0
  sarva_children: list[list[tuple[str, str]]] = []
  while i < len(top_parsed) and top_parsed[i][2] == vp_title:
    if i + 1 >= len(top_parsed) or top_parsed[i + 1][2] != sarva_title:
      issues.append(SamhitaSplitIssue("bad_pairing", f"{vp_title} block not followed by {sarva_title}", section_id))
      return issues
    sarva_children.append([(t, b.strip()) for _, _, t, b in parse_top_level_details(top_parsed[i + 1][3])])
    i += 2
  trailing = top_parsed[i:]
  if not parsed.vps or len(sarva_children) != len(parsed.vps):
    issues.append(SamhitaSplitIssue("bad_pairing", f"Unpaired VP/sarva blocks: vp={len(parsed.vps)} sarva={len(sarva_children)}", section_id))
    return issues

  for idx, kids in enumerate(sarva_children):
    loc = f"{section_id}[{idx + 1}]"
    by_name = dict(kids)
    if mula_title not in by_name:
      issues.append(SamhitaSplitIssue("missing_mula", f"Missing {mula_title} block", loc))
    for nm, val in kids:
      if not val:
        issues.append(SamhitaSplitIssue("empty_child", f"Empty child block {nm}", loc))
    if not allow_empty_pada and pada_title not in by_name and parsed.padas:
      issues.append(SamhitaSplitIssue("empty_pada_slot", f"Missing {pada_title} in block", loc))

  issues.extend(_check_clause_text_issues(parsed.vps, "vp", section_id))
  issues.extend(_check_clause_text_issues(parsed.mulas, "mula", section_id))

  if check_griffith and parsed.griffiths and len(parsed.griffiths) != len(parsed.vps):
    issues.append(
      SamhitaSplitIssue(
        "griffith_count_mismatch",
        f"Griffith count ({len(parsed.griffiths)}) != VP count ({len(parsed.vps)})",
        section_id,
      )
    )
  if check_griffith:
    for idx, gr in enumerate(parsed.griffiths):
      if len(gr) < 3 or re.search(r"\b(?:[IVXLCDM]{2,}|[XVLC]|Ch)\.$", gr):
        issues.append(SamhitaSplitIssue("griffith_truncated", f"Suspicious Griffith ending: {gr[-30:]!r}", f"{section_id}[{idx + 1}]"))

  if original_section is not None:
    orig = parse_samhita_section(
      original_section,
      vp_title=vp_title,
      sarva_title=sarva_title,
      griffith_title=griffith_title,
      mula_title=mula_title,
      pada_title=pada_title,
    )
    if section_text.splitlines()[0] != orig.heading:
      issues.append(SamhitaSplitIssue("heading_changed", f"Heading changed from {orig.heading!r}", section_id))
    if orig.residual_blocks:
      if len(trailing) != 1 or trailing[0][2] != sarva_title:
        issues.append(SamhitaSplitIssue("residual_missing", f"Residual {sarva_title} missing", section_id))
      else:
        tr_body = trailing[0][3]
        got_res = [tr_body[s:e] for s, e in get_top_level_detail_spans(tr_body)]
        if got_res != orig.residual_blocks:
          issues.append(SamhitaSplitIssue("residual_altered", "Residual commentary blocks altered", section_id))
    elif trailing:
      issues.append(SamhitaSplitIssue("unexpected_trailing", f"Unexpected trailing blocks: {[t[2] for t in trailing]}", section_id))

    orig_mula = original_mula_fixed if original_mula_fixed is not None else orig.mula_full
    orig_mula_sp = " ".join(re.findall(r"\S+", orig_mula))
    for idx, ms in enumerate(parsed.mulas):
      toks_m = ms.split()
      if len(toks_m) >= 3:
        mid = " ".join(toks_m[1:-1])
        if mid not in orig_mula_sp:
          issues.append(SamhitaSplitIssue("mula_interior_altered", f"Interior मूलम् altered: {mid[:30]!r}", f"{section_id}[{idx + 1}]"))
    if len(parsed.mulas) == 1 and re.sub(r"\s+", "", parsed.mulas[0]) != re.sub(r"\s+", "", orig_mula):
      issues.append(SamhitaSplitIssue("single_mula_mismatch", "Single-block मूलम् differs from source", section_id))

    if check_pada_concat:
      orig_pada = original_pada_fixed if original_pada_fixed is not None else orig.pada_full
      if re.sub(r"\s+", "", "".join(parsed.padas)) != re.sub(r"\s+", "", orig_pada):
        issues.append(SamhitaSplitIssue("pada_concat_mismatch", "पदपाठः concatenation differs from source", section_id))

    orig_sc = count_inline_sandhi(orig.vps)
    cur_sc = count_inline_sandhi(parsed.vps)
    if any(cur_sc[k] > orig_sc[k] for k in orig_sc):
      issues.append(SamhitaSplitIssue("inline_sandhi_regression", f"Inline sandhi regression: {orig_sc} -> {cur_sc}", section_id))

  return issues


def validate_samhita_markdown(
  md_text: str,
  *,
  original_md_text: str | None = None,
  doc_id: str = "",
  mula_fixes_by_section: Mapping[int, str] | None = None,
  pada_fixes_by_section: Mapping[int, str] | None = None,
  check_griffith: bool = True,
  check_pada_concat: bool = True,
  allow_empty_pada: bool = False,
) -> list[SamhitaSplitIssue]:
  """Validate a complete chapter/file of split saṁhitā sections."""
  issues: list[SamhitaSplitIssue] = []
  if md_text.count("<details") != md_text.count("</details>") or md_text.count("<div") != md_text.count("</div>"):
    issues.append(SamhitaSplitIssue("file_tag_unbalanced", "File-level mismatched <details> or <div>", doc_id))

  cur_parts = re.split(r"(?m)^(?=## )", md_text)
  orig_parts = re.split(r"(?m)^(?=## )", original_md_text) if original_md_text is not None else None
  if orig_parts is not None:
    if len(cur_parts) != len(orig_parts):
      issues.append(
        SamhitaSplitIssue("section_count_mismatch", f"Sections {len(cur_parts) - 1} != {len(orig_parts) - 1}", doc_id)
      )
      return issues
    if cur_parts[0] != orig_parts[0]:
      issues.append(SamhitaSplitIssue("frontmatter_changed", "Frontmatter differs from original", doc_id))

  for mno in range(1, len(cur_parts)):
    sec_id = f"{doc_id}.{mno:02d}" if doc_id else f"sec_{mno:02d}"
    issues.extend(
      validate_samhita_section(
        cur_parts[mno],
        sec_id,
        original_section=orig_parts[mno] if orig_parts is not None else None,
        original_mula_fixed=(mula_fixes_by_section or {}).get(mno),
        original_pada_fixed=(pada_fixes_by_section or {}).get(mno),
        check_griffith=check_griffith,
        check_pada_concat=check_pada_concat,
        allow_empty_pada=allow_empty_pada,
      )
    )
  return issues


_PADAPATHA_UPASARGA_BASE = (
  "प्र", "परा", "अप", "सम्", "सँ", "अनु", "अव", "निस्", "निर्", "निः",
  "दुस्", "दुर्", "दुः", "वि", "नि", "अधि", "अपि", "अति", "सु", "उत्",
  "अभि", "प्रति", "परि", "उप", "आ", "अ", "अन्", "स", "कु",
)
_PADAPATHA_UPASARGA_SKIP = frozenset(
  list(_PADAPATHA_UPASARGA_BASE)
  + [
    ("अन" + _VOW_TO_MATRA.get(u[0], "") + u[1:]) if u[0] in VOW_INDEP else ("अ" + u)
    for u in _PADAPATHA_UPASARGA_BASE
    if u not in ("अ", "अन्", "स", "कु")
  ]
)
_PADAPATHA_BOUND_SUFFIX_PREFIXES = (
  "भिः", "भ्या", "भ्यः", "सु", "षु", "तम", "तर", "त्व", "ता", "मय",
  "वत्", "वति", "वती", "वन्त", "वन्", "मत्", "मति", "मती", "मन्त", "मन्",
  "इव",
)
_ACCENT_CHAR_SET = frozenset(
  "\u0951\u0952\u0953\u0954\u0957\u1cf4\u1cf8\u1cf9"
  + "".join(chr(c) for c in range(0x1CD0, 0x1CE9))
  + "\u1cdf"
  + "".join(chr(c) for c in range(0xA8E0, 0xA8F2))
)


def _trace_align_chars(text: str) -> tuple[str, list[int], list[int]]:
  """Return alignment key along with per-character raw ``[start, end)`` spans in ``text``."""
  chars: list[str] = []
  starts: list[int] = []
  ends: list[int] = []
  for i, ch in enumerate(text):
    for nc in normalize_devanagari_for_alignment(ch):
      chars.append(nc)
      starts.append(i)
      ends.append(i + 1)
  return "".join(chars), starts, ends


def _build_padapatha_seam_map(pada_inner: str) -> tuple[str, dict[int, tuple[str, str, str]]]:
  """Build normalized padapāṭha string and map aligned char indices to ``(PADA|SAMASA, left, right)``."""
  pwords = extract_padapatha_words(pada_inner, keep_avagraha=True)
  parts: list[str] = []
  bounds: dict[int, tuple[str, str, str]] = {}
  acc = 0
  prev_sub = ""
  for pw in pwords:
    pw_clean = normalize_pada_geminates(strip_vedic_accents(pw))
    subs = [sub for sub in pw_clean.split("ऽ") if sub]
    for si, sub in enumerate(subs):
      ns = normalize_devanagari_for_alignment(sub)
      if acc > 0 and ns:
        kind = "PADA" if (si == 0 or sub == "इव") else "SAMASA"
        bounds[acc] = (kind, prev_sub, sub)
      parts.append(ns)
      acc += len(ns)
      prev_sub = sub
  return "".join(parts), bounds


def _split_fused_pada_boundary(tok: str, rel_i: int, pl: str, pr: str) -> str | None:
  """Split one separable inter-pada sandhi boundary at alignment index ``rel_i`` inside ``tok``."""
  nh, st, en = _trace_align_chars(tok)
  if rel_i <= 0 or rel_i >= len(nh):
    return None
  while 0 < rel_i < len(nh) and st[rel_i] == st[rel_i - 1]:
    rel_i += 1
  if rel_i >= len(nh):
    return None
  r_prev_end = en[rel_i - 1]
  r_cur_start = st[rel_i]

  if pl.endswith(("े", "ो", "ः", "ा")) and pr.startswith("अ"):
    lo = max(1, r_prev_end - 4)
    hi = min(len(tok), r_cur_start + 5)
    cands = []
    pos_av = lo
    while True:
      pos_av = tok.find("ऽ", pos_av, hi)
      if pos_av == -1:
        break
      p_prev = pos_av - 1
      while p_prev > 0 and tok[p_prev] in _ACCENT_CHAR_SET:
        p_prev -= 1
      if tok[pos_av - 1] not in (" ", "-") and tok[p_prev] in ("े", "ो", "ा"):
        cands.append((abs(pos_av - r_prev_end), pos_av))
      pos_av += 1
    if cands:
      av_idx = min(cands)[1]
      return tok[:av_idx] + " " + tok[av_idx:]

  if pl.endswith(("म्", "ं", "न्")) and pr:
    if pr[0] in VOW_INDEP:
      want_m = "न" if pl.endswith("न्") else "म"
      lo_m = max(1, r_prev_end - 3)
      hi_m = min(len(tok), r_cur_start + 2)
      want_matra = _VOW_TO_MATRA.get(pr[0], "")
      m_cands = []
      for p in range(lo_m, hi_m):
        if tok[p] != want_m or tok[p - 1] == "-":
          continue
        after = tok[p + 1:]
        if pr[0] == "अ":
          if not after or (after[0] not in MATRAS and after[0] != "्"):
            m_cands.append((abs(p - (r_prev_end - 1)), p, after))
        elif want_matra and after and after[0] == want_matra:
          m_cands.append((abs(p - (r_prev_end - 1)), p, after))
      if m_cands:
        _, m_pos, after = min(m_cands)
        if after and after[0] in MATRAS:
          return tok[:m_pos + 1] + "् " + _MATRA_TO_INDEP[after[0]] + after[1:]
        return tok[:m_pos + 1] + "् अ" + after
    else:
      lo_n = max(1, r_prev_end - 4)
      hi_n = min(len(tok), r_cur_start + 2)
      n_cands = [
        (abs(p - (r_prev_end - 1)), p)
        for p in range(lo_n, hi_n)
        if tok[p] in ("ँ", "ं")
      ]
      for _, n_pos in sorted(n_cands):
        sp = n_pos + 1
        while sp < len(tok) and tok[sp] in _ACCENT_CHAR_SET:
          sp += 1
        if pl.endswith("न्") and pr[0] in ("त", "थ", "च", "छ"):
          want_sib = "स" if pr[0] in ("त", "थ") else "श"
          if tok[sp:sp + 2] == f"{want_sib}्" and tok[sp + 2:sp + 3] == pr[0]:
            return tok[:sp + 2] + " " + tok[sp + 2:]
        if pl.endswith("न्") and pr[0] == "ल" and tok[sp:sp + 3] == "ल्" + "ल":
          return tok[:sp + 2] + " " + tok[sp + 2:]
        if (
          sp < len(tok)
          and tok[sp] in CONS_DEVA
          and normalize_devanagari_for_alignment(tok[sp]) == normalize_devanagari_for_alignment(pr[0])
        ):
          return tok[:sp] + " " + tok[sp:]

  if pl.endswith("ः") and not pl.endswith("ो"):
    lo_r = max(1, r_prev_end - 5)
    hi_r = min(len(tok), r_cur_start + 2)
    r_cands = [
      (abs(p - (r_prev_end - 1)), p)
      for p in range(lo_r, hi_r)
      if tok[p] == "र" and tok[p - 1] not in ("्", "-")
    ]
    for _, r_pos in sorted(r_cands):
      after = tok[r_pos + 1:]
      if pr and pr[0] not in VOW_INDEP:
        if after.startswith("्") and after[1:2] == pr[0]:
          return tok[:r_pos + 2] + " " + after[1:]
      elif pr and pr[0] in VOW_INDEP and r_pos >= r_prev_end - 2:
        if after.startswith("्"):
          continue
        if pr[0] == "अ":
          if not after or (after[0] not in MATRAS and after[0] != "्"):
            return tok[:r_pos + 1] + "् अ" + after
        elif after and _MATRA_TO_INDEP.get(after[0]) == pr[0]:
          return tok[:r_pos + 1] + "् " + pr[0] + after[1:]
    r_pos = r_prev_end - 1
    while r_pos > 0 and tok[r_pos] in _ACCENT_CHAR_SET:
      r_pos -= 1
    visarga_sib_next = {
      "स": ("त", "थ", "स", "क", "ख", "प", "फ"),
      "श": ("च", "छ", "श"),
      "ष": ("ट", "ठ", "ष", "क", "ख", "प", "फ"),
    }
    if (
      0 < r_pos < len(tok)
      and tok[r_pos] in visarga_sib_next
      and tok[r_pos - 1] != "ऽ"
      and tok[r_pos + 1:r_pos + 2] == "्"
      and tok[r_pos + 2:r_pos + 3] in visarga_sib_next[tok[r_pos]]
      and pr
      and pr[0] in visarga_sib_next[tok[r_pos]]
    ):
      return tok[:r_pos + 2] + " " + tok[r_pos + 2:]

  if pr and pr[0] in VOW_INDEP and pl.endswith(("ि", "ी", "ु", "ू")):
    want_c = "य" if pl[-1] in ("ि", "ी") else "व"
    y_pos = r_prev_end - 1
    while y_pos > 0 and tok[y_pos] in _ACCENT_CHAR_SET:
      y_pos -= 1
    if 0 < y_pos < len(tok) and tok[y_pos] == want_c:
      after = tok[y_pos + 1:]
      if after and after[0] in MATRAS:
        return tok[:y_pos + 1] + "् " + _MATRA_TO_INDEP[after[0]] + after[1:]
      if not after or after[0] != "्":
        return tok[:y_pos + 1] + "् अ" + after

  if pl.endswith(("त्", "क्", "ट्", "प्", "न्")) and pr and pr[0] not in VOW_INDEP:
    _surds = ("क", "ख", "च", "छ", "ट", "ठ", "त", "थ", "प", "फ", "श", "ष", "स")
    _sonants = ("ग", "घ", "ज", "झ", "ड", "ढ", "द", "ध", "ब", "भ", "य", "र", "ल", "व")
    stop_rules = {
      "त्": {
        "त": ("त", "थ", "क", "ख", "प", "फ", "स"),
        "द": ("ग", "घ", "द", "ध", "ब", "भ", "य", "र", "ल", "व", "ह"),
        "च": ("च", "छ"),
        "ज": ("ज", "झ"),
        "ट": ("ट", "ठ"),
        "ड": ("ड", "ढ"),
        "न": ("न", "म"),
        "ल": ("ल",),
      },
      "क्": {"क": _surds, "ग": _sonants + ("ह",), "ङ": ("न", "म")},
      "ट्": {"ट": _surds, "ड": _sonants + ("ह",), "ण": ("न", "म")},
      "प्": {"प": _surds, "ब": _sonants + ("ह",), "म": ("न", "म")},
      "न्": {"न": ("न",), "ल": ("ल",)},
    }[pl[-2:]]
    special_pairs = {
      "द": ("ह", "ध"),
      "ग": ("ह", "घ"),
      "ड": ("ह", "ढ"),
      "ब": ("ह", "भ"),
      "च": ("श", "छ"),
      "ट": ("श", "छ"),
      "ण": ("न", "ण"),
    }
    lo_c = max(1, r_prev_end - 3)
    hi_c = min(len(tok) - 1, r_cur_start + 2)
    stop_cands = [
      (abs((p + 2) - r_prev_end), p)
      for p in range(lo_c, hi_c)
      if (
        tok[p - 1] != "्"
        and tok[p] in stop_rules
        and tok[p + 1:p + 2] == "्"
        and p + 2 < len(tok)
        and (
          (tok[p + 2] == pr[0] and pr[0] in stop_rules[tok[p]])
          or special_pairs.get(tok[p]) == (pr[0], tok[p + 2])
        )
      )
    ]
    if stop_cands:
      c_pos = min(stop_cands)[1]
      return tok[:c_pos + 2] + " " + tok[c_pos + 2:]

  return None


def _is_eligible_samasa_split(pl: str, pr: str, hyp_matched: bool) -> bool:
  if not pl or not pr:
    return False
  if pl in _PADAPATHA_UPASARGA_SKIP:
    return False
  if pr.startswith(_PADAPATHA_BOUND_SUFFIX_PREFIXES):
    return False
  if (pl[-1] in VOW_INDEP or pl[-1] in MATRAS) and pr[0] in VOW_INDEP:
    return False
  if hyp_matched:
    return True
  return len(pl) >= 2 and len(pr) >= 2


def _collect_hyp_cuts(orig_ws: list[str], hyp_pieces: list[str], st_all: list[int], nh_all: str) -> dict[int, tuple[str, int, int, str]]:
  """Match ``hyphene`` pieces back onto original whitespace tokens via canonical sandhi skeleton."""
  from doc_curation.llm.proofreader.guards import canonical_sandhi_skeleton

  out: dict[int, tuple[str, int, int, str]] = {}
  hi = 0
  pos = 0
  for item in orig_ws:
    end = pos + len(item)
    if not item.isspace():
      i_s = next((idx for idx, s in enumerate(st_all) if s >= pos), len(nh_all))
      i_e = next((idx for idx, s in enumerate(st_all) if s >= end), len(nh_all))
      otok_sk = canonical_sandhi_skeleton(item.replace("ऽ", "Z"))
      acc_h: list[str] = []
      start_hi = hi
      matched_h = None
      while hi < len(hyp_pieces):
        acc_h.append(hyp_pieces[hi])
        hi += 1
        cur_sk = canonical_sandhi_skeleton(" ".join(acc_h).replace("ऽ", "Z"))
        if cur_sk == otok_sk or len(cur_sk) >= len(otok_sk):
          matched_h = " ".join(acc_h)
          break
      if matched_h is None:
        matched_h = item
        hi = start_hi + 1
      out[pos] = (matched_h, i_s, i_e, item)
    pos = end
  return out


def _restore_visarga_on_token(tok: str) -> str:
  """Insert ``ः`` before any trailing accents and daṇḍa/numeral punctuation."""
  p_idx = len(tok)
  while p_idx > 0 and tok[p_idx - 1] in "।॥०१२३४५६७८९":
    p_idx -= 1
  a_idx = p_idx
  while a_idx > 0 and tok[a_idx - 1] in _ACCENT_CHAR_SET:
    a_idx -= 1
  if a_idx > 0 and tok[a_idx - 1] == "ः":
    return tok
  return tok[:a_idx] + "ः" + tok[a_idx:p_idx] + tok[p_idx:]


def _restore_padapatha_dropped_visargas(text: str, pada_inner: str) -> str:
  """Restore padapāṭha-attested visargas dropped before ``स/श/ष+्`` or at clause end."""
  jn_p, j_bounds = _build_padapatha_seam_map(pada_inner)
  pwords = extract_padapatha_words(pada_inner)
  if not jn_p or not pwords:
    return text

  nh, st, _ = _trace_align_chars(text)
  j2i = banded_monotonic_align(nh, jn_p)
  if j2i is None:
    return text

  ws = re.findall(r"\S+|\s+", text)
  tok_info: list[tuple[int, str, int, int]] = []
  pos = 0
  for idx_ws, item in enumerate(ws):
    end = pos + len(item)
    if not item.isspace():
      i_s = next((x for x, sp in enumerate(st) if sp >= pos), len(nh))
      i_e = next((x for x, sp in enumerate(st) if sp >= end), len(nh))
      tok_info.append((idx_ws, item, i_s, i_e))
    pos = end

  for ti in range(len(tok_info) - 1):
    idx_ws, tok, i_s, i_e = tok_info[ti]
    _, ntok, ni_s, _ = tok_info[ti + 1]
    ntb = strip_vedic_accents(ntok).lstrip("ऽ")
    if len(ntb) < 2 or ntb[0] not in ("स", "श", "ष") or ntb[1] != "्":
      continue
    tb = strip_vedic_accents(tok).rstrip("।॥०१२३४५६७८९")
    if not tb or tb[-1] in ("ः", "र्", "्", "ो", "र"):
      continue
    tb_clean = tb.replace("-", "").replace("ऽ", "")
    for j, (kind, pl, pr) in sorted(j_bounds.items()):
      iv = j2i[j]
      if (
        kind == "PADA"
        and i_e <= iv <= ni_s
        and pl.endswith("ः")
        and pl not in ("सः", "एषः")
        and len(pr) >= 2
        and pr[0] in ("स", "श", "ष")
        and pr[1] == "्"
      ):
        pl_stem = pl[:-1]
        sfx = pl_stem[-2:] if len(pl_stem) >= 2 else pl_stem
        if tb_clean.endswith(sfx):
          ws[idx_ws] = _restore_visarga_on_token(tok)
          break

  # Clause-final pausa visarga restoration (after clause splits before voiced/consonant words)
  if pwords[-1].endswith("ः"):
    for idx_ws, tok, _, _ in reversed(tok_info):
      tb = strip_vedic_accents(tok).rstrip("।॥०१२३४५६७८९")
      if not tb:
        continue
      if tb[-1] not in ("ः", "र्", "्", "ो"):
        pw_stem = normalize_pada_geminates(strip_vedic_accents(pwords[-1]))[:-1]
        sfx = pw_stem[-2:] if len(pw_stem) >= 2 else pw_stem
        if tb.replace("-", "").replace("ऽ", "").endswith(sfx):
          ws[idx_ws] = _restore_visarga_on_token(tok)
      break

  return "".join(ws)


def hyphenate_samhita_with_padapatha(vp_text: str, pada_inner: str = "") -> str:
  """Hyphenate Vedic saṁhitā text with ``hyphene`` while guarding and guiding cuts via ``पदपाठः``."""
  from doc_curation.llm.proofreader.guards import (
    canonical_sandhi_skeleton,
    rejoin_merger_violations,
  )
  from doc_curation.sanskrit.hyphenator import hyphene

  if not vp_text or not vp_text.strip():
    return vp_text
  if not pada_inner.strip() or "+++" in vp_text:
    return hyphene(vp_text, clause_newlines=False)

  jn_p, j_bounds = _build_padapatha_seam_map(pada_inner)
  if not jn_p:
    return hyphene(vp_text, clause_newlines=False)

  nh_all, st_all, _ = _trace_align_chars(vp_text)
  j2i = banded_monotonic_align(nh_all, jn_p)
  if j2i is None:
    return hyphene(vp_text, clause_newlines=False)

  hyp_text = hyphene(vp_text, clause_newlines=False)
  orig_ws = re.findall(r"\S+|\s+", vp_text)
  hyp_pieces = re.findall(r"\S+", hyp_text)
  matched_map = _collect_hyp_cuts(orig_ws, hyp_pieces, st_all, nh_all)

  out: list[str] = []
  pos = 0
  for item in orig_ws:
    end = pos + len(item)
    if item.isspace():
      out.append(item)
      pos = end
      continue

    matched_h, i_s, i_e, otok = matched_map[pos]
    inner_bnds: list[tuple[int, str, str, str]] = []
    for j, (kind, pl, pr) in sorted(j_bounds.items()):
      iv = j2i[j]
      if i_s < iv < i_e:
        inner_bnds.append((iv - i_s, kind, pl, pr))

    if not inner_bnds:
      out.append(otok)
      pos = end
      continue

    seg_parts = re.split(r"([ \-–])", matched_h)
    hyp_cut_norms: set[int] = set()
    if len(seg_parts) > 1:
      cum = 0
      for idx_p in range(0, len(seg_parts) - 1, 2):
        cum += len(normalize_devanagari_for_alignment(seg_parts[idx_p]))
        hyp_cut_norms.add(cum)

    cur_tok = otok
    for rel_i, kind, pl, pr in sorted(inner_bnds, key=lambda x: -x[0]):
      if kind == "PADA":
        if pl in _PADAPATHA_UPASARGA_SKIP and pr != "इव":
          continue
        cand = _split_fused_pada_boundary(cur_tok, rel_i, pl, pr)
        if cand and canonical_sandhi_skeleton(cand) == canonical_sandhi_skeleton(cur_tok):
          if rejoin_merger_violations(cur_tok, cand) == cand:
            cur_tok = cand
      else:
        hyp_hit = any(abs(c - rel_i) <= 1 for c in hyp_cut_norms)
        if not _is_eligible_samasa_split(pl, pr, hyp_hit):
          continue
        nh_c, st_c, _ = _trace_align_chars(cur_tok)
        rel_s = rel_i
        while 0 < rel_s < len(nh_c) and st_c[rel_s] == st_c[rel_s - 1]:
          rel_s += 1
        if 0 < rel_s < len(nh_c):
          r_p = st_c[rel_s]
          if (
            0 < r_p < len(cur_tok)
            and cur_tok[r_p] in (CONS_DEVA | VOW_INDEP)
            and cur_tok[r_p - 1] not in ("-", "–", " ", "ऽ")
            and not (cur_tok[r_p - 1] == "्" and pl[-1] not in ("्", "ः", "ं"))
          ):
            cand = cur_tok[:r_p] + "-" + cur_tok[r_p:]
            if (
              rejoin_merger_violations(cur_tok, cand) == cand
              and canonical_sandhi_skeleton(cand) == canonical_sandhi_skeleton(cur_tok)
            ):
              cur_tok = cand

    out.append(cur_tok)
    pos = end
  return _restore_padapatha_dropped_visargas("".join(out), pada_inner)


def _rewrite_details_body(text: str, span_replacements: list[tuple[int, int, str]]) -> str:
  """Apply non-overlapping ``(start, end, replacement)`` edits from right to left."""
  out = text
  for start, end, rep in sorted(span_replacements, key=lambda x: -x[0]):
    out = out[:start] + rep + out[end:]
  return out


def normalize_mAdhyandina_markdown(
  md_text: str,
  *,
  hyphenate_vp: bool = False,
  skip_js_include: bool = True,
  vp_title: str = DEFAULT_VP_TITLE,
  sarva_title: str = DEFAULT_SARVA_TITLE,
  mula_title: str = DEFAULT_MULA_TITLE,
  pada_title: str = DEFAULT_PADA_TITLE,
) -> str:
  """Normalize non-include Mādhyandina sections across a saṁhitā Markdown file.

  - Inside ``विश्वास-प्रस्तुतिः``: runs :func:`normalize_mAdhyandina` with pre-vowel
    avagraha expansion, and optionally :func:`hyphenate_samhita_with_padapatha` using the
    paired ``पदपाठः - दयानन्दादि`` block.
  - Inside ``मूलम्`` and ``पदपाठः - दयानन्दादि``: fixes bad accent sequences and pausa /
    prevocalic anusvāras while preserving traditional hiatus/compound ``ऽ`` markers.
  - Preserves ``js_include`` sections, ``Griffith``, commentary blocks, and headings verbatim.
  """
  parts = re.split(r"(?m)^(?=## )", md_text)
  if len(parts) <= 1:
    return md_text

  out_parts: list[str] = [parts[0]]
  for sec in parts[1:]:
    if skip_js_include and "js_include" in sec:
      out_parts.append(sec)
      continue
    nl_pos = sec.find("\n")
    if nl_pos == -1:
      out_parts.append(sec)
      continue
    heading = sec[:nl_pos + 1]
    body = sec[nl_pos + 1:]

    top_spans = get_top_level_detail_spans(body)
    top_parsed = parse_top_level_details(body)
    if len(top_spans) != len(top_parsed):
      out_parts.append(sec)
      continue

    top_repls: list[tuple[int, int, str]] = []
    idx = 0
    while idx < len(top_parsed):
      _, _, t_title, t_inner = top_parsed[idx]
      b_s, b_e = top_spans[idx]
      block_txt = body[b_s:b_e]
      close_idx = block_txt.rfind("</details>")
      summ_end = block_txt.find("</summary>")
      if summ_end == -1 or close_idx == -1:
        idx += 1
        continue
      inner_s = summ_end + len("</summary>")

      if t_title == vp_title and idx + 1 < len(top_parsed) and top_parsed[idx + 1][2] == sarva_title:
        paired_pada_norm = ""
        s_s, s_e = top_spans[idx + 1]
        sarva_txt = body[s_s:s_e]
        s_summ_end = sarva_txt.find("</summary>")
        s_close = sarva_txt.rfind("</details>")
        if s_summ_end != -1 and s_close != -1:
          s_inner_start = s_summ_end + len("</summary>")
          s_inner = sarva_txt[s_inner_start:s_close]
          c_spans = get_top_level_detail_spans(s_inner)
          c_parsed = parse_top_level_details(s_inner)
          c_repls: list[tuple[int, int, str]] = []
          for (cs, ce), (_, _, c_title, _) in zip(c_spans, c_parsed):
            c_block = s_inner[cs:ce]
            csum = c_block.find("</summary>")
            ccls = c_block.rfind("</details>")
            if csum == -1 or ccls == -1:
              continue
            c_in_s = csum + len("</summary>")
            c_body = c_block[c_in_s:ccls]
            if c_title in (mula_title, pada_title):
              c_new = normalize_mAdhyandina(c_body, normalize_pre_vowel_avagrahas=False)
              if c_title == pada_title:
                paired_pada_norm = c_new.strip()
              if c_new != c_body:
                c_repls.append((c_in_s + cs, ccls + cs, c_new))
          if c_repls:
            new_s_inner = _rewrite_details_body(s_inner, c_repls)
            top_repls.append((s_s + s_inner_start, s_s + s_close, new_s_inner))

        vp_orig_inner = block_txt[inner_s:close_idx]
        lead_ws = vp_orig_inner[:len(vp_orig_inner) - len(vp_orig_inner.lstrip())]
        trail_ws = vp_orig_inner[len(vp_orig_inner.rstrip()):]
        vp_core = vp_orig_inner.strip()
        vp_new = normalize_mAdhyandina(vp_core, normalize_pre_vowel_avagrahas=True)
        if hyphenate_vp:
          vp_new = hyphenate_samhita_with_padapatha(vp_new, paired_pada_norm)
        new_vp_inner = f"{lead_ws}{vp_new}{trail_ws}"
        if new_vp_inner != vp_orig_inner:
          top_repls.append((b_s + inner_s, b_s + close_idx, new_vp_inner))
        idx += 2
        continue

      if t_title == sarva_title:
        s_inner = block_txt[inner_s:close_idx]
        c_spans = get_top_level_detail_spans(s_inner)
        c_parsed = parse_top_level_details(s_inner)
        c_repls = []
        for (cs, ce), (_, _, c_title, _) in zip(c_spans, c_parsed):
          c_block = s_inner[cs:ce]
          csum = c_block.find("</summary>")
          ccls = c_block.rfind("</details>")
          if csum == -1 or ccls == -1:
            continue
          c_in_s = csum + len("</summary>")
          c_body = c_block[c_in_s:ccls]
          if c_title in (mula_title, pada_title):
            c_new = normalize_mAdhyandina(c_body, normalize_pre_vowel_avagrahas=False)
            if c_new != c_body:
              c_repls.append((c_in_s + cs, ccls + cs, c_new))
        if c_repls:
          top_repls.append((b_s + inner_s, b_s + close_idx, _rewrite_details_body(s_inner, c_repls)))
      idx += 1

    out_parts.append(heading + _rewrite_details_body(body, top_repls) if top_repls else sec)
  return "".join(out_parts)
