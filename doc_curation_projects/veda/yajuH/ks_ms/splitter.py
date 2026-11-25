"""Mantra (yajuṣ & ṛk) and Brāhmaṇa prose splitting for Maitrāyaṇī (MS) and Kāṭhaka (KS) Saṁhitās.

Core principles:
1. **Viniyoga authority first**: Distinct Mānava/Vārāha Śrauta Sūtra or KS Brāhmaṇa
   viniyogas pin hard mantra boundaries — splitting even a single ṛk when its halves
   carry distinct ritual viniyogas (e.g. MS 1.1.2 / KS 1.2 ``शतवल्शं विरोह`` vs
   ``सहस्रवल्शा वि वयं रुहेम``).
2. **TS + VS-M + VS-K + RV (+ MS for KS) alignment**: Splits fused yajuṣ sequences (even
   across sandhi-fused Schroeder seams like ``त्वोर्जे᳓``, ``स्थोपाय᳓वस्स्थ``,
   ``रा᳓स्नासीन्द्राण्या᳓ः``) and merges multi-line halves of a single metrical ṛk when NOT
   separated by distinct viniyogas.
3. **Brāhmaṇa sense-unit splitting (Tests 1–5)**: Keeps correlatives (``यत्…तत्/तेन``),
   embedded ``इति`` quotes, and ``-त्वा/-य`` clauses intact while splitting independent
   declarative sentences cleanly.
"""

from __future__ import annotations

import dataclasses
import difflib
import re
from typing import Sequence

import chandas
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.accent.reconciler import US_SVARITA, US_UDATTA, has_us_accents
from doc_curation.sanskrit.accent.samhita_splitter import (
  BAD_SEAM_START_CHARS,
  CONS_DEVA,
  MATRAS,
  VOW_INDEP,
)
from doc_curation.sanskrit.accent.shatapatha_solver import UnifiedVedicLexicon
from doc_curation_projects.veda.yajuH.ks_ms.reference_index import (
  MantraRefUnit,
  VedicReferenceIndex,
  ViniyogaEntry,
  clean_vedic_text,
  norm_words,
  normalize_for_matching,
  skeleton_key,
)
from doc_curation_projects.veda.yajuH.ks_ms.source_parser import (
  KsAnuvakaSource,
  MsAnuvakaSource,
  strip_ms_quote_backslashes,
)

_ALL_ACC_RE = re.compile(r"[\u0951-\u0957\u1cd0-\u1cff]")
_DEVA_LETTER_RE = re.compile(r"[\u0905-\u0939\u0958-\u095f]")

# Brāhmaṇa prose discourse cues vs Mantra ritual cues
_BRAHMANA_MARKERS = frozenset({
  "वै", "तस्मात्", "एतत्", "खलु", "अथ", "अथो", "अभवत्", "अभवन्", "भवति", "भवन्ति",
  "असृजत", "अजायत", "आसीत्", "आसन्", "ब्रह्मवादिनः", "वदन्ति", "वेद", "आह", "आहुः",
  "उवाच", "अब्रवीत्", "अब्रुवन्", "जुहोति", "हूयते", "उच्यते", "प्रजापतिः", "असुराः",
  "भ्रातृव्य", "भ्रातृव्यवान्", "यजमानः", "अध्वर्युः", "ततः", "तेन", "एवम्", "निवर्पेत्",
  "निर्वपेत्", "प्रजाकामः", "पशुकामः", "स्वर्गकामः", "ब्रह्मवर्चसकामः", "अभिचरन्",
  "याज्यानुवाक्ये", "पुरोनुवाक्या", "दक्षिणा", "तदाहुः", "इत्याह", "अवरुन्धे", "अवरुन्द्धे",
})
_MANTRA_MARKERS = frozenset({
  "त्वा", "असि", "स्थ", "स्वाहा", "पाहि", "वीहि", "दृँह", "दृंह", "दृँहस्व", "सादयामि",
  "निर्वपामि", "प्रोक्षामि", "गृह्णामि", "आददे", "जुषस्व", "नमः", "नमो", "रक्षस्व",
  "वेत्तु", "सीद", "मे", "नः", "वः", "ते", "स्वाहा", "हुतः", "हुतो", "जुष्टम्",
  "जुष्टान्", "सविता", "सवितुः", "प्रसवे", "बाहुभ्याम्", "हस्ताभ्याम्", "प्रत्युष्टम्",
  "अवधूतम्", "परापूतम्", "निर्दग्धम्", "पवित्रम्", "गोषत्", "विरोह", "रुहेम",
  "जागृत", "पच", "शमीष्व", "आवद", "धिनुहि", "उद्यछे", "उद्यच्छे", "हरामि",
})

_RELATIVE_OPENERS = frozenset({
  "यत्", "यः", "यो", "या", "ये", "यम्", "याम्", "यान्", "याः", "यानि", "येन", "यस्य",
  "यस्मै", "यस्मात्", "यस्मिन्", "यस्याम्", "यत्र", "यथा", "यदा", "यदि", "यावत्", "यावन्तः",
  "यावतीः", "यावान्",
})
_CORRELATIVE_WORDS = frozenset({
  "तत्", "तद्", "सः", "सो", "स", "सा", "ते", "तम्", "ताम्", "तान्", "ताः", "तानि",
  "तेन", "तस्य", "तस्मै", "तस्मात्", "तस्मिन्", "तस्याम्", "तत्र", "तथा", "तदा",
  "तर्हि", "तावत्", "तावन्तः", "तावतीः", "तावान्", "ततः", "एतेन", "एतत्", "एषः", "एषा",
})
_BRAHMANA_CLAUSE_OPENERS = frozenset({
  "तस्मात्", "तस्माद्", "तस्माल्", "ततः", "ततो", "तस्य", "तत्", "तद्", "तेन",
  "सः", "सो", "स", "सा", "ते", "तम्", "ताः", "तानि", "न", "अथ", "अथो",
  "एषः", "एषो", "एषा", "एतत्", "एतद्", "इदम्", "अयम्", "इयम्", "अमुम्",
  "यत्", "यद्", "यः", "यो", "या", "ये", "यत्र", "यथा", "यदा", "यदि",
  "प्रजापतिः", "देवाः", "असुराः", "इन्द्रः", "अग्निः", "वायुः", "सोमः", "ब्रह्मवादिनः",
  "कस्मै", "चक्षुः", "सत्यम्", "ओजः", "ऐन्द्राग्नम्", "आग्नेयम्", "ब्राह्मणः",
})
_COMMON_BRAHMANA_FINITE_VERBS = frozenset({
  "आसीत्", "आस्ताम्", "आसन्", "अस्ति", "सन्ति", "असि", "अस्मि", "स्यात्", "स्युः",
  "अभवत्", "अभवन्", "भवति", "भवन्ति", "भवतः", "भवेत्", "बभूव",
  "असृजत", "असृजन्त", "असृज्यत", "अध्यसृज्यत", "असृज्येताम्", "सहास्येताम्", "सहासृज्येताम्",
  "अजायत", "जायते", "जायन्ते", "पच्यते", "पच्यन्ते", "पच्येरन्",
  "उदद्रवत्", "प्राद्रवत्", "अपामृष्ट", "न्यमार्ट्", "पर्यमृष्ट", "ऐट्ट",
  "अजुहोत्", "जुहोति", "जुह्वति", "हूयते", "हूयन्ते", "जुहुयात्",
  "उच्यते", "उच्यन्ते", "आह", "आहुः", "उवाच", "ऊचुः", "अब्रवीत्", "अब्रुवन्", "वदति", "वदन्ति", "ब्रूयात्",
  "विवासयति", "रमयति", "दाधार", "विन्दते", "विन्देत", "अविन्दत्", "अविन्दन्", "विविदुः",
  "उपगूहति", "उपगूहतः", "अपागूहताम्", "उपाधावत्", "अदत्ताम्", "उपासरत्", "दत्तः", "ददाति", "दधाति", "अपिदधाति", "उपदधाति",
  "करोति", "कुर्वन्ति", "कुर्यात्", "अकरोत्", "अकुर्वन्", "क्रियते", "कुरुते", "कुरुतः",
  "एति", "यन्ति", "अगात्", "अगन्", "अभ्यजयन्", "अपाक्रामत्", "अपाक्रामन्", "प्राविशत्", "उपैति", "समेति", "व्येति", "अभ्यैति", "आयन्",
  "अवरुन्धे", "अवरुन्द्धे", "अवारुन्द्ध", "प्रतिष्ठापयति", "उपजीवन्ति", "प्रमार्ष्टि", "संमार्ष्टि", "सम्मार्ष्टि", "प्रतिनुदते",
  "गृह्णाति", "गृह्णीयात्", "परिगृह्णाति", "विधूनुयात्", "परिदधाति", "आदधाति", "स्तृणाति", "प्रणयति",
  "आशास्ते", "निर्वपेत्", "निवर्पेत्", "प्रोक्षति", "प्रोक्षन्ति", "मार्जयन्ते", "सादयति", "आसादयति", "आसादयेत्",
  "अभिभवति", "अभिप्रयाति", "उपास्यते", "मन्यते", "मन्यन्ते", "वेद", "विदुः", "हन्ति", "अपहन्ति",
  "प्रीणाति", "अयाट्", "अददात्", "विसृजति", "मीयते", "समभवत्", "अहोष्यत्", "गच्छति", "गच्छन्ति",
  "प्रचरति", "प्रचरन्ति", "आलभते", "आलभेत", "प्राप्नुयात्", "आप्नोति", "उपावर्तते", "अह्वयन्त", "अह्वयन्",
  "अपश्यन्", "अदृंहन्", "अदृँहन्", "प्रतितिष्ठति", "तिष्ठति", "तिष्ठन्ति", "चिन्वीत", "चिनुते", "चिनुत", "चियन्ते",
  "ऋध्नोति", "सन्निवपति", "उपवपति", "विमुञ्चति", "क्रीणाति", "क्रीणीयात्", "विक्रीणीते", "पुष्यति", "पुष्यन्ति",
  "जनयति", "अगोपायन्", "आहरन्", "प्रारोचयत्", "रोचयति", "अन्तरधीयत", "सञ्चन्ते", "सचन्ते", "वहन्ति",
  "समर्धयति", "व्यर्धयति", "पर्यानह्यति", "प्रत्यानह्यन्ति", "जिघाँसन्ति", "अभ्यारोहयति", "अवतिरति", "व्याचष्टे",
  "पणेत", "पणते", "धत्ते", "अस्पर्धन्त", "अकामयत", "अध्यवस्यति", "अवरुन्द्धे", "सम्पद्यन्ते", "समपद्यन्त",
  "संशास्ति", "सँशास्ति", "विहरति", "आपूरयते", "अपोर्णुते", "प्रत्यपोर्णुते", "अन्वायन्", "हरन्ति", "हरेत्",
})


@dataclasses.dataclass
class SplitBlock:
  """One atomic split unit (yajuṣ, metrical ṛk, or Brāhmaṇa sense-unit)."""

  vp_text: str  # Cleaned / OCR-repaired text for विश्वास-प्रस्तुतिः
  mula_text: str  # Source text for मूलम्
  is_rk: bool = False
  is_brahmana: bool = False
  viniyogas: list[ViniyogaEntry] = dataclasses.field(default_factory=list)
  parallel_ref: MantraRefUnit | None = None
  footnote_ids: list[str] = dataclasses.field(default_factory=list)


