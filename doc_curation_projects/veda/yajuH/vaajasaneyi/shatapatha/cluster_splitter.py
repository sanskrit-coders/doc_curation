"""Split coarse Śatapatha Brāhmaṇa (Mādhyandina & Kāṇva) kaṇḍikā clusters into fine sense-unit blocks.

Follows ``/text_to_blocks`` (Tests 1–5: correlatives, embedded ``इति`` quotes, mantra/verse
integrity, parallel lists, minimal/maximal unit sizing) and ŚB ``/interleaver`` conventions:
each resulting sub-cluster preserves the canonical ŚB order::

  विश्वास-प्रस्तुतिः -> [विश्वास-टिप्पनी] -> मूलम्* -> पद-पाठः (यान्त्रिकः...) -> [commentaries] -> [translation] -> [मूलम् - Makoto]

and is verified in-memory via ``verify_mantra_sandhi``, ``audit_padapatha_against_sb``, and
``reconcile_markdown_blocks`` (zero audit regressions or dropped content).
"""

from __future__ import annotations

import dataclasses
import difflib
import os
import re
from pathlib import Path
from typing import Mapping, Sequence

import regex
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.llm.proofreader.block_splitter import has_genuine_iti
from doc_curation.llm.proofreader.interleave_aligner import (
  _clean_sanskrit_surface,
  extract_segment_cues,
  normalize_for_alignment,
  score_segment_against_cores,
)
from doc_curation.llm.proofreader.translation_aligner import find_core_anchor_hits
from doc_curation.sanskrit.accent.reconciler import (
  DETAILS_RE,
  DEVANAGARI_VOWELS,
  PadapathaItem,
  US_SVARITA,
  US_UDATTA,
  _STOP_NORM,
  _VOWEL_FAMILY,
  _extract_vp_pieces,
  _flatten_pp_syllables,
  _map_pp_to_vp_syllables,
  _no_punct_between,
  _pp_member_starts,
  bare_devanagari,
  format_padapatha_summary,
  format_suggested_vp_summary,
  has_us_accents,
  parse_padapatha_items,
  reconcile_markdown_blocks,
  syllables_with_marks,
)
from doc_curation.sanskrit.accent.sandhi_check import verify_mantra_sandhi
from doc_curation.sanskrit.accent.shatapatha import (
  _extract_vp_clusters,
  audit_padapatha_against_sb,
  extract_sb_syllables,
  normalize_kanva_mula_for_sb,
  normalize_sb_orthography,
  us_marks_to_sb_marks,
)

# ---------------------------------------------------------------------------
# Constants & grammatical sets
# ---------------------------------------------------------------------------

_DETAILS_BLOCK_RE = re.compile(r"<details(?:\s+(open))?><summary>([^<]+)</summary>(.*?)</details>", re.S)
_H2_SPLIT_RE = re.compile(r"(?m)(?=^##\s+)")
_FN_DEF_BLOCK_RE = re.compile(r"(?m)^\[\^([^\]]+)\]:[^\n]*(?:\n(?:[ \t]+[^\n]+|\s*(?=\n[ \t]+\S)))*")
_FN_REF_RE = re.compile(r"\[\^([^\]]+)\](?!:)")
_TRAIL_KANDIKA_NUM_RE = re.compile(r"([।॥]+\s*[०-९\d]+\s*॥+)\s*$")
_SB_MARKS = frozenset(("\u1cd8", "\u1cdf", "\u0957", "\u0951", "\u0952"))
_US_MARKS = frozenset((US_UDATTA, US_SVARITA))
_ALL_ACCENTS = frozenset(("\u1cd8", "\u1cdf", "\u0957", "\u0951", "\u0952", "\u1cd3", "\u1cd9", "\u0953", "\u0954"))
_YOGAVAAHAS = frozenset("ंःँᳫ᳭ᳮ\ua8f3")
_MATRAS = frozenset("ािीुूृॄॢॣेैोौ")
_VOW_INDEP = frozenset("अआइईउऊऋॠऌॡएऐओऔ")
_MATRA_TO_INDEP = {
  "ा": "आ", "ि": "इ", "ी": "ई", "ु": "उ", "ू": "ऊ", "ृ": "ऋ", "ॄ": "ॠ",
  "ॢ": "ऌ", "ॣ": "ॡ", "े": "ए", "ै": "ऐ", "ो": "ओ", "ौ": "औ",
}
_CONSONANTS = frozenset("कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहळ")
_HALANT = "्"

_TRANSLATION_SUMMARIES = frozenset({"Eggeling", "C R Swaminathan", "सिद्धार्थः - En", "En - सिद्धार्थः"})

# Relative/correlative & starter sets on bare (unaccented, unhyphenated) padapāṭha forms
_REL_FORMS = frozenset({
  "यत्", "यद्", "यः", "या", "यौ", "ये", "यम्", "याम्", "यान्", "येन", "यया", "यैः",
  "यस्मै", "यस्यै", "यस्मात्", "यस्माद्", "यस्य", "यस्याः", "यस्मिन्", "यस्याम्", "येषाम्",
  "यासाम्", "यत्र", "यदा", "यदि", "यथा", "यावत्", "यतः", "यर्हि",
})
_CORREL_TAD_STARTERS = frozenset({
  "तत्", "तद्", "सः", "सा", "तौ", "ते", "तम्", "ताम्", "तान्", "तेन", "तया", "तैः",
  "तस्मै", "तस्यै", "तस्य", "तस्याः", "तस्मिन्", "तस्याम्", "तेषाम्", "तासाम्",
  "तत्र", "तदा", "तथा", "तर्हि", "तावत्", "ततः", "एतत्", "एतद्", "एषः", "एषा", "एते",
})
_STRONG_SENT_STARTERS = frozenset({
  "अथ", "अथो", "तस्मात्", "तस्माद्", "सः", "सा", "ते", "तौ", "तत्", "एतत्", "एषः", "एषा",
  "अयम्", "इयम्", "इदम्", "असौ", "अतः", "इतः", "न", "कथम्", "किम्", "यत्", "यदि", "यत्र", "यदा",
  "यथा", "यस्मात्", "प्राक्", "उदीची", "प्राची", "दक्षिणा",
})
_POSTPOS_ENCLITICS = frozenset({
  "वै", "हि", "च", "वा", "उ", "तु", "एव", "ह", "इव", "किल", "खलु", "नु", "स्म", "इति", "अपि", "आ",
})
_SPEECH_VERBS = frozenset({
  "आह", "आहुः", "उवाच", "ऊचुः", "अब्रवीत्", "अब्रुवन्", "ब्रवीति", "ब्रुवन्ति", "ब्रूयात्",
  "ऐक्षत", "अमन्यत", "मन्यन्ते", "प्राह", "पप्रच्छ", "विदाम्", "अकरोत्", "उक्तम्",
})
_FINITE_ENDINGS = (
  "ति", "ते", "न्ति", "न्ते", "तिस्म", "सि", "से", "थ", "ध्वे", "मि", "मः", "महे", "स्मः",
  "यात्", "येत्", "एत्", "एत", "एयुः", "याः", "अत्", "अन्", "आम्", "तु", "न्तु", "ताम्", "न्ताम्",
  "ईत्", "ऐत्", "आत्", "अत", "त", "थाः", "ध्वम्", "स्युः", "अह", "आह", "आसीत्", "आसुः",
)

# ŚB English-Sanskrit glossary hints for bilingual DP alignment
_SB_EN_SKT_ANCHORS: dict[str, tuple[str, ...]] = {
  "fire": ("agni", "ahavaniya", "garhapatya", "dakshinagni"),
  "fires": ("agni", "ahavaniya", "garhapatya"),
  "water": ("ap", "udaka", "salila"),
  "vow": ("vrata",),
  "east": ("prac", "praci", "purastat"),
  "west": ("pratya", "pratici", "pascat"),
  "north": ("udic", "udak", "uttara"),
  "south": ("daksina", "avanci"),
  "gods": ("deva",),
  "asuras": ("asura",),
  "man": ("purusa", "manusya"),
  "men": ("purusa", "manusya"),
  "speech": ("vac", "vag"),
  "mind": ("manas", "mano"),
  "breath": ("prana",),
  "airs": ("prana",),
  "vital": ("prana",),
  "sun": ("aditya", "surya"),
  "moon": ("candrama",),
  "sky": ("dyu", "dyau", "naka"),
  "earth": ("prthivi", "iyam", "bhumi"),
  "air": ("antariksa", "vayu"),
  "heaven": ("div", "svarga", "naka"),
  "world": ("loka",),
  "sacrifice": ("yajna", "medha", "devayajana"),
  "sacrificer": ("yajamana",),
  "priest": ("brahma", "adhvaryu", "hotr", "udgatr"),
  "brahman": ("brahma",),
  "plants": ("osadhi",),
  "therefore": ("tasmat",),
  "reason": ("tasmat", "yad"),
  "because": ("hi", "yad", "tena"),
  "now": ("atha",),
  "then": ("atha", "tatas", "tada"),
  "pure": ("medhya", "pavitra", "sudh"),
  "impure": ("amedhya",),
  "untruth": ("anrta",),
  "truth": ("satya",),
  "cow": ("dhenu", "go"),
  "ox": ("anaduh",),
  "year": ("samvatsara",),
  "horse": ("asva", "haya", "vajin", "arvan"),
  "sea": ("samudra",),
  "gold": ("hiranya",),
  "verse": ("rk", "rc"),
  "metres": ("chandas",),
  "bricks": ("istaka",),
  "layer": ("citi",),
  "first": ("prathama",),
  "second": ("dvitiya",),
  "third": ("trtiya",),
  "fourth": ("caturtha",),
  "fifth": ("pancama",),
  "sixth": ("sastha",),
  "seventh": ("saptama",),
  "eighth": ("astama",),
  "ninth": ("navama",),
  "tenth": ("dasama",),
  "eleventh": ("ekadasa",),
  "twelfth": ("dvadasa",),
  "immortal": ("amrta",),
  "mortal": ("martya",),
  "form": ("rupa",),
  "forms": ("rupa",),
  "death": ("mrtyu",),
  "hunger": ("asanaya",),
  "called": ("nama",),
}

