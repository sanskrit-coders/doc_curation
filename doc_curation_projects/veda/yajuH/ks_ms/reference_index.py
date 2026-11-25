"""Cached parallel-mantra (TS, VS-M, VS-K, RV, MS) and viniyoga (MŚS, VŚS, KS Brāhmaṇa) index.

Provides O(1) prefix & n-gram lookups for:
1. Known mantra units (yajuṣes and metrical ṛks) from TS, VS-M, VS-K, RV (and optionally MS
   once MS ``sarva-prastutiH`` has been built, as the closest Caraka witness for KS).
2. Sequential ritual viniyogas from Mānava Śrauta Sūtra, Vārāha Śrauta Sūtra, and KS Brāhmaṇa
   chapters.
"""

from __future__ import annotations

import dataclasses
import glob
import os
import pickle
import re
from collections import defaultdict
from typing import Iterable, Sequence

from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.md.content_processor.details.common import parse_top_level_details
from doc_curation.sanskrit.accent.reconciler import US_SVARITA, US_UDATTA, has_us_accents

INDEX_VERSION = 5
DEFAULT_INDEX_CACHE_PATH = os.path.expanduser(
  "~/.cache/doc_curation/ks_ms_reference_index_v5.pkl"
)

DEFAULT_TS_DIR = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/saMhitA/sarva-prastutiH"
DEFAULT_VSM_DIR = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/saMhitA/sarva-prastutiH"
DEFAULT_VSK_DIR = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/kANvam/saMhitA"
DEFAULT_RV_DIR = "/home/vvasuki/gitland/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH"
DEFAULT_MSS_PATH = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/maitrAyaNIyam/sUtram_mAnavam/shrautam.md"
DEFAULT_VSS_PATH = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/maitrAyaNIyam/varAhaH/vArAhashrautasUtram.md"
DEFAULT_KS_VISVARA_DIR = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/visvara-saMhitA"
DEFAULT_MS_SARVA_DIR = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/maitrAyaNIyam/saMhitA/sarva-prastutiH"

_DEV_TO_ASCII = str.maketrans("०१२३४५६७८९", "0123456789")
_ASCII_TO_DEV = str.maketrans("0123456789", "०१२३४५६७८९")

_ALL_ACCENTS_RE = re.compile(r"[\u0951-\u0957\u1cd0-\u1cff\u0300-\u036f]")
_MARKUP_RE = re.compile(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]|<[^>]+>", re.S)
_SUG_RE = re.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]")
_DEVA_WORD_RE = re.compile(r"[\u0900-\u0963\u0971-\u097f]+")

# Words too generic on their own to serve as single-word pratīka anchors
_GENERIC_SINGLE_PRATIKAS: frozenset[str] = frozenset({
  "स्वाहा", "नमः", "अग्ने", "इन्द्र", "देवाः", "देव", "विष्णो", "सोम", "वायो", "असि", "स्थ",
  "त्वा", "ते", "मे", "वः", "नः", "इदम्", "अयम्", "एषः", "एतत्", "तत्", "यत्", "सः", "सा",
  "अथ", "एव", "वै", "हि", "च", "वा", "न", "मा", "ओम्", "भूः", "भुवः", "स्वः", "अमुम्",
  "अमुष्मै", "असौ", "अमूम", "प्रथमम्", "द्वितीयम्", "तृतीयम्", "उत्तराम्", "उत्तरम्",
})

# Ritual/sūtra action words that confirm a preceding `... इति` is a mantra viniyoga citation
_SUTRA_ACTION_RE = re.compile(
  r"(?:छिनत्ति|अनुमार्ष्टि|सन्नमयति|संनमयति|अपाकरोति|प्रार्पयति|अनुमन्त्रयते|जपति|"
  r"उपकर्षति|आदत्ते|उपतिष्ठते|व्रजति|निष्टपति|परिषुवति|अभिमृशति|अतिसृजति|लुनाति|"
  r"सादयति|प्रतिदधाति|सम्भरति|संभरति|आवेष्टयति|आरभते|उद्यछ|उद्यच्छ|हरति|आदधाति|"
  r"जुहोति|निर्वपति|प्रोक्षति|गृह्णाति|प्रणयति|स्तृणाति|पिनष्टि|अवहन्ति|श्रपयति|अभिघारयति|"
  r"संमार्ष्टि|अवेक्षते|प्रेक्षते|परिदधाति|प्रथयति|विमुञ्चति|क्रामति|अतिक्रामति|उद्वापयति|"
  r"अवद्यति|समवद्यति|संप्रेष्यति|आश्रावयति|प्रत्याश्रावयति|उत्पुनाति|पवते|दोग्धि|आतनक्ति|"
  r"अधिश्रयति|उद्वासयति|संवपति|आनयति|निनीय|उपस्पृश्य|परिवेशयति|अभ्यादधाति|संयुनक्ति|"
  r"युनक्ति|उपयच्छति|प्रहरति|अवसिञ्चति|उपवसति|अन्वादधाति|पर्युक्षति|अन्वाहरति|प्रत्यभिमृशति|"
  r"पर्यावर्तते|प्रक्रम्य|अभिचरन्|पृच्छति|पृछति|अभ्यनक्ति|आनक्ति|अवदधाति|उपदधाति|"
  r"वाचयति|अनुब्रूयात्|ब्रूयात्|आह|यजति|आह्वयति|ददाति|प्रतिगृह्णाति|अन्वारभते|आस्थापयति|"
  r"अभिषिञ्चति|प्रदक्षिण|स्रुव|जुहू|उपभृत्|ध्रुवा|वेदि|बर्हि|कपाल|पुरोडाश|आहवनीय|गार्हपत्य)"
)


def to_dev_digits(n: int | str) -> str:
  return str(n).translate(_ASCII_TO_DEV)


def to_ascii_digits(s: str) -> str:
  return s.translate(_DEV_TO_ASCII)


def clean_vedic_text(text: str, *, keep_us_accents: bool = False) -> str:
  """Strip editorial glosses/markup while optionally preserving US accent marks."""
  s = _SUG_RE.sub(r"\2", text)
  s = _MARKUP_RE.sub(" ", s)
  s = s.replace("**", "").replace("*", "").replace("\\", " ")
  s = s.replace("ᳵ", "ः").replace("ᳶ", "ः").replace("ꣳ", "ं")
  # Normalize MS TITUS long ṝ (`ृ̄` / `ृ᳓̄`) and `क्ŀ̥`
  s = re.sub(r"ृ([\u1cd3\u1cd9]*)\u0304", r"ॄ\1", s)
  s = re.sub(r"क्र्?ŀ\u0325", "कॢ", s)
  if not keep_us_accents:
    s = _ALL_ACCENTS_RE.sub("", s)
  s = re.sub(r"[०-९0-9]+", " ", s)
  s = re.sub(r"\s+", " ", s).strip()
  return s