def classify_is_brahmana(text: str) -> bool:
  """Classify whether an anuvāka (or long passage) is predominantly Brāhmaṇa prose vs Mantra."""
  ws = norm_words(text)
  if not ws:
    return False
  b_hits = sum(1 for w in ws if w in _BRAHMANA_MARKERS)
  m_hits = sum(1 for w in ws if w in _MANTRA_MARKERS)
  # Check strong unmistakable Brāhmaṇa phrases even in short anuvākas
  norm_s = normalize_for_matching(text)
  if any(p in norm_s for p in ("य एवं वेद", "ब्रह्मवादिनो वदन्ति", "तस्मात्", "खलु वै", "ह वै")):
    b_hits += 3
  if any(p in norm_s for p in ("देवस्य त्वा सवितुः", "प्रत्युष्टं रक्ष", "अवधूतं रक्ष", "परापूतं रक्ष", "निर्दग्धं रक्ष")):
    m_hits += 4
  if b_hits >= 3 and b_hits > m_hits * 1.1:
    return True
  if len(ws) >= 35 and b_hits >= 2 and m_hits == 0:
    return True
  return False


# ---------------------------------------------------------------------------
# Sandhi Seam Splitter (for fused KS yajuṣes & Brāhmaṇa sentences and MS seams)
# ---------------------------------------------------------------------------

_VOW_PAIR_SPLITS: dict[str, list[tuple[str, str]]] = {
  # (left_ending_matra_or_empty, right_initial_indep_vowel)
  "ा": [("", "अ"), ("", "आ"), ("ा", "अ"), ("ा", "आ")],
  "ी": [("ि", "इ"), ("ि", "ई"), ("ी", "इ"), ("ी", "ई")],
  "ू": [("ु", "उ"), ("ु", "ऊ"), ("ू", "उ"), ("ू", "ऊ")],
  "े": [("", "इ"), ("", "ई"), ("ा", "इ"), ("ा", "ई")],
  "ो": [("", "उ"), ("", "ऊ"), ("ा", "उ"), ("ा", "ऊ")],
  "ै": [("", "ए"), ("ा", "ए"), ("", "ऐ")],
  "ौ": [("", "ओ"), ("ा", "ओ"), ("", "औ")],
}

_VOICED_TO_PAUSA = {
  "द": "त्", "ग": "क्", "ड": "ट्", "ब": "प्", "ज": "त्", "ल": "त्",
}


def restore_pausa_end(text: str) -> str:
  """Restore clean pausa word-ending on the left side of a split (e.g. ``माघशँसो`` -> ``माघशँसः``)."""
  s = text.rstrip()
  if not s:
    return s
  # Strip trailing punctuation temporarily to inspect last word
  m_trail = re.search(r"([।॥,\s]+)$", s)
  trail = m_trail.group(1) if m_trail else ""
  core = s[: len(s) - len(trail)] if trail else s
  if not core:
    return s

  # Preserve any trailing US accent mark while inspecting base ending
  m_acc = re.search(r"([\u1cd3\u1cd9]+)$", core)
  acc_tail = m_acc.group(1) if m_acc else ""
  base = core[: len(core) - len(acc_tail)] if acc_tail else core

  # 1. Trailing repha `र्` or `स्` or `श्` or `ष्` -> `ः` (keep accent before `ः`)
  if base.endswith(("र्", "स्", "श्", "ष्")) and len(base) >= 3:
    return base[:-2] + "ः" + acc_tail + trail
  # 2. Trailing voiced stop `द्` -> `त्` (unless single short word like `उद्`? No, pausa is always `त्`!)
  if base.endswith("द्") and len(base) >= 3:
    return base[:-2] + "त्" + acc_tail + trail
  # 3. Trailing `ो` from sandhi `-अः` -> `-ओ` before voiced consonant (`मा᳓घ᳓शँसो`, `र᳓क्षो`, `स्तुपो᳓`, `भागो᳓`)
  # Careful: DO NOT convert true `-ओ` words (`विष्णो`, `वायो`, `अथो`, `उतो`, `नो`, `वो`, `सो`, `यो`, `भो`, `प्रभो`, `घर्मो`? Wait: `घर्मो` IS `घर्मः`!)
  last_w_m = re.search(r"[\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff]+$", core)
  if last_w_m:
    lw = last_w_m.group(0)
    lw_bare = _ALL_ACC_RE.sub("", lw)
    _KEEP_O = frozenset({
      "नो", "वो", "अथो", "उतो", "मो", "ओ", "भो", "अहो", "वायो", "विष्णो", "प्रभो",
      "शम्भो", "मनो", "नमो", "ज्यो", "अदो", "गो", "द्यावो", "हविर्धानो", "प्रभो",
      "इन्दो", "बन्धो", "सिन्धो", "पितरो", "तनो", "मृत्यो", "हेतो", "भानो", "सूनो",
      "शत्रो", "विभो", "गुरो", "पशो", "वसो", "मधो", "केतो", "ऋतो",
    })
    if lw_bare.endswith("ो") and len(lw_bare) >= 3 and lw_bare not in _KEEP_O and not lw_bare.endswith(("तनो", "विष्णो", "वायो", "वसो", "पशो", "ऋतो", "भानो", "सूनो")):
      # Convert `-ो` + optional accent to `-ः` (e.g. `मा᳓घ᳓शँसो` -> `मा᳓घ᳓शँसः`, `र᳓क्षो` -> `र᳓क्षः`, `स्तुपो᳓` -> `स्तुपः᳓`)
      return base[:-1] + "ः" + acc_tail + trail
  # 4. Trailing anusvāra `ं` or candrabindu `ँ` at pausa -> `म्` (only when not a nasalized particle like `माँ`, `ताँ`, `सँ`)
  if base.endswith("ं") and len(base) >= 3:
    return base[:-1] + "म्" + acc_tail + trail
  return s


def _build_flat_char_index(text: str) -> tuple[str, list[int]]:
  """Build skeleton-like bare Devanagari string with char indices in ``text`` for O(L) anchor scanning."""
  out: list[str] = []
  idxs: list[int] = []
  i = 0
  n = len(text)
  while i < n:
    ch = text[i]
    if ch in (" ", "\t", "\n", "।", "॥", ",", ";", "ऽ") or "\u0951" <= ch <= "\u0957" or "\u1cd0" <= ch <= "\u1cff":
      i += 1
      continue
    if "\u0900" <= ch <= "\u0963" or "\u0971" <= ch <= "\u097f":
      # Normalize orthography identically to `skeleton_key` while keeping index of each emitted char!
      if ch == "ँ":
        out.append("ं")
        idxs.append(i)
      elif ch == "ळ":
        out.append("ड")
        idxs.append(i)
      elif ch == "ः":
        pass  # skeleton drops visarga
      elif ch in ("स", "श", "ष") and i + 1 < n and text[i + 1] == "्":
        # Check if followed by consonant -> skeleton drops `स्`/`श्`/`ष्`
        i += 2
        continue
      elif ch == "म" and i + 1 < n and text[i + 1] == "्":
        # Check if followed by whitespace + independent vowel (halant-vowel join!)
        j = i + 2
        while j < n and text[j] in " \t":
          j += 1
        if j < n and text[j] in VOW_INDEP:
          out.append("म")
          idxs.append(i)
          if text[j] != "अ":
            matra = {"आ":"ा","इ":"ि","ई":"ी","उ":"ु","ऊ":"ू","ऋ":"ृ","ॠ":"ॄ","ऌ":"ॢ","ए":"े","ऐ":"ै","ओ":"ो","औ":"ौ"}.get(text[j], "")
            if matra:
              out.append(matra)
              idxs.append(j)
          i = j + 1
          continue
        else:
          out.append("ं")
          idxs.append(i)
          i += 2
          continue
      elif ch == "न" and i + 1 < n and text[i + 1] == "्":
        out.append("ं")
        idxs.append(i)
        i += 2
        continue
      elif ch in CONS_DEVA and i + 1 < n and text[i + 1] == "्":
        # Check `C् + space + vowel` join
        j = i + 2
        while j < n and text[j] in " \t":
          j += 1
        if j < n and text[j] in VOW_INDEP:
          out.append(ch)
          idxs.append(i)
          if text[j] != "अ":
            matra = {"आ":"ा","इ":"ि","ई":"ी","उ":"ु","ऊ":"ू","ऋ":"ृ","ॠ":"ॄ","ऌ":"ॢ","ए":"े","ऐ":"ै","ओ":"ो","औ":"ौ"}.get(text[j], "")
            if matra:
              out.append(matra)
              idxs.append(j)
          i = j + 1
          continue
        # Check doubled consonant `C्C` -> collapse to single `C`
        if i + 2 < n and text[i + 2] == ch:
          i += 2
          continue
        # Check `च् छ` -> `छ`
        if ch == "च" and i + 2 < n and text[i + 2] == "छ":
          i += 2
          continue
        # Homorganic nasal before consonant -> `ं`
        if ch in ("ङ", "ञ", "ण") and i + 2 < n and text[i + 2] in CONS_DEVA:
          out.append("ं")
          idxs.append(i)
          i += 2
          continue
        out.append(ch)
        idxs.append(i)
        out.append("्")
        idxs.append(i + 1)
        i += 2
        continue
      else:
        out.append(ch)
        idxs.append(i)
    i += 1
  return "".join(out), idxs


def _probe_candidates_at_pos(
  text: str,
  raw_idx: int,
  flat_skel: str,
  flat_pos: int,
) -> list[tuple[str, str, int, str]]:
  """Generate ``(probe_skel, split_kind, orig_cut_idx, right_prefix_vowel)`` at ``flat_pos``.

  Handles:
  - Clean word/akṣara starts (space boundary or consonant start)
  - Repha boundary (`र्` + consonant, e.g. `बह्वी᳓र्यजमानस्य` -> `बह्वीः᳓` | `यजमानस्य`)
  - Consonant+vowel sandhi seam (`स्थादि᳓न्द्रस्य` -> `स्थात्` | `इ᳓न्द्रस्य`, `ऋध्यासमाच्छेत्ता` -> `ऋध्यासम्` | `आच्छेत्ता`)
  - Vowel coalescence seam (`त्वोर्जे᳓` -> `त्वा` | `ऊर्जे᳓`, `रास्नासीन्द्राण्याः` -> `रास्नासि` | `इन्द्राण्याः`, `रक्षस्वापो` -> `रक्षस्व` | `आपो`)
  """
  n = len(text)
  rem_skel = flat_skel[flat_pos:]
  if len(rem_skel) < 5:
    return []
  cands: list[tuple[str, str, int, str]] = []

  ch = text[raw_idx]
  prev_ch = text[raw_idx - 1] if raw_idx > 0 else " "

  # 1. Direct clean start at whitespace or after avagraha `ऽ` or after repha `र्` or consonant boundary
  if prev_ch in " \t\n।॥":
    cands.append((rem_skel, "space", raw_idx, ""))
  elif prev_ch == "ऽ":
    # Abhinihita `ऽ`: restore leading `अ` on the right! (`रक्षोऽवधूत` -> `रक्षः` | `अवधूत`)
    cands.append(("अ" + rem_skel, "avagraha", raw_idx, "अ"))
  elif raw_idx >= 2 and text[raw_idx - 2 : raw_idx] == "र्" and ch in CONS_DEVA:
    cands.append((rem_skel, "repha", raw_idx, ""))
  elif ch in CONS_DEVA and prev_ch != "्":
    cands.append((rem_skel, "direct", raw_idx, ""))
  elif ch in VOW_INDEP:
    cands.append((rem_skel, "direct", raw_idx, ""))

  # 2. Matra vowel-coalescence OR consonant+vowel sandhi right at a matra `ch in MATRAS`!
  # E.g. `त्वोर्जे` has `raw_idx` pointing to `ो` (`flat_pos` is `ो`):
  if ch in MATRAS and raw_idx > 0 and text[raw_idx - 1] in CONS_DEVA:
    tail_after_matra = flat_skel[flat_pos + 1 :]
    prev_cons = text[raw_idx - 1]
    # (a) Halant consonant + vowel FIRST when `prev_cons` is a common final consonant (`म्`, `त्/द्`, `न्`, `र्`)
    # so `ऋध्यासमाच्छेत्ता` -> `ऋध्यासम् | आच्छेत्ता` and `स्थादिन्द्रस्य` -> `स्थात् | इन्द्रस्य`!
    if prev_cons in ("म", "द", "त", "न", "र", "ग", "ब", "ड"):
      matra_v = {"ा":"आ","ि":"इ","ी":"ई","ु":"उ","ू":"ऊ","ृ":"ऋ","े":"ए","ै":"ऐ","ो":"ओ","ौ":"औ"}.get(ch, "")
      if matra_v:
        cands.append((matra_v + tail_after_matra, f"csandhi:{prev_cons}:{ch}", raw_idx, matra_v))
    # (b) Vowel sandhi coalescence (`ो` -> `उ`/`ऊ`, `ी` -> `इ`/`ई`, `ा` -> `अ`/`आ`, `े` -> `इ`/`ई`, `ू` -> `उ`/`ऊ`)
    seen_v: set[str] = set()
    for _, rv in _VOW_PAIR_SPLITS.get(ch, ()):
      if rv not in seen_v:
        seen_v.add(rv)
        cands.append((rv + tail_after_matra, f"vsandhi:{ch}:{rv}", raw_idx, rv))
  # (c) Inherent `अ` after voiced/nasal consonant (`गोपतौ स्यात ...` no, `क्रव्यादँ` no, `अदस्तमसि` at `द` -> `अदस्तम्` | `असि`!)
  elif ch in ("म", "द", "न", "र", "ग", "ब", "ड") and (raw_idx + 1 >= n or text[raw_idx + 1] not in MATRAS and text[raw_idx + 1] != "्"):
    tail_after_c = flat_skel[flat_pos + 1 :]
    if len(tail_after_c) >= 4:
      cands.append(("अ" + tail_after_c, f"csandhi_a:{ch}", raw_idx, "अ"))

  return cands