_ABBREV_EN_RE = re.compile(
  r"(?:cf|i\.e|e\.g|etc|vs|viz|vol|ch|chap|p|pp|v|vv|fig|no|nos|st|mr|dr|ms|mss|sr|śr|br|up|katy|kāty|vaj|vāj|sat|śat|rg|r̥g|s|sūt|comm|schol)\.$",
  re.I,
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class CharSyllable:
  """One phonetic Devanagari syllable with exact byte span in the scanned string."""

  start: int
  end: int
  vowel_start: int
  key: tuple[str, str]
  mark: str  # US or SB mark summary
  raw: str


@dataclasses.dataclass
class ClusterRecord:
  """Parsed contiguous ŚB kaṇḍikā cluster with its trailing layers."""

  raw_start: int
  raw_end: int
  vp_summary: str
  vp_body: str
  vp_open: bool
  pre_vp_extras: list[tuple[str, str, bool]]  # any uncommon blocks before VP inside section
  tippani_blocks: list[tuple[str, str, bool]]
  mulam_blocks: list[tuple[str, str, bool]]  # श्रीधरादि, Weber, विस्वरम्, मूलम्
  pp_summary: str
  pp_body: str
  pp_items: list[PadapathaItem]
  pp_bullet_lines: list[str]
  stale_plain_pp: tuple[str, str, bool] | None
  trailing_blocks: list[tuple[str, str, bool]]  # सायणः, हरिस्वामी, Eggeling, Swaminathan, Makoto, etc.


@dataclasses.dataclass
class SplitResult:
  """Result of splitting all clusters inside one ŚB Markdown file."""

  new_text: str
  changed: bool
  orig_clusters: int
  new_clusters: int
  kandikas_split: int
  audit_fallbacks: list[str]


# ---------------------------------------------------------------------------
# Footnote extraction / re-attachment & section structure parsing
# ---------------------------------------------------------------------------

def extract_footnotes(body: str) -> tuple[str, dict[str, str], list[str]]:
  """Separate inline body prose from ``[^id]: ...`` definitions while preserving order."""
  fn_defs: dict[str, str] = {}
  fn_order: list[str] = []

  def _collect(m: re.Match[str]) -> str:
    fid = m.group(1).strip()
    block = m.group(0).strip()
    if fid not in fn_defs:
      fn_defs[fid] = block
      fn_order.append(fid)
    else:
      fn_defs[fid] += "\n" + block
    return ""

  clean = _FN_DEF_BLOCK_RE.sub(_collect, body)
  clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
  return clean, fn_defs, fn_order


def reattach_footnotes(
  sub_bodies: list[str],
  fn_defs: dict[str, str],
  fn_order: list[str],
) -> list[str]:
  """Place each footnote definition inside the sub-block where its ``[^id]`` ref first appears."""
  if not fn_defs:
    return sub_bodies
  used: set[str] = set()
  out: list[str] = []
  last_nonempty = -1
  for i, sb in enumerate(sub_bodies):
    if sb.strip():
      last_nonempty = i

  for i, sb in enumerate(sub_bodies):
    refs: list[str] = []
    for rm in _FN_REF_RE.finditer(sb):
      fid = rm.group(1).strip()
      if fid in fn_defs and fid not in used:
        used.add(fid)
        refs.append(fid)
    if i == last_nonempty:
      # Keep any unreferenced footnote definition on the last non-empty block so zero content is lost
      for fid in fn_order:
        if fid not in used and fid in fn_defs:
          used.add(fid)
          refs.append(fid)
    if refs and sb.strip():
      defs_txt = "\n\n".join(fn_defs[fid] for fid in refs)
      out.append(sb.rstrip() + "\n\n" + defs_txt)
    else:
      out.append(sb)
  return out


def _render_details(summary: str, body: str, *, is_open: bool = False) -> str:
  open_attr = " open" if is_open else ""
  b = body.strip()
  if not b:
    return ""
  return f"<details{open_attr}><summary>{summary.strip()}</summary>\n\n{b}\n</details>"


def parse_section_clusters(part: str) -> list[ClusterRecord]:
  """Parse a ``## <heading>`` section into ordered ``ClusterRecord`` objects owning their layers."""
  dmatches = list(_DETAILS_BLOCK_RE.finditer(part))
  if not dmatches:
    return []

  # Identify contiguous VP+Mula+PP blocks using the canonical extractor logic
  vp_clusters = _extract_vp_clusters(part)
  if not vp_clusters:
    return []

  # Map each VP match to its index in dmatches
  vp_to_dm_idx: list[int] = []
  for cl in vp_clusters:
    target = cl.vp_match or cl.mula_match
    idx = next(i for i, dm in enumerate(dmatches) if dm.start() == target.start())
    vp_to_dm_idx.append(idx)

  records: list[ClusterRecord] = []
  for ci, cl in enumerate(vp_clusters):
    start_dm = vp_to_dm_idx[ci]
    next_start_dm = vp_to_dm_idx[ci + 1] if ci + 1 < len(vp_clusters) else len(dmatches)
    pre_extras: list[tuple[str, str, bool]] = []
    if ci == 0:
      for j in range(0, start_dm):
        dm = dmatches[j]
        pre_extras.append((dm.group(2).strip(), dm.group(3).strip(), bool(dm.group(1))))

    vp_sum = cl.vp_match.group(1).strip() if cl.vp_match is not None else "विश्वास-प्रस्तुतिः"
    vp_body = cl.vp_match.group(2).strip() if cl.vp_match is not None else ""
    vp_open = True if cl.vp_match is None else bool(cl.vp_match.group(0).startswith("<details open"))

    k = start_dm + 1
    tippanis: list[tuple[str, str, bool]] = []
    while k < next_start_dm and dmatches[k].group(2).strip().startswith("विश्वास-टिप्पनी"):
      dm = dmatches[k]
      tippanis.append((dm.group(2).strip(), dm.group(3).strip(), bool(dm.group(1))))
      k += 1

    mulams: list[tuple[str, str, bool]] = []
    while k < next_start_dm:
      s = dmatches[k].group(2).strip()
      if s.startswith("मूलम्") and "Makoto" not in s:
        mulams.append((s, dmatches[k].group(3).strip(), bool(dmatches[k].group(1))))
        k += 1
      else:
        break

    pp_sum = "पद-पाठः (यान्त्रिकः)"
    pp_body = ""
    if k < next_start_dm and dmatches[k].group(2).strip().startswith("पद-पाठः (यान्त्रिकः"):
      pp_sum = dmatches[k].group(2).strip()
      pp_body = dmatches[k].group(3).strip()
      k += 1

    stale_plain_pp: tuple[str, str, bool] | None = None
    if k < next_start_dm and dmatches[k].group(2).strip() == "पद-पाठः":
      stale_plain_pp = (dmatches[k].group(2).strip(), dmatches[k].group(3).strip(), bool(dmatches[k].group(1)))
      k += 1

    trailing: list[tuple[str, str, bool]] = []
    while k < next_start_dm:
      dm = dmatches[k]
      trailing.append((dm.group(2).strip(), dm.group(3).strip(), bool(dm.group(1))))
      k += 1

    pp_items = parse_padapatha_items(pp_body)
    pp_lines = [ln for ln in pp_body.splitlines() if ln.startswith("- ")]

    raw_s = dmatches[0].start() if ci == 0 else dmatches[start_dm].start()
    raw_e = dmatches[next_start_dm - 1].end()
    records.append(
      ClusterRecord(
        raw_start=raw_s,
        raw_end=raw_e,
        vp_summary=vp_sum,
        vp_body=vp_body,
        vp_open=vp_open,
        pre_vp_extras=pre_extras,
        tippani_blocks=tippanis,
        mulam_blocks=mulams,
        pp_summary=pp_sum,
        pp_body=pp_body,
        pp_items=pp_items,
        pp_bullet_lines=pp_lines,
        stale_plain_pp=stale_plain_pp,
        trailing_blocks=trailing,
      )
    )
  return records


# ---------------------------------------------------------------------------
# Devanagari byte-offset syllable scanner & exact alignment
# ---------------------------------------------------------------------------

def _ignored_char_mask(text: str, *, skip_pratika_parens: bool = True) -> list[bool]:
  """Mark char offsets belonging to non-syllable markdown markup (footnotes, notes, pratīka parens, etc.)."""
  n = len(text)
  masked = [False] * n
  patterns = [
    re.compile(r"\+\+\+.*?\+\+\+", re.S),
    re.compile(r"\[\^[^\]]+\](?::[^\n]*)?"),
    re.compile(r"\[\[[?!]+\]\]"),
    re.compile(r"\*\*|\*|`|~"),
  ]
  if skip_pratika_parens:
    patterns.append(
      re.compile(r"(?:^|(?<=\n)|(?<=[।॥]))[ \t]*(?:ॐ\s*॥\s*)?(?:\(\s*[\u0900-\u097f\u1cd0-\u1cff\u0951-\u0957\sऽ]{1,14}\)[ \t]*)+")
    )
  for pat in patterns:
    for m in pat.finditer(text):
      for idx in range(m.start(), m.end()):
        masked[idx] = True
  return masked


def scan_deva_syl_spans(text: str, *, mask_pratika_prefix: bool = True) -> list[CharSyllable]:
  """Scan Devanagari syllables keeping exact ``(start, end, vowel_start)`` character offsets in ``text``."""
  masked = _ignored_char_mask(text, skip_pratika_parens=mask_pratika_prefix)
  n = len(text)
  syls: list[CharSyllable] = []
  onset_chars: list[str] = []
  cur_start: int | None = None
  i = 0

  def _absorb_coda_and_marks(pos: int) -> int:
    """Include trailing accents, yogavāhas, and word-final halant consonants (`म्`, `त्`, `न्`, `क्`) in `syl.end`."""
    p = pos
    while p < n and not masked[p] and (text[p] in _ALL_ACCENTS or text[p] in _YOGAVAAHAS or text[p] in _US_MARKS):
      p += 1
    # Check for word-final halant consonant coda (followed by whitespace, punct, footnote/note mask, `ऽ`, or EOS)
    while p + 1 < n and not masked[p] and text[p] in _CONSONANTS and text[p + 1] == _HALANT:
      k = p + 2
      while k < n and (masked[k] or text[k] in _ALL_ACCENTS):
        k += 1
      if k >= n or text[k] not in _CONSONANTS and text[k] not in _VOW_INDEP and text[k] not in _MATRAS:
        p += 2
        while p < n and not masked[p] and (text[p] in _ALL_ACCENTS or text[p] in _YOGAVAAHAS or text[p] in _US_MARKS):
          p += 1
      else:
        break
    return p

  while i < n:
    if masked[i]:
      i += 1
      continue
    ch = text[i]
    if ch in _CONSONANTS:
      if cur_start is None:
        cur_start = i
      j = i + 1
      while j < n and masked[j]:
        j += 1
      if j < n and text[j] == _HALANT:
        k = j + 1
        while k < n and masked[k]:
          k += 1
        if k < n and text[k] in _CONSONANTS:
          onset_chars.append(ch)
          i = j + 1
          continue
        else:
          # Orphan coda halant (should be attached to previous syl if adjacent, or skip safely)
          if syls and syls[-1].end >= cur_start - 2:
            syls[-1].end = j + 1
            syls[-1].raw = text[syls[-1].start : j + 1]
          onset_chars.clear()
          cur_start = None
          i = j + 1
          continue
      elif j < n and (text[j] in _MATRAS or text[j] in _ALL_ACCENTS or text[j] in _YOGAVAAHAS):
        onset_chars.append(ch)
        v_start = j
        if text[j] in _MATRAS:
          v0 = _MATRA_TO_INDEP[text[j]]
          j += 1
        else:
          v0 = "अ"
        marks: list[str] = []
        p = j
        while p < n and not masked[p] and (text[p] in _ALL_ACCENTS or text[p] in _YOGAVAAHAS or text[p] in _US_MARKS):
          if text[p] in _ALL_ACCENTS or text[p] in _US_MARKS:
            marks.append(text[p])
          p += 1
        end_pos = _absorb_coda_and_marks(p)
        c_norm = _norm_onset(onset_chars)
        syls.append(CharSyllable(
          start=cur_start, end=end_pos, vowel_start=v_start,
          key=(c_norm, _VOWEL_FAMILY.get(v0, "a")),
          mark="".join(marks), raw=text[cur_start:end_pos],
        ))
        onset_chars.clear()
        cur_start = None
        i = end_pos
        continue
      else:
        onset_chars.append(ch)
        end_pos = _absorb_coda_and_marks(i + 1)
        c_norm = _norm_onset(onset_chars)
        syls.append(CharSyllable(
          start=cur_start, end=end_pos, vowel_start=i,
          key=(c_norm, "a"), mark="", raw=text[cur_start:end_pos],
        ))
        onset_chars.clear()
        cur_start = None
        i = end_pos
        continue
    elif ch in _VOW_INDEP:
      st = i if cur_start is None else cur_start
      v0 = ch
      j = i + 1
      marks = []
      while j < n and not masked[j] and (text[j] in _ALL_ACCENTS or text[j] in _YOGAVAAHAS or text[j] in _US_MARKS):
        if text[j] in _ALL_ACCENTS or text[j] in _US_MARKS:
          marks.append(text[j])
        j += 1
      end_pos = _absorb_coda_and_marks(j)
      c_norm = _norm_onset(onset_chars)
      syls.append(CharSyllable(
        start=st, end=end_pos, vowel_start=i,
        key=(c_norm, _VOWEL_FAMILY.get(v0, "a")),
        mark="".join(marks), raw=text[st:end_pos],
      ))
      onset_chars.clear()
      cur_start = None
      i = end_pos
      continue
    else:
      if ch in " \t\n।॥,;—-ऽ":
        onset_chars.clear()
        cur_start = None
      i += 1

  return syls


def _norm_onset(onset_chars: list[str]) -> str:
  c_norm = "".join(_STOP_NORM.get(c, c) for c in onset_chars)
  return re.sub(r"(.)\1+", r"\1", c_norm)


def _norm_bare_word(s: str) -> str:
  return re.sub(r"[^अ-हऀ-ृे-ौ्ँंःऽ]", "", accent.strip_accents(s)).replace("ः", "").replace("ं", "").replace("म्", "म")


def _pada_bare_forms(items: Sequence[PadapathaItem]) -> list[str]:
  out: list[str] = []
  for it in items:
    ref = it.ref if it.ref != "?" else it.ar
    w = accent.strip_accents(ref).replace("-", "")
    out.append(w)
  return out


def _align_layer_syls_to_pp(
  layer_syls: Sequence[CharSyllable],
  pp_items: Sequence[PadapathaItem],
) -> tuple[list[int], list[tuple[int, ...]]]:
  """Map every syllable of ``layer_syls`` to owning ``pp_items`` index(es) monotonically via banded DP."""
  pp_keys, pp_meta, _, _ = _flatten_pp_syllables(pp_items)
  ls_keys = [s.key for s in layer_syls]
  np = len(pp_keys)
  nl = len(ls_keys)
  if nl == 0 or np == 0:
    return [-1] * nl, [() for _ in range(nl)]

  # Fast banded global Needleman-Wunsch DP: handles resyllabification (`यत् अपः -> यदपो`),
  # 2-to-1 sandhi fusion, and repeated refrain words (`वज्रो वा आपो...`) without forward-jumps.
  band = max(24, abs(np - nl) + 18)
  NEG_INF = -1e9
  dp = [[NEG_INF] * (nl + 1) for _ in range(np + 1)]
  bt = [[(0, 0)] * (nl + 1) for _ in range(np + 1)]
  dp[0][0] = 0.0
  # Allow free leading inserts in layer (e.g. विस्वरम् bold title / ॐ॥ before pp_items[0])
  for b in range(1, min(nl + 1, band + 1)):
    dp[0][b] = -0.3 * b
    bt[0][b] = (0, b - 1)

  for a in range(np + 1):
    b_lo = max(0, a - band)
    b_hi = min(nl, a + band)
    for b in range(b_lo, b_hi + 1):
      cur = dp[a][b]
      if cur <= NEG_INF * 0.5:
        continue
      diag_pen = 0.015 * abs((a - b))
      # 1 -> 1 match / replace
      if a < np and b < nl:
        pk, lk = pp_keys[a], ls_keys[b]
        if pk == lk:
          sc = 4.0
        elif pk[1] == lk[1] and (pk[0] == "" or lk[0] == "" or pk[0][-1:] == lk[0][-1:]):
          sc = 2.4
        elif pk[0] == lk[0] and pk[0] != "":
          sc = 2.0  # e.g. final `पः` -> `पो`
        elif pk[1] == lk[1]:
          sc = 1.0
        else:
          sc = -1.2
        val = cur + sc - diag_pen
        if val > dp[a + 1][b + 1]:
          dp[a + 1][b + 1], bt[a + 1][b + 1] = val, (a, b)
      # 2 -> 1 sandhi vowel coalescence or yan merger (`इति + अ -> त्य`, `त + इ -> ते`)
      if a + 2 <= np and b + 1 <= nl and (a + 2 - (b + 1)) <= band:
        p1, p2, lk = pp_keys[a], pp_keys[a + 1], ls_keys[b]
        sc = 2.6 if (p1[0] == lk[0] or lk[0].endswith(p1[0])) else 0.4
        val = cur + sc - diag_pen
        if val > dp[a + 2][b + 1]:
          dp[a + 2][b + 1], bt[a + 2][b + 1] = val, (a, b)
      # 1 -> 2 resyllabification (`यत् + अपः -> य-द-पो`: skip coda/onset shift across `pp[a]` -> `ls[b], ls[b+1]`)
      if a + 1 <= np and b + 2 <= nl and abs((a + 1) - (b + 2)) <= band:
        pk, l1, l2 = pp_keys[a], ls_keys[b], ls_keys[b + 1]
        if pk == l1 or (pk[0] == l1[0] and l2[0] != ""):
          val = cur + 1.8 - diag_pen
          if val > dp[a + 1][b + 2]:
            dp[a + 1][b + 2], bt[a + 1][b + 2] = val, (a, b)
      # Skip in pp or insert in layer (svarabhakti / bold header / extra word)
      if a + 1 <= np and abs((a + 1) - b) <= band:
        val = cur - 2.4
        if val > dp[a + 1][b]:
          dp[a + 1][b], bt[a + 1][b] = val, (a, b)
      if b + 1 <= nl and abs(a - (b + 1)) <= band:
        pen = 1.6 if a > 0 else 0.4
        val = cur - pen
        if val > dp[a][b + 1]:
          dp[a][b + 1], bt[a][b + 1] = val, (a, b)

  syl_owners: list[set[int]] = [set() for _ in range(nl)]
  ca, cb = np, nl
  while ca > 0 or cb > 0:
    pa, pb = bt[ca][cb]
    if (pa, pb) == (ca, cb):
      break
    if cb > pb and ca > pa:
      for pi in range(pa, ca):
        p_idx = pp_meta[pi][0]
        for li in range(pb, cb):
          syl_owners[li].add(p_idx)
    elif cb > pb and ca == pa:
      owner = pp_meta[pa - 1][0] if pa > 0 else -1
      for li in range(pb, cb):
        syl_owners[li].add(owner)
    ca, cb = pa, pb

  primary: list[int] = []
  last_p = 0
  for s in syl_owners:
    clean = sorted(x for x in s if x >= 0)
    if clean:
      p = clean[0]
      last_p = clean[-1]
    elif -1 in s:
      p = -1
    else:
      p = last_p
    primary.append(p)
  return primary, [tuple(sorted(x for x in s if x >= 0)) for s in syl_owners]


# ---------------------------------------------------------------------------
# Candidate boundary detection & /text_to_blocks Tests 1–5 lock rules
# ---------------------------------------------------------------------------

def _is_finite_verb_pada(it: PadapathaItem, bare_form: str) -> bool:
  if "तिङन्तम्" in it.prov or "यद्वृत्तान्नित्यम्" in it.prov:
    return True
  # Common finite verb endings (avoid matching participial -न्त्/-अत्/-त/-वान् nouns unless clear finite)
  if any(bare_form.endswith(suf) for suf in ("ति", "ते", "न्ति", "न्ते", "स्युः", "एयुः", "आह", "उवाच", "बभूव", "आसीत्", "स्यति", "स्यते", "स्यात्", "भवेत्", "ब्रुवन्", "अब्रवीत्", "ऐक्षत", "अमन्यत", "जोषयेरन्", "कुर्यात्", "इयात्")):
    if len(bare_form) >= 3 and bare_form not in ("इति", "पतिः", "रात्रिः", "सति", "प्रजापतिः", "गृहपतिः", "वनस्पतिः"):
      return True
  return False


def _detect_must_keep_locks(
  vp_body: str,
  pp_items: Sequence[PadapathaItem],
  vp_pieces: list[dict],
  pc_syl_sources: list[list[list[tuple[int, ...]]]],
  pp_meta: list[tuple[int, int]],
) -> list[bool]:
  """Compute ``must_keep[k]`` (len P-1): True when cutting after ``pp_items[k]`` violates Tests 1–5."""
  n = len(pp_items)
  locks = [False] * max(0, n - 1)
  if n < 2:
    return locks

  bares = _pada_bare_forms(pp_items)

  # 1. Lock inside any `+++(...)+++` or explicit `"..."` quote span or unsplit `[[OLD|NEW]]`?
  #    Actually `+++(...)+++` is external to pieces: lock across gap if `+++...+++` spans >1 piece without boundary punct
  quote_depth = 0
  quote_padas: set[int] = set()
  last_piece_end = 0
  piece_pada_ranges: list[tuple[int, int]] = []
  for pi, pc in enumerate(vp_pieces):
    p_idxs = [pp_meta[ps[0]][0] for src in pc_syl_sources[pi] for ps in src if ps]
    if p_idxs:
      piece_pada_ranges.append((min(p_idxs), max(p_idxs)))
    else:
      piece_pada_ranges.append((-1, -1))
    gap = vp_body[last_piece_end : pc["start"]]
    quote_depth = (quote_depth + gap.count('"') + gap.count("“") - gap.count("”")) % 2
    if quote_depth == 1 and p_idxs:
      quote_padas.update(p_idxs)
    tok = pc["old"]
    if ('"' in tok or "“" in tok or "”" in tok) and p_idxs:
      q_open = tok.count("“") + (1 if tok.startswith('"') else 0)
      q_close = tok.count("”") + (1 if tok.endswith('"') and len(tok) > 1 else 0)
      if quote_depth == 1 or q_open != q_close:
        quote_padas.update(p_idxs)
      if tok.count('"') % 2 == 1:
        quote_depth ^= 1
      quote_depth = max(0, (quote_depth + tok.count("“") - tok.count("”")) % 2)
    last_piece_end = pc["end"]

  # Lock adjacent quote_padas inside short/medium quoted speeches (<= 24 padas)
  for k in range(n - 1):
    if k in quote_padas and (k + 1) in quote_padas:
      # Find continuous quote extent
      l, r = k, k + 1
      while l > 0 and (l - 1) in quote_padas:
        l -= 1
      while r + 1 < n and (r + 1) in quote_padas:
        r += 1
      if (r - l + 1) <= 28:
        locks[k] = True

  # 2. Protect every `इति` closure: never split right BEFORE `इति`, lock short preceding quote (<= 16 padas
  #    from speech-introducer or last sentence boundary), and lock following `इति ह स्माह <Speaker>` attribution.
  for j, bf in enumerate(bares):
    if bf == "इति":
      if j - 1 >= 0:
        locks[j - 1] = True  # never split before `इति`
      # Lock backwards to an explicit speech verb introducer if within 18 padas
      for back in range(j - 1, max(-1, j - 19), -1):
        if bares[back] in _SPEECH_VERBS and bares[back] not in ("इति",):
          for m_idx in range(back, j):
            locks[m_idx] = True
          break
        # If there is a mantra vocative or 1st-person optative/fut like अग्ने / चरिष्यामि / उपायानि after last finite verb
        if j - back <= 12 and bares[back] in ("अग्ने", "इन्द्र", "विष्णो", "सूर्य", "हन्त"):
          for m_idx in range(back, j):
            locks[m_idx] = True
          break
      # Lock forwards across `इति ह स्माह आसुरिः` / `इति होवाच याज्ञवल्क्यः` / `इति ब्रह्मा`
      if j + 1 < n and bares[j + 1] in ("ह", "वै", "स्म", "उवाच", "आह", "आहुः", "ऊचुः", "अन्यः", "नाना"):
        for f in range(j, min(n - 1, j + 5)):
          locks[f] = True
          if _is_finite_verb_pada(pp_items[f], bares[f]) and f + 1 < n and bares[f + 1] in _STRONG_SENT_STARTERS:
            break

  # 3. Enclitic / postposition guard: never split BEFORE वै, हि, च, वा, उ, तु, एव, इव, अपि, नाम
  for k in range(n - 1):
    if bares[k + 1] in _POSTPOS_ENCLITICS:
      locks[k] = True
    # Also don't split between 1-word subject/pronoun and its immediate 2nd-pos enclitic particle!
    # (`सः वै`, `अग्निः वै`, `तद् यद्`): if k == 0 or locks[k-1] == False ... handled automatically by above!
    # Also never split after bare pronoun/conjunction (`सः`, `यद्`, `तद्`, `अथ`, `तस्मात्`, `यथा`, `इव`, `च`, `वा`)!
    if bares[k] in _REL_FORMS or bares[k] in _CORREL_TAD_STARTERS or bares[k] in ("अथ", "अथो", "तस्मात्", "तस्माद्", "च", "वा", "वै", "हि", "न", "मा"):
      locks[k] = True

  # 4. Relative-correlative lock (Test 1: `यत् ... तत् ...`, `स य...`, `यथा ... तथा ...`):
  #    Walk clause by clause using provisional finite verbs / `।`: if a chunk contains an unresolved
  #    relative `य*` without a following correlative predicate inside it, lock across its end!
  #    Also if the NEXT word after a finite verb is a postposed relative (`... उपोत्क्रामति यो दीक्षते`), lock,
  #    UNLESS the upcoming `य*` itself starts a brand-new `यत् ... तत्` correlative pair!
  for k in range(n - 1):
    if bares[k + 1] in _REL_FORMS and k >= 1 and _is_finite_verb_pada(pp_items[k], bares[k]):
      # Walk backwards up to clause start (`k-7..k`)
      win_prev = bares[max(0, k - 7) : k + 1]
      # Only lock postposed relative if previous span didn't already resolve a `य*`, AND the new `य*`
      # doesn't introduce its own `तत्`/`तद्` apodosis within 6 padas (`यद्विजृम्भते तद्विद्योतते`).
      prev_had_rel = any(w in _REL_FORMS for w in win_prev)
      next_has_correl = any(w in _CORREL_TAD_STARTERS for w in bares[k + 2 : min(n, k + 8)])
      if not prev_had_rel and not next_has_correl and any(w in ("एषः", "एषा", "तत्", "तद्", "सः", "ते", "तस्मै") for w in win_prev):
        locks[k] = True

  # Detect unresolved leading `य...` waiting for `त...` in the next <= 16 padas:
  last_rel = -1
  has_correl_since_rel = False
  for j, bf in enumerate(bares):
    if bf in _REL_FORMS:
      # Check if previous 1..2 padas was `तत्` as in `तद् यद्` ("The reason why...") or `स यः` ("Whoever...")
      last_rel = j
      has_correl_since_rel = False
    elif last_rel >= 0:
      if bf in _CORREL_TAD_STARTERS or bf in ("तस्मात्", "तस्माद्") and j > last_rel + 1:
        has_correl_since_rel = True
      # While `last_rel >= 0` and NOT `has_correl_since_rel` and still within reasonable correlative distance (<= 16 padas):
      # if we hit a finite verb inside the `yad` clause (`उपस्पृशति`), don't split before its `tad` resolution!
      if j < n - 1 and not has_correl_since_rel and (j - last_rel) <= 16:
        if _is_finite_verb_pada(pp_items[j], bf):
          # Look ahead up to 10 padas to see if a correlative main verb or `तस्मात्`/`तद्`/`तेन`/`एतद्` actually follows
          if any(bares[m] in _CORREL_TAD_STARTERS for m in range(j + 1, min(n, j + 10))):
            locks[j] = True
          elif any(bares[m] in ("अमेध्यः", "तेन", "एव", "हि") for m in range(j + 1, min(n, j + 6))) and last_rel > 0 and bares[last_rel - 1] in ("तत्", "तद्"):
            # `तद् यद् अप उपस्पृशति । अमेध्यो वै पुरुषो यद् अनृतं वदति, तेन पूतिर् अन्तरतः`
            locks[j] = True

  # 5. Lock nominal enumerations unless there are >= 4 padas AND a finite verb / sentence break
  #    Check `SBM 01/01/1`: Never split right after a participial opener (e.g. `व्रतमुपैष्यन्`) lacking any finite verb in 0..k
  has_verb_before = False
  for k in range(n - 1):
    if _is_finite_verb_pada(pp_items[k], bares[k]) or bares[k] == "इति":
      has_verb_before = True
    if not has_verb_before and k < 6:
      # Allow opening nominal equational predication like `उषा वा अश्वस्य मेध्यस्य शिरः` only if `वै` occurred
      if "वै" not in bares[: k + 1]:
        locks[k] = True

  return locks


def _project_visvaram_dandas(
  visv_text: str,
  pp_items: Sequence[PadapathaItem],
) -> set[int]:
  """Map every internal ``।`` / ``॥`` in ``मूलम् - विस्वरम्`` onto its exact ``pp_items`` cut index ``k``."""
  if not visv_text:
    return set()
  clean = _TRAIL_KANDIKA_NUM_RE.sub("", visv_text).strip()
  clean, _, _ = extract_footnotes(clean)
  # Strip bold section headers at top
  clean_lines = [ln for ln in clean.splitlines() if not re.match(r"^\s*\*\*[^*\n]+\*\*\s*$", ln)]
  clean = "\n".join(clean_lines)
  syls = scan_deva_syl_spans(clean, mask_pratika_prefix=False)
  if not syls:
    return set()
  primary, _ = _align_layer_syls_to_pp(syls, pp_items)
  danda_padas: set[int] = set()
  n_pp = len(pp_items)
  for idx in range(len(syls) - 1):
    gap = clean[syls[idx].end : syls[idx + 1].start]
    if ("।" in gap or "॥" in gap) and 0 <= primary[idx] < n_pp - 1:
      danda_padas.add(primary[idx])
  return danda_padas


def _project_vp_dandas_and_paras(
  vp_body: str,
  pp_items: Sequence[PadapathaItem],
  vp_pieces: list[dict],
  pc_syl_sources: list[list[list[tuple[int, ...]]]],
  pp_meta: list[tuple[int, int]],
) -> tuple[set[int], set[int]]:
  """Find existing ``।``/``॥`` and blank-line paragraph breaks inside ``विश्वास-प्रस्तुतिः``."""
  dandas: set[int] = set()
  paras: set[int] = set()
  n = len(pp_items)
  for pi in range(len(vp_pieces) - 1):
    gap = vp_body[vp_pieces[pi]["end"] : vp_pieces[pi + 1]["start"]]
    p_idxs = [pp_meta[ps[0]][0] for src in pc_syl_sources[pi] for ps in src if ps]
    if not p_idxs:
      continue
    pk = max(p_idxs)
    if pk >= n - 1:
      continue
    if "।" in gap or "॥" in gap:
      dandas.add(pk)
    if re.search(r"\n[ \t]*\n", gap):
      paras.add(pk)
  return dandas, paras


def _project_commentary_pratika_breaks(
  comm_blocks: Sequence[tuple[str, str]],
  pp_items: Sequence[PadapathaItem],
) -> set[int]:
  """Locate where major commentary pratīka headers (`**bold**`) begin inside ``pp_items``."""
  breaks: set[int] = set()
  if not comm_blocks or len(pp_items) < 4:
    return breaks
  bares = _pada_bare_forms(pp_items)
  n = len(bares)
  # Build concatenated bare forms and start offset per pada
  pada_norms = [normalize_for_alignment(b)["compact"] for b in bares]
  full_str = "".join(pada_norms)
  starts: list[int] = []
  pos = 0
  for pn in pada_norms:
    starts.append(pos)
    pos += len(pn)

  for title, body in comm_blocks:
    if title.startswith("मूलम्"):
      continue
    clean_b, _, _ = extract_footnotes(body)
    bold_matches = list(re.finditer(r"\*\*([^*।\n]{3,60})\*\*", clean_b))
    cursor = 0
    for bm in bold_matches:
      # Strip trailing इति in bold pratīka (`तद्यदिति` -> `तद्यद्` / `सोऽग्निमिति` -> `सोऽग्निम्`)
      raw_p = bm.group(1).strip()
      p_norm = normalize_for_alignment(re.sub(r"इति\s*$", "", raw_p))["compact"]
      # Remove trailing `ति` if `...इति` sandhi (`तद्यदि`ti -> `तद्यद्` or match prefix)
      p_probe = p_norm[: min(len(p_norm), 10)]
      if len(p_probe) < 3:
        continue
      for k in range(cursor, n - 1):
        if k == 0:
          continue
        joined_from_k = full_str[starts[k] : starts[k] + 18]
        # Allow matching prefix (6+ chars or full short pratīka without last sandhi vowel)
        need = min(len(p_probe), max(4, len(p_probe) - 2))
        if joined_from_k.startswith(p_probe[:need]):
          breaks.add(k - 1)
          cursor = k + 1
          break
  return breaks


# ---------------------------------------------------------------------------
# English clause segmentation & Translation-guided alignment
# ---------------------------------------------------------------------------

def split_english_clauses(text: str) -> list[str]:
  """Split Eggeling / C. R. Swaminathan prose into sentence and semicolon clauses safely."""
  clean = text.strip()
  if not clean:
    return []
  clauses: list[str] = []
  buf: list[str] = []
  paren_d = 0
  bracket_d = 0
  sq_open = False
  dq_open = False
  i = 0
  n = len(clean)

  while i < n:
    ch = clean[i]
    buf.append(ch)
    if ch == "(":
      paren_d += 1
    elif ch == ")":
      paren_d = max(0, paren_d - 1)
    elif ch == "[":
      bracket_d += 1
    elif ch == "]":
      bracket_d = max(0, bracket_d - 1)
    elif ch == "“":
      dq_open = True
    elif ch == "”":
      dq_open = False
    elif ch == '"':
      dq_open = not dq_open
    elif ch == "‘":
      sq_open = True
    elif ch == "’" and not (i > 0 and clean[i - 1].isalpha() and i + 1 < n and clean[i + 1].isalpha()):
      sq_open = False

    if paren_d == 0 and bracket_d == 0 and not dq_open:
      if ch in (";", "?", "!") or (ch == "." and not (i + 1 < n and clean[i + 1].isdigit())):
        so_far = "".join(buf).strip()
        # Do not break after initials / abbreviations / leading section numbers like `1.` or `II.`
        is_num_prefix = bool(re.match(r"^(?:[IVXLC]+|\d+)\.$", so_far))
        is_abbr = ch == "." and bool(_ABBREV_EN_RE.search(so_far))
        is_roman = ch == "." and bool(re.search(r"\b[IVXLC]{1,4}\.$", so_far))
        # Peek ahead past whitespace & optional `[^egg_...]` footnote refs!
        j = i + 1
        while j < n and clean[j] in " \t\n":
          j += 1
        # Keep trailing `]`/`'`/`"`/`[^fn]` attached to the sentence before splitting
        if not is_num_prefix and not is_abbr and not is_roman and j < n:
          # Absorb closing quote or footnote ref directly touching this punct (`.' [^egg_84]`)
          k = i + 1
          while k < n and clean[k] in "'’\"”)":
            buf.append(clean[k])
            k += 1
          m_fn = re.match(r"[ \t]*\[\^[^\]]+\](?=[ \t]|$)", clean[k:])
          if m_fn:
            buf.append(m_fn.group(0))
            k += len(m_fn.group(0))
          if k < n and clean[k:].strip():
            # Require uppercase start or quote/bracket/number after `.`, whereas `;` always separates clauses
            rem = clean[k:].lstrip()
            if ch == ";" or (rem and (rem[0].isupper() or rem[0] in "'\"“[(")):
              clauses.append("".join(buf).strip())
              buf = []
              i = k
              while i < n and clean[i] in " \t":
                i += 1
              continue
    i += 1

  tail = "".join(buf).strip()
  if tail:
    clauses.append(tail)
  return clauses


def _stem_word(w: str) -> str:
  return w[: max(4, len(w) - 2)] if len(w) > 5 else w


def _core_anchor_stems(padas: Sequence[PadapathaItem]) -> set[str]:
  """Convert a span of ŚB padapāṭha forms to lowercase IAST stems + English anchor stems."""
  stems: set[str] = set()
  for it in padas:
    raw = bare_devanagari(it.ref if it.ref != "?" else it.ar)
    iast = sanscript.transliterate(raw, sanscript.DEVANAGARI, sanscript.IAST).lower()
    for part in re.findall(r"[a-zāīūṛṝḷśṣḥṅñṇṭḍ]+", iast):
      st = _stem_word(part)
      if len(st) >= 3:
        stems.add(st)
  return stems


_IAST_ASCII_TRANS = str.maketrans("āīūṛṝḷśṣḥṅñṇṭḍṁṃ", "aiurrlshnnntdmmm")


def _clause_skt_en_score(skt_stems: set[str], en_clause: str) -> float:
  """Score semantic/lexical overlap between one Sanskrit span and one English clause."""
  low_words = set(re.findall(r"[a-z]+", en_clause.lower()))
  score = 0.0
  # 1. Direct transliteration stem overlap (`agni`, `vrata`, `surya`, `samidheni`, `aditi`, ...)
  en_stems = {_stem_word(w) for w in low_words if len(w) >= 4}
  for ss in skt_stems:
    ascii_ss = ss.translate(_IAST_ASCII_TRANS)
    for es in en_stems:
      if len(ascii_ss) >= 4 and len(es) >= 4 and (ascii_ss.startswith(es[:4]) or es.startswith(ascii_ss[:4])):
        score += 2.5
        break
  # 2. ŚB sacrificial bilingual glossary overlap
  for en_kw, skt_opts in _SB_EN_SKT_ANCHORS.items():
    if en_kw in low_words:
      for opt in skt_opts:
        if any(ss.startswith(opt) for ss in skt_stems):
          score += 2.0
          break
  return score


def _translation_guided_breaks(
  pp_items: Sequence[PadapathaItem],
  tr_text: str,
  locked: Sequence[bool],
  cand_scores: Sequence[float],
) -> set[int]:
  """Align translation period/semicolon boundaries to unlocked Sanskrit clause breaks via monotonic DP."""
  n = len(pp_items)
  clean_tr, _, _ = extract_footnotes(tr_text)
  en_clauses = split_english_clauses(clean_tr)
  if len(en_clauses) < 2 or n < 12:
    return set()

  # Extract Sanskrit atomic candidate spans partitioned at strong/moderate unlocked cuts
  cuts = [k for k in range(n - 1) if not locked[k] and cand_scores[k] >= 1.5]
  if not cuts:
    return set()
  spans = []
  prev = 0
  for c in cuts:
    spans.append((prev, c + 1))
    prev = c + 1
  spans.append((prev, n))
  m_s = len(spans)
  if m_s <= 1:
    return set()

  # Group consecutive atomic English clauses only when there are far more en_clauses than spans
  m_e = len(en_clauses)
  skt_stems = [_core_anchor_stems(pp_items[a:b]) for a, b in spans]
  skt_tot = sum(b - a for a, b in spans) or 1
  en_wcs = [max(1, len(c.split())) for c in en_clauses]
  en_tot = sum(en_wcs) or 1

  # Monotonic DP partitioning `en_clauses[0..m_e]` onto `spans[0..m_s]` (allowing >= 1 en clause or skip per span)
  # Wait: what matters for boundary guidance is matching each period-ending English clause index `e` to span boundary `s`!
  cum_s = [0]
  for a, b in spans:
    cum_s.append(cum_s[-1] + (b - a))
  cum_e = [0]
  for w in en_wcs:
    cum_e.append(cum_e[-1] + w)

  tr_bounds: set[int] = set()
  # For each major English period/semicolon end `e_end`, find best matching cut `cuts[si]`
  for ei in range(m_e - 1):
    # Proportional word position of end of en_clauses[ei]
    is_period = en_clauses[ei].rstrip("'\") ").endswith((".", "!", "?")) or bool(
      re.search(r"[.?!]['\"\)]*\s*(?:\[\^[^\]]+\])?\s*$", en_clauses[ei])
    )
    prop = cum_e[ei + 1] / en_tot
    best_si = -1
    best_val = -1e9
    for si in range(m_s - 1):
      s_prop = cum_s[si + 1] / skt_tot
      dist_pen = abs(s_prop - prop) * 14.0
      left_match = _clause_skt_en_score(skt_stems[si], en_clauses[ei])
      right_match = _clause_skt_en_score(skt_stems[si + 1], en_clauses[ei + 1])
      val = cand_scores[cuts[si]] * 0.4 + left_match + right_match - dist_pen
      if is_period:
        val += 1.0
      if val > best_val:
        best_val = val
        best_si = si
    if best_si >= 0 and abs(cum_s[best_si + 1] / skt_tot - prop) <= 0.25:
      tr_bounds.add(cuts[best_si])
  return tr_bounds


# ---------------------------------------------------------------------------
# Sense-unit boundary selector (`0 = b_0 < b_1 < ... < b_K = P`)
# ---------------------------------------------------------------------------

def select_cluster_split_points(
  cluster: ClusterRecord,
  *,
  parallel_hint: tuple[str, str] | None = None,
) -> list[int]:
  """Select pada split indices ``[b_1, ..., b_{K-1}]`` partitioning one kaṇḍikā into fine sense units."""
  items = cluster.pp_items
  n = len(items)
  if n < 15:
    # Keep very short kaṇḍikās intact unless >1 distinct long sentence (>10p each)
    return []

  bares = _pada_bare_forms(items)
  vp_pieces = _extract_vp_pieces(cluster.vp_body)
  pp_keys, pp_meta, _, _ = _flatten_pp_syllables(items)
  vp_keys = [kv for pc in vp_pieces for kv in pc["keys"]]
  vp_meta = [(pi, si) for pi, pc in enumerate(vp_pieces) for si in range(len(pc["keys"]))]
  pc_syl_sources = _map_pp_to_vp_syllables(
    cluster.vp_body, vp_pieces, pp_keys, pp_meta, vp_keys, vp_meta, _pp_member_starts(items)
  )

  locked = _detect_must_keep_locks(cluster.vp_body, items, vp_pieces, pc_syl_sources, pp_meta)

  # Signal 1: explicit VP daṇḍas & paragraph breaks
  vp_dandas, vp_paras = _project_vp_dandas_and_paras(cluster.vp_body, items, vp_pieces, pc_syl_sources, pp_meta)

  # Signal 2: विस्वरम् (or SBM parallel hint for SBK 17)
  visv_body = next((b for s, b, _ in cluster.mulam_blocks if s == "मूलम् - विस्वरम्"), "")
  visv_dandas = _project_visvaram_dandas(visv_body, items)
  makoto_body = next((b for s, b, _ in cluster.trailing_blocks if s == "मूलम् - Makoto"), "")
  makoto_dandas = _project_visvaram_dandas(makoto_body, items)
  if not visv_dandas and parallel_hint and parallel_hint[0]:
    visv_dandas = _project_visvaram_dandas(parallel_hint[0], items)

  # Signal 3: Sanskrit commentary pratīkas (सायणः / हरिस्वामी / वासुदेव / रङ्गरामानुजः)
  comm_blocks = [(s, b) for s, b, _ in cluster.trailing_blocks if s not in _TRANSLATION_SUMMARIES and not s.startswith("मूलम्")]
  comm_breaks = _project_commentary_pratika_breaks(comm_blocks, items)

  # Signal 4: Syntactic clause boundaries on padapāṭha
  cand_scores = [0.0] * (n - 1)
  for k in range(n - 1):
    if locked[k]:
      continue
    s = 0.0
    if k in visv_dandas:
      s += 4.0
    if k in vp_dandas:
      s += 3.5
    if k in vp_paras:
      s += 2.5
    if k in makoto_dandas:
      s += 2.5
    if k in comm_breaks:
      s += 4.0
    is_fv = _is_finite_verb_pada(items[k], bares[k])
    is_iti = bares[k] == "इति"
    nxt_starter = bares[k + 1] in _STRONG_SENT_STARTERS
    nxt2_vai = (k + 2 < n and bares[k + 2] in ("वै", "हि", "ह"))
    if is_fv or is_iti:
      s += 2.0
      if nxt_starter or nxt2_vai:
        s += 2.5
    elif nxt2_vai and k >= 3:
      # Nominal `X वै Y` sentence boundary when preceded by completed predication
      if "वै" in bares[max(0, k - 6) : k + 1] or bares[k + 1] in ("तस्मात्", "तस्माद्", "अथ"):
        s += 1.8
    cand_scores[k] = s

  # Signal 5: Translation alignment (Eggeling / C R Swaminathan / SBM Eggeling hint)
  tr_text = next((b for s, b, _ in cluster.trailing_blocks if s in ("Eggeling", "C R Swaminathan")), "")
  if not tr_text and parallel_hint and parallel_hint[1]:
    tr_text = parallel_hint[1]
  tr_breaks = _translation_guided_breaks(items, tr_text, locked, cand_scores) if tr_text else set()
  for k in tr_breaks:
    if not locked[k]:
      cand_scores[k] += 3.5

  # Select cohesive unit split points via 1D DP balancing boundary confidence and target unit length (~10-32 padas)
  # Only consider cuts with meaningful evidence (>= 3.5, or >= 2.2 when creating an overlong span escape)
  valid_cuts = [k + 1 for k in range(n - 1) if not locked[k] and cand_scores[k] >= 3.2]
  # Check if any residual span exceeds 38 padas and unlock >= 2.0 syntactic breaks inside it
  all_pts = [0] + valid_cuts + [n]
  extra: list[int] = []
  for idx in range(len(all_pts) - 1):
    a, b = all_pts[idx], all_pts[idx + 1]
    if b - a > 38:
      for k in range(a, b - 1):
        if not locked[k] and cand_scores[k] >= 2.0 and (k + 1) not in valid_cuts:
          extra.append(k + 1)
  pts = sorted(set([0] + valid_cuts + extra + [n]))
  if len(pts) <= 2:
    return []

  # 1D DP over `pts`: choose subset ending at `n` maximizing total boundary score - size penalty
  score_at = {0: 0.0, n: 0.0}
  for p in pts[1:-1]:
    k = p - 1
    score_at[p] = cand_scores[k]

  m = len(pts)
  dp = [-1e9] * m
  back = [-1] * m
  dp[0] = 0.0
  for j in range(1, m):
    end_p = pts[j]
    for i in range(j):
      start_p = pts[i]
      length = end_p - start_p
      # Min chunk size = 6 padas UNLESS strong explicit opening injunction (`अथ ब्रह्माणं दीक्षयति` = 3p with comm + tr + visv >= 7.5)
      if length < 3:
        continue
      b_bonus = score_at[end_p] if j < m - 1 else 0.0
      if length < 6:
        if i == 0 and b_bonus >= 7.0:
          size_pen = 1.5
        else:
          size_pen = 12.0  # forbid tiny micro-crumbs
      elif length < 9:
        size_pen = 3.2
      elif length <= 32:
        size_pen = 0.0
      elif length <= 45:
        size_pen = (length - 32) * 0.25
      else:
        size_pen = 3.25 + (length - 45) * 0.55

      # Split reward baseline (-3.6 threshold so weak 3.2 boundaries don't split mediocre chunks)
      cut_cost = 3.6 if j < m - 1 else 0.0
      cand = dp[i] + b_bonus - cut_cost - size_pen
      if cand > dp[j]:
        dp[j] = cand
        back[j] = i

  # Reconstruct chosen split points
  chosen: list[int] = []
  cur = m - 1
  while cur > 0:
    prev = back[cur]
    if prev > 0:
      chosen.append(pts[prev])
    cur = prev
  chosen.reverse()
  return chosen


# ---------------------------------------------------------------------------
# Exact syllable/pada cutting for VP and all मूलम् witnesses
# ---------------------------------------------------------------------------

def _restore_word_pausa(stem: str, pada: PadapathaItem) -> str:
  """Restore grammatical pausa ending (``ः`` / ``म्`` / ``न्`` / hiatal ``-ए/-ऐ``) matching ``pada``."""
  ref_bare = bare_devanagari(pada.ref if pada.ref != "?" else pada.ar).replace("-", "")
  st = stem.rstrip()
  if not st or st[-1] in "।॥,;—-)]\"'”*":
    return stem
  tail_marks = ""
  while st and (st[-1] in _ALL_ACCENTS or st[-1] in _US_MARKS):
    tail_marks = st[-1] + tail_marks
    st = st[:-1]
  if not st or st[-1] in "।॥,;—-)]\"'”*":
    return stem

  st_bare = bare_devanagari(st).replace("-", "")
  ref_tail = ref_bare[1:] if len(ref_bare) >= 2 and ref_bare[0] in _VOW_INDEP else ref_bare
  # Pragrhya / vowel-hiatus `-e/-ai` before vowel (`समिन्धत एताभिः` -> `समिन्धते`, `तस्मा एतत्` -> `तस्मै`)
  if ref_bare.endswith("ए") and not st.endswith(("ए", "े")) and st[-1] in _CONSONANTS:
    if (st_bare + "े").endswith(ref_bare) or (len(ref_tail) >= 2 and (st_bare + "े").endswith(ref_tail)):
      return st + "े" + tail_marks
  if ref_bare.endswith("ऐ") and st.endswith("ा"):
    if (st_bare[:-1] + "ै").endswith(ref_bare) or (len(ref_tail) >= 2 and (st_bare[:-1] + "ै").endswith(ref_tail)):
      return st[:-1] + "ै" + tail_marks
  if ref_bare.endswith("ः"):
    if st.endswith(("ः", "ो")):
      if st.endswith("ो") and ((st_bare[:-1] + "ः").endswith(ref_bare) or (len(ref_tail) >= 2 and (st_bare[:-1] + "ः").endswith(ref_tail))):
        return st[:-1] + "ः" + tail_marks
      return st + tail_marks
    if st.endswith(("र्", "स्", "श्", "ष्")):
      return st[:-2] + "ः" + tail_marks
    if st.endswith(("अ", "आ")) or (len(st) >= 1 and st[-1] not in _CONSONANTS and st[-1] != _HALANT):
      return st + "ः" + tail_marks
  if ref_bare.endswith("म्"):
    if st.endswith("म्"):
      return st + tail_marks
    if st.endswith(("ं", "ँ", "\ua8f3", "ᳫ")):
      return st[:-1] + "म्" + tail_marks
    if st.endswith(("न्", "ञ्", "ङ्", "ण्")):
      return st[:-2] + "म्" + tail_marks
  if ref_bare.endswith("त्") or ref_bare.endswith("द्"):
    for end in ("द्", "न्", "ल्", "च्", "ज्"):
      if st.endswith(end):
        return st[:-2] + "त्" + tail_marks
    if not st.endswith("त्"):
      return st + "त्" + tail_marks
  if ref_bare.endswith("क्") or ref_bare.endswith("ग्"):
    if st.endswith(("ग्", "ङ्")):
      return st[:-2] + "क्" + tail_marks
  if ref_bare.endswith("न्"):
    if st.endswith("न्त्"):
      return st[:-2] + tail_marks
    if st.endswith(("ं", "ञ्")):
      return (st[:-1] if st.endswith("ं") else st[:-2]) + "न्" + tail_marks
  return st + tail_marks


def _last_syl_of_text(s: str) -> str:
  """Return final phonetic syllable (+ trailing halant/visarga/anusvāra) of a single pada."""
  syls = scan_deva_syl_spans(s, mask_pratika_prefix=False)
  if not syls:
    return s
  return s[syls[-1].start:]


def _first_syl_of_text(s: str) -> str:
  """Return initial vowel/syllable of a single pada."""
  syls = scan_deva_syl_spans(s, mask_pratika_prefix=False)
  if not syls:
    return s
  return s[:syls[0].end]


def _slice_at_global_syl_seam(
  text: str,
  cur_char_pos: int,
  syls: Sequence[CharSyllable],
  l_idx: int,
  r_idx: int,
  shared_idx: int | None,
  left_pada: PadapathaItem,
  right_pada: PadapathaItem,
  *,
  use_ref_marks: bool,
  is_vp: bool,
) -> tuple[str, int, str] | None:
  """Cut ``text[cur_char_pos:]`` cleanly using pre-aligned global syllable seam ``(l_idx, r_idx, shared_idx)``.

  Returns ``(left_chunk, next_char_pos, right_prefix_override)`` or ``None`` if ambiguous.
  """
  lp_txt = (left_pada.ref if use_ref_marks and left_pada.ref != "?" else left_pada.ar).replace("-", "")
  rp_txt = (right_pada.ref if use_ref_marks and right_pada.ref != "?" else right_pada.ar).replace("-", "")
  lp_syls = scan_deva_syl_spans(lp_txt, mask_pratika_prefix=False)
  rp_syls = scan_deva_syl_spans(rp_txt, mask_pratika_prefix=False)
  if not lp_syls or not rp_syls:
    return None

  if shared_idx is not None:
    s_sh = syls[shared_idx]
    if s_sh.start < cur_char_pos:
      return None
    tail_l = _last_syl_of_text(lp_txt)
    head_r = _first_syl_of_text(rp_txt)
    if not is_vp:
      tail_l = accent.strip_accents(tail_l)
      head_r = accent.strip_accents(head_r)
      sb_mk = s_sh.mark
      if sb_mk:
        lm = lp_syls[-1].mark
        rm = rp_syls[0].mark
        if lm in (US_UDATTA, US_SVARITA) and rm not in (US_UDATTA, US_SVARITA):
          tail_l = _insert_mark_after_vowel(tail_l, sb_mk)
        elif rm == US_UDATTA and not lm:
          tail_l = _insert_mark_after_vowel(tail_l, sb_mk)
        else:
          head_r = _insert_mark_after_vowel(head_r, sb_mk)
    left_chunk = text[cur_char_pos : s_sh.start] + tail_l
    return left_chunk, s_sh.end, head_r

  # Distinct syllables `l_idx < r_idx` with fused boundary (`स्या᳓त्त᳓द्`, `यजते᳘ऽथ`, `शि᳘रस्सू᳘र्यः`)
  if l_idx < 0 or r_idx >= len(syls) or r_idx <= l_idx or syls[l_idx].start < cur_char_pos:
    return None
  s_left = syls[l_idx]
  s_right = syls[r_idx]
  mid = text[s_left.end : s_right.start]

  # Avagraha `ऽ`: `यजते᳘ऽथ` / `[[एत᳓न्नि᳓ह्नुतेऽथो|एत᳓न्नि᳓ह्नुते᳓ऽथो]]`
  if "ऽ" in mid and rp_txt.startswith("अ"):
    if is_vp:
      left_fixed = text[cur_char_pos : s_left.start] + _last_syl_of_text(lp_txt)
      m_a = re.match(r"^(अ[\u1cd3\u1cd9]*)", rp_txt)
      r_a = m_a.group(1) if m_a else "अ"
    else:
      left_fixed = text[cur_char_pos : s_left.end]
      r_a = "अ"
    return left_fixed, s_right.start, r_a

  # Consonant cluster / repha boundary inside `s_right.start .. scan_limit`
  scan_limit = s_right.vowel_start + (
    1 if s_right.vowel_start < len(text) and text[s_right.vowel_start] in _CONSONANTS else 0
  )
  r_ons_bare = bare_devanagari(_first_syl_onset(rp_txt))
  r_span = text[s_left.end : scan_limit]
  split_off = s_right.start
  if r_ons_bare and len(r_ons_bare) == 1:
    c_pos = r_span.rfind(r_ons_bare[0])
    if c_pos >= 0:
      split_off = s_left.end + c_pos
  elif r_ons_bare:
    first_c = r_ons_bare[0]
    c_pos = r_span.find(first_c)
    if c_pos >= 0:
      split_off = s_left.end + c_pos

  if split_off < s_left.end:
    split_off = s_left.end
  left_raw = text[cur_char_pos:split_off]
  left_fixed = _restore_word_pausa(left_raw, left_pada)
  return left_fixed, split_off, ""


def _first_syl_onset(s: str) -> str:
  m = re.match(r"^([\u0915-\u0939]+्)*[\u0915-\u0939]?", s)
  return m.group(0) if m else ""


def _insert_mark_after_vowel(syl: str, mk: str) -> str:
  for idx, ch in enumerate(syl):
    if ch in _MATRAS or ch in _VOW_INDEP:
      return syl[: idx + 1] + mk + syl[idx + 1 :]
  if syl and syl[0] in _CONSONANTS:
    pos = len(syl)
    for idx in range(len(syl) - 1, -1, -1):
      if syl[idx] in _CONSONANTS and (idx + 1 >= len(syl) or syl[idx + 1] != _HALANT):
        pos = idx + 1
        break
    return syl[:pos] + mk + syl[pos:]
  return syl + mk


def _cut_vp_at_padas(
  vp_body: str,
  pp_items: Sequence[PadapathaItem],
  split_padas: Sequence[int],
) -> list[str] | None:
  """Cut ``विश्वास-प्रस्तुतिः`` into ``len(split_padas) + 1`` clean US blocks preserving ``+++(...)+++`` and ``[[OLD|NEW]]``."""
  if not split_padas:
    return [vp_body]
  cuts = sorted(split_padas)
  vp_pieces = _extract_vp_pieces(vp_body)
  pp_keys, pp_meta, _, _ = _flatten_pp_syllables(items=pp_items)
  vp_keys = [kv for pc in vp_pieces for kv in pc["keys"]]
  vp_meta = [(pi, si) for pi, pc in enumerate(vp_pieces) for si in range(len(pc["keys"]))]
  pc_syl_sources = _map_pp_to_vp_syllables(
    vp_body, vp_pieces, pp_keys, pp_meta, vp_keys, vp_meta, _pp_member_starts(pp_items)
  )

  piece_pada_sets: list[list[set[int]]] = []
  for pi, pc in enumerate(vp_pieces):
    s_sets: list[set[int]] = []
    for srcs in pc_syl_sources[pi]:
      s_sets.append({pp_meta[ps[0]][0] for ps in srcs if ps})
    piece_pada_sets.append(s_sets)

  segments: list[str] = []
  cur_char_start = 0
  cur_prefix_override = ""

  def _split_one_token_globally(tok_str: str, tok_pp_start: int, tok_pp_end: int, cut_p: int, use_ref: bool) -> tuple[str, str] | None:
    sub_syls = scan_deva_syl_spans(tok_str, mask_pratika_prefix=False)
    sub_items = pp_items[tok_pp_start : tok_pp_end + 1]
    rel_cut = cut_p - tok_pp_start
    if not sub_syls or rel_cut <= 0 or rel_cut >= len(sub_items):
      return None
    _, owners = _align_layer_syls_to_pp(sub_syls, sub_items)
    sh = next((si for si, o in enumerate(owners) if (rel_cut - 1) in o and rel_cut in o), None)
    li = max((si for si, o in enumerate(owners) if o and min(o) < rel_cut), default=-1)
    ri = next((si for si, o in enumerate(owners) if o and max(o) >= rel_cut), len(sub_syls))
    res = _slice_at_global_syl_seam(
      tok_str, 0, sub_syls, li, ri, sh,
      pp_items[cut_p - 1], pp_items[cut_p],
      use_ref_marks=use_ref, is_vp=True,
    )
    if res is None:
      return None
    l_ch, nxt_pos, r_pre = res
    return l_ch, r_pre + tok_str[nxt_pos:]

  for cut_p in cuts:
    found_pi: int | None = None
    in_piece_split = False
    for pi in range(len(vp_pieces)):
      all_p = sorted({p for s in piece_pada_sets[pi] for p in s})
      if not all_p:
        continue
      if max(all_p) < cut_p:
        nxt_pi = pi + 1
        while nxt_pi < len(vp_pieces) and not any(piece_pada_sets[nxt_pi]):
          nxt_pi += 1
        if nxt_pi < len(vp_pieces):
          nxt_p = [p for s in piece_pada_sets[nxt_pi] for p in s]
          if nxt_p and min(nxt_p) >= cut_p:
            found_pi = pi
            in_piece_split = False
            break
      elif min(all_p) < cut_p <= max(all_p):
        found_pi = pi
        in_piece_split = True
        break

    if found_pi is None:
      return None

    pc = vp_pieces[found_pi]
    if not in_piece_split:
      nxt_pi = found_pi + 1
      while nxt_pi < len(vp_pieces) and not any(piece_pada_sets[nxt_pi]):
        nxt_pi += 1
      gap = vp_body[pc["end"] : vp_pieces[nxt_pi]["start"]]
      m_gap = re.match(r'^([ \t]*[,;।॥"\'”*]*[ \t]*(?:\+\+\+[^+]+\+\+\+[ \t]*)?)(.*)$', gap, re.S)
      left_gap = m_gap.group(1) if m_gap else ""
      right_gap = m_gap.group(2) if m_gap else gap
      raw_left = cur_prefix_override + vp_body[cur_char_start : pc["end"]] + left_gap
      if not re.search(r'(?:"|“|\+\+\+[^\n+]+\+\+\+)', right_gap):
        cur_char_start = vp_pieces[nxt_pi]["start"]
      else:
        cur_char_start = pc["end"] + len(left_gap)
      cur_prefix_override = ""
    else:
      all_p = sorted({p for s in piece_pada_sets[found_pi] for p in s})
      p_min, p_max = all_p[0], all_p[-1]
      if cur_char_start > pc["start"] and cur_prefix_override:
        tok_prefix = ""
        m_cur_sug = re.match(r"^\[\[([^|\]]+)\|([^\]]+)\]\]$", cur_prefix_override)
        is_sug_cur = bool(m_cur_sug)
        old_in = m_cur_sug.group(1) if m_cur_sug else cur_prefix_override
        new_in = m_cur_sug.group(2) if m_cur_sug else cur_prefix_override
      else:
        tok_prefix = vp_body[cur_char_start : pc["start"]]
        is_sug_cur = pc["is_sug"]
        old_in, new_in = pc["old"], pc["new"]

      if is_sug_cur:
        old_cut = _split_one_token_globally(old_in, p_min, p_max, cut_p, False)
        new_cut = _split_one_token_globally(new_in, p_min, p_max, cut_p, True)
        if not old_cut or not new_cut:
          return None
        ol, or_ = old_cut
        nl, nr = new_cut
        l_piece = ol if ol == nl else f"[[{ol}|{nl}]]"
        r_piece = or_ if or_ == nr else f"[[{or_}|{nr}]]"
      else:
        res_cut = _split_one_token_globally(old_in, p_min, p_max, cut_p, True)
        if not res_cut:
          return None
        l_piece, r_piece = res_cut

      raw_left = tok_prefix + l_piece
      cur_char_start = pc["end"]
      cur_prefix_override = r_piece

    segments.append(
      _clean_vp_chunk(
        raw_left,
        is_final=False,
        prev_cut_pada=pp_items[cut_p - 1],
        is_first=(len(segments) == 0),
      )
    )

  raw_last = cur_prefix_override + vp_body[cur_char_start:]
  segments.append(_clean_vp_chunk(raw_last, is_final=True, is_first=(len(segments) == 0)))
  return [_fix_vp_leading_avagraha(s, idx == 0) for idx, s in enumerate(segments)]


def _fix_vp_leading_avagraha(txt: str, is_first: bool) -> str:
  if is_first:
    return txt
  s = txt.lstrip()
  if s.startswith("ऽ"):
    nxt = s[1:2]
    if nxt in _VOW_INDEP:
      return s[1:]
    return "अ" + s[1:]
  if s.startswith("[[ऽ"):
    # `[[ऽधः|ऽधः]]` -> `[[अधः|अधः]]`
    s = re.sub(r"^\[\[ऽ([^|\]]+)\|ऽ([^\]]+)\]\]", r"[[\1|\2]]", s)
    return re.sub(r"^\[\[", "[[अ", s.replace("[[", "[[", 1))
  return s


def _clean_vp_chunk(txt: str, *, is_final: bool, prev_cut_pada: PadapathaItem | None = None, is_first: bool = True) -> str:
  s = txt.strip()
  if not is_first:
    s = re.sub(r"^[,\s;—\-।॥]+", "", s)
  s = re.sub(r"[,\s;—\-]+$", "", s)
  if prev_cut_pada is not None:
    parts = s.rsplit(" ", 1)
    tail_tok = parts[-1]
    m_sug = re.match(r"^\[\[([^|\]]+)\|([^\]]+)\]\]$", tail_tok)
    if m_sug:
      ol = _restore_word_pausa(m_sug.group(1), PadapathaItem(ar=prev_cut_pada.ar, ref=prev_cut_pada.ar, prov="", vyat=False, solid=True))
      nl = _restore_word_pausa(m_sug.group(2), prev_cut_pada)
      fixed = ol if ol == nl else f"[[{ol}|{nl}]]"
      s = (parts[0] + " " + fixed) if len(parts) == 2 else fixed
    elif not tail_tok.endswith("+++"):
      fixed = _restore_word_pausa(tail_tok, prev_cut_pada)
      s = (parts[0] + " " + fixed) if len(parts) == 2 else fixed
  if not is_final:
    if re.search(r"[।॥](?:\s*\+\+\+[^+]+\+\+\+)*\s*$", s):
      # Keep single । / trailing +++(...)+++ intact without adding duplicate ` ।`
      pass
    else:
      s = re.sub(r"[।॥]+\s*$", "", s).strip() + " ।"
  else:
    if not re.search(r"[।॥](?:\s*\+\+\+[^+]+\+\+\+)*\s*$", s):
      s += " ॥"
  return s


def _cut_mula_at_padas(
  summary: str,
  raw_body: str,
  pp_items: Sequence[PadapathaItem],
  split_padas: Sequence[int],
) -> list[str] | None:
  """Cut one ``मूलम्*`` witness cleanly at ``split_padas`` preserving footnotes, titles & trailing numbers."""
  if not split_padas:
    return [raw_body]
  cuts = sorted(split_padas)
  clean_no_fn, fn_defs, fn_order = extract_footnotes(raw_body)
  trail_m = _TRAIL_KANDIKA_NUM_RE.search(clean_no_fn)
  trail_num = trail_m.group(1) if trail_m else ""
  body_core = clean_no_fn[: trail_m.start()].rstrip() if trail_m else clean_no_fn

  syls = scan_deva_syl_spans(body_core, mask_pratika_prefix=("श्रीधरादि" in summary or "Weber" in summary))
  if not syls:
    return None
  primary, owners = _align_layer_syls_to_pp(syls, pp_items)

  chunks: list[str] = []
  cur_char_pos = 0
  cur_prefix_override = ""

  for cut_p in cuts:
    l_idx = -1
    r_idx = len(syls)
    for si, p_own in enumerate(owners):
      if p_own and min(p_own) < cut_p:
        l_idx = si
      if p_own and max(p_own) >= cut_p and r_idx == len(syls):
        r_idx = si
    shared_idx = next((si for si, o in enumerate(owners) if (cut_p - 1) in o and cut_p in o), None)

    if shared_idx is None:
      if l_idx < 0 or r_idx >= len(syls):
        return None
      while r_idx <= l_idx and r_idx < len(syls):
        r_idx += 1
      if r_idx >= len(syls):
        return None
      gap = body_core[syls[l_idx].end : syls[r_idx].start]
      if re.search(r"[ \t\n।॥]", gap) or re.search(r"\[\^[^\]]+\]", gap):
        # Consume trailing punctuation/footnotes belonging to left word (`[ \t]*(?:।|॥|\[\^...\]|\[\[!!\]\])*`)
        m_end_tok = re.match(r'^([^\s()]*?(?:\[\^[^\]]+\]|\[\[!!\]\])?(?:[ \t]*[।॥]+)?(?:[ \t]*\[\^[^\]]+\])?)', gap)
        tok_tail = m_end_tok.group(1) if m_end_tok else ""
        cut_off = syls[l_idx].end + len(tok_tail)
        nxt_off = cut_off
        while nxt_off < syls[r_idx].start and body_core[nxt_off] in " \t\n।॥,;—":
          nxt_off += 1
        left_raw = body_core[cur_char_pos : syls[l_idx].end]
        left_fixed = _restore_word_pausa(left_raw, pp_items[cut_p - 1]) if "विस्वरम्" not in summary else left_raw
        left_chunk = cur_prefix_override + left_fixed + tok_tail
        cur_char_pos = nxt_off
        cur_prefix_override = ""
      else:
        res = _slice_at_global_syl_seam(
          body_core, cur_char_pos, syls, l_idx, r_idx, None,
          pp_items[cut_p - 1], pp_items[cut_p],
          use_ref_marks=False, is_vp=False,
        )
        if not res:
          return None
        l_ch, nxt_pos, r_pre = res
        left_chunk = cur_prefix_override + l_ch
        cur_char_pos = nxt_pos
        cur_prefix_override = r_pre
    else:
      res = _slice_at_global_syl_seam(
        body_core, cur_char_pos, syls, l_idx, r_idx, shared_idx,
        pp_items[cut_p - 1], pp_items[cut_p],
        use_ref_marks=False, is_vp=False,
      )
      if not res:
        return None
      l_ch, nxt_pos, r_pre = res
      left_chunk = cur_prefix_override + l_ch
      cur_char_pos = nxt_pos
      cur_prefix_override = r_pre

    left_chunk = left_chunk.strip()
    if chunks:
      left_chunk = re.sub(r"^[,\s;—\-]+", "", left_chunk)
    if "विस्वरम्" in summary or "Makoto" in summary:
      left_chunk = re.sub(r"[।॥]+\s*$", "", left_chunk).strip() + " ।"
    chunks.append(left_chunk)

  last_chunk = (cur_prefix_override + body_core[cur_char_pos:]).strip()
  if chunks:
    last_chunk = re.sub(r"^[,\s;—\-]+", "", last_chunk)
  if trail_num:
    last_chunk = re.sub(r"[।॥]+\s*$", "", last_chunk).strip() + " " + trail_num
  chunks.append(last_chunk)
  return reattach_footnotes(chunks, fn_defs, fn_order)


# ---------------------------------------------------------------------------
# Commentary & Translation layer partitioning across K sub-clusters
# ---------------------------------------------------------------------------

def _split_bhashya_units(body: str) -> tuple[str, list[str], str]:
  """Split Sāyaṇa / Harisvāmi / Vāsudeva bhāṣya into ``(lead_mangala, pratika_units, colophon)``."""
  clean, _, _ = extract_footnotes(body)
  lines = clean.splitlines()

  # 1. Separate trailing colophon (`इति ... ब्राह्मणम् ।`) if on final lines
  colophon_lines: list[str] = []
  while lines and re.match(r"^\s*इति\s+(?:सायणाचार्य|श्रीहरिस्वामि|हरिस्वामि|श्रीमद्वासुदेव|शङ्कर).*ब्राह्मणम्", lines[-1]):
    colophon_lines.insert(0, lines.pop())
  while lines and not lines[-1].strip():
    lines.pop()
  colophon = "\n".join(colophon_lines).strip()

  # 2. Group paragraphs & split mid-paragraph ONLY at `avatārikā - **pratīka**` / bold-pratīka sentence starts
  core_txt = "\n".join(lines).strip()
  if not core_txt:
    return "", [], colophon

  # Split mid-paragraph right after sentence-ending `।` / `॥` when next sentence introduces a new bold pratīka
  raw_units: list[str] = []
  cur: list[str] = []
  for para in re.split(r"\n\s*\n+", core_txt):
    p = para.strip()
    if not p:
      continue
    # Break `p` at `... । [optional avatārikā without **] **pratīka**` (up to 240 chars avatārikā)
    sents = re.split(r"(?<=[।॥])\s+(?=[^।\n]{0,240}\*\*[^*\n]{2,60}\*\*)", p)
    for si, s in enumerate(sents):
      s = s.strip()
      if not s:
        continue
      has_bold_lead = bool(re.match(r"^(?:[^।\n]{0,240})\*\*[^*\n]{2,60}\*\*", s))
      if si > 0 and has_bold_lead and cur:
        raw_units.append("\n\n".join(cur))
        cur = [s]
      elif si == 0 and has_bold_lead and cur:
        raw_units.append("\n\n".join(cur))
        cur = [s]
      else:
        cur.append(s)
  if cur:
    raw_units.append("\n\n".join(cur))

  if not raw_units:
    return "", [], colophon

  # Pull out pure mangala / adhyāya intro paragraphs (`यस्य निःश्वसितं`, no bold pratīka in unit 0) as lead_mangala
  lead_parts: list[str] = []
  while raw_units and "**" not in raw_units[0] and len(raw_units) > 1:
    lead_parts.append(raw_units.pop(0))
  return "\n\n".join(lead_parts).strip(), raw_units, colophon


def split_commentary_across_clusters(
  summary: str,
  body: str,
  sub_vps: Sequence[str],
) -> list[str]:
  """Align and partition one Sanskrit commentary block cleanly across ``sub_vps`` with 100% coverage."""
  k_n = len(sub_vps)
  if k_n <= 1:
    return [body]

  clean_all, fn_defs, fn_order = extract_footnotes(body)
  # Single short editorial/availability note (e.g. "सायणभाष्यं नोपलब्धम्...") -> keep once on sub-cluster 0
  if len(clean_all) <= 180 and "**" not in clean_all and "\n\n" not in clean_all:
    return [body] + [""] * (k_n - 1)

  # Translator/editorial notes (`सिद्धार्थः`) referencing "last line" -> attach on final sub-cluster
  if "सिद्धार्थ" in summary:
    if "last line" in clean_all.lower() or "अन्तिम" in clean_all:
      return [""] * (k_n - 1) + [body]
    return [body] + [""] * (k_n - 1)

  lead, units, colophon = _split_bhashya_units(body)
  if not units:
    combined = "\n\n".join(x for x in (lead, colophon) if x)
    res = [combined] + [""] * (k_n - 1) if combined else [body] + [""] * (k_n - 1)
    return reattach_footnotes(res, fn_defs, fn_order)

  # Clean normalized cores + IDF from sub_vps for `score_segment_against_cores`
  core_norms = [normalize_for_alignment(v) for v in sub_vps]
  # Compute simple stem IDF
  df: dict[str, int] = {}
  for cn in core_norms:
    for st in set(cn["words"]):
      df[st] = df.get(st, 0) + 1
  import math
  stem_idf = {st: math.log((k_n + 1.0) / (cnt + 0.5)) + 0.5 for st, cnt in df.items()}

  u_n = len(units)
  # Score matrix `score[u][c]`
  score_mat: list[list[float]] = []
  for u in units:
    cues = extract_segment_cues(u)
    un = normalize_for_alignment(u)
    sc, _ = score_segment_against_cores(cues, un, core_norms, stem_idf)
    score_mat.append(sc)

  # Monotonic Viterbi DP assigning each commentary unit `u` to core index `c_of_u[u] ∈ [0..k_n-1]`
  dp = [[-1e9] * k_n for _ in range(u_n)]
  back = [[0] * k_n for _ in range(u_n)]
  for c in range(k_n):
    dp[0][c] = score_mat[0][c] - 0.1 * c
  for u in range(1, u_n):
    for c in range(k_n):
      best_prev = -1e9
      best_pc = 0
      for pc in range(c + 1):
        val = dp[u - 1][pc] + (0.4 if pc == c else 0.0)
        if val > best_prev:
          best_prev = val
          best_pc = pc
      dp[u][c] = best_prev + score_mat[u][c]
      back[u][c] = best_pc

  c_end = max(range(k_n), key=lambda c: dp[u_n - 1][c])
  assigned = [0] * u_n
  cur = c_end
  for u in range(u_n - 1, -1, -1):
    assigned[u] = cur
    cur = back[u][cur]

  buckets: list[list[str]] = [[] for _ in range(k_n)]
  if lead:
    buckets[0].append(lead)
  for u, c in zip(units, assigned):
    buckets[c].append(u)
  if colophon:
    buckets[-1].append(colophon)

  raw_res = ["\n\n".join(b).strip() for b in buckets]
  return reattach_footnotes(raw_res, fn_defs, fn_order)


def _translation_stem_idf(skt_stems: Sequence[set[str]]) -> dict[str, float]:
  import math
  k_n = max(1, len(skt_stems))
  df: dict[str, int] = {}
  for st_set in skt_stems:
    for st in st_set:
      df[st] = df.get(st, 0) + 1
  return {st: math.log((k_n + 1.0) / (cnt + 0.5)) + 0.5 for st, cnt in df.items()}


def split_translation_across_clusters(
  summary: str,
  body: str,
  sub_pp_items: Sequence[Sequence[PadapathaItem]],
) -> list[str]:
  """Align Eggeling / C. R. Swaminathan clauses monotonically across ``sub_pp_items``."""
  k_n = len(sub_pp_items)
  if k_n <= 1:
    return [body]

  clean_tr, fn_defs, fn_order = extract_footnotes(body)
  en_clauses = split_english_clauses(clean_tr)
  if len(en_clauses) <= 1:
    return reattach_footnotes([clean_tr] + [""] * (k_n - 1), fn_defs, fn_order)

  m_e = len(en_clauses)
  skt_stems = [_core_anchor_stems(p) for p in sub_pp_items]
  stem_idf = _translation_stem_idf(skt_stems)

  def _idf_score(st_set: set[str], en_cl: str) -> float:
    low_words = set(re.findall(r"[a-z]+", en_cl.lower()))
    en_stems = {_stem_word(w) for w in low_words if len(w) >= 4}
    sc = 0.0
    for ss in st_set:
      w = stem_idf.get(ss, 1.0)
      ascii_ss = ss.translate(_IAST_ASCII_TRANS)
      for es in en_stems:
        if len(ascii_ss) >= 4 and len(es) >= 4 and (ascii_ss.startswith(es[:4]) or es.startswith(ascii_ss[:4])):
          sc += 2.2 * w
          break
    for en_kw, skt_opts in _SB_EN_SKT_ANCHORS.items():
      if en_kw in low_words:
        for opt in skt_opts:
          matched = [ss for ss in st_set if ss.startswith(opt)]
          if matched:
            sc += 2.2 * max(stem_idf.get(ss, 1.0) for ss in matched)
            break
    return sc

  cum_s = [0]
  for p in sub_pp_items:
    cum_s.append(cum_s[-1] + len(p))
  skt_tot = cum_s[-1] or 1

  en_wcs = [max(1, len(c.split())) for c in en_clauses]
  cum_e = [0]
  for w in en_wcs:
    cum_e.append(cum_e[-1] + w)
  en_tot = cum_e[-1] or 1

  # Monotonic assignment `assigned[ei] ∈ [0..k_n-1]` strongly respecting `.`-sentences + rare lexical anchors!
  dp = [[-1e9] * k_n for _ in range(m_e)]
  back = [[0] * k_n for _ in range(m_e)]
  for c in range(k_n):
    s_prop = (cum_s[c] + cum_s[c + 1]) / (2.0 * skt_tot)
    e_prop = (cum_e[0] + cum_e[1]) / (2.0 * en_tot)
    dp[0][c] = _idf_score(skt_stems[c], en_clauses[0]) - abs(s_prop - e_prop) * 3.5 - 1.5 * c

  for ei in range(1, m_e):
    e_prop = (cum_e[ei] + cum_e[ei + 1]) / (2.0 * en_tot)
    prev_is_period = bool(re.search(r"[.?!]['\"\)]*\s*(?:\[\^[^\]]+\])?\s*$", en_clauses[ei - 1]))
    for c in range(k_n):
      s_prop = (cum_s[c] + cum_s[c + 1]) / (2.0 * skt_tot)
      anch = _idf_score(skt_stems[c], en_clauses[ei])
      pos_pen = abs(s_prop - e_prop) * 3.5
      best_p = -1e9
      best_pc = 0
      for pc in range(c + 1):
        # Reward keeping `;` clauses inside same core unless strong anchors disagree; reward `.` transition!
        if pc == c:
          trans = 0.3 if not prev_is_period else 0.0
        elif pc + 1 == c:
          trans = 1.6 if prev_is_period else -0.8
        else:
          trans = 0.4 if prev_is_period else -2.0
        val = dp[ei - 1][pc] + trans
        if val > best_p:
          best_p = val
          best_pc = pc
      dp[ei][c] = best_p + anch - pos_pen
      back[ei][c] = best_pc

  c_end = max(range(k_n), key=lambda c: dp[m_e - 1][c])
  assigned = [0] * m_e
  cur = c_end
  for ei in range(m_e - 1, -1, -1):
    assigned[ei] = cur
    cur = back[ei][cur]

  buckets: list[list[str]] = [[] for _ in range(k_n)]
  for cl, c in zip(en_clauses, assigned):
    buckets[c].append(cl)
  raw_res = [" ".join(b).strip() for b in buckets]
  return reattach_footnotes(raw_res, fn_defs, fn_order)


# ---------------------------------------------------------------------------
# Cluster splitter + strict in-memory ŚB audit verification
# ---------------------------------------------------------------------------

def _verify_split_subclusters(
  sub_vps: Sequence[str],
  sub_items: Sequence[Sequence[PadapathaItem]],
  sub_mulams: dict[str, Sequence[str]],
  sub_bullet_chunks: Sequence[Sequence[str]] = (),
  next_kandika_first_mark: str | None = None,
  is_yantra: bool = False,
) -> int | None:
  """Verify EVERY sub-cluster passes ŚB audit and reconciler fixed point; returns ``None`` or first failing index."""
  weber_list = sub_mulams.get("मूलम् - Weber", [""] * len(sub_vps))
  shri_list = sub_mulams.get("मूलम् - श्रीधरादि") or sub_mulams.get("मूलम्") or [""] * len(sub_vps)
  primary_mula_hdr = "मूलम् - श्रीधरादि" if "मूलम् - श्रीधरादि" in sub_mulams else ("मूलम्" if "मूलम्" in sub_mulams else "मूलम् - Weber")
  primary_mula_list = sub_mulams.get(primary_mula_hdr, [""] * len(sub_vps))

  first_marks: list[str | None] = []
  for vp in sub_vps:
    c = re.sub(r"\+\+\+.*?\+\+\+|\[\[(?:\?+|!+)\]\]", " ", vp, flags=re.S)
    c = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", c)
    _, mks = syllables_with_marks(c)
    first_marks.append(mks[0] if mks else None)

  for idx, vp in enumerate(sub_vps):
    items = list(sub_items[idx])
    if not items:
      return idx
    vp_clean = re.sub(r"\+\+\+.*?\+\+\+|\[\[(?:\?+|!+)\]\]", " ", vp, flags=re.S)
    vp_clean = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\1", vp_clean)
    vp_clean = accent.strip_accents(vp_clean)
    vp_clean = re.sub(r"ऽ(?=[अआइईउऊऋॠऌॡएऐओऔ])", "", vp_clean)
    vp_clean = re.sub(r'["\'“”‘’\*\+]+', "", vp_clean).strip()

    ok_vp, _, _, _ = verify_mantra_sandhi([it.ref for it in items], vp_clean)
    if not ok_vp:
      return idx

    nxt_m = first_marks[idx + 1] if idx + 1 < len(first_marks) else next_kandika_first_mark
    rep = audit_padapatha_against_sb(
      vp_clean, items, weber_list[idx], shri_list[idx], next_first_mark=nxt_m
    )
    if rep.unmapped_vp_syllables or rep.unflagged_vyatyasta_padas or rep.possibly_spurious_vyatyasta_padas:
      return idx

    if sub_bullet_chunks:
      n_vyat = sum(1 for it in items if it.vyat)
      p_tot = len(items)
      vp_sum = "विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)" if is_yantra else format_suggested_vp_summary("विश्वास-प्रस्तुतिः", n_vyat, p_tot)
      pp_sum = format_padapatha_summary(n_vyat, p_tot)
      snippet = (
        f"<details open><summary>{vp_sum}</summary>\n\n{vp.strip()}\n</details>\n\n"
        f"<details><summary>{primary_mula_hdr}</summary>\n\n{primary_mula_list[idx].strip()}\n</details>\n\n"
        f"<details><summary>{pp_sum}</summary>\n\n" + "\n".join(sub_bullet_chunks[idx]) + "\n</details>"
      )
      rec_out, rec_logs = reconcile_markdown_blocks(snippet)
      if rec_logs or rec_out != snippet:
        return idx
  return None


def split_single_cluster(
  cluster: ClusterRecord,
  *,
  parallel_hint: tuple[str, str] | None = None,
  next_kandika_first_mark: str | None = None,
) -> tuple[list[str], bool, bool]:
  """Split one ``ClusterRecord`` into canonical ``<details>`` markdown blocks."""
  items = cluster.pp_items
  if not items or not cluster.vp_body:
    return [], False, False

  split_pts = select_cluster_split_points(cluster, parallel_hint=parallel_hint)
  if not split_pts:
    return [], False, False

  candidate_pts = list(split_pts)
  while candidate_pts:
    bounds = [0] + candidate_pts + [len(items)]
    sub_vps = _cut_vp_at_padas(cluster.vp_body, items, candidate_pts)
    sub_items = [items[bounds[i] : bounds[i + 1]] for i in range(len(bounds) - 1)]
    sub_bullet_chunks = [cluster.pp_bullet_lines[bounds[i] : bounds[i + 1]] for i in range(len(bounds) - 1)]

    sub_mulams: dict[str, list[str]] = {}
    mulam_ok = sub_vps is not None and all(sub_vps)
    if mulam_ok:
      for m_sum, m_body, _ in cluster.mulam_blocks:
        res_m = _cut_mula_at_padas(m_sum, m_body, items, candidate_pts)
        if res_m is None or any(not x.strip() for x in res_m):
          mulam_ok = False
          break
        sub_mulams[m_sum] = res_m
      for t_sum, t_body, _ in cluster.trailing_blocks:
        if t_sum.startswith("मूलम्"):
          res_t = _cut_mula_at_padas(t_sum, t_body, items, candidate_pts)
          if res_t is None or any(not x.strip() for x in res_t):
            mulam_ok = False
            break
          sub_mulams[t_sum] = res_t

    is_yantra = "यन्त्र-स्वरः" in cluster.vp_summary
    fail_idx = (
      _verify_split_subclusters(
        sub_vps,
        sub_items,
        sub_mulams,
        sub_bullet_chunks,
        next_kandika_first_mark,
        is_yantra=is_yantra,
      )
      if mulam_ok
      else 0
    )
    if mulam_ok and fail_idx is None:
      k_n = len(sub_vps)
      sub_tr: dict[str, list[str]] = {}
      sub_comm: dict[str, list[str]] = {}
      for t_sum, t_body, _ in cluster.trailing_blocks:
        if t_sum.startswith("मूलम्"):
          continue
        if t_sum in _TRANSLATION_SUMMARIES:
          sub_tr[t_sum] = split_translation_across_clusters(t_sum, t_body, sub_items)
        else:
          sub_comm[t_sum] = split_commentary_across_clusters(t_sum, t_body, sub_vps)

      rendered: list[str] = []
      for i in range(k_n):
        blocks_i: list[str] = []
        if i == 0:
          for esum, ebody, eopen in cluster.pre_vp_extras:
            blocks_i.append(_render_details(esum, ebody, is_open=eopen))
        s_items = sub_items[i]
        n_vyat = sum(1 for it in s_items if it.vyat)
        p_tot = len(s_items)
        if is_yantra:
          vp_sum_i = "विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)"
        else:
          vp_sum_i = format_suggested_vp_summary("विश्वास-प्रस्तुतिः", n_vyat, p_tot)
        pp_sum_i = format_padapatha_summary(n_vyat, p_tot)
        blocks_i.append(_render_details(vp_sum_i, sub_vps[i], is_open=cluster.vp_open))
        if i == 0:
          for tsum, tbody, topen in cluster.tippani_blocks:
            blocks_i.append(_render_details(tsum, tbody, is_open=topen))
        for m_sum, _, m_open in cluster.mulam_blocks:
          blocks_i.append(_render_details(m_sum, sub_mulams[m_sum][i], is_open=m_open))
        blocks_i.append(_render_details(pp_sum_i, "\n".join(sub_bullet_chunks[i]), is_open=False))
        for t_sum, _, t_open in cluster.trailing_blocks:
          if t_sum.startswith("मूलम्"):
            part_txt = sub_mulams[t_sum][i]
          elif t_sum in _TRANSLATION_SUMMARIES:
            part_txt = sub_tr[t_sum][i]
          else:
            part_txt = sub_comm[t_sum][i]
          if part_txt.strip():
            blocks_i.append(_render_details(t_sum, part_txt, is_open=t_open))
        rendered.append("\n\n".join(b for b in blocks_i if b))
      return rendered, True, False

    if len(candidate_pts) == 1:
      return [], False, True
    # Drop the cut boundary directly responsible for `fail_idx`!
    drop_pos = min(fail_idx, len(candidate_pts) - 1) if fail_idx is not None else len(candidate_pts) - 1
    candidate_pts.pop(drop_pos)

  return [], False, True


# ---------------------------------------------------------------------------
# Parallel SBM/14 hint index for SBK/17_bRhadAraNyakam
# ---------------------------------------------------------------------------

def build_sbm_parallel_hints(sbm_sarva_root: str | os.PathLike[str]) -> list[tuple[str, str, str]]:
  """Load ``(normalized_skel, visvaram_body, eggeling_body)`` entries from SBM Kāṇḍas 10 & 14 for SBK 17 hints."""
  root = Path(sbm_sarva_root)
  entries: list[tuple[str, str, str]] = []
  targets = list(sorted((root / "14").rglob("*.md"))) + ([root / "10" / "06" / "4.md"] if (root / "10" / "06" / "4.md").exists() else [])
  for p in targets:
    if p.name in ("_index.md", "file_list.md"):
      continue
    txt = p.read_text(encoding="utf-8")
    for part in _H2_SPLIT_RE.split(txt):
      if not part.startswith("## "):
        continue
      blocks = {m.group(2).strip(): m.group(3).strip() for m in _DETAILS_BLOCK_RE.finditer(part)}
      vis = blocks.get("मूलम् - विस्वरम्", "")
      egg = blocks.get("Eggeling", "")
      if vis:
        sk = normalize_for_alignment(re.sub(r"^\*\*[^\n]+\*\*", "", vis))["compact"]
        entries.append((sk, vis, egg))
  return entries


def find_parallel_hint(
  cluster: ClusterRecord,
  sbm_hints: Sequence[tuple[str, str, str]],
) -> tuple[str, str] | None:
  """Return matching ``(visvaram_text, eggeling_text)`` from SBM when skeleton aligns >= 0.65."""
  if not sbm_hints or not cluster.vp_body:
    return None
  q_sk = normalize_for_alignment(cluster.vp_body)["compact"]
  if len(q_sk) < 20:
    return None
  probe = q_sk[:18]
  cands = [e for e in sbm_hints if probe[:10] in e[0] or e[0][:10] in q_sk]
  if not cands:
    return None
  best: tuple[float, tuple[str, str]] | None = None
  for sk, vis, egg in cands[:8]:
    r = difflib.SequenceMatcher(None, q_sk[:120], sk[:120], autojunk=False).ratio()
    if r >= 0.65 and (best is None or r > best[0]):
      best = (r, (vis, egg))
  return best[1] if best else None


# ---------------------------------------------------------------------------
# Whole-file processor
# ---------------------------------------------------------------------------

def split_sb_markdown_text(
  text: str,
  *,
  sbm_hints: Sequence[tuple[str, str, str]] = (),
) -> SplitResult:
  """Split all multi-unit kaṇḍikā clusters inside one SBM or SBK Markdown document."""
  sections = _H2_SPLIT_RE.split(text)
  if len(sections) <= 1:
    return SplitResult(text, False, 0, 0, 0, [])

  # Precompute each section's parsed clusters and next section's leading US mark for exact audit
  sec_clusters = [parse_section_clusters(sec) if sec.startswith("## ") else [] for sec in sections]
  first_mark_by_sec: list[str | None] = []
  for clist in sec_clusters:
    if clist and clist[0].vp_body:
      c = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", clist[0].vp_body)
      _, mks = syllables_with_marks(c)
      first_mark_by_sec.append(mks[0] if mks else None)
    else:
      first_mark_by_sec.append(None)

  out_secs: list[str] = []
  orig_c = 0
  new_c = 0
  k_split = 0
  fallbacks: list[str] = []
  changed = False

  for si, sec in enumerate(sections):
    if not sec.startswith("## "):
      out_secs.append(sec)
      continue
    clist = sec_clusters[si]
    if not clist:
      out_secs.append(sec)
      continue
    hdr = sec.splitlines()[0].strip()
    orig_c += len(clist)

    # Next US mark across whole section boundary
    sec_next_mark: str | None = None
    for nj in range(si + 1, len(sec_clusters)):
      if first_mark_by_sec[nj] is not None:
        sec_next_mark = first_mark_by_sec[nj]
        break

    rebuilt_parts: list[str] = []
    pos = 0
    sec_had_split = False
    for ci, cl in enumerate(clist):
      # Text before this cluster (includes `## heading` for `ci == 0`)
      rebuilt_parts.append(sec[pos : cl.raw_start])
      cl_nxt_mark = (
        syllables_with_marks(clist[ci + 1].vp_body)[1][0]
        if ci + 1 < len(clist) and clist[ci + 1].vp_body and syllables_with_marks(clist[ci + 1].vp_body)[1]
        else sec_next_mark
      )
      # Look up parallel SBM hint only when section has no `विस्वरम्` and no translation
      has_tr = any(s in ("Eggeling", "C R Swaminathan") for s, _, _ in cl.trailing_blocks)
      has_visv = any(s == "मूलम् - विस्वरम्" for s, _, _ in cl.mulam_blocks)
      hint = find_parallel_hint(cl, sbm_hints) if (sbm_hints and not has_visv and not has_tr) else None

      split_blocks, did_split, did_fb = split_single_cluster(
        cl, parallel_hint=hint, next_kandika_first_mark=cl_nxt_mark
      )
      if did_fb:
        fallbacks.append(hdr)
      if did_split:
        changed = True
        sec_had_split = True
        new_c += len(split_blocks)
        rebuilt_parts.append("\n\n".join(split_blocks))
      else:
        new_c += 1
        rebuilt_parts.append(sec[cl.raw_start : cl.raw_end])
      pos = cl.raw_end

    rebuilt_parts.append(sec[pos:])
    if sec_had_split:
      k_split += 1
    out_secs.append("".join(rebuilt_parts))

  new_text = "".join(out_secs)
  return SplitResult(
    new_text=new_text,
    changed=(changed and new_text != text),
    orig_clusters=orig_c,
    new_clusters=new_c,
    kandikas_split=k_split,
    audit_fallbacks=fallbacks,
  )


def process_sb_file(
  md_path: str | os.PathLike[str],
  *,
  dry_run: bool = False,
  sbm_hints: Sequence[tuple[str, str, str]] = (),
) -> SplitResult:
  """Read, split, and optionally write one ŚB content Markdown file."""
  p = Path(md_path)
  orig = p.read_text(encoding="utf-8")
  res = split_sb_markdown_text(orig, sbm_hints=sbm_hints)
  if res.changed and not dry_run:
    p.write_text(res.new_text, encoding="utf-8")
  return res