def normalize_for_matching(text: str) -> str:
  """Fold Devanagari into an orthography-normalized, accent-stripped word-spaced form."""
  s = clean_vedic_text(text, keep_us_accents=False)
  s = s.replace("।", " ").replace("॥", " ").replace(",", " ").replace(";", " ")
  s = s.replace("-", " ").replace("–", " ").replace("—", " ")
  # Normalize Taittirīya/Caraka nasalized glides & candrabindu
  s = re.sub(r"([वयल])्[ँं]", "ं", s)
  s = s.replace("ँ", "ं").replace("ळ्ह", "ढ").replace("ळ", "ड")
  # Normalize doubled consonants after repha & chh/ch
  s = re.sub(r"र्([क-ह])्\1", r"र्\1", s)
  s = s.replace("च्छ", "छ")
  s = re.sub(r"स्स्(?=[थतपफकख])", "स्", s)
  # Normalize MS/KS final `-स्` / `-र्` at word end -> `ः`
  s = re.sub(r"[सर]्(?=\s|$)", "ः", s)
  s = re.sub(r"\s+", " ", s).strip()
  return s


_INDEP_TO_MATRA = {
  "आ": "ा", "इ": "ि", "ई": "ी", "उ": "ु", "ऊ": "ू",
  "ऋ": "ृ", "ॠ": "ॄ", "ऌ": "ॢ", "ए": "े", "ऐ": "ै", "ओ": "ो", "औ": "ौ",
}
_HALANT_VOWEL_RE = re.compile(r"([\u0915-\u0939])्\s*([अआइईउऊऋॠऌएऐओऔ])")


def _join_halant_vowels(text: str) -> str:
  """Fuse ``C् + V`` across spaces (e.g. ``गोषद् असि`` -> ``गोषदसि``, ``आप्यायध्वम् अघ्न्या`` -> ``आप्यायध्वमघ्न्या``)."""
  def _repl(m: re.Match) -> str:
    c, v = m.group(1), m.group(2)
    return c if v == "अ" else c + _INDEP_TO_MATRA[v]
  return _HALANT_VOWEL_RE.sub(_repl, text)


def skeleton_key(text: str) -> str:
  """Compact phonetic skeleton (sandhi-joined, no spaces/accents, folded sibilants/nasals)."""
  s = normalize_for_matching(text)
  s = s.replace("ऽ", "")
  # Join `C् + V` across spaces BEFORE stripping spaces or turning `म्` -> `ं`!
  s = _join_halant_vowels(s)
  s = s.replace(" ", "")
  # Fold homorganic nasals to anusvāra & visarga/sibilants
  s = re.sub(r"[ङञणनम]्(?=[क-ह])", "ं", s)
  s = s.replace("म्", "ं").replace("न्", "ं")
  s = s.replace("ः", "").replace("स्", "").replace("श्", "").replace("ष्", "")
  # Fold final/medial stop voicing mismatches (`त्`~`द्`, `क्`~`ग्`, `प्`~`ब्`) & doubled consonants
  s = re.sub(r"([क-ह])्\1", r"\1", s)
  return s


def norm_words(text: str) -> tuple[str, ...]:
  """Return orthography-normalized accent-free Devanagari words for ``text``."""
  s = normalize_for_matching(text).replace("ऽ", "")
  out: list[str] = []
  for w in _DEVA_WORD_RE.findall(s):
    if w.endswith(("स्", "र्")) and len(w) >= 3:
      w = w[:-2] + "ः"
    out.append(w)
  return tuple(out)


@dataclasses.dataclass(frozen=True)
class MantraRefUnit:
  """One reference mantra unit (yajuṣ or ṛk) from TS, VS-M, VS-K, RV, or MS."""

  source: str  # "TS", "VS-M", "VS-K", "RV", "MS"
  ref_id: str
  vp_us: str
  is_rk: bool
  words: tuple[str, ...]
  skeleton: str
  n_lines: int = 1


@dataclasses.dataclass(frozen=True)
class ViniyogaEntry:
  """One ritual viniyoga citation extracted from MŚS, VŚS, or KS Brāhmaṇa."""

  source: str  # "मानवश्रौतसूत्र-विनियोगः", "वाराहश्रौतसूत्र-विनियोगः", "काठकब्राह्मण-विनियोगः"
  ref: str  # e.g. "१.१.१.१३" or "का॰सं॰ ६.१"
  seq_idx: int
  pratika_raw: str
  pratika_words: tuple[str, ...]
  pratika_skeleton: str
  sutra_text: str


def _collect_leaf_details(text: str) -> list[tuple[str, str]]:
  """Recursively collect leaf ``(summary, body)`` details blocks, descending through wrappers."""
  out: list[tuple[str, str]] = []
  for blk in parse_top_level_details(text):
    summary = blk.summary.strip()
    body = blk.body
    if "<details" in body:
      inner = _collect_leaf_details(body)
      if inner:
        out.extend(inner)
        continue
    out.append((summary, body))
  return out


def _clean_vp_to_us(vp_body: str, mula_body: str = "") -> str:
  """Extract clean US-accented text from VP (falling back to classical ``मूलम्`` -> US)."""
  vp_clean = clean_vedic_text(vp_body, keep_us_accents=True)
  if has_us_accents(vp_clean):
    return vp_clean
  if mula_body:
    m_clean = clean_vedic_text(mula_body, keep_us_accents=True)
    if has_us_accents(m_clean):
      return m_clean
    if "\u0951" in m_clean or "\u0952" in m_clean:
      return accent.to_US_accents(m_clean, pauses=r"[।॥,;]+")
  return vp_clean