def apply_sandhi_cut(text: str, split_kind: str, cut_idx: int) -> tuple[str, str]:
  """Split ``text`` into clean ``(left, right)`` resolving any fused sandhi at ``cut_idx``."""
  if split_kind == "space":
    left = restore_pausa_end(text[:cut_idx].rstrip())
    right = text[cut_idx:].lstrip()
    return left, right

  if split_kind == "avagraha":
    # `cut_idx` points to the char RIGHT AFTER `ऽ` (`रक्षोऽवधूत` -> cut_idx at `व`)
    left_raw = text[: cut_idx - 1].rstrip()
    left = restore_pausa_end(left_raw)
    right = "अ" + text[cut_idx:]
    return left, right

  if split_kind == "repha":
    # `cut_idx` points to consonant after `र्` (`बह्वी᳓र्यजमानस्य` -> `cut_idx` at `य`)
    # Preserve any accent sitting right before `र्`!
    left_raw = text[: cut_idx - 2]
    m_acc = re.search(r"([\u1cd3\u1cd9]+)$", left_raw)
    acc = m_acc.group(1) if m_acc else ""
    base = left_raw[: len(left_raw) - len(acc)] if acc else left_raw
    left = base + "ः" + acc
    right = text[cut_idx:]
    return left, right

  if split_kind == "direct":
    left = restore_pausa_end(text[:cut_idx].rstrip())
    right = text[cut_idx:].lstrip()
    return left, right

  if split_kind.startswith("vsandhi:"):
    # `vsandhi:<matra>:<right_vowel>` where `cut_idx` points to the matra!
    _, matra, rv = split_kind.split(":")
    # Capture any US accent directly following the matra (e.g. `रक्षस्वा᳓पो` -> `᳓` belongs to `आ᳓पो` or left!)
    acc_end = cut_idx + 1
    while acc_end < len(text) and text[acc_end] in (US_UDATTA, US_SVARITA):
      acc_end += 1
    acc_on_matra = text[cut_idx + 1 : acc_end]
    # Choose canonical left matra based on `(matra, rv)` & word ending:
    # `त्वोर्जे` (`त्व` + `ो` + `र्जे` with `rv=ऊ`) -> `त्वा` | `ऊर्जे`
    # `स्थोपायव` (`स्थ` + `ो` + `पायव` with `rv=उ`) -> `स्थ` | `उपायव`
    # `रास्नासीन्द्राण्याः` (`अस` + `ी` + `न्द्राण्याः` with `rv=इ`) -> `असि` | `इन्द्राण्याः`
    # `वीहीन्द्रस्य` (`वीह` + `ी` + `न्द्रस्य` with `rv=इ`) -> `वीहि` | `इन्द्रस्य`
    # `रक्षस्वा᳓पो` (`रक्षस्व` + `ा` + `पो` with `rv=आ`) -> `रक्षस्व` | `आ᳓पो`
    left_stem = text[:cut_idx]
    if matra == "ो":
      left_m = "ा" if left_stem.endswith("त्व") else ""
    elif matra == "ी":
      left_m = "ि"
    elif matra == "ू":
      left_m = "ु"
    elif matra == "ा":
      left_m = "ा" if left_stem.endswith(("त्व", "स्वह", "स्वाहा"[:-1])) else ""
    elif matra == "े":
      left_m = "ा" if left_stem.endswith("त्व") else ""
    else:
      left_m = ""
    # Accent on fused syllable: if `acc_on_matra` is present and left already has an accent or is enclitic `त्वा`/`असि`, give accent to right (`आ᳓पो`), else keep on left if right already has an accent!
    rem_right = text[acc_end:]
    next_word_has_acc = has_us_accents(rem_right.split()[0]) if rem_right.split() else False
    prev_word_has_acc = has_us_accents(left_stem.split()[-1]) if left_stem.split() else False
    if acc_on_matra:
      if not next_word_has_acc and (prev_word_has_acc or left_stem.endswith(("त्व", "स्व", "अस"))):
        l_acc, r_acc = "", acc_on_matra
      elif next_word_has_acc and not prev_word_has_acc:
        l_acc, r_acc = acc_on_matra, ""
      else:
        l_acc, r_acc = "", acc_on_matra
    else:
      l_acc, r_acc = "", ""
    left = left_stem + left_m + l_acc
    right = rv + r_acc + rem_right
    return left, right

  if split_kind.startswith("csandhi:"):
    # `csandhi:<cons>:<matra>` where `cut_idx` points to the matra right after `cons` (`स्थादि᳓न्द्रस्य` -> `स्थात्` | `इ᳓न्द्रस्य`)
    _, cons, matra = split_kind.split(":")
    acc_end = cut_idx + 1
    while acc_end < len(text) and text[acc_end] in (US_UDATTA, US_SVARITA):
      acc_end += 1
    acc_on_matra = text[cut_idx + 1 : acc_end]
    matra_v = {"ा":"आ","ि":"इ","ी":"ई","ु":"उ","ू":"ऊ","ृ":"ऋ","े":"ए","ै":"ऐ","ो":"ओ","ौ":"औ"}[matra]
    pausa_c = _VOICED_TO_PAUSA.get(cons, cons + "्")
    if cons == "र":
      pausa_c = "ः"
    left = text[: cut_idx - 1] + pausa_c
    right = matra_v + acc_on_matra + text[acc_end:]
    return left, right

  if split_kind.startswith("csandhi_a:"):
    # `cut_idx` points to consonant carrying inherent `अ` (`अदस्तमसि` -> `अदस्तम्` | `असि`)
    _, cons = split_kind.split(":")
    acc_end = cut_idx + 1
    while acc_end < len(text) and text[acc_end] in (US_UDATTA, US_SVARITA):
      acc_end += 1
    acc_on_c = text[cut_idx + 1 : acc_end]
    pausa_c = _VOICED_TO_PAUSA.get(cons, cons + "्")
    if cons == "र":
      pausa_c = "ः"
    left = text[:cut_idx] + pausa_c
    right = "अ" + acc_on_c + text[acc_end:]
    return left, right

  return text[:cut_idx].rstrip(), text[cut_idx:].lstrip()


def _map_vp_cut_to_mula(vp_core: str, mula_core: str, c_idx: int) -> int:
  """Map character cut index ``c_idx`` in OCR-repaired ``vp_core`` to the exact index in ``mula_core``."""
  if mula_core == vp_core:
    return c_idx
  sm = difflib.SequenceMatcher(None, vp_core, mula_core, autojunk=False)
  for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if i1 <= c_idx <= i2:
      if tag == "equal":
        return j1 + (c_idx - i1)
      # Inside a 1–2 char OCR patch: snap cleanly to the closer edge of [j1, j2]
      return j1 if (c_idx - i1) <= (i2 - c_idx) else j2
  return min(c_idx, len(mula_core))


def _is_clean_cut_result(left: str, right: str) -> bool:
  """Verify a proposed sandhi split produces two syntactically valid Devanagari strings."""
  ls = left.strip()
  rs = right.strip()
  if len(ls) < 2 or len(rs) < 2:
    return False
  if rs[0] in BAD_SEAM_START_CHARS or ls[-1] in ("",):
    return False
  if rs.startswith("र्") and len(rs) >= 3 and rs[2] in CONS_DEVA:
    return False
  return True


def _looks_like_rk_block(lines: Sequence[str], ref_index: VedicReferenceIndex) -> bool:
  """Return True if ``lines`` is a metrical ṛk by RV/TS parallel match OR ``chandas.is_rk``."""
  if not lines:
    return False
  joined_nl = "\n".join(ln.strip() for ln in lines if ln.strip())
  # 1. `chandas.is_rk` check (normalize trailing `॥` so 2-line half-verses scan properly)
  chk_lines = [
    ln.strip() if re.search(r"[।॥]\s*$", ln.strip()) else ln.strip() + " ।"
    for ln in lines
    if ln.strip()
  ]
  if len(chk_lines) >= 2 and chandas.is_rk("\n".join(chk_lines)):
    return True
  # 2. Check parallel match against RV or TS-Rk!
  par = ref_index.find_best_parallel_mantra(joined_nl, prefer_sources=("RV", "TS", "VS-M", "VS-K"), min_overlap=0.65)
  if par is not None and par[0].is_rk:
    return True
  return False


def _syllable_count_fast(text: str) -> int:
  """Count Devanagari vowel nuclei (syllables) in ``text``."""
  s = _ALL_ACC_RE.sub("", text)
  cnt = 0
  n = len(s)
  for i, ch in enumerate(s):
    if ch in VOW_INDEP:
      cnt += 1
    elif ch in CONS_DEVA:
      if i + 1 < n and s[i + 1] == "्":
        continue
      cnt += 1
  return cnt


_RITUAL_1SG_YAJUS_VERBS = frozenset({
  "प्रोक्षामि", "निर्वपामि", "सादयामि", "गृह्णामि", "दामि", "आददे", "हरामि", "आहरामि",
  "उद्यछे", "उद्यच्छे", "संवपामि", "अभिघारयामि", "संमार्ज्मि", "आतनच्मि", "प्रेक्षे", "अवेक्षे",
  "निवेष्टयामि", "सम्भरामि", "संभरामि", "आरभे", "जुहोमि",
})