def _ingest_ts_dir(ts_dir: str) -> list[MantraRefUnit]:
  """Parse all TS ``sarva-prastutiH`` anuvāka files (including embedded ``js_include`` Rks)."""
  units: list[MantraRefUnit] = []
  if not os.path.isdir(ts_dir):
    return units
  for fp in sorted(glob.glob(os.path.join(ts_dir, "**", "*.md"), recursive=True)):
    base = os.path.basename(fp)
    if base in ("_index.md", "file_list.md"):
      continue
    rel = os.path.relpath(fp, ts_dir).replace("\\", "/")
    txt = open(fp, encoding="utf-8", errors="ignore").read()
    # Extract sequential VP blocks and any adjacent मूलम् blocks.
    # For js_include divs, capture the URL so `/Rk/` marks is_rk=True!
    rk_spans: list[tuple[int, int]] = []
    for m_inc in re.finditer(r'<div class="js_include"[^>]*url="([^"]+)"[^>]*>.*?</div>', txt, re.S):
      if "/Rk/" in m_inc.group(1):
        rk_spans.append((m_inc.start(), m_inc.end()))

    # Walk all leaf details with positions by scanning non-wrapper details tags
    # Match innermost <details> blocks cleanly via iterative regex on leaf tags
    leaf_re = re.compile(
      r"<details(?:\s+open)?><summary>(?:<h4>)?([^<]*?)(?:</h4>)?</summary>((?:(?!</?details).)*?)</details>",
      re.S,
    )
    leaves: list[tuple[int, str, str]] = [
      (m.start(), m.group(1).strip(), m.group(2)) for m in leaf_re.finditer(txt)
    ]
    idx_u = 0
    for li, (pos, hdr, body) in enumerate(leaves):
      if not hdr.startswith("विश्वास-प्रस्तुतिः"):
        continue
      # Find nearest following मूलम् before next VP
      mula_body = ""
      for lj in range(li + 1, min(li + 8, len(leaves))):
        nh = leaves[lj][1]
        if nh.startswith("विश्वास-प्रस्तुतिः"):
          break
        if nh == "मूलम्":
          mula_body = leaves[lj][2]
          break
      vp_us = _clean_vp_to_us(body, mula_body)
      words = norm_words(vp_us)
      if not words:
        continue
      skel = skeleton_key(vp_us)
      is_rk = ("ऋक्" in hdr) or any(a <= pos < b for a, b in rk_spans)
      n_lines = max(1, len([ln for ln in body.strip().splitlines() if ln.strip()]))
      idx_u += 1
      units.append(
        MantraRefUnit(
          source="TS",
          ref_id=f"TS:{rel}#{idx_u}",
          vp_us=vp_us,
          is_rk=is_rk,
          words=words,
          skeleton=skel,
          n_lines=n_lines,
        )
      )
  return units


def _ingest_vs_dir(vs_dir: str, source: str) -> list[MantraRefUnit]:
  """Parse VS-M or VS-K ``sarva-prastutiH`` markdown files."""
  units: list[MantraRefUnit] = []
  if not os.path.isdir(vs_dir):
    return units
  leaf_re = re.compile(
    r"<details(?:\s+open)?><summary>(?:<h4>)?([^<]*?)(?:</h4>)?</summary>((?:(?!</?details).)*?)</details>",
    re.S,
  )
  for fp in sorted(glob.glob(os.path.join(vs_dir, "**", "*.md"), recursive=True)):
    base = os.path.basename(fp)
    if base in ("_index.md", "file_list.md"):
      continue
    if source == "VS-K" and "/sarva-prastutiH/" not in fp and "sarva-prastutiH" not in os.path.dirname(fp):
      # Prefer sarva-prastutiH if present, else accept top-level files
      pass
    rel = os.path.relpath(fp, vs_dir).replace("\\", "/")
    txt = open(fp, encoding="utf-8", errors="ignore").read()
    leaves = [(m.group(1).strip(), m.group(2)) for m in leaf_re.finditer(txt)]
    idx_u = 0
    for li, (hdr, body) in enumerate(leaves):
      if not hdr.startswith("विश्वास-प्रस्तुतिः"):
        continue
      mula_body = ""
      for lj in range(li + 1, min(li + 6, len(leaves))):
        nh = leaves[lj][0]
        if nh.startswith("विश्वास-प्रस्तुतिः"):
          break
        if nh.startswith("मूलम्"):
          mula_body = leaves[lj][1]
          break
      vp_us = _clean_vp_to_us(body, mula_body)
      words = norm_words(vp_us)
      if not words:
        continue
      skel = skeleton_key(vp_us)
      is_rk = "ऋक्" in hdr
      n_lines = max(1, len([ln for ln in body.strip().splitlines() if ln.strip()]))
      idx_u += 1
      units.append(
        MantraRefUnit(
          source=source,
          ref_id=f"{source}:{rel}#{idx_u}",
          vp_us=vp_us,
          is_rk=is_rk,
          words=words,
          skeleton=skel,
          n_lines=n_lines,
        )
      )
  return units


def _ingest_rv_dir(rv_dir: str) -> list[MantraRefUnit]:
  """Parse Ṛgveda ``sarvASh_TIkAH`` ṛk files (``Thomson & Solcum`` US accents; every verse is ``is_rk=True``)."""
  units: list[MantraRefUnit] = []
  if not os.path.isdir(rv_dir):
    return units
  ts_re = re.compile(r"<details><summary>Thomson & Solcum</summary>(.*?)</details>", re.S)
  mula_re = re.compile(r"<details><summary>मूलम् - शाकलम्</summary>(.*?)</details>", re.S)
  for fp in sorted(glob.glob(os.path.join(rv_dir, "**", "*.md"), recursive=True)):
    base = os.path.basename(fp)
    if base in ("_index.md", "file_list.md"):
      continue
    rel = os.path.relpath(fp, rv_dir).replace("\\", "/")
    txt = open(fp, encoding="utf-8", errors="ignore").read()
    m_ts = ts_re.search(txt)
    if m_ts:
      raw_body = m_ts.group(1)
      vp_us = clean_vedic_text(raw_body, keep_us_accents=True)
    else:
      m_mu = mula_re.search(txt)
      if not m_mu:
        continue
      raw_body = m_mu.group(1)
      vp_us = _clean_vp_to_us("", raw_body)
    words = norm_words(vp_us)
    if len(words) < 3:
      continue
    skel = skeleton_key(vp_us)
    n_lines = max(1, len([ln for ln in raw_body.strip().splitlines() if ln.strip()]))
    units.append(
      MantraRefUnit(
        source="RV",
        ref_id=f"RV:{rel}",
        vp_us=vp_us,
        is_rk=True,
        words=words,
        skeleton=skel,
        n_lines=n_lines,
      )
    )
  return units


def _extract_iti_pratika(clause: str) -> str:
  """Extract the mantra pratīka immediately preceding ``इति``/``इत्य्`` in one sūtra fragment."""
  s = clause.strip()
  if not s:
    return ""
  s = re.sub(r"^[\s,।॥०-९0-9]+", "", s)
  s = re.sub(r"[\s,।॥]+$", "", s)
  return s


def _expand_iti_sandhi(left: str, iti_tok: str) -> str:
  """Undo vowel/consonant sandhi right before ``इति``/``इत्य्`` to recover clean pratīka ending."""
  w = left.rstrip()
  if not w:
    return w
  if iti_tok.startswith("इत"):
    return w
  # Case 1: Consonant + `इति` -> `Cिति`/`Cिती`/`Cित्य` (e.g. `प्रेयमगादिति` -> `प्रेयमगाद्`,
  # `बह्वीरिति` -> `बह्वीर्`, `भागमितीन्द्र` -> `भागम्`, `प्रार्पयत्विति` -> `प्रार्पयतु`)
  if iti_tok.endswith(("िति", "िती", "ित्य", "ित्या")):
    # `left` already stripped `िति`/`िती`/`ित्य`/`ित्या`, leaving bare consonant `C` (without virāma!)
    if w.endswith("त्व"):
      return w[:-1] + "ु"
    if w and "\u0915" <= w[-1] <= "\u0939":
      return w + "्"
    return w
  # Case 2: `-अ`/`-आ` + `इति` -> `ेति`/`ेत्य` (`त्वेति` -> `त्वा`, `सुभूतायेति` -> `सुभूताय`, `स्थेति` -> `स्थ`)
  if w.endswith("े"):
    if w.endswith("त्वे"):
      return w[:-1] + "ा"
    return w[:-1]
  # Case 3: `-इ`/`-ई` + `इति` -> `ीति`/`ीत्य` (`पाहीति` -> `पाहि`, `वीहीति` -> `वीहि`, `असीति` -> `असि`)
  if w.endswith("ी"):
    if w.endswith(("सी", "ही", "मी", "ती", "री", "दी", "नी", "पी", "यी", "वि")):
      return w[:-1] + "ि"
    return w
  return w