def _merge_rk_blocks(blocks: list[SplitBlock], ref_index: VedicReferenceIndex) -> list[SplitBlock]:
  """Merge consecutive mantra lines forming a SINGLE metrical ṛk when NOT separated by distinct viniyogas."""
  if not blocks:
    return blocks
  out: list[SplitBlock] = []
  i = 0
  n = len(blocks)
  while i < n:
    cur = blocks[i]
    merged = False
    for span_len in (4, 3, 2):
      if i + span_len > n:
        continue
      grp = blocks[i : i + span_len]
      # HARD RULE: NEVER merge across a block that has its OWN distinct viniyoga!
      # Exception (whole-ṛk viniyoga rescue): if `grp[0]` has NO viniyoga and `grp[1]`'s viniyoga(s)
      # ALREADY quote `grp[0]`'s opening words (e.g. MŚS 18.9.23 `उत्तिष्ठ ब्रह्मणस्पते ... उप प्रयन्तु ...`
      # matching on line 2 when OCR/punctuation obscured line 1), those viniyogas belong to the WHOLE ṛk!
      merged_vins = list(grp[0].viniyogas)
      if any(b.viniyogas for b in grp[1:]):
        sk0 = skeleton_key(grp[0].vp_text)
        can_rescue = (
          not grp[0].viniyogas
          and len(sk0) >= 8
          and all(not b.viniyogas for b in grp[2:])
          and bool(grp[1].viniyogas)
          and all(sk0[:8] in skeleton_key(v.sutra_text) for v in grp[1].viniyogas)
        )
        if not can_rescue:
          continue
        merged_vins = list(grp[1].viniyogas)
      if any(b.is_rk and "\n" in b.vp_text for b in grp):
        continue
      vp_lines = [b.vp_text.strip() for b in grp]
      # NEVER merge distinct 1st-sg ritual action yajuṣes (`प्रोक्षामि`, `निर्वपामि`, `सादयामि`, etc.) into a ṛk!
      if any(set(norm_words(ln)) & _RITUAL_1SG_YAJUS_VERBS for ln in vp_lines):
        continue
      chk_lines = [
        ln if re.search(r"[।॥]\s*$", ln) else ln + " ।"
        for ln in vp_lines
      ]
      is_chandas_rk = chandas.is_rk("\n".join(chk_lines))
      # 3-pāda virāṭ-triṣṭubh/jagatī (`20..24 + 10..12` syllables, e.g. MS 1.1.2 `प्रेयमगाद्धिषणा...` + `तयावहन्ते कवयः पुरस्तात्`)
      is_3pada_rk = False
      if span_len == 2:
        c0, c1 = _syllable_count_fast(vp_lines[0]), _syllable_count_fast(vp_lines[1])
        if 20 <= c0 <= 24 and 10 <= c1 <= 12:
          p_comb3 = ref_index.find_best_parallel_mantra(
            " ".join(vp_lines), prefer_sources=("RV", "TS"), min_overlap=0.45
          )
          if p_comb3 is not None and p_comb3[0].is_rk:
            is_3pada_rk = True

      combined_vp_flat = " ".join(vp_lines)
      ws_comb = set(norm_words(combined_vp_flat))
      has_yajus_prose = bool({"असि", "स्वाहा"} & ws_comb)
      # Also guard `chandas.is_rk` against coincidental 2–4 line Śatarudrīya (`नमो...`) or Camaka (`... च मे`) litanies!
      is_litany_lines = (
        all(re.match(r"^\s*न[\u1cd3\u1cd9]*म", ln) for ln in vp_lines)
        or all(bool(_CAMAKA_CHAME_RE.search(ln)) for ln in vp_lines)
      )
      if is_chandas_rk and (has_yajus_prose or is_litany_lines) and not any(b.is_rk for b in grp):
        is_chandas_rk = False

      # Check parallel match across RV, TS, AND VS-M/VS-K (for Yajurveda-only ṛks like Agnicayana Sāvitras!)
      par_comb = ref_index.find_best_parallel_mantra(
        combined_vp_flat, prefer_sources=("RV", "TS", "VS-M", "VS-K"), min_overlap=0.58
      )
      par_first = ref_index.find_best_parallel_mantra(
        vp_lines[0], prefer_sources=("RV", "TS", "VS-M", "VS-K"), min_overlap=0.58
      )
      is_ref_rk = (
        par_comb is not None
        and par_comb[0].is_rk
        and (
          par_first is None
          or par_comb[1] > par_first[1] + 0.05
          or len(skeleton_key(combined_vp_flat)) >= 0.75 * len(par_comb[0].skeleton)
        )
      )
      tot_syls = sum(_syllable_count_fast(ln) for ln in vp_lines)
      is_yv_ref_unit = (
        par_comb is not None
        and not par_comb[0].is_rk
        and not has_yajus_prose
        and par_comb[1] >= 0.65
        and len(skeleton_key(combined_vp_flat)) >= 0.75 * len(par_comb[0].skeleton)
        and (
          par_first is None
          or par_comb[1] > par_first[1] + 0.08
          or len(skeleton_key(vp_lines[0])) <= 0.72 * len(par_comb[0].skeleton)
        )
        and (18 <= tot_syls <= 56)
      )
      if (is_chandas_rk or is_3pada_rk or is_ref_rk or is_yv_ref_unit) and not (is_litany_lines and not is_ref_rk):
        mula_lines = [b.mula_text.strip() for b in grp]
        all_fns: list[str] = []
        for b in grp:
          all_fns.extend(b.footnote_ids)
        mark_rk = bool(is_chandas_rk or is_3pada_rk or is_ref_rk or (is_yv_ref_unit and not has_yajus_prose))
        out.append(
          SplitBlock(
            vp_text="  \n".join(vp_lines),
            mula_text="  \n".join(mula_lines),
            is_rk=mark_rk,
            is_brahmana=False,
            viniyogas=merged_vins,
            parallel_ref=par_comb[0] if par_comb else grp[0].parallel_ref,
            footnote_ids=all_fns,
          )
        )
        i += span_len
        merged = True
        break
    if not merged:
      # Check if two consecutive viniyoga-split blocks are TWO METRICAL HALVES of a single ṛk
      # (e.g. MS 1.1.2 `अतस्त्वं बर्हिः शतवल्शं विरोह` [11 syl] + `सहस्रवल्शा वि वयं रुहेम` [11 syl])!
      # Require BOTH halves to have >= 8 syllables so short yajuṣes like `वायवः स्थ` (4 syls) are NEVER mistagged!
      if not cur.is_rk and i + 1 < n and blocks[i + 1].viniyogas:
        c0 = _syllable_count_fast(cur.vp_text)
        c1 = _syllable_count_fast(blocks[i + 1].vp_text)
        if c0 >= 8 and c1 >= 8:
          pair_lines = [
            cur.vp_text.strip() if re.search(r"[।॥]\s*$", cur.vp_text.strip()) else cur.vp_text.strip() + " ।",
            blocks[i + 1].vp_text.strip() if re.search(r"[।॥]\s*$", blocks[i + 1].vp_text.strip()) else blocks[i + 1].vp_text.strip() + " ।",
          ]
          pair_par = ref_index.find_best_parallel_mantra(" ".join(pair_lines), prefer_sources=("RV", "TS"), min_overlap=0.62)
          ws_pair = set(norm_words(" ".join(pair_lines)))
          is_yajus_prose = bool({"असि", "स्वाहा"} & ws_pair)
          if (not is_yajus_prose and chandas.is_rk("\n".join(pair_lines))) or (
            pair_par is not None and pair_par[0].is_rk and abs(c0 - c1) <= 3 and c0 in range(10, 14)
          ):
            cur.is_rk = True
            blocks[i + 1].is_rk = True
      out.append(cur)
      i += 1
  return out


_INCOMPLETE_LEFT_ONLY = frozenset({
  "देवस्य", "वसूनाम्", "वसोः", "मातरिश्वनः", "अदित्याः", "अदित्या", "देवानाम्", "विष्णोः",
  "इन्द्रस्य", "बृहस्पतेः", "अग्नेः", "मित्रस्य", "यजमानस्य", "सविता", "सवितुः", "देवः",
  "अग्ने", "इन्द्र", "विष्णो", "वायो", "सोम", "प्रजापते", "अग्नये", "इन्द्राय", "विष्णवे",
  "पूष्णः", "अश्विनोः", "वाचः", "प्रजायाः", "पितॄणाम्", "मरुताम्", "अस्मै", "तस्य", "अस्य",
})

_VALID_CLAUSE_END_WORDS = frozenset({
  "त्वा", "वाम्", "वः", "असि", "स्थ", "स्थः", "स्वाहा", "पाहि", "वीहि", "दृंह", "दृंहस्व",
  "आददे", "वेत्तु", "सीद", "रक्षस्व", "रक्षः", "अरातिः", "अरातयः", "भागः", "भागम्", "स्तुपः",
  "सन्नहनम्", "संनहनम्", "ग्रथ्नातु", "स्थात्", "उद्यछे", "उद्यच्छे", "हरामि", "सादयामि", "निर्वपामि",
  "प्रोक्षामि", "गृह्णामि", "दामि", "कर्मणे", "विरोह", "रुहेम", "अयक्ष्माः", "अघशंसः", "वृणक्तु",
  "बह्वीः", "वितष्टा", "पुरस्तात्", "ह्वाः", "विश्वायुः", "विश्वव्यचाः", "विश्वधायाः", "विश्वकर्मा",
  "स्तोकः", "द्रप्सः", "आतनच्मि", "विष्णवे", "जागृत", "रिषत्", "रिषम्", "ऋध्यासम्", "असौ",
  "प्रथस्व", "प्रथताम्", "जुषस्व", "नमः", "अस्तु", "भव", "भूयाः", "भूयासम्", "भूयास्म",
  "गमेयम्", "पुषेयम्", "प्रजनिषेयम्", "दभेयम्", "पच", "शमीष्व", "आवद", "धिनुहि", "संमार्ज्मि",
  "अमुक्षि", "प्रेक्षे", "अवेक्षे", "उपगृह्णातु", "प्रतिगृह्णातु", "जिन्व", "विसर्जनम्",
  "भवामि", "जुहोमि", "यजामहे", "हुवे", "जेष्म", "सदेम", "दधातन", "विमुञ्चताम्", "पवित्रेण",
  "रश्मिभिः", "धाक्", "नुदस्व", "वह", "परिवेशय", "परिविशन्तु", "योनिः", "पृष्ठे", "उपस्थे",
  "रास्नासि", "घर्मोऽसि", "द्यौरसि", "पृथिव्यसि", "धूरसि", "गोषदसि", "अह्रुतासि", "अह्रुतमसि",
  "अभिघारयामि", "संवपामि", "श्रपयतु", "हिंसीत्", "हिंसीः", "जहि", "पर्यूह", "तप्यध्वम्",
  "विविनक्तु", "रक्ष", "प्रणयतु", "प्रार्पयतु", "दधातु", "परिधत्ताम्", "मादयन्ताम्", "धाः",
  "शतधारम्", "सहस्रधारम्", "द्यावापृथिवीभ्याम्", "पृथिव्याम्", "अन्तरिक्षम्", "दिवम्",
})


_NEVER_START_NEW_MANTRA_WORDS = frozenset({
  "पूष्णः", "पूष्णो", "अश्विनोः", "अश्विनोर्", "सवितुः", "प्रसवे", "बाहुभ्याम्", "हस्ताभ्याम्",
  "द्यावापृथिवीभ्याम्", "बृहते", "नाकाय", "स्वाहा", "कर्मणे", "श्रेष्ठतमाय", "पवित्रेण", "रश्मिभिः",
  "दैव्याय",
})


_NON_PAUSA_END_HALANTS = ("ञ्", "ङ्", "ण्", "च्", "ज्", "श्", "ष्", "स्", "र्", "ल्", "व्", "य्", "ह्", "भ्", "ध्", "घ्", "झ्", "ढ्")
_DANGLING_LAST_WORDS = frozenset({"तत्", "तद्", "तन्", "तम्", "तञ्", "यत्", "यद्", "सः", "ते", "मे", "नः", "वः", "च", "वा", "एव", "वै"})


def _left_looks_complete_mantra(
  t_left: str,
  left_sk: str,
  l_ws: tuple[str, ...],
  right_ws: tuple[str, ...],
  sp_kind: str,
  ref_index: VedicReferenceIndex,
) -> bool:
  """Verify ``t_left`` is a syntactically complete mantra unit (never a broken word or bare genitive)."""
  if not l_ws or len(left_sk) < 5:
    return False
  # NEVER split leaving a parasavarṇa/non-pausa halant (`त᳓ञ् | शुन्धध्वम्`) or dangling pronoun (`तत्`, `यत्`) at end!
  left_bare_strip = _ALL_ACC_RE.sub("", t_left).rstrip(" ।॥,;")
  if left_bare_strip.endswith(_NON_PAUSA_END_HALANTS) and sp_kind != "space":
    return False
  if left_bare_strip.endswith(("ञ्", "ङ्", "ण्", "च्", "ज्", "ल्")):
    return False
  if l_ws[-1] in _DANGLING_LAST_WORDS:
    return False
  # NEVER split right before a continuation of the Savitṛ/dative formula (`पूष्णो हस्ताभ्याम्`, `द्यावापृथिवीभ्याम्`, `सवितुः प्रसवे`)
  if right_ws and right_ws[0] in _NEVER_START_NEW_MANTRA_WORDS:
    return False
  # NEVER split `देवस्य त्वा | सवितुः` or `देवस्य वः | सवितुः`!
  if len(l_ws) == 2 and l_ws[0] == "देवस्य" and l_ws[1] in ("त्वा", "वः") and right_ws and right_ws[0].startswith("सवितु"):
    return False
  # NEVER leave a bare single genitive/vocative (`मातरिश्वनः`, `वसूनाम्`, `अदित्याः`, `इन्द्रस्य`) alone on the left!
  if len(l_ws) == 1 and l_ws[0] in _INCOMPLETE_LEFT_ONLY:
    return False
  # For a `"direct"` mid-token consonant split (no space, no sandhi seam — e.g. `ना | काय`!),
  # STRICTLY require `l_ws[-1]` to end in a complete mantra-ending word (never mid-stem!)
  if sp_kind == "direct":
    lw = l_ws[-1]
    if lw not in _VALID_CLAUSE_END_WORDS and not lw.endswith((
      "असि", "स्थ", "त्वा", "वाम्", "स्वाहा", "आमि", "अतु", "अन्तु", "अस्व", "ध्वम्",
      "पाहि", "वीहि", "दृंह", "सीद", "वेत्तु", "जहि", "वह", "ददे", "रुहेम", "विरोह",
      "गोषत्", "रक्षः", "अरातिः", "स्तुपः", "भागः", "स्तोकः", "द्रप्सः", "विष्णवे", "भूयासम्",
      "दधाति", "दधातु", "भवति", "भवतु", "अस्तु", "नमः", "रक्षस्व", "आतनच्मि", "जागृत",
    )):
      return False
  return True


_SVAHA_LITANY_RE = re.compile(r"स्वा[\u1cd3\u1cd9]*ह(?:ा[\u1cd3\u1cd9]*|े[\u1cd3\u1cd9]*|ो[\u1cd3\u1cd9]*)")


def _split_svaha_litany(
  vp_core: str,
  mula_core: str,
  lex: UnifiedVedicLexicon | None = None,
) -> list[tuple[str, str]] | None:
  """Split long ``… स्वाहा … स्वाहा …`` offering litanies (>= 4 offerings) cleanly without hitting recursion depth."""
  matches = list(_SVAHA_LITANY_RE.finditer(vp_core))
  if len(matches) < 4:
    return None

  def _split_one_text(txt: str) -> list[str]:
    ms = list(_SVAHA_LITANY_RE.finditer(txt))
    if len(ms) < 4:
      return [txt]
    out: list[str] = []
    start = 0
    for idx, m in enumerate(ms):
      end = m.end()
      # If this `स्वाहा` is at the very end of the chunk, include any trailing punctuation/whitespace
      if idx == len(ms) - 1:
        piece = txt[start:].strip()
        if piece:
          out.append(piece)
        start = len(txt)
        break
      tok = m.group(0)
      rem = txt[end:]
      if not rem or rem[0] in " \t\n।॥,;":
        # Clean spaced `स्वाहा `
        piece = txt[start:end].strip()
        if piece:
          out.append(piece)
        start = end
        while start < len(txt) and txt[start] in " \t\n।॥,;":
          start += 1
        continue
      # Fused sandhi right after `स्वाहा`: `स्वाहे...` (`स्वाहा + इ/ई`), `स्वाहो...` (`स्वाहा + उ/ऊ`),
      # `स्वाहा...` (`स्वाहा + अ/आ`!)
      # Preserve accent on `स्वाहा` vs right initial vowel
      m_acc = re.search(r"([\u1cd3\u1cd9]+)$", tok)
      acc_tail = m_acc.group(1) if m_acc else ""
      base_tok = tok[: len(tok) - len(acc_tail)] if acc_tail else tok
      last_v = base_tok[-1]
      # Pick best right initial vowel (`इ`/`ई`, `उ`/`ऊ`, `अ`/`आ`) using lexicon when available
      if last_v == "े":
        v_cands = ("इ", "ई")
      elif last_v == "ो":
        v_cands = ("उ", "ऊ")
      else:
        v_cands = ("अ", "आ")
      nxt_word_tail = re.match(r"[\u0900-\u0963\u0971-\u097f]+", _ALL_ACC_RE.sub("", rem))
      chosen_v = v_cands[0]
      if lex is not None and nxt_word_tail:
        tail_w = nxt_word_tail.group(0)
        from doc_curation.sanskrit.accent.shatapatha_solver import _deva_to_slp
        best_v_sc = 0.0
        for vc in v_cands:
          sc = lex.word_score_slp(_deva_to_slp(vc + tail_w))
          if sc > best_v_sc:
            best_v_sc = sc
            chosen_v = vc
        # Common Ashvamedha prefixes (`आसीनाय`, `आसिताय`, `आसिष्यते`, `अपानाय`, `अवक्रन्दते`)
        if best_v_sc <= 0 and last_v == "ा" and tail_w.startswith(("सीन", "सित", "सिष्य")):
          chosen_v = "आ"
      svaha_clean = re.sub(r"[ेो]([\u1cd3\u1cd9]*)$", r"ा\1", tok)
      piece = (txt[start : m.start()] + svaha_clean).strip()
      if piece:
        out.append(piece)
      # Prepend `chosen_v` to next slice by mutating local remainder via virtual prefix!
      out.append(f"__PREPEND__:{chosen_v}")
      start = end

    if start < len(txt):
      tail = txt[start:].strip()
      if tail:
        out.append(tail)

    # Resolve `__PREPEND__` markers onto the immediately following slice
    resolved: list[str] = []
    pending_pre = ""
    for item in out:
      if item.startswith("__PREPEND__:"):
        pending_pre = item.split(":", 1)[1]
      else:
        resolved.append(pending_pre + item)
        pending_pre = ""
    return [r for r in resolved if r.strip()]

  vp_list = _split_one_text(vp_core)
  if len(vp_list) < 4:
    return None
  mula_list = _split_one_text(mula_core) if mula_core != vp_core else list(vp_list)
  if len(mula_list) != len(vp_list):
    mula_list = list(vp_list)
  return list(zip(vp_list, mula_list))


_NAMAS_OPEN_RE = re.compile(r"(?<=\s)न[\u1cd3\u1cd9]*म(?:ः[\u1cd3\u1cd9]*|ो[\u1cd3\u1cd9]*|स्|श्|ष्|(?=\s))")
_CAMAKA_CHAME_RE = re.compile(r"च[\u1cd3\u1cd9]*\s+मे[\u1cd3\u1cd9]*(?=\s|$|[।॥,;])")


def _split_namas_litany(vp_core: str, mula_core: str) -> list[tuple[str, str]] | None:
  """Split long Śatarudrīya / Namaskāra litanies (>= 4 clause-initial ``नमः/नमो/...``) in O(L)."""
  cuts: list[int] = []
  last_cut = 0
  for m in _NAMAS_OPEN_RE.finditer(vp_core):
    pos = m.start()
    left = vp_core[last_cut:pos].strip()
    l_ws = norm_words(left)
    if len(l_ws) < 2:
      continue
    # Do NOT cut before clause-final `वो नमः` / `ते नमः` / `नः नमः`!
    if l_ws[-1] in ("वो", "वः", "ते", "मे", "नः"):
      continue
    cuts.append(pos)
    last_cut = pos
  if len(cuts) < 3:
    return None
  out: list[tuple[str, str]] = []
  prev_v = 0
  prev_m = 0
  for c in cuts + [len(vp_core)]:
    vp_p = restore_pausa_end(vp_core[prev_v:c].strip())
    if c == len(vp_core):
      mu_p = mula_core[prev_m:].strip()
    else:
      mc = _map_vp_cut_to_mula(vp_core, mula_core, c)
      mu_p = mula_core[prev_m:mc].strip()
      prev_m = mc
    prev_v = c
    if vp_p and _DEVA_LETTER_RE.search(accent.strip_accents(vp_p)):
      out.append((vp_p, mu_p or vp_p))
  return out if len(out) >= 4 else None


def _split_camaka_litany(vp_core: str, mula_core: str) -> list[tuple[str, str]] | None:
  """Split long Camaka litanies (>= 4 ``… च मे`` clauses) into semantic pairs ``X च मे Y च मे``."""
  ms = list(_CAMAKA_CHAME_RE.finditer(vp_core))
  if len(ms) < 4:
    return None
  # Cut after every 2nd `च मे` (pairing `अश्मा च मे मृत्तिका च मे`, matching VS-M 18 & MS 2.11!)
  cuts: list[int] = []
  for idx in range(1, len(ms) - 1, 2):
    cuts.append(ms[idx].end())
  if not cuts:
    return None
  out: list[tuple[str, str]] = []
  prev_v = 0
  prev_m = 0
  for c in cuts + [len(vp_core)]:
    vp_p = vp_core[prev_v:c].strip()
    if c == len(vp_core):
      mu_p = mula_core[prev_m:].strip()
    else:
      mc = _map_vp_cut_to_mula(vp_core, mula_core, c)
      mu_p = mula_core[prev_m:mc].strip()
      prev_m = mc
    prev_v = c
    if vp_p and _DEVA_LETTER_RE.search(accent.strip_accents(vp_p)):
      out.append((vp_p, mu_p or vp_p))
  return out if len(out) >= 2 else None