_CONS_ITI_STEM_ENDINGS = (
  "त्विति", "त्विती", "त्वित्य", "त्वित्या",
  "मिति", "मिती", "मित्य", "मित्या",
  "दिति", "दिती", "दित्य", "दित्या",
  "रिति", "रिती", "रित्य", "रित्या",
  "निति", "निती", "नित्य", "नित्या",
  "विति", "विती", "वित्य", "वित्या",
  "णिति", "णिती", "णित्य", "णित्या",
  "लिति", "लिती", "लित्य", "लित्या",
  "तिति", "तिती", "तित्य", "तित्या",
  "गिति", "गिती", "गित्य", "गित्या",
  "डिति", "डिती", "डित्य", "डित्या",
  "टिति", "टिती", "टित्य", "टित्या",
  "पिति", "पिती", "पित्य", "पित्या",
  "बिति", "बिती", "बित्य", "बित्या",
  "भिति", "भिती", "भित्य", "भित्या",
)

_NON_ITI_WORDS = frozenset({
  "अदिति", "अदितिः", "अदितिम्", "अदित्याः", "समिति", "समितिः",
  "नित्य", "नित्यम्", "नित्यः", "नित्या", "प्रति", "प्रत्य", "अति", "अत्य",
  "जपति", "ददाति", "दधाति", "भवति", "करोति", "जुहोति", "हन्ति", "यन्ति", "सन्ति",
  "अस्ति", "एति", "पृच्छति", "पृछति", "छिनत्ति", "गच्छति", "वदति", "पचति",
  "ब्रवीति", "शृणोति", "दोग्धि", "नयति", "वहति", "हरति", "पिनष्टि", "लुनाति",
  "प्रतिदधाति", "अन्वादधाति", "उपदधाति", "अवदधाति", "परिदधाति", "आदधाति",
  "उपसंदधाति", "प्राश्नीयात्", "विन्दति", "रक्षति", "सादयति", "निर्वपति",
  "प्रोक्षति", "संवपति", "अभिघारयति", "अभिमृशति", "अतिसृजति", "अपाकरोति",
  "प्रार्पयति", "उपतिष्ठते", "उपकर्षति", "प्रणयति", "स्तृणाति", "अवहन्ति",
  "श्रपयति", "संमार्ष्टि", "उत्पुनाति", "पर्युक्षति", "आतनक्ति", "अधिश्रयति",
  "संयुनक्ति", "युनक्ति", "प्रहरति", "अवसिञ्चति", "उपवसति", "अभ्यादधाति",
  "गृह्णाति", "प्रतिगृह्णाति", "प्रथयति", "विमुञ्चति", "क्रामति", "अतिक्रामति",
  "अवद्यति", "समवद्यति", "संप्रेष्यति", "आश्रावयति", "प्रत्याश्रावयति", "सन्नमयति",
  "अनुमार्ष्टि", "निष्टपति", "परिषुवति", "सम्भरति", "संभरति", "आवेष्टयति",
  "अभिषिञ्चति", "आस्थापयति", "यजति", "आह्वयति", "अन्वाहरति", "पर्यावर्तते",
  "प्रत्यभिमृशति", "अनुमन्त्रयते", "अवेक्षते", "प्रेक्षते", "आरभते", "अन्वारभते",
  "आदत्ते", "विद्यते", "मन्यते", "लभते", "वर्तते", "तिष्ठति", "भवन्ति",
  "कुर्वन्ति", "सृजति", "सृजते", "दृष्ट्वा", "हुत्वा", "इति",
})


def _extract_viniyogas_from_sutra_text(
  sutra_text: str,
  *,
  source: str,
  ref: str,
  seq_counter: list[int],
  max_pratika_words: int = 16,
  max_sutra_window_chars: int = 240,
) -> list[ViniyogaEntry]:
  """Extract one or more ``(pratīka, sūtra)`` viniyoga entries from a sūtra or Brāhmaṇa sentence."""
  entries: list[ViniyogaEntry] = []
  clean_sutra = re.sub(r"\s+", " ", sutra_text).strip()
  if len(clean_sutra) < 6:
    return entries

  # Match standalone `इति`/`इत्य...`/`इती...` OR sandhi-fused `ेति`/`ेत्य`/`ीति`/`ीत्य`/`Cिति`/`Cिती`/`Cित्य`
  iti_pat = re.compile(
    r"(?:(?<=\s)|(?<=॥)|(?<=।))(इति|इती[क-ह]?|इत्या?[क-हअ-औा-ौ]?|इत्य[क-हअ-औा-ौ]?)"
    r"|([ेी](?:ति|ती|त्य|त्या))(?=\s|।|॥|,|$|[क-ह])"
    r"|(" + "|".join(_CONS_ITI_STEM_ENDINGS) + r")"
  )

  prev_end = 0
  matches = list(iti_pat.finditer(clean_sutra))
  if not matches:
    return entries

  for m in matches:
    tok = m.group(0)
    w_start = clean_sutra.rfind(" ", prev_end, m.start())
    w_start = prev_end if w_start < 0 else w_start + 1
    w_end = clean_sutra.find(" ", m.end())
    w_end = len(clean_sutra) if w_end < 0 else w_end
    full_word = clean_sutra[w_start:w_end].strip("।॥,;")

    if not tok.startswith("इत"):
      if full_word in _NON_ITI_WORDS:
        continue
      # Skip ordinary verbs ending in `...ति` / `...ती` when matched via consonant+`िति` (like `अभिमृशति` doesn't have `ि`,
      # `गृह्णाति` doesn't, `ददाति` doesn't, `भवति` doesn't — only `-िति` verbs like `हिनस्ति`/`अस्ति`/`तिष्ठति` have no `ि` before `त`,
      # except `विदिति`/`स्थिति`/`धृति` -> guard short nouns ending in `-िति`!)
      if tok.endswith("ति") and m.end() < len(clean_sutra) and clean_sutra[m.end()] not in " ।॥,;\n":
        continue
      if tok in ("नित्य", "नित्या") and full_word.startswith("नित्य"):
        continue
      if tok in ("तिति", "दिति", "मिति", "रिति", "विति", "निति", "णिति", "पिति", "बिति") and len(full_word) <= 4:
        continue
      if full_word.endswith(("स्थितिः", "स्थितिम्", "स्थित्या", "समितिः", "समित्या", "अदितिः", "अदित्या", "प्रकृतिः", "विकृतिः", "आकृतिः", "आहुतिः", "आहुतिम्", "आहुत्या", "आहुतीः", "पद्धतिः", "विभूतिः", "संपत्तिः", "निष्पत्तिः", "उत्पत्तिः", "प्रतीतिः", "प्रतीत्या", "प्रतीती", "प्रसृतिः", "प्रसृतिम्", "धृतिः", "धृत्यै", "गुप्तिः", "गुप्त्यै", "वृष्टिः", "सृष्टिः", "कॢप्तिः", "कॢप्त्यै")):
        continue

    # Compute raw pratīka left of `इति`
    if tok.startswith("इत"):
      raw_left = clean_sutra[prev_end : m.start()]
    elif tok[0] in ("े", "ी"):
      # Strip `ति`/`ती`/`त्य`/`त्या` while keeping `े`/`ी` for `_expand_iti_sandhi`
      suffix_len = len(tok) - 1
      raw_left = _expand_iti_sandhi(clean_sutra[prev_end : m.end() - suffix_len], tok)
    else:
      # Consonant + `िति`/`िती`/`ित्य`/`ित्या`: keep the consonant(s) before `ि`!
      i_pos = tok.find("ि")
      raw_left = _expand_iti_sandhi(clean_sutra[prev_end : m.start() + i_pos], tok)

    pratika_raw = _extract_iti_pratika(raw_left)
    p_words = norm_words(pratika_raw)
    if len(p_words) > max_pratika_words:
      # Trim very long preceding narrative to the trailing window before `इति`
      p_words = p_words[-max_pratika_words:]
      pratika_raw = " ".join(pratika_raw.split()[-max_pratika_words:])

    if p_words:
      if len(p_words) >= 2 or (len(p_words[0]) >= 5 and p_words[0] not in _GENERIC_SINGLE_PRATIKAS):
        seq_counter[0] += 1
        # Keep a concise snippet for long Brāhmaṇa paragraphs so avatārikā stays readable
        if len(clean_sutra) <= max_sutra_window_chars:
          snippet = clean_sutra
        else:
          s_lo = max(prev_end, m.start() - 120)
          if s_lo > 0:
            sp_lo = clean_sutra.find(" ", s_lo)
            if 0 <= sp_lo < m.start():
              s_lo = sp_lo + 1
          s_hi = min(len(clean_sutra), m.end() + 100)
          if s_hi < len(clean_sutra):
            sp_hi = clean_sutra.rfind(" ", m.end(), s_hi)
            if sp_hi > m.end():
              s_hi = sp_hi
          snippet = clean_sutra[s_lo:s_hi].strip()
        entries.append(
          ViniyogaEntry(
            source=source,
            ref=ref,
            seq_idx=seq_counter[0],
            pratika_raw=pratika_raw,
            pratika_words=p_words,
            pratika_skeleton=skeleton_key(pratika_raw),
            sutra_text=snippet,
          )
        )
    # Advance prev_end past the end of `इति` word (or right after `इति`/`िती`/`ित्य` if fused with next word!)
    if tok.startswith("इत") and tok == "इति":
      prev_end = m.end()
    elif tok.endswith(("ति",)):
      prev_end = m.end()
    else:
      # `इतीन्द्र` / `भागमितीन्द्र` / `इत्याह` -> advance past the fused word only if short verb, else right after `ती`/`त्य`
      prev_end = m.end()

  return entries


def parse_manava_shrautasutra(path: str = DEFAULT_MSS_PATH) -> list[ViniyogaEntry]:
  """Parse Mānava Śrauta Sūtra (``shrautam.md``) into ordered ``ViniyogaEntry`` citations."""
  if not os.path.exists(path):
    return []
  raw = open(path, encoding="utf-8", errors="ignore").read()
  body = raw.split("+++", 2)[2] if raw.startswith("+++") and raw.count("+++") >= 2 else raw
  # Drop header note lines before `मानवश्रौतसूत्रम्`
  idx_start = body.find("मानवश्रौतसूत्रम्")
  if idx_start >= 0:
    body = body[idx_start + len("मानवश्रौतसूत्रम्") :]

  # Rejoin wrapped lines while preserving section-end colophons & standalone khaṇḍa numbers
  lines = body.splitlines()
  chapter = 1
  khanda = 1
  entries: list[ViniyogaEntry] = []
  seq_counter = [0]
  buf: list[str] = []

  def _flush_khanda(text_chunk: str, ch: int, kh: int) -> None:
    if not text_chunk.strip():
      return
    # Remove line-wrap hyphens (`अभिमृशति` wrapped as `म-भिमृशति` -> `मभिमृशति`)
    joined = re.sub(r"-\s+", "", text_chunk)
    joined = re.sub(r"(?<=[\u0900-\u097f])-(?=[\u0900-\u097f])", "", joined)
    # Repair known Van Gelder MŚS OCR typo `ऊर्णे त्वेत्यनुमार्ष्टि` -> `ऊर्जे त्वेत्यनुमार्ष्टि`
    joined = joined.replace("ऊर्णे त्वेत्यनुमार्ष्टि", "ऊर्जे त्वेत्यनुमार्ष्टि")
    joined = re.sub(r"\s+", " ", joined).strip()
    # Split into individual numbered sūtras ending in `<space><devanagari-num>`
    parts = re.split(r"(?<=\s)([०-९]{1,3})(?=\s|$)", joined)
    for i in range(0, len(parts) - 1, 2):
      s_txt = parts[i].strip()
      s_num = parts[i + 1].strip()
      if not s_txt:
        continue
      ref = f"{to_dev_digits(ch)}.{to_dev_digits(kh)}.{s_num}"
      entries.extend(
        _extract_viniyogas_from_sutra_text(
          s_txt, source="मानवश्रौतसूत्र-विनियोगः", ref=ref, seq_counter=seq_counter
        )
      )

  for i, ln in enumerate(lines):
    s = ln.strip()
    if not s:
      continue
    # Colophon line `इति मानवसूत्रे ... अध्याय...`
    if s.startswith("इति मानव") or ("ऽध्याय" in s and len(s) < 80):
      _flush_khanda("\n".join(buf), chapter, khanda)
      buf = []
      chapter += 1
      khanda = 1
      continue
    # Standalone khaṇḍa end number (`१`, `२`, ...) preceded/followed by blank line
    prev_blank = (i == 0) or (not lines[i - 1].strip())
    next_blank = (i + 1 >= len(lines)) or (not lines[i + 1].strip())
    if re.fullmatch(r"[०-९]{1,2}", s) and (prev_blank or next_blank) and len(buf) > 3:
      # Check if previous buffered line already ended with a sūtra number -> this standalone number is khaṇḍa end!
      if re.search(r"[०-९]\s*$", buf[-1]):
        _flush_khanda("\n".join(buf), chapter, khanda)
        buf = []
        khanda += 1
        continue
    buf.append(s)

  if buf:
    _flush_khanda("\n".join(buf), chapter, khanda)
  return entries