def _split_fused_mantra_chunk(
  vp_chunk: str,
  mula_chunk: str,
  ref_index: VedicReferenceIndex,
  *,
  corpus: str,
  cursors: dict[str, int],
  allow_interior_ref_splits: bool = True,
  lex: UnifiedVedicLexicon | None = None,
  _depth: int = 0,
) -> list[SplitBlock]:
  """Split a single mantra line/paragraph into distinct yajuṣes using viniyogas + TS/VS/MS/RV."""
  vp_work = vp_chunk.strip()
  mula_work = mula_chunk.strip()
  if not vp_work or not _DEVA_LETTER_RE.search(accent.strip_accents(vp_work)):
    return []

  vp_core = re.sub(r"\s*[।॥]+\s*[०-९0-9]+\s*[।॥]*\s*$", "", vp_work).strip()
  mula_core = re.sub(r"\s*[।॥]+\s*[०-९0-9]+\s*[।॥]*\s*$", "", mula_work).strip()
  if not vp_core or not _DEVA_LETTER_RE.search(accent.strip_accents(vp_core)):
    return []

  # Pre-split long litanies (`… स्वाहा …`, Śatarudrīya `नमो …`, Camaka `… च मे …`) cleanly in O(L)!
  if _depth == 0:
    litany = (
      _split_svaha_litany(vp_core, mula_core, lex=lex)
      or _split_namas_litany(vp_core, mula_core)
      or _split_camaka_litany(vp_core, mula_core)
    )
    if litany:
      out_lit: list[SplitBlock] = []
      prefer_lit = ("TS", "VS-M", "VS-K", "RV") if corpus == "MS" else ("MS", "TS", "VS-M", "VS-K", "RV")
      for vl, ml in litany:
        ws_l = norm_words(vl)
        sk_l = skeleton_key(vl)
        vins_l = ref_index.match_viniyogas_at(
          sk_l, ws_l, corpus=corpus,
          cursor_mss=cursors.get("mss"), cursor_vss=cursors.get("vss"), cursor_ksb=cursors.get("ksb"),
        )
        par_l = ref_index.find_best_parallel_mantra(vl, prefer_sources=prefer_lit, min_overlap=0.65)
        out_lit.append(
          SplitBlock(
            vp_text=vl,
            mula_text=ml,
            is_rk=False,
            is_brahmana=False,
            viniyogas=vins_l,
            parallel_ref=par_l[0] if par_l else None,
          )
        )
      return out_lit

  # Safety recursion guard: NEVER drop text — emit intact SplitBlock if depth limit reached!
  if _depth > 120:
    return [SplitBlock(vp_text=vp_core, mula_text=mula_core, is_rk=False, is_brahmana=False)]

  ws_all = norm_words(vp_core)
  sk_all = skeleton_key(vp_core)
  init_vins = ref_index.match_viniyogas_at(
    sk_all,
    ws_all,
    corpus=corpus,
    cursor_mss=cursors.get("mss"),
    cursor_vss=cursors.get("vss"),
    cursor_ksb=cursors.get("ksb"),
  )
  init_vin_refs = {(v.source, v.ref) for v in init_vins}
  # Seed local cursor view with `init_vins` so an interior viniyoga in the SAME line (e.g. `इषे त्वा` [1.1.13]
  # followed by `सुभूताय` [1.1.15] or `इन्द्रस्य... उद्यच्छे` [1.1.47] followed by `बृहस्पतेः...` [1.1.48])
  # immediately sees `in_window=True`!
  scan_cursors = dict(cursors)
  for v in init_vins:
    ck = "mss" if v.source.startswith("मानव") else ("vss" if v.source.startswith("वाराह") else "ksb")
    if ck not in scan_cursors or (0 < v.seq_idx - scan_cursors[ck] <= 40):
      scan_cursors[ck] = v.seq_idx

  prefer = ("TS", "VS-M", "VS-K", "RV") if corpus == "MS" else ("MS", "TS", "VS-M", "VS-K", "RV")
  whole_par = ref_index.find_best_parallel_mantra(vp_core, prefer_sources=prefer, min_overlap=0.78)

  flat_skel, char_map = _build_flat_char_index(vp_core)
  L = len(flat_skel)

  best_cut: tuple[int, int, str, int, list[ViniyogaEntry]] | None = None

  for fi in range(4, L - 4):
    raw_idx = char_map[fi]
    cands = _probe_candidates_at_pos(vp_core, raw_idx, flat_skel, fi)
    for probe_sk, sp_kind, c_idx, _ in cands:
      if len(probe_sk) < 5:
        continue
      t_left, t_right = apply_sandhi_cut(vp_core, sp_kind, c_idx)
      if not _is_clean_cut_result(t_left, t_right):
        continue
      if len(t_left) >= len(vp_core) or len(t_right) >= len(vp_core):
        continue
      left_sk = skeleton_key(t_left)
      l_ws = norm_words(t_left)
      right_ws = norm_words(t_right)
      if not _left_looks_complete_mantra(t_left, left_sk, l_ws, right_ws, sp_kind, ref_index):
        continue

      # Priority 1: Distinct Śrautasūtra / KS Brāhmaṇa viniyoga starting right here!
      r_vins = ref_index.match_viniyogas_at(
        probe_sk,
        right_ws,
        corpus=corpus,
        cursor_mss=scan_cursors.get("mss"),
        cursor_vss=scan_cursors.get("vss"),
        cursor_ksb=scan_cursors.get("ksb"),
        preceding_skel=left_sk,
      )
      fresh_vins = [
        v for v in r_vins
        if (v.source, v.ref) not in init_vin_refs
        and not (len(left_sk) >= 5 and left_sk[-5:] in v.pratika_skeleton)
      ]
      if fresh_vins:
        strong_vin = False
        for v in fresh_vins:
          c_key = "mss" if v.source.startswith("मानव") else ("vss" if v.source.startswith("वाराह") else "ksb")
          cur_val = scan_cursors.get(c_key)
          in_window = (cur_val is not None and 0 < v.seq_idx - cur_val <= 20)
          v_sk_len = len(v.pratika_skeleton)
          if in_window:
            strong_vin = True
            break
          # Outside current ritual window: ONLY trust if whole chunk is NOT already a single mantra AND
          # left ends in a verified complete mantra-ending word (`_VALID_CLAUSE_END_WORDS`) AND pratīka >= 8 chars!
          if whole_par is None and v_sk_len >= 8 and l_ws[-1] in _VALID_CLAUSE_END_WORDS:
            strong_vin = True
            break
        if strong_vin:
          best_cut = (0, c_idx, sp_kind, len(probe_sk), fresh_vins)
          break

      # Priority 2: Parallel TS / VS-M / VS-K / MS mantra boundary!
      if allow_interior_ref_splits and whole_par is None:
        r_refs = ref_index.find_mantra_starts_at(probe_sk, right_ws)
        if r_refs:
          l_refs = ref_index.find_mantra_starts_at(left_sk, l_ws)
          left_matches_ref = any(
            abs(len(u.skeleton) - len(left_sk)) <= max(3, int(0.25 * len(u.skeleton)))
            and (left_sk.startswith(u.skeleton[: min(7, len(u.skeleton))]) or u.skeleton.startswith(left_sk[: min(7, len(left_sk))]))
            for u in l_refs
          )
          left_ends_clause = (
            l_ws[-1] in _VALID_CLAUSE_END_WORDS
            or l_ws[-1].endswith(("असि", "आमि", "आतु", "अतु", "अन्तु", "अस्व", "ध्वम्", "यामि", "इषम्", "भूयासम्"))
          )
          top_r = r_refs[0]
          right_strong = (
            probe_sk.startswith(top_r.skeleton)
            or (len(top_r.skeleton) >= 10 and probe_sk[:10] == top_r.skeleton[:10])
          )
          if right_strong and (left_matches_ref or left_ends_clause):
            best_cut = (1, c_idx, sp_kind, len(top_r.skeleton), [])
            break
    if best_cut is not None:
      break

  if best_cut is not None:
    _, c_idx, sp_kind, _, _ = best_cut
    vp_l, vp_r = apply_sandhi_cut(vp_core, sp_kind, c_idx)
    if mula_core == vp_core:
      mula_l, mula_r = vp_l, vp_r
    else:
      m_idx = _map_vp_cut_to_mula(vp_core, mula_core, c_idx)
      mula_l, mula_r = apply_sandhi_cut(mula_core, sp_kind, m_idx)
      if not _is_clean_cut_result(mula_l, mula_r):
        mula_l, mula_r = vp_l, vp_r

    left_blocks = _split_fused_mantra_chunk(
      vp_l, mula_l, ref_index, corpus=corpus, cursors=cursors,
      allow_interior_ref_splits=allow_interior_ref_splits, _depth=_depth + 1,
    )
    right_blocks = _split_fused_mantra_chunk(
      vp_r, mula_r, ref_index, corpus=corpus, cursors=cursors,
      allow_interior_ref_splits=allow_interior_ref_splits, _depth=_depth + 1,
    )
    return left_blocks + right_blocks

  # Base case: emit ONE atomic SplitBlock and advance ritual cursors (preventing single-block teleports > 150 sūtras!)
  for v in init_vins:
    ck = "mss" if v.source.startswith("मानव") else ("vss" if v.source.startswith("वाराह") else "ksb")
    prev_c = cursors.get(ck)
    if prev_c is None or (-5 <= v.seq_idx - prev_c <= 150):
      cursors[ck] = v.seq_idx

  par = whole_par or ref_index.find_best_parallel_mantra(vp_core, prefer_sources=prefer, min_overlap=0.65)
  par_unit = par[0] if par else None
  is_rk = bool(par_unit and par_unit.is_rk)
  return [
    SplitBlock(
      vp_text=vp_core,
      mula_text=mula_core,
      is_rk=is_rk,
      is_brahmana=False,
      viniyogas=init_vins,
      parallel_ref=par_unit,
    )
  ]


# ---------------------------------------------------------------------------
# Brāhmaṇa Prose Splitting (Tests 1–5)
# ---------------------------------------------------------------------------

def _is_finite_verb_word(word_bare: str, lex: UnifiedVedicLexicon | None) -> bool:
  w = word_bare.replace("ऽ", "")
  if w in _COMMON_BRAHMANA_FINITE_VERBS:
    return True
  if len(w) < 3 or w in _BRAHMANA_CLAUSE_OPENERS or w in _RELATIVE_OPENERS or w in _CORRELATIVE_WORDS:
    return False
  if lex is not None:
    morph = lex.analyze_morph(w)
    if morph["is_tinanta"] and not morph["is_subanta"] and not morph["is_avyaya"]:
      return True
  return False


def _starts_with_relative(text: str) -> bool:
  ws = norm_words(text)
  if not ws:
    return False
  if ws[0] in _RELATIVE_OPENERS:
    return True
  if len(ws) >= 2 and ws[0] in ("सः", "सो", "स", "सा", "ते", "तत्", "अथ", "तस्य") and ws[1] in _RELATIVE_OPENERS:
    return True
  return False


def _has_correlative(text: str) -> bool:
  ws = norm_words(text)
  return any(w in _CORRELATIVE_WORDS for w in ws)


def split_ms_brahmana_anuvaka(anu: MsAnuvakaSource) -> list[SplitBlock]:
  """Split an MS Brāhmaṇa anuvāka following Tests 1–5 (merging correlatives & quotes)."""
  raw_lines = anu.raw_lines
  clean_lines = anu.clean_lines
  if not clean_lines:
    return []

  groups: list[list[int]] = []
  i = 0
  n = len(clean_lines)
  while i < n:
    grp = [i]
    # Test 2: If line has odd number of `\` quote markers, absorb following lines until closed + `इति`!
    while grp[-1] + 1 < n:
      cur_joined = " ".join(clean_lines[k] for k in grp)
      nxt_line = clean_lines[grp[-1] + 1]
      nxt_ws = norm_words(nxt_line)
      cur_ws = norm_words(cur_joined)

      # (a) Unclosed TITUS quote `\`: ONLY merge if the line opens a quote that does NOT close before `इति`!
      # Note: MS TITUS frequently writes `<mantra> \ इ᳓ति ॥` (a single `\` before `इति` with no opening `\`) —
      # that is ALREADY closed by `इति` on the same line and MUST NOT absorb subsequent Brāhmaṇa sentences!
      has_unclosed_backslash = (
        cur_joined.count("\\") % 2 == 1
        and not re.search(r"\\\s*इ[\u1cd3\u1cd9]*ति", cur_joined)
        and len(grp) < 4
      )
      if has_unclosed_backslash:
        grp.append(grp[-1] + 1)
        continue
      # (b) Next line is a stray `इति` continuation (`इ᳓ति॥`, `इ᳓त्याह॥`)
      if nxt_ws and nxt_ws[0] in ("इति", "इत्याह", "इत्य्") and len(nxt_ws) <= 4:
        grp.append(grp[-1] + 1)
        continue
      # (c) Test 1: Correlative `यत्...` line without correlative followed by answering `तत्/तेन/...` line!
      if _starts_with_relative(cur_joined) and not _has_correlative(cur_joined) and _has_correlative(nxt_line):
        # Don't chain multiple correlative pairs (`यत् सायं... तेन...` + `यत् प्रातः...` -> stop before second `यत्`!)
        if not _starts_with_relative(nxt_line):
          grp.append(grp[-1] + 1)
          continue
      # (d) Short `यत् प्रातः` elliptical antecedent (<= 3 words) followed by answering clause
      if len(cur_ws) <= 3 and cur_ws and cur_ws[0] in _RELATIVE_OPENERS and not _starts_with_relative(nxt_line):
        grp.append(grp[-1] + 1)
        continue
      break
    groups.append(grp)
    i = grp[-1] + 1

  blocks: list[SplitBlock] = []
  for grp in groups:
    vp = "  \n".join(strip_ms_quote_backslashes(clean_lines[k]) for k in grp)
    mula = "  \n".join(raw_lines[k].strip() for k in grp)
    blocks.append(SplitBlock(vp_text=vp, mula_text=mula, is_rk=False, is_brahmana=True))
  return blocks