def parse_varaha_shrautasutra(path: str = DEFAULT_VSS_PATH) -> list[ViniyogaEntry]:
  """Parse Vārāha Śrauta Sūtra (``vArAhashrautasUtram.md``) into ordered ``ViniyogaEntry`` citations."""
  if not os.path.exists(path):
    return []
  raw = open(path, encoding="utf-8", errors="ignore").read()
  body = raw.split("+++", 2)[2] if raw.startswith("+++") and raw.count("+++") >= 2 else raw
  idx_start = body.find("प्राक्सौमिकम्")
  if idx_start >= 0:
    body = body[idx_start + len("प्राक्सौमिकम्") :]

  chapter = 1
  khanda = 1
  entries: list[ViniyogaEntry] = []
  seq_counter = [0]
  buf: list[str] = []

  def _flush_vss(text_chunk: str, ch: int, kh: int) -> None:
    if not text_chunk.strip():
      return
    joined = re.sub(r"\s+", " ", text_chunk).strip()
    parts = re.split(r"(?<=\s)([०-९]{1,3})(?=\s|$)", joined)
    for i in range(0, len(parts) - 1, 2):
      s_txt = parts[i].strip()
      s_num = parts[i + 1].strip()
      if not s_txt:
        continue
      ref = f"{to_dev_digits(ch)}.{to_dev_digits(kh)}.{s_num}"
      entries.extend(
        _extract_viniyogas_from_sutra_text(
          s_txt, source="वाराहश्रौतसूत्र-विनियोगः", ref=ref, seq_counter=seq_counter
        )
      )

  for ln in body.splitlines():
    s = ln.strip()
    if not s:
      continue
    if s.startswith("इति") and ("खण्डम्" in s or "खण्डः" in s):
      _flush_vss("\n".join(buf), chapter, khanda)
      buf = []
      khanda += 1
      continue
    if s.startswith("इति") and ("ऽध्याय" in s or "अध्याय" in s):
      _flush_vss("\n".join(buf), chapter, khanda)
      buf = []
      chapter += 1
      khanda = 1
      continue
    buf.append(s)

  if buf:
    _flush_vss("\n".join(buf), chapter, khanda)
  return entries


def parse_ks_brahmana_viniyogas(ks_visvara_dir: str = DEFAULT_KS_VISVARA_DIR) -> list[ViniyogaEntry]:
  """Extract mantra pratīkas cited with ``इति`` in KS Brāhmaṇa sthānakas (e.g. KS 6–14, 19–37)."""
  if not os.path.isdir(ks_visvara_dir):
    return []
  entries: list[ViniyogaEntry] = []
  seq_counter = [0]
  for fp in sorted(glob.glob(os.path.join(ks_visvara_dir, "*.md"))):
    base = os.path.basename(fp)
    if base in ("_index.md", "file_list.md"):
      continue
    sth_num = os.path.splitext(base)[0]
    txt = open(fp, encoding="utf-8", errors="ignore").read()
    body = txt.split("+++", 2)[2] if txt.startswith("+++") and txt.count("+++") >= 2 else txt
    # Only scan sthānakas that look predominantly Brāhmaṇa (`वै`, `तस्मात्`, `इत्याह`)
    if body.count("वै") < 10 and body.count("तस्मात्") < 5:
      continue
    # Split into anuvākas at `॥ N ॥`
    anu_parts = re.split(r"[॥।]\s*([०-९0-9]+)\s*[॥।]", body)
    for idx in range(0, len(anu_parts) - 1, 2):
      anu_txt = anu_parts[idx]
      anu_num = anu_parts[idx + 1]
      for sent in re.split(r"[।॥]+", anu_txt):
        s = re.sub(r"\s+", " ", sent).strip()
        if not s or len(s) < 12:
          continue
        if "इति" not in s and "इत्य" not in s and "ेति" not in s and "ेत्य" not in s and "ीति" not in s and "ीत्य" not in s and "िति" not in s:
          continue
        ref = f"का॰सं॰ {to_dev_digits(sth_num.lstrip('0') or '0')}.{anu_num}"
        entries.extend(
          _extract_viniyogas_from_sutra_text(
            s, source="काठकब्राह्मण-विनियोगः", ref=ref, seq_counter=seq_counter,
            max_pratika_words=10, max_sutra_window_chars=220,
          )
        )
  return entries


class VedicReferenceIndex:
  """Fast lookup index over TS/VS-M/VS-K/RV/(MS) mantras and MŚS/VŚS/KS-Brāhmaṇa viniyogas."""

  def __init__(
    self,
    mantras: list[MantraRefUnit],
    mss_viniyogas: list[ViniyogaEntry],
    vss_viniyogas: list[ViniyogaEntry],
    ks_brahmana_viniyogas: list[ViniyogaEntry],
  ) -> None:
    self.mantras = mantras
    self.mss_viniyogas = mss_viniyogas
    self.vss_viniyogas = vss_viniyogas
    self.ks_brahmana_viniyogas = ks_brahmana_viniyogas
    self._build_lookup_tables()

  def _build_lookup_tables(self) -> None:
    # Mantra prefix indices
    self.mantra_by_skel10: dict[str, list[int]] = defaultdict(list)
    self.mantra_by_skel7: dict[str, list[int]] = defaultdict(list)
    self.mantra_by_w2: dict[tuple[str, str], list[int]] = defaultdict(list)
    self.mantra_by_w1_short: dict[str, list[int]] = defaultdict(list)
    self.mantra_by_any_w2: dict[tuple[str, str], list[int]] = defaultdict(list)

    for idx, u in enumerate(self.mantras):
      sk = u.skeleton
      if len(sk) >= 10:
        self.mantra_by_skel10[sk[:10]].append(idx)
      if len(sk) >= 7:
        self.mantra_by_skel7[sk[:7]].append(idx)
      ws = u.words
      if len(ws) >= 2:
        self.mantra_by_w2[(ws[0], ws[1])].append(idx)
        for j in range(min(len(ws) - 1, 12)):
          self.mantra_by_any_w2[(ws[j], ws[j + 1])].append(idx)
      if 1 <= len(ws) <= 3 and len(sk) >= 5:
        self.mantra_by_w1_short[ws[0]].append(idx)

    # Viniyoga suffix/sub-window indices (because a sūtra clause before `इति` may include
    # leading ritual framing words like `उत्तरतो गार्हपत्यस्य देवस्य त्वा...`, we index EVERY
    # trailing word-pair and trailing 8-char skeleton suffix of the pratīka!)
    self.mss_by_skel8: dict[str, list[int]] = defaultdict(list)
    self.vss_by_skel8: dict[str, list[int]] = defaultdict(list)
    self.ksb_by_skel8: dict[str, list[int]] = defaultdict(list)
    self._index_viniyogas(self.mss_viniyogas, self.mss_by_skel8)
    self._index_viniyogas(self.vss_viniyogas, self.vss_by_skel8)
    self._index_viniyogas(self.ks_brahmana_viniyogas, self.ksb_by_skel8)

  @staticmethod
  def _index_viniyogas(entries: Sequence[ViniyogaEntry], skel_map: dict[str, list[int]]) -> None:
    for idx, e in enumerate(entries):
      ws = e.pratika_words
      if not ws:
        continue
      seen_keys: set[str] = set()
      if len(ws) == 1:
        sub_sk = skeleton_key(ws[0])
        if len(sub_sk) >= 5 and ws[0] not in _GENERIC_SINGLE_PRATIKAS:
          skel_map[f"1:{sub_sk}"].append(idx)
        continue
      # For multi-word pratīkas, NEVER index the bare last single word (`st == len(ws) - 1`) —
      # require at least 2 trailing words (`start_i <= len(ws) - 2`) so a mantra never matches its own final word!
      max_tail = min(len(ws), 14)
      for start_i in range(max(0, len(ws) - max_tail), len(ws) - 1):
        sub_ws = ws[start_i:]
        sub_sk = skeleton_key(" ".join(sub_ws))
        if len(sub_sk) >= 8:
          k = sub_sk[:8]
          if k not in seen_keys:
            seen_keys.add(k)
            skel_map[k].append(idx)
        elif len(sub_sk) >= 5:
          k = f"s:{sub_sk}"
          if k not in seen_keys:
            seen_keys.add(k)
            skel_map[k].append(idx)

  def add_ms_sarva_mantras(self, ms_sarva_dir: str = DEFAULT_MS_SARVA_DIR) -> int:
    """Ingest freshly generated MS ``sarva-prastutiH`` per-anuvāka blocks for KS witness use."""
    ms_units = _ingest_vs_dir(ms_sarva_dir, source="MS")
    if not ms_units:
      return 0
    # Drop any old MS units first
    self.mantras = [u for u in self.mantras if u.source != "MS"] + ms_units
    self._build_lookup_tables()
    return len(ms_units)

  @classmethod
  def build(
    cls,
    *,
    ts_dir: str = DEFAULT_TS_DIR,
    vsm_dir: str = DEFAULT_VSM_DIR,
    vsk_dir: str = DEFAULT_VSK_DIR,
    rv_dir: str = DEFAULT_RV_DIR,
    mss_path: str = DEFAULT_MSS_PATH,
    vss_path: str = DEFAULT_VSS_PATH,
    ks_visvara_dir: str = DEFAULT_KS_VISVARA_DIR,
  ) -> "VedicReferenceIndex":
    mantras: list[MantraRefUnit] = []
    mantras.extend(_ingest_ts_dir(ts_dir))
    mantras.extend(_ingest_vs_dir(vsm_dir, "VS-M"))
    mantras.extend(_ingest_vs_dir(vsk_dir, "VS-K"))
    mantras.extend(_ingest_rv_dir(rv_dir))
    mss = parse_manava_shrautasutra(mss_path)
    vss = parse_varaha_shrautasutra(vss_path)
    ksb = parse_ks_brahmana_viniyogas(ks_visvara_dir)
    return cls(mantras, mss, vss, ksb)

  @classmethod
  def load_or_build(
    cls,
    *,
    cache_path: str = DEFAULT_INDEX_CACHE_PATH,
    force_rebuild: bool = False,
  ) -> "VedicReferenceIndex":
    if not force_rebuild and os.path.exists(cache_path):
      try:
        with open(cache_path, "rb") as fh:
          payload = pickle.load(fh)
        if isinstance(payload, dict) and payload.get("version") == INDEX_VERSION:
          return cls(
            payload["mantras"],
            payload["mss"],
            payload["vss"],
            payload["ksb"],
          )
      except Exception:
        pass
    inst = cls.build()
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "wb") as fh:
      pickle.dump(
        {
          "version": INDEX_VERSION,
          "mantras": inst.mantras,
          "mss": inst.mss_viniyogas,
          "vss": inst.vss_viniyogas,
          "ksb": inst.ks_brahmana_viniyogas,
        },
        fh,
        protocol=pickle.HIGHEST_PROTOCOL,
      )
    return inst

  def find_mantra_starts_at(self, span_skeleton: str, span_words: Sequence[str]) -> list[MantraRefUnit]:
    """Return reference mantras (TS/VS/RV/MS) that start right at ``span_skeleton``."""
    cands_idx: set[int] = set()
    if len(span_skeleton) >= 10:
      cands_idx.update(self.mantra_by_skel10.get(span_skeleton[:10], ()))
    if len(span_skeleton) >= 7:
      cands_idx.update(self.mantra_by_skel7.get(span_skeleton[:7], ()))
    if len(span_words) >= 2:
      cands_idx.update(self.mantra_by_w2.get((span_words[0], span_words[1]), ()))
    if span_words:
      cands_idx.update(self.mantra_by_w1_short.get(span_words[0], ()))

    matched: list[tuple[int, MantraRefUnit]] = []
    for idx in cands_idx:
      u = self.mantras[idx]
      u_sk = u.skeleton
      if not u_sk:
        continue
      # Check prefix agreement: either span starts with the full short reference mantra,
      # or both share >= 10 skeleton chars (or >= 2 full words)
      if span_skeleton.startswith(u_sk) and len(u_sk) >= 5:
        matched.append((len(u_sk) + 20, u))
      elif u_sk.startswith(span_skeleton) and len(span_skeleton) >= 6:
        matched.append((len(span_skeleton) + 10, u))
      else:
        # Compute common skeleton prefix length
        lcp = 0
        lim = min(len(span_skeleton), len(u_sk))
        while lcp < lim and span_skeleton[lcp] == u_sk[lcp]:
          lcp += 1
        if lcp >= 10 or (lcp >= 6 and len(u_sk) <= 9 and lcp >= len(u_sk) - 1):
          matched.append((lcp, u))
    matched.sort(key=lambda x: (-x[0], x[1].source))
    return [u for _, u in matched]

  def find_best_parallel_mantra(
    self,
    text: str,
    *,
    prefer_sources: Sequence[str] = ("MS", "TS", "VS-M", "VS-K", "RV"),
    min_overlap: float = 0.65,
  ) -> tuple[MantraRefUnit, float] | None:
    """Find the closest parallel mantra unit for a complete candidate block."""
    ws = norm_words(text)
    sk = skeleton_key(text)
    if not ws or len(sk) < 4:
      return None

    cand_counts: dict[int, int] = defaultdict(int)
    if len(sk) >= 10:
      for idx in self.mantra_by_skel10.get(sk[:10], ()):
        cand_counts[idx] += 4
    if len(sk) >= 7:
      for idx in self.mantra_by_skel7.get(sk[:7], ()):
        cand_counts[idx] += 2
    for j in range(min(len(ws) - 1, 14)):
      for idx in self.mantra_by_any_w2.get((ws[j], ws[j + 1]), ()):
        cand_counts[idx] += 1
    if len(ws) <= 3:
      for idx in self.mantra_by_w1_short.get(ws[0], ()):
        cand_counts[idx] += 2

    if not cand_counts:
      return None

    src_rank = {s: i for i, s in enumerate(prefer_sources)}
    # Evaluate top 40 candidates by word Jaccard + skeleton similarity
    top_idxs = sorted(cand_counts.keys(), key=lambda i: -cand_counts[i])[:40]
    w_set = set(ws)
    best: tuple[float, int, MantraRefUnit] | None = None
    for idx in top_idxs:
      u = self.mantras[idx]
      if not u.words:
        continue
      # Length ratio guard (avoid matching a 2-word yajuṣ against a 20-word Ṛk)
      len_ratio = min(len(sk), len(u.skeleton)) / max(len(sk), len(u.skeleton), 1)
      if len_ratio < 0.45:
        continue
      u_set = set(u.words)
      inter = len(w_set & u_set)
      jacc = inter / max(len(w_set | u_set), 1)
      # Skeleton prefix/trigram overlap
      t1 = {sk[k : k + 3] for k in range(max(1, len(sk) - 2))}
      t2 = {u.skeleton[k : k + 3] for k in range(max(1, len(u.skeleton) - 2))}
      tri = len(t1 & t2) / max(len(t1 | t2), 1)
      sim = 0.45 * jacc + 0.55 * tri
      if sk == u.skeleton:
        sim = 1.0
      if sim < min_overlap:
        continue
      rk = src_rank.get(u.source, 99)
      if best is None or (sim > best[0] + 0.03) or (abs(sim - best[0]) <= 0.03 and rk < best[1]):
        best = (sim, rk, u)

    if best is None:
      return None
    return best[2], best[0]

  def match_viniyogas_at(
    self,
    span_skeleton: str,
    span_words: Sequence[str],
    *,
    corpus: str = "MS",
    cursor_mss: int | None = None,
    cursor_vss: int | None = None,
    cursor_ksb: int | None = None,
    preceding_skel: str = "",
  ) -> list[ViniyogaEntry]:
    """Find Śrautasūtra/Brāhmaṇa viniyoga citations matching the opening of ``span_skeleton``."""
    out: list[ViniyogaEntry] = []
    streams: list[tuple[list[ViniyogaEntry], dict[str, list[int]], int | None]]
    if corpus == "MS":
      streams = [
        (self.mss_viniyogas, self.mss_by_skel8, cursor_mss),
        (self.vss_viniyogas, self.vss_by_skel8, cursor_vss),
      ]
    else:
      streams = [
        (self.ks_brahmana_viniyogas, self.ksb_by_skel8, cursor_ksb),
        (self.mss_viniyogas, self.mss_by_skel8, cursor_mss),
        (self.vss_viniyogas, self.vss_by_skel8, cursor_vss),
      ]

    for entries, skel_map, cursor in streams:
      cands: set[int] = set()
      if len(span_skeleton) >= 8:
        cands.update(skel_map.get(span_skeleton[:8], ()))
      # Also probe short 5..7 char exact prefixes (e.g. `इषे त्वा`, `वायवः स्थ`, `गोषदसि`, `सुभूताय`)
      for plen in (5, 6, 7):
        if len(span_skeleton) >= plen:
          cands.update(skel_map.get(f"s:{span_skeleton[:plen]}", ()))
          cands.update(skel_map.get(f"1:{span_skeleton[:plen]}", ()))
      if span_words and len(span_words[0]) >= 5:
        w0_sk = skeleton_key(span_words[0])
        if len(w0_sk) >= 5:
          cands.update(skel_map.get(f"1:{w0_sk}", ()))
      if not cands:
        continue

      best_e: ViniyogaEntry | None = None
      best_score = -1e9
      for idx in cands:
        e = entries[idx]
        ws_e = e.pratika_words
        if not ws_e:
          continue
        best_match_len = 0
        best_st = 999
        # Only try `st == 0` for 1-word pratīkas, and `st <= len(ws_e) - 2` for multi-word pratīkas!
        st_end = 1 if len(ws_e) == 1 else (len(ws_e) - 1)
        for st in range(max(0, len(ws_e) - 14), st_end):
          # CRITICAL GUARD: if matching an interior suffix (`st > 0`) of a longer pratīka,
          # check whether the preceding word(s) `ws_e[st-1]` ALREADY appear at the end of `preceding_skel`!
          # If yes, this pratīka is quoting the SAME mantra starting earlier — NOT a new mantra at `st`!
          if st > 0 and preceding_skel:
            prev_w_sk = skeleton_key(ws_e[st - 1])
            if len(prev_w_sk) >= 2 and (
              preceding_skel.endswith(prev_w_sk)
              or (len(prev_w_sk) >= 4 and prev_w_sk[:-1] in preceding_skel[-len(prev_w_sk) - 2 :])
            ):
              continue
          sub_sk = skeleton_key(" ".join(ws_e[st:]))
          if len(sub_sk) < 5:
            continue
          mlen = 0
          if span_skeleton.startswith(sub_sk):
            mlen = len(sub_sk)
          elif sub_sk.startswith(span_skeleton) and len(span_skeleton) >= 5 and len(sub_sk) <= len(span_skeleton) + 4:
            mlen = len(span_skeleton)
          elif len(sub_sk) >= 7 and span_skeleton.startswith(sub_sk[:-1]):
            mlen = len(sub_sk) - 1
          elif len(sub_sk) >= 12 and len(span_skeleton) >= 12:
            lcp = 0
            lim = min(len(span_skeleton), len(sub_sk))
            while lcp < lim and span_skeleton[lcp] == sub_sk[lcp]:
              lcp += 1
            if lcp >= max(10, int(0.8 * len(sub_sk))):
              mlen = lcp
          if mlen > best_match_len or (mlen == best_match_len and st < best_st):
            best_match_len = mlen
            best_st = st
        if best_match_len < 5:
          continue
        # Score: prefer full pratīka start (`best_st == 0`) and close sequential ritual order!
        score = float(best_match_len) + (6.0 if best_st == 0 else -1.5 * min(best_st, 6))
        if cursor is not None:
          delta = e.seq_idx - cursor
          if 0 < delta <= 15:
            score += 40.0 - delta * 0.5
          elif 15 < delta <= 60:
            score += 20.0 - delta * 0.2
          elif -5 <= delta <= 0:
            score += 5.0
          else:
            score -= min(25.0, abs(delta) * 0.05)
        if score > best_score:
          best_score = score
          best_e = e
      if best_e is not None:
        out.append(best_e)
    return out