def split_ks_brahmana_paragraph(
  vp_para: str,
  mula_para: str,
  lex: UnifiedVedicLexicon | None,
) -> list[SplitBlock]:
  """Split a fused KS Schroeder Brāhmaṇa paragraph into Tests 1–5 sense-units."""
  vp_core = re.sub(r"\s*[।॥]+\s*[०-९0-9]+\s*[।॥]*\s*$", "", vp_para.strip()).strip()
  mula_core = re.sub(r"\s*[।॥]+\s*[०-९0-9]+\s*[।॥]*\s*$", "", mula_para.strip()).strip()
  if not vp_core:
    return []

  # First split on explicit `॥` / `।` (keep embedded quotes intact if `इति` immediately follows!)
  vp_segs = [s.strip() for s in re.split(r"॥+", vp_core) if s.strip()]
  mula_segs = [s.strip() for s in re.split(r"॥+", mula_core) if s.strip()]
  if len(vp_segs) != len(mula_segs):
    mula_segs = list(vp_segs)

  blocks: list[SplitBlock] = []
  for v_seg, m_seg in zip(vp_segs, mula_segs):
    if not _DEVA_LETTER_RE.search(accent.strip_accents(v_seg)):
      continue
    blocks.extend(_split_ks_brahmana_clause_chain(v_seg, m_seg, lex))
  return blocks


_BRAHMANA_QUOTE_INTRO_VERBS = frozenset({
  "जुहोति", "जुहुयात्", "आह", "आहुः", "उवाच", "ऊचुः", "अब्रवीत्", "अब्रुवन्",
  "ब्रूयात्", "वदति", "वदन्ति", "जपति", "जपेत्", "मन्त्रयते", "अभिमन्त्रयते",
})
_NO_CUT_NEXT_WORDS = frozenset({
  "इति", "इत्य्", "इत्याह", "इत्युक्त्वा", "च", "वा", "हि", "ह", "वै", "चेत्",
  "यदि", "एव", "उ", "नु", "खलु", "किल", "स्म", "तु", "अपि", "अथवा",
})


def _split_ks_brahmana_clause_chain(
  vp_seg: str,
  mula_seg: str,
  lex: UnifiedVedicLexicon | None,
) -> list[SplitBlock]:
  """Split one unpunctuated KS Brāhmaṇa prose block at finite-verb + clause-opener seams (Tests 1–5)."""
  ws = norm_words(vp_seg)
  if len(ws) <= 10:
    return [SplitBlock(vp_text=vp_seg, mula_text=mula_seg, is_rk=False, is_brahmana=True)]

  # Strip US accents ONLY for matching indices, keeping exact char map back to `vp_seg`
  bare_chars: list[str] = []
  b2orig: list[int] = []
  for idx, ch in enumerate(vp_seg):
    if "\u0951" <= ch <= "\u0957" or "\u1cd0" <= ch <= "\u1cff":
      continue
    bare_chars.append(ch)
    b2orig.append(idx)
  bare_s = "".join(bare_chars)

  # Candidate boundary positions `(pos_b, split_kind, match_priority)`:
  # 1) Consonant-fused `त्/द्/म्/न्/ः` seams before clear Brāhmaṇa clause openers (`आसीत्तस्मात्`, `उदद्रवत्तस्य`, `क्रीणीयाद्वाग्वै`)
  # 2) Spaced boundaries right AFTER any clause-final finite verb or `दक्षिणा` (with strict Tests 1–5 guards!)
  # 3) Vowel-fused `दक्षिणा` + `आ/ऐ` (`दक्षिणाग्नावैष्णव`, `दक्षिणाग्नेयो`, `दक्षिणैन्द्राग्न`) and `-ति` + yaṇ (`अपिदधात्यादित्येभ्यो`)
  fused_opener_re = re.compile(
    r"(?:(?<=त्)|(?<=द्)|(?<=म्)|(?<=न्)|(?<=ः))"
    r"(तस्मा[त्द्ल]|ततः|ततो|तस्य|तत्|तद्|तेन|सो|सः|स\s|सा\s|ताः?\s|तयोः|ते\s|"
    r"अथ|अथो|एषा|एषो|एष\s|एतत्|एतद्|एते|न\s+वै|यत्|यद्|यः|यो\s|या\s|ये\s|"
    r"प्रजापति|देवाः|अग्नि|इन्द्र|सोम|वायु|वरुण|मित्र|बृहस्पति|रुद्र|विष्णु|सविता|"
    r"गायत्री|त्रिष्टुप्|जगती|पङ्क्ति|विराट्|अष्ट|चतस्र|पञ्च|त्रीणि|द्वे|एक|"
    r"प्राची|दक्षिणा|प्रतीची|उदीची|छन्दाँसि|रक्षाँसि|गन्धर्वा|पशव|यज्ञ|ब्रह्म|क्षत्र|"
    r"चक्षुर्वाव|ज्योतिरेव|ब्रह्माजुहोत्|सत्यमजुहोत्|अमुमेव|एष\s+ह्येव|वाग्वै|श्वेत|कृष्ण|आग्नेय|ऐन्द्राग्न|सौम्य|वैश्वदेव)"
  )
  # Match all candidate positions in order of `pos_b`
  cand_cuts: dict[int, str] = {}
  for m in fused_opener_re.finditer(bare_s):
    cand_cuts[m.start()] = "direct"
  # Also collect every whitespace boundary `pos_b` (start of next token after space)
  for m in re.finditer(r"\s+(?=\S)", bare_s):
    pos = m.end()
    if pos not in cand_cuts:
      cand_cuts[pos] = "space"
  # Also catch unmistakable havir-vidhi `दक्षिणा + आ/ऐ` vowel sandhi (`दक्षिणाग्नावैष्णव` -> `दक्षिणा | आग्नावैष्णव`,
  # `दक्षिणाग्नीषोमीय`, `दक्षिणाग्नेयो`, `दक्षिणैन्द्राग्न`) and `अपिदधात्यादित्येभ्यो` (`अपिदधाति | आदित्येभ्यो`)!
  for m in re.finditer(r"दक्षिण(ा(?=ग्नावैष्णव|ग्नीषोमीय|ग्नेय|दित्य)|ै(?=न्द्राग्न))", bare_s):
    matra_pos = m.start(1)
    rv = "आ" if bare_s[matra_pos] == "ा" else "ऐ"
    cand_cuts[matra_pos] = f"vsandhi_daksina:{rv}"

  cut_specs: list[tuple[int, str]] = []
  last_cut_b = 0

  for pos_b in sorted(cand_cuts):
    kind = cand_cuts[pos_b]
    if pos_b - last_cut_b < 12:
      continue
    if len(bare_s) - pos_b < 8:
      continue

    left_slice = bare_s[last_cut_b:pos_b].strip()
    right_slice = bare_s[pos_b:].strip()
    left_ws = norm_words(left_slice)
    right_ws = norm_words(right_slice[:80])
    if len(left_ws) < 2 or len(right_ws) < 2:
      continue

    if kind.startswith("vsandhi_daksina:"):
      cut_specs.append((pos_b, kind))
      last_cut_b = pos_b
      continue

    nxt_w = right_ws[0]
    # Never cut right before `इति`/particles/enclitics or dative of purpose (`शान्त्यै`, `समृद्ध्यै`, `प्रतिष्ठित्यै`, `अनुद्दाहाय`)!
    if nxt_w in _NO_CUT_NEXT_WORDS or right_slice.startswith(("इति", "इत्य")):
      continue
    if nxt_w.endswith(("त्यै", "द्ध्यै", "ष्ट्यै", "धृत्यै", "प्त्यै", "हाय")) and len(nxt_w) >= 5:
      continue

    # Test 1 guard: If current sentence opened a relative (`यत्`/`यः`/`या`/`ये`/`यत्र`/`यदा`/`यदि`/`यथा`)
    # without a correlative yet, NEVER split right before its answering `तत्`/`तेन`/`तस्मात्`/`तस्य`/`सः`/`ताः`!
    left_has_open_rel = (
      _starts_with_relative(left_slice)
      or left_ws[0].startswith(("यत्", "यद्", "यल्"))
      or any(w in _RELATIVE_OPENERS or w.startswith(("यत्", "यद्", "यल्")) for w in left_ws[-4:])
    )
    if left_has_open_rel and not _has_correlative(left_slice):
      if nxt_w in _CORRELATIVE_WORDS or nxt_w.startswith(("तत्", "तद्", "तेन", "तस्म", "तस्य", "तत", "स", "सो", "ता")):
        continue

    last_w = left_ws[-1]
    # Never split mid-quote after a 1st/2nd-person mantra verb (`क्रीणामि`, `असि`, `जपामि`, `ददामि`, `अस्मि`)
    # when an `इति` quote (`इति`, `-ेति`, `-ीति`, `-ेत्य्`, `-ीत्य्`) closes soon!
    if last_w.endswith(("ामि", "ेमि", "ोमि", "असि", "अस्मि", "स्मि", "स्व", "ध्वम्")):
      look_q = norm_words(bare_s[pos_b : min(len(bare_s), pos_b + 90)])[:8]
      if any(w == "इति" or w.endswith(("इति", "ेति", "ीति")) or "इति" in w or "ेत्य" in w or "ीत्य" in w for w in look_q):
        continue

    prev_is_verb = _is_finite_verb_word(last_w, lex) or last_w.endswith((
      "आसीत्", "असृज्यत", "उदद्रवत्", "अपामृष्ट", "न्यमार्ट्", "अजायत", "पच्यते", "पच्यन्ते",
      "प्राद्रवत्", "अजुहोत्", "ऐट्ट", "भवति", "भवन्ति", "हूयते", "हूयन्ते", "भवतः", "भवेत्",
      "आस्ताम्", "असृज्येताम्", "विवासयति", "रमयति", "उच्यते", "अस्ति", "सन्ति", "स्यात्", "स्युः",
      "अभवत्", "अभवन्", "आह", "आहुः", "करोति", "कुर्वन्ति", "कुर्यात्", "कुरुते", "दधाति",
      "जुहोति", "जुहुयात्", "एति", "यन्ति", "वेद", "गच्छति", "मार्ट्", "मृष्ट", "अयाट्",
      "सृज्यत", "द्रवत्", "जायत", "जुहोत्", "सृज्येताम्", "सृज्येतां", "आस्तां",
      "अवरुन्द्धे", "अवरुन्धे", "अवारुन्द्ध", "प्रचरन्ति", "प्रचरति", "आलभेत", "आलभते",
      "उपदधाति", "अपिदधाति", "प्रतितिष्ठति", "तिष्ठति", "चिनुते", "चिन्वीत", "सन्निवपति",
      "उपवपति", "विमुञ्चति", "क्रीणाति", "क्रीणीयात्", "विक्रीणीते", "प्रोक्षन्ति", "मार्जयन्ते",
      "सम्मार्ष्टि", "संमार्ष्टि", "उपावर्तते", "उपैति", "आप्नोति", "प्राप्नुयात्", "पुष्यति",
      "समर्धयति", "व्यर्धयति", "अभ्यारोहयति", "व्याचष्टे", "अवतिरति", "धत्ते", "क्रियते",
    ))
    prev_is_daksina_end = (kind == "space" and (last_w == "दक्षिणा" or last_w.endswith("दक्षिणा")))
    prev_is_svaha_end = (kind == "space" and (last_w == "स्वाहा" or last_w.endswith("स्वाहा")))
    # For `space`, also allow `...इति` ONLY when `next` is NOT a verb (because `... इति <verb>` stays together!)
    if not (prev_is_verb or prev_is_daksina_end or prev_is_svaha_end):
      continue

    # Test 2 guard: Do NOT cut right after a quote-introducing verb (`जुहोति`, `ब्रूयात्`, `आह`, `उवाच`)
    # if a mantra/quote ending in `स्वाहा` or `इति`/`-ेति`/`-ीति` immediately follows within the next 14 words!
    if last_w in _BRAHMANA_QUOTE_INTRO_VERBS:
      lookahead_ws = norm_words(bare_s[pos_b : min(len(bare_s), pos_b + 140)])[:14]
      if any(w in ("स्वाहा", "इति") or w.endswith(("स्वाहा", "इति", "ेति", "ीति")) or "स्वाहा" in w or "इति" in w or "ेत्य" in w or "ीत्य" in w for w in lookahead_ws):
        continue

    # If `kind == "space"`, avoid splitting a very short verb-initial clause (`उवाच ह सनाच्छव`)
    if kind == "space" and len(left_slice) < 12:
      continue

    cut_specs.append((pos_b, kind))
    last_cut_b = pos_b

  if not cut_specs:
    return [SplitBlock(vp_text=vp_seg, mula_text=mula_seg, is_rk=False, is_brahmana=True)]

  # Slice `vp_seg` and `mula_seg` cleanly at mapped positions (handling `vsandhi_daksina` seamlessly!)
  out: list[SplitBlock] = []
  prev_v = 0
  prev_m = 0
  prepend_v = ""
  prepend_m = ""
  for pos_b, kind in cut_specs:
    oc = b2orig[pos_b]
    m_oc = _map_vp_cut_to_mula(vp_seg, mula_seg, oc)
    if kind.startswith("vsandhi_daksina:"):
      rv = kind.split(":", 1)[1]
      v_piece = (prepend_v + vp_seg[prev_v:oc] + "ा").strip()
      m_piece = (prepend_m + mula_seg[prev_m:m_oc] + "ा").strip()
      # Skip the coalesced matra (`ा` or `ै`) and any accent directly after it on next slice
      nxt_v = oc + 1
      while nxt_v < len(vp_seg) and vp_seg[nxt_v] in (US_UDATTA, US_SVARITA):
        nxt_v += 1
      nxt_m = m_oc + 1
      while nxt_m < len(mula_seg) and mula_seg[nxt_m] in (US_UDATTA, US_SVARITA):
        nxt_m += 1
      prev_v = nxt_v
      prev_m = nxt_m
      prepend_v = rv
      prepend_m = rv
    else:
      v_piece = (prepend_v + vp_seg[prev_v:oc]).strip()
      m_piece = (prepend_m + mula_seg[prev_m:m_oc]).strip()
      prev_v = oc
      prev_m = m_oc
      prepend_v = ""
      prepend_m = ""
    if v_piece and _DEVA_LETTER_RE.search(accent.strip_accents(v_piece)):
      out.append(
        SplitBlock(vp_text=restore_pausa_end(v_piece), mula_text=m_piece or v_piece, is_rk=False, is_brahmana=True)
      )
  tail_v = (prepend_v + vp_seg[prev_v:]).strip()
  tail_m = (prepend_m + mula_seg[prev_m:]).strip()
  if tail_v and _DEVA_LETTER_RE.search(accent.strip_accents(tail_v)):
    out.append(
      SplitBlock(vp_text=restore_pausa_end(tail_v), mula_text=tail_m or tail_v, is_rk=False, is_brahmana=True)
    )
  return out or [SplitBlock(vp_text=vp_seg, mula_text=mula_seg, is_rk=False, is_brahmana=True)]


# ---------------------------------------------------------------------------
# Public Top-Level Anuvāka Splitters (MS & KS)
# ---------------------------------------------------------------------------

def split_ms_anuvaka(
  anu: MsAnuvakaSource,
  ref_index: VedicReferenceIndex,
  *,
  cursors: dict[str, int] | None = None,
) -> list[SplitBlock]:
  """Split one MS anuvāka into distinct yajuṣes, ṛks (merged unless viniyoga-split), or Brāhmaṇa units."""
  full_txt = " ".join(anu.clean_lines)
  if classify_is_brahmana(full_txt):
    return split_ms_brahmana_anuvaka(anu)

  cur = cursors if cursors is not None else {}
  raw_blocks: list[SplitBlock] = []
  for raw_ln, clean_ln in zip(anu.raw_lines, anu.clean_lines):
    # Strip trailing `॥` for atomic processing (will render clean punctuation later)
    vp_clean = strip_ms_quote_backslashes(clean_ln)
    vp_clean = re.sub(r"\s*[।॥]+\s*$", "", vp_clean).strip()
    mula_clean = re.sub(r"\s*[।॥]+\s*$", "", raw_ln.strip()).strip()
    if not vp_clean:
      continue
    sub = _split_fused_mantra_chunk(
      vp_clean, mula_clean, ref_index, corpus="MS", cursors=cur, allow_interior_ref_splits=True
    )
    raw_blocks.extend(sub)

  return _merge_rk_blocks(raw_blocks, ref_index)


def split_ks_anuvaka(
  anu: KsAnuvakaSource,
  ref_index: VedicReferenceIndex,
  *,
  lex: UnifiedVedicLexicon | None = None,
  cursors: dict[str, int] | None = None,
) -> list[SplitBlock]:
  """Split one KS anuvāka into distinct yajuṣes, ṛks (honoring bold + viniyogas), or Brāhmaṇa units."""
  full_vp = " ".join(p.repaired_vp for p in anu.pieces)
  is_brahmana = classify_is_brahmana(full_vp)
  cur = cursors if cursors is not None else {}
  raw_blocks: list[SplitBlock] = []

  for piece in anu.pieces:
    if piece.is_bold_rk:
      # Bold piece in Schroeder: usually 1 or more metrical ṛks (occasionally a preceding yajuṣ + `॥` + ṛk!)
      vp_parts = [s.strip() for s in re.split(r"॥+\s*(?:[०-९0-9]+\s*॥*)?", piece.repaired_vp) if s.strip()]
      mula_parts = [s.strip() for s in re.split(r"॥+\s*(?:[०-९0-9]+\s*॥*)?", piece.raw_mula) if s.strip()]
      if len(vp_parts) != len(mula_parts):
        mula_parts = list(vp_parts)
      for idx_p, (vp_p, mu_p) in enumerate(zip(vp_parts, mula_parts)):
        vp_p = re.sub(r"^[\u1cd3\u1cd9\s]+", "", vp_p)
        mu_p = re.sub(r"^[\u1cd3\u1cd9\s]+", "", mu_p)
        if not _DEVA_LETTER_RE.search(accent.strip_accents(vp_p)):
          continue
        # Check if this bold block is a single ṛk (keep line breaks) OR has distinct viniyogas inside it
        vp_lines = [ln.strip() for ln in vp_p.splitlines() if ln.strip()]
        mu_lines = [ln.strip() for ln in mu_p.splitlines() if ln.strip()]
        if len(vp_lines) >= 2:
          # Inside a Schroeder `**bold**` ṛk, ONLY split line 1 vs line 2 if BOTH lines have their OWN distinct
          # viniyogas where line 2's pratīka genuinely BEGINS with line 2 (not the tail of a full-verse quote!)
          l1_sk = skeleton_key(vp_lines[0])
          l2_sk = skeleton_key(vp_lines[1])
          l1_vins = ref_index.match_viniyogas_at(
            l1_sk, norm_words(vp_lines[0]), corpus="KS",
            cursor_mss=cur.get("mss"), cursor_vss=cur.get("vss"), cursor_ksb=cur.get("ksb"),
          )
          l2_vins = ref_index.match_viniyogas_at(
            l2_sk, norm_words(vp_lines[1]), corpus="KS",
            cursor_mss=cur.get("mss"), cursor_vss=cur.get("vss"), cursor_ksb=cur.get("ksb"),
            preceding_skel=l1_sk,
          )
          l1_refs = {(v.source, v.ref) for v in l1_vins}
          # True distinct half-verse viniyoga: line 2's pratīka itself starts with line 2's opening!
          fresh_l2 = [
            v for v in l2_vins
            if (v.source, v.ref) not in l1_refs
            and v.pratika_skeleton.startswith(l2_sk[: min(8, len(l2_sk))])
          ]
          if l1_vins and fresh_l2 and len(vp_lines) == 2 and len(mu_lines) == 2:
            raw_blocks.append(SplitBlock(vp_text=vp_lines[0], mula_text=mu_lines[0], is_rk=True, viniyogas=l1_vins, footnote_ids=list(piece.footnote_ids) if idx_p == 0 else []))
            raw_blocks.append(SplitBlock(vp_text=vp_lines[1], mula_text=mu_lines[1], is_rk=True, viniyogas=fresh_l2))
            continue
          par = ref_index.find_best_parallel_mantra(" ".join(vp_lines), prefer_sources=("MS", "TS", "RV", "VS-M", "VS-K"), min_overlap=0.60)
          raw_blocks.append(
            SplitBlock(
              vp_text="  \n".join(vp_lines),
              mula_text="  \n".join(mu_lines),
              is_rk=True,
              viniyogas=l1_vins,
              parallel_ref=par[0] if par else None,
              footnote_ids=list(piece.footnote_ids) if idx_p == 0 else [],
            )
          )
        else:
          # Single-line bold part (like KS 1.3 `वसोः पवित्रमसि शतधारं वसूनां पवित्रमसि सहस्रधारम्`): run mantra splitter!
          sub = _split_fused_mantra_chunk(vp_p, mu_p, ref_index, corpus="KS", cursors=cur, allow_interior_ref_splits=True)
          if sub and idx_p == 0:
            sub[0].footnote_ids.extend(piece.footnote_ids)
          raw_blocks.extend(sub)
      continue

    if is_brahmana:
      sub_b = split_ks_brahmana_paragraph(piece.repaired_vp, piece.raw_mula, lex)
      if sub_b:
        sub_b[0].footnote_ids.extend(piece.footnote_ids)
      raw_blocks.extend(sub_b)
      continue

    # Non-bold mantra paragraph: split on `॥` first, then run fused mantra splitter on each chunk!
    # Handle leading `ओम्॥` cleanly
    vp_chunks = [s.strip() for s in re.split(r"॥+\s*(?:[०-९0-9]+\s*॥*)?", piece.repaired_vp) if s.strip()]
    mu_chunks = [s.strip() for s in re.split(r"॥+\s*(?:[०-९0-9]+\s*॥*)?", piece.raw_mula) if s.strip()]
    if len(vp_chunks) != len(mu_chunks):
      mu_chunks = list(vp_chunks)

    first_emitted = False
    for vc, mc in zip(vp_chunks, mu_chunks):
      if normalize_for_matching(vc) == "ओम्":
        blk = SplitBlock(vp_text=vc, mula_text=mc, is_rk=False, footnote_ids=list(piece.footnote_ids) if not first_emitted else [])
        raw_blocks.append(blk)
        first_emitted = True
        continue
      sub = _split_fused_mantra_chunk(vc, mc, ref_index, corpus="KS", cursors=cur, allow_interior_ref_splits=True, lex=lex)
      if sub and not first_emitted:
        sub[0].footnote_ids.extend(piece.footnote_ids)
        first_emitted = True
      raw_blocks.extend(sub)

  if is_brahmana:
    return raw_blocks
  return _merge_rk_blocks(raw_blocks, ref_index)
