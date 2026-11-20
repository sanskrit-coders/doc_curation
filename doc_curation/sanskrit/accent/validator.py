"""Validators for US/classical Vedic accent notation, ``पद-पाठः (यान्त्रिकः)`` blocks, and ``विश्वास-प्रस्तुतिः`` integrity."""

from __future__ import annotations

import dataclasses
import functools
import re
from typing import AbstractSet, Sequence

from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.accent.reconciler import (
  DETAILS_RE,
  PP_HEADER_RE,
  bare_devanagari,
  find_js_include_spans,
  has_us_accents,
  parse_padapatha_items,
  syllables_with_marks,
)

SCHEME = sanscript.SCHEMES[sanscript.DEVANAGARI]
LINE_BREAK_PAUSES = r"[।॥,;]+"

VALID_ANUDATTA_RULE_TAGS: tuple[str, ...] = (
  "८.१.२८",
  "८.१.१८",
  "८.१.१९",
  "८.१.२०",
  "८.१.२१",
  "८.१.२२",
  "८.१.२३",
  "८.१.३",
  "८.१.७०",
  "८.१.७१",
  "२.४.३२",
  "२.४.३४",
  "६.१.१९१",
  "सर्वस्य सुपि",
  "सर्वानुदात्त",
  "स्वरव्यत्यय",
)

UPASARGA_PREFIXES: tuple[str, ...] = (
  # Base upasargas
  "परा",
  "अप",
  "सम्",
  "सं",
  "अनु",
  "अव",
  "निस्",
  "निर्",
  "दुस्",
  "दुर्",
  "अधि",
  "अपि",
  "अति",
  "उत्",
  "उद्",
  "अभि",
  "प्रति",
  "परि",
  "उप",
  "प्र",
  "सु",
  "नि",
  "वि",
  "आ",
  # Prevocalic consonant-final upasargas (सम्, उद्, निर्, दुर् + vowel)
  "सम",
  "समा",
  "समि",
  "समी",
  "समु",
  "समू",
  "समृ",
  "समे",
  "समै",
  "समो",
  "उद",
  "उदा",
  "उदि",
  "उदी",
  "उदु",
  "उदे",
  "उदै",
  "निर",
  "निरा",
  "निरि",
  "निरु",
  "निरे",
  "दुर",
  "दुरा",
  "दुरु",
  # Parasavarṇa-assimilated upasargas
  "सँ",
  "सङ्",
  "सञ्",
  "सण्",
  "सन्",
  "सम्ब",
  "सम्भ",
  "सम्म",
  "उच्च",
  "उच्छ",
  "उज्ज",
  "उड्ड",
  "उत्त",
  "उन्न",
  "उल्ल",
  "निष",
  "निश्",
  "निः",
  "दुष",
  "दुश्",
  "दुः",
  # Yaṇ-coalesced upasargas
  "अन्व",
  "अन्वा",
  "अन्वि",
  "अन्वी",
  "अन्वे",
  "अध्य",
  "अध्या",
  "अध्यु",
  "अध्ये",
  "अप्य",
  "अत्य",
  "अत्या",
  "अभ्य",
  "अभ्या",
  "अभ्यु",
  "अभ्ये",
  "प्रत्य",
  "प्रत्या",
  "प्रत्यु",
  "पर्य",
  "पर्या",
  "पर्यु",
  "न्य",
  "न्या",
  "न्यु",
  "व्य",
  "व्या",
  "व्यु",
  "व्यू",
  "व्ये",
  # Guṇa / vṛddhi / savarṇadīrgha coalesced upasargas
  "प्रे",
  "प्रै",
  "प्रो",
  "परे",
  "परै",
  "अपे",
  "अपै",
  "अवे",
  "अवै",
  "उपे",
  "उपै",
  "अधी",
  "अती",
  "अभी",
  "प्रती",
  "परी",
)

SIMPLEX_TINANTA_ALLOWLIST: frozenset[str] = frozenset({
  "विक्थाः",
  "आजन्त",
  "विद्युः",
  "विद्रे",
  "विजते",
  "सुवाति",
  "सुवासि",
  "सुवानि",
  "सुवति",
  "सुवन्ति",
  "सुवतु",
  "सुवन्तु",
  "सुवताम्",
  "अभवत्",
  "अभिनत्",
  "अभूत्",
  "अभुवन्",
  "अब्रुवन्",
  "अवर्तत",
  "अशृणवत्",
  "अपश्यत्",
  "अपृणात्",
  "अप्राः",
  "अवसन्",
  "अवहन्",
  "अवयन्",
  "अवाक्षुः",
  "आशत",
  "अवित्सि",
  "अविन्दन्",
  "अवृणोत्",
  "अवृञ्जन्",
  "असृजत",
  "अजायत",
  "अतिष्ठत्",
  "अतिरम्",
  "असन्",
  "असि",
  "अस्मि",
  "अस्ति",
  "अस्तु",
  "अगात्",
  "अगन्",
  "अद्मि",
  "आद्मि",
  "आदयत",
  "आर्त",
  "अवतु",
  "अवन्तु",
  "अवतात्",
  "अवमीत्",
  "अव्यथन्",
  "आः",
  "आवाः",
  "आसीत्",
  "आसीत",
  "आध्वम्",
  "आसते",
  "आसन्",
  "आस्ते",
  "आसताम्",
  "आहुः",
  "आनशुः",
  "आनट्",
  "आरत्",
  "आप्नोति",
  "आप्नुयात्",
  "आप्नुवन्ति",
  "आपन्",
  "आशयामि",
  "विद्यते",
  "विद्धि",
  "विविदे",
  "विविच्यन्ते",
  "विदध्मसि",
  "विद्म",
  "विद्मः",
  "विद्महे",
  "विद्यात्",
  "विदुः",
  "विन्दते",
  "विन्दस्व",
  "विवेश",
  "विशति",
  "विशते",
  "विशन्ति",
  "विशन्तु",
  "विशतात्",
  "विशामि",
  "विशेत्",
  "प्रीणाति",
  "सुव",
  "सुवति",
  "सुवतु",
  "निनीयात्",
  "निन्युः",
  "अवृत्रन्",
  "अवादिषुः",
  "अवीवृतत्",
  "आपाम",
  "आराम",
  "आमयति",
  "आक्षि",
  "अपात्",
  "अपातम्",
  "आरुक्त",
  "आममत्",
  "अविन्दत्",
  "अवथः",
  "वित्सि",
  "विवित्से",
  "अवदत्",
  "विधेम",
  "विशस्व",
  "विशताम्",
  "विद्ध्यामि",
  "अवादिषम्",
  "आवीत्",
  "आसीः",
  "अपश्यन्",
  "अव्यात्",
  "अपप्तत्",
  "सुवामसि",
  "सुवामि",
  "सन्तु",
  "सन्ति",
  "स्यन्दन्ते",
  "व्यथते",
  "व्यथः",
  "व्ययन्तु",
  "व्ययस्व",
  "उच्छन्तु",
  "उच्छतु",
  "ऐच्छम्",
  "अनुष्व",
  "वीरयध्वम्",
  "वीहि",
  "नीयते",
  "एति",
  "एधि",
  "सुवः",
  "अवीः",
  "ऐत्",
  "आयन्",
  "आस्यत्",
  "सुषुप्थाः",
  "अविदत्",
  "अविदम्",
  "विदन्",
  "अपतत्",
  "आपयेत्",
  "आपयति",
  "आपयन्ति",
  "आपयते",
  "आप्नुयाम्",
  "आप्नुयाम",
  "आप्नुहि",
  "आप्नुवते",
  "आशयति",
  "आशति",
  "आह",
  "आहुः",
  "आहतुः",
  "आत्थ",
  "आस",
  "आसुः",
  "आसन्",
  "आसीत्",
  "आसीः",
  "आसम्",
  "आस्थ",
  "आस्म",
  "आस्ताम्",
  "आस्",
  "आस्ते",
  "आसते",
  "आसाते",
  "आप",
  "आपुः",
  "आप्नोति",
  "आप्नुवन्ति",
  "आप्नोत्",
  "आर",
  "आरुः",
  "आन",
  "आट्",
  "आनशुः",
  "आनृचुः",
  "आदत्",
  "आदन्",
  "आर्चत्",
  "आर्ध्नोत्",
  "आर्षीत्",
  "आसतुः",
  "आवम्",
  "अवृणीत",
  "अवृणीध्वम्",
  "सुस्राव",
  "विनक्ति",
  "विनक्तु",
  "विच्यते",
  "प्रथस्व",
  "प्रथताम्",
  "विन्दति",
  "वेद",
  "विदुः",
  "विद्म",
  "विद्मसि",
  "विदथ",
  "विदतुः",
  "विदः",
  "विदत्",
  "विदते",
  "विदन्ते",
  "विदे",
  "विदेत",
  "विदेरन्",
  "विद्यात्",
  "विद्याताम्",
  "विद्युः",
  "विद्याम्",
  "विद्याम",
  "वेत्ति",
  "विदन्ति",
  "विद्धि",
  "वेत्तु",
  "विदन्तु",
  "अवेत्",
  "अविदन्",
  "विशति",
  "विशतः",
  "विशन्ति",
  "विशसि",
  "विशथ",
  "विशामि",
  "विशामः",
  "विशते",
  "विशन्ते",
  "विशतु",
  "विशतात्",
  "विशन्तु",
  "विशस्व",
  "विशन्ताम्",
  "विशेयुः",
  "विशेत",
  "विशेरन्",
  "अविशत्",
  "अविशन्",
  "विवेश",
  "विविशुः",
  "विविशे",
  "विविशिरे",
  "आस्से",
  "आसध्वम्",
  "आसे",
  "आस्महे",
  "आसताम्",
  "आस्व",
  "आसत",
  "आसीरन्",
  "आस्त",
  "आसिथ",
  "आसथुः",
  "आसिम",
  "आप्नुतः",
  "आप्नोषि",
  "आप्नोमि",
  "आप्नुमः",
  "आप्नुवन्",
  "आप्नोतु",
  "आप्नुवन्तु",
  "आप्नुयात्",
  "आप्नुयुः",
  "आपतुः",
  "आप्स्यति",
  "आप्स्यन्ति",
  "अवति",
  "अवतः",
  "अवन्ति",
  "अवसि",
  "अवथ",
  "अवामि",
  "अवामः",
  "अवतात्",
  "अवतु",
  "अवताम्",
  "अवन्तु",
  "अवेयुः",
  "आवत्",
  "आवन्",
  "आव",
  "आवतुः",
  "आवुः",
  "आवीत्",
  "आविषुः",
  "सूते",
  "सूवते",
  "सुवति",
  "सुवतः",
  "सुवन्ते",
  "सुवतु",
  "सुवतात्",
  "सुवन्तु",
  "सुवस्व",
  "सुवताम्",
  "सुवेत्",
  "सूत",
  "सौति",
  "असौषीत्",
  "सोष्यति",
  "सोष्यते",
  "अवधीत्",
  "अवधीः",
  "अवधीम्",
  "अवधिषुः",
  "अवधिष्ट",
  "आद",
  "आदुः",
  "आजत्",
  "आजन्",
  "आजत",
  "आजन्त",
  "आर्चन्",
  "आनर्च",
  "आर्ध्नुवन्",
  "आरतुः",
  "आयम्",
  "ऐताम्",
  "विजते",
  "विजन्ते",
  "विजेत",
  "अतिष्ठत्",
  "अतिष्ठन्",
  "अतिष्ठताम्",
  "अप्रीणात्",
  "अप्रीणन्",
  "आशयात्",
  "अवृज्यत",
  "अपद्यत",
  "निन्ये",
  "अपादयत",
  "अपादयत्",
  "अपादयन्",
  "अवपत्",
  "अवपन्",
  "अवपत",
  "अवपन्त",
  "उद्यते",
  "उद्यन्ते",
  "अप्रथयत्",
  "अप्रथयन्",
  "अप्रथत",
  "अविशन्त",
  "अपादि",
  "व्ययामसि",
  "प्रैषम्",
  "वित्ते",
  "विदते",
  "अपाः",
  "अवात्",
  "अपूयत्",
  "निनाय",
  "विवासन्ति",
  "अवृहन्",
  "वित्तात्",
  "विवेद",
  "विदति",
  "विध्यति",
  "सुनोति",
  "सुन्वन्ति",
  "सुवते",
  "सुवन्ति",
  "प्रथते",
  "प्रथयति",
  "अधिषि",
  "व्यन्तु",
  "अविषः",
  "अव्लीनात्",
  "अपिक्षन्",
  "आवीः",
  "विदेयम्",
  "अक्रुक्षः",
  "अशकः",
  "अविदुः",
  "आप्सीत्",
  "अवृञ्जन्त",
  "सुवान्",
  "सुवध्वम्",
  "सुवान्तै",
  "अपद्महि",
  "आक्षीः",
  "प्राक्षीः",
  "अप्राक्षीः",
  "अदिदीक्षः",
  "अवसाम",
  "सुवात्",
})


@functools.lru_cache(maxsize=4096)
def _is_vidyut_simplex_tinanta(bare: str) -> bool:
  """Return True if ``vidyut.kosha`` parses ``bare`` as an unprefixed (simplex) ``Tinanta``."""
  if not bare or "-" in bare or bare == "अविशताम्":
    return False
  try:
    from doc_curation.sanskrit.accent.shatapatha_solver import get_vidyut_kosha

    kosha = get_vidyut_kosha()
    if kosha is None:
      return False
    slp = sanscript.transliterate(bare, sanscript.DEVANAGARI, sanscript.SLP1)
    for ent in kosha.get(slp):
      if type(ent).__name__.endswith("Tinanta"):
        dhatu = getattr(getattr(ent, "dhatu_entry", None), "dhatu", None)
        if dhatu is not None and not getattr(dhatu, "prefixes", None):
          return True
  except Exception:  # noqa: BLE001
    return False
  return False

_GATI_HYPHEN_PREFIXES: frozenset[str] = frozenset({
  "प्र", "परा", "अप", "सम्", "सं", "सँ", "सङ्", "सञ्", "सण्", "सन्",
  "अनु", "अव", "निस्", "निर्", "निः", "निष्", "निश्",
  "दुस्", "दुर्", "दुः", "दुष्", "दुश्",
  "वि", "आ", "नि", "अधि", "अपि", "अति", "सु",
  "उत्", "उद्", "उच्", "उज्", "उन्", "उल्",
  "अभि", "प्रति", "परि", "उप",
})

DEFAULT_VERIFIED_AA_HIATUSES: frozenset[tuple[str, str]] = frozenset({
  ("सप्त", "इमे"),
  ("शता", "अस्य"),
  ("अमुष्य", "ओम्"),
  ("ता", "अतुर्यथुः"),
  ("ता", "अविसृष्टौ"),
  ("सरमा", "इति"),
  ("च", "उग्रात्"),
  ("वह्नि-शिखा", "अणीयस्-ऊर्ध्वा"),
  ("ऊत", "एकम्"),
  ("इन्द्रियाय", "ऋषिभ्यः"),
  ("सम्मा", "असि"),
  ("उन्मा", "असि"),
  ("विश्व-वार", "उप"),
  ("विश्व-वार", "उपो"),
  ("स्याम", "उपयामगृहीतः"),
  ("स्याम", "उपयाम-गृहीतः"),
  ("स्थ", "अप्सु-क्षितः"),
  ("स्थ", "अप्सुक्षितः"),
  ("विश्वस्य", "अ-रिष्ट्यै"),
  ("विश्वस्य", "अरिष्ट्यै"),
  ("सदना", "अकर्म"),
  ("च", "इन्द्राय"),
  ("घोर", "आसन्"),
  ("विदित", "आ-मन्त्रितः"),
  ("विदित", "आमन्त्रितः"),
  ("राजा", "इति"),
  ("राजा ३", "इति"),
  ("द्रवन्ता", "आ"),
  ("संवत्सर", "आस"),
  ("आसिथ", "उप"),
  ("भव", "आत्मा"),
  ("अधूषत", "अस्तोषत"),
})


@dataclasses.dataclass(frozen=True)
class AccentValidationIssue:
  """One integrity failure detected inside an accented Markdown block or file."""

  kind: str
  message: str
  line: str = ""


def has_post_udatta_svarita_in_mula(
  mula_clean: str,
  target_word_bare: str,
  *,
  pauses: str = LINE_BREAK_PAUSES,
) -> bool:
  """Return True if classical ``॑`` directly follows an udātta on ``target_word_bare`` (ambiguous dependent/independent svarita)."""
  pauses_re = re.compile(pauses)
  us = accent.to_US_accents(mula_clean, pauses=pauses)
  raw_syls = SCHEME.split_vyanjanas_and_svaras(mula_clean, skip_pattern=r"\+\+\+(?:.+?)\+\+\+")
  us_syls = SCHEME.split_vyanjanas_and_svaras(us, skip_pattern=r"\+\+\+(?:.+?)\+\+\+")
  if len(raw_syls) != len(us_syls):
    return False
  for idx, syl in enumerate(raw_syls):
    if "\u0951" in syl and "\u0952" not in syl and "᳙" not in syl:
      prev_i = SCHEME.get_adjacent_syllable_index(idx, raw_syls, -1, pauses_pattern=pauses_re)
      if prev_i is not None and "᳓" in us_syls[prev_i] and "᳙" not in us_syls[idx]:
        ws = idx
        while ws > 0 and not raw_syls[ws - 1].isspace() and not pauses_re.fullmatch(raw_syls[ws - 1]):
          ws -= 1
        we = idx + 1
        while we < len(raw_syls) and not raw_syls[we].isspace() and not pauses_re.fullmatch(raw_syls[we]):
          we += 1
        w_bare = accent.strip_accents(SCHEME.join_strings(raw_syls[ws:we]))
        if target_word_bare in w_bare:
          return True
  return False


def check_padapatha_header(header: str, pp_body: str) -> AccentValidationIssue | None:
  """Verify that the ``N/P व्यत्यस्त-स्वराः`` count in ``header`` matches bullet items in ``pp_body``."""
  lines = [ln.strip() for ln in pp_body.splitlines() if ln.strip().startswith("- ")]
  n_arrows = sum(1 for ln in lines if "→ **" in ln)
  p_total = len(lines)
  m_hdr = PP_HEADER_RE.match(header.strip())
  if not m_hdr:
    return AccentValidationIssue("header_mismatch", f"Malformed header {header!r} (expected N={n_arrows}, P={p_total})")
  n_h = int(m_hdr.group(1)) if m_hdr.group(1) else 0
  p_h = int(m_hdr.group(2)) if m_hdr.group(2) else None
  if n_h != n_arrows or (p_h is not None and p_h != p_total) or (n_arrows > 0 and p_h is None) or (n_arrows == 0 and p_h is not None):
    return AccentValidationIssue("header_mismatch", f"Header {header!r} != actual {n_arrows}/{p_total}")
  return None


def find_virama_matra_glitches(pp_lines: Sequence[str]) -> list[str]:
  """Return padapāṭha bullet lines containing stray ``्`` + vowel-sign/anusvāra or stray ``+``/``,`` artifacts."""
  hits: list[str] = []
  for ln in pp_lines:
    head = ln.split("(", 1)[0]
    if re.search(r"्[ा-ौःंँ]", ln.replace("्ँ", "")) or "+" in head or "," in head:
      hits.append(ln)
  return hits


def find_false_post_udatta_svarita_arrows(
  pp_lines: Sequence[str],
  mula_clean: str,
  *,
  pauses: str = LINE_BREAK_PAUSES,
) -> list[str]:
  """Return padapāṭha ``X → **X᳙**`` arrows where classical ``मूलम्`` places ``॑`` right after an udātta."""
  if not mula_clean:
    return []
  hits: list[str] = []
  for ln in pp_lines:
    m_ar = re.match(r"^- ([^→\n]+?)\s*→\s*\*\*([^*]+)\*\*", ln)
    if m_ar and "᳙" in m_ar.group(2) and "᳙" not in m_ar.group(1):
      ar_clean = m_ar.group(1).strip().replace("-", "")
      ref_without_svarita = m_ar.group(2).strip().replace("᳙", "").replace("-", "")
      if ar_clean == ref_without_svarita:
        w_bare = accent.strip_accents(m_ar.group(2)).replace("-", "")
        if has_post_udatta_svarita_in_mula(mula_clean, w_bare, pauses=pauses):
          hits.append(ln)
  return hits


def find_unexplained_aa_hiatuses(
  pp_lines: Sequence[str],
  mula_clean: str,
  *,
  verified_prakrtibhava_pairs: AbstractSet[tuple[str, str]] | None = None,
) -> list[tuple[str, str, str]]:
  """Return adjacent ``-अ/-आ`` + vowel padapāṭha pairs appearing uncoalesced in ``mula_clean`` without daṇḍa."""
  if not mula_clean:
    return []
  allow = DEFAULT_VERIFIED_AA_HIATUSES if verified_prakrtibhava_pairs is None else verified_prakrtibhava_pairs
  padas: list[str] = []
  for ln in pp_lines:
    body_l = ln[2:].strip() if ln.startswith("- ") else ln.strip()
    m_ar = re.match(r"^([^→\n]+?)\s*→\s*\*\*([^*]+)\*\*", body_l)
    if m_ar and m_ar.group(2).strip() != "?":
      padas.append(accent.strip_accents(m_ar.group(2).strip()))
    else:
      padas.append(accent.strip_accents(body_l.split()[0].strip("*.,")))

  flat_mula = re.sub(r"\+\+\+\([^)]*\)\+\+\+", "", mula_clean)
  flat_mula = re.sub(r"\n\s*\n", " । ", flat_mula)
  mula_joined_bare = accent.strip_accents(re.sub(r"\s+", " ", flat_mula).strip())
  hits: list[tuple[str, str, str]] = []
  for pi in range(len(padas) - 1):
    w1, w2 = padas[pi], padas[pi + 1]
    if (w1, w2) in allow:
      continue
    s1 = sanscript.transliterate(w1.replace("-", ""), sanscript.DEVANAGARI, sanscript.SLP1)
    s2 = sanscript.transliterate(w2.replace("-", ""), sanscript.DEVANAGARI, sanscript.SLP1)
    if s1 and s2 and s1[-1] in ("a", "A") and s2[0] in ("a", "A", "i", "I", "u", "U", "e", "E", "o", "O"):
      w1_c = w1.replace("-", "")
      w2_c = w2.replace("-", "")
      pat = rf"(?:^|[\s।॥,\-]){re.escape(w1_c)}\s+{re.escape(w2_c[:2])}"
      m_unm = re.search(pat, mula_joined_bare)
      if m_unm and not any(d in mula_joined_bare[m_unm.start():m_unm.end()] for d in "।॥;"):
        # Avoid false positives when a separate `वै` + vowel pair (पा॰ ८.३.१९ -> `वा V`) produces the matched
        # substring while the queried `वा` + `आ...` pair itself appears coalesced (e.g. `स वा आरण्यम्` vs `या वारण्या`).
        if w1_c == "वा" and w2_c.startswith("आ") and ("वा" + w2_c[1:4]) in mula_joined_bare:
          if any(padas[k] == "वै" and k + 1 < len(padas) and padas[k + 1].replace("-", "").startswith(w2_c[:2]) for k in range(len(padas))):
            continue
        hits.append((w1, w2, mula_joined_bare[m_unm.start():m_unm.end()]))
  return hits


def find_unresolved_question_arrows(pp_lines: Sequence[str]) -> list[str]:
  """Return padapāṭha bullet lines with an unresolved ``→ **?**`` placeholder."""
  hits: list[str] = []
  for ln in pp_lines:
    it_list = parse_padapatha_items(ln)
    if it_list and "?" in it_list[0].ref:
      hits.append(ln)
  return hits


_FORBIDDEN_ACCENT_SOURCE_RE = re.compile(r"\*(?:TA|EK)\*(?:-\d+)?")


def find_forbidden_accent_sources(pp_lines: Sequence[str]) -> list[str]:
  """Return padapāṭha bullet lines citing dubious sources (``*TA*`` / ``*EK*``)."""
  hits: list[str] = []
  for ln in pp_lines:
    it_list = parse_padapatha_items(ln)
    target = it_list[0].prov if it_list else ln
    if _FORBIDDEN_ACCENT_SOURCE_RE.search(target):
      hits.append(ln)
  return hits


def find_malformed_arrows(pp_lines: Sequence[str]) -> list[str]:
  """Return padapāṭha bullet lines containing more than one ``→ **...**`` arrow."""
  hits: list[str] = []
  for ln in pp_lines:
    if len(re.findall(r"(?:→|->)\s*\*\*", ln)) > 1:
      hits.append(ln)
  return hits


def find_bad_gati_kta_purvapadas(pp_lines: Sequence[str]) -> list[str]:
  """Return bahuvrīhi / gati-kta compounds placing udātta on ``-त/-न/-ण`` instead of the gati (``पा॰ ६.२.४९ गतिरनन्तरः``)."""
  gati_prefixes = (
    "प्र", "परा", "अप", "सम्", "सङ्", "सं", "सञ्", "सन्", "सँ",
    "अनु", "अव", "निस्", "निर्", "निः", "वि", "आ", "नि",
    "अधि", "अपि", "अति", "उत्", "उद्", "अभि", "प्रति", "परि", "उप",
  )
  kta_stems_re = re.compile(
    r"^(गत|कृत|हत|तत|यत|हित|नत|रत|मत|जित|श्रित|स्थित|भूत|पूत|युक्त|मुक्त|वृत्त|वृत|दत्त|लब्ध|सिद्ध|बुद्ध|शुद्ध|बद्ध|सक्त|क्रान्त|क्लान्त|शान्त|दान्त|भ्रान्त)$"
  )
  hits: list[str] = []
  for ln in pp_lines:
    it_list = parse_padapatha_items(ln)
    if not it_list:
      continue
    it = it_list[0]
    if "?" in it.ref or "-" not in it.ref:
      continue
    # Only check bahuvrīhis retaining pūrvapada prakṛtisvara (पा॰ ६.२.१) or explicit ६.२.४९ compounds
    is_bv_621 = ("६.२.१" in it.prov or "बहुव्री" in it.prov) and not any(
      ap in it.prov for ap in ("६.२.१७२", "६.२.१७७", "६.२.१९९", "५.४.११३", "६.२.१०६", "६.२.११७", "६.२.११९")
    )
    is_6249 = "६.२.४९" in it.prov or "गतिरनन्तरः" in it.prov
    if not (is_bv_621 or is_6249):
      continue
    p0 = it.ref.split("-", 1)[0]
    p0_plain = accent.strip_accents(p0)
    for g in gati_prefixes:
      if p0_plain.startswith(g) and len(p0_plain) > len(g):
        rem = p0_plain[len(g):]
        if kta_stems_re.match(rem):
          _, marks = syllables_with_marks(p0)
          if marks and marks[-1] and not marks[0]:
            hits.append(ln)
          break
  return hits


def find_false_nighata_arrows(
  pp_lines: Sequence[str],
  mula_clean: str = "",
) -> list[str]:
  """Return ``X᳓ → **X**`` nighāta arrows (``पा॰ ८.१.२८`` / ``८.१.१९``) blocked by ``पादादि`` (``८.१.१८``), ``अतिङः``, ``८.१.७२``, or ``८.१.५९``."""
  items_per_line = [parse_padapatha_items(ln) for ln in pp_lines]
  flat_items = [it_l[0] for it_l in items_per_line if it_l]
  if len(flat_items) != len(pp_lines):
    return []

  gati_bare_set = frozenset({
    "प्र", "परा", "अप", "सम्", "सं", "सँ", "अनु", "अव", "निस्", "निर्", "निः",
    "दुस्", "दुर्", "दुः", "वि", "आ", "नि", "अधि", "अपि", "अति", "सु",
    "उत्", "उद्", "अभि", "प्रति", "परि", "उप",
  })
  yad_bare_re = re.compile(
    r"^(यत्|यद्|यः|यम्|येन|यस्य|यस्मै|यस्मात्|यस्मिन्|यत्र|यदा|यथा|यदि|या|ये|याः|यानि|येभिः|याभिः|यासाम्|येषाम्|यासु|येषु|यया|यैः|याभ्याम्|येभ्यः|याभ्यः|हि|चेत्|नेत्|कुवित्)$"
  )
  correl_stop_set = frozenset({
    "तत्", "तद्", "सः", "स", "सा", "ते", "ताः", "तानि", "तत्र", "तदा",
    "तथा", "एवम्", "एवा", "तस्मात्", "तेन", "तम्", "ताम्", "तस्मिन्", "तस्य", "तस्मै", "तान्", "ताभिः", "तैः", "अथ", "अथो",
  })

  segs: list[tuple[str, str, int]] = []
  if mula_clean and any(ch in mula_clean for ch in ("\u0951", "\u0952")):
    mula_stripped = re.sub(r"\[[\d०-९]+\]|\([\d०-९]+\)|[०-९\d]+", "", mula_clean)
    for raw_seg in re.split(r"[।॥]+", mula_stripped):
      s = raw_seg.strip()
      if s:
        sb = accent.strip_accents(s)
        segs.append((s, sb, len(syllables_with_marks(sb)[0])))

  hits: list[str] = []
  for i, (ln, it) in enumerate(zip(pp_lines, flat_items)):
    if not (it.vyat and has_us_accents(it.ar) and not has_us_accents(it.ref)):
      continue
    is_8128 = "८.१.२८" in it.prov
    is_8119 = "८.१.१९" in it.prov
    if not (is_8128 or is_8119):
      continue
    if any(k in it.prov for k in ("मिथ्या", "पाठदोष", "८.१.३", "द्विर्वचन", "मुख्यवाक्य", "वाक्यभेद")):
      continue

    # (a) Mantra-initial (#0) stands at पादादि (पा॰ ८.१.१८ / ६.१.१९८)
    if i == 0:
      hits.append(ln)
      continue

    prev = flat_items[i - 1]
    prev_bare = bare_devanagari(prev.ref)

    # (b) Immediately after a pāda-initial vocative (#0 -> #1): पा॰ ८.१.७२ आमन्त्रितं पूर्वमविद्यमानवत्
    if i == 1 and ("६.१.१९८" in prev.prov or "आमन्त्रित" in prev.prov) and has_us_accents(prev.ref):
      hits.append(ln)
      continue

    # (c) Finite verb (८.१.२८) immediately after another finite verb: अतिङः blocks nighāta
    if is_8128 and prev_bare not in gati_bare_set and prev_bare != "ओम्":
      if any(t in prev.prov for t in ("८.१.२८", "तिङन्त", "आशीर्लिङ्")) or (
        "पादाद" in prev.prov and "६.१.१९८" not in prev.prov and "आमन्त्रित" not in prev.prov
      ):
        hits.append(ln)
        continue

    # (d) चवायोगे प्रथमा (पा॰ ८.१.५९): finite verb followed immediately by च/वा + another verb + च/वा
    if is_8128 and i + 1 < len(flat_items) and bare_devanagari(flat_items[i + 1].ref) in ("च", "वा"):
      tail = flat_items[i + 2 : min(len(flat_items), i + 7)]
      if any("८.१.२८" in t.prov or "तिङन्त" in t.prov for t in tail) and any(
        bare_devanagari(t.ref) in ("च", "वा") for t in tail
      ):
        hits.append(ln)
        continue

    # (e) Subordinate यद्वृत्त / हि clause without intervening correlative (पा॰ ८.१.६६ / ८.१.३४)
    if is_8128 and sum(1 for ch in it.ar if ch in ("\u1cd3", "\u1cd9")) == 1:
      win_items = flat_items[max(0, i - 6) : i]
      win_bares = [bare_devanagari(x.ref) for x in win_items]
      last_yad = max(( idx_w for idx_w, wb in enumerate(win_bares) if yad_bare_re.match(wb) ), default=-1)
      if last_yad >= 0:
        between_items = win_items[last_yad + 1 :]
        between_bares = win_bares[last_yad + 1 :]
        # Ensure the यद्-clause didn't already finish with its own finite verb before a new main clause
        had_prior_verb = any(
          any(vt in bi.prov for vt in ("८.१.६६", "८.१.३४", "८.१.३०", "८.१.२८", "तिङन्त"))
          for bi in between_items
        )
        if not had_prior_verb and not any(wb in correl_stop_set for wb in between_bares):
          hits.append(ln)
          continue

    # (f) Metrical पादादि (पा॰ ८.१.१८ / ६.१.१९८) in single-accented Vedic mantras
    if segs and sum(1 for ch in it.ar if ch in ("\u1cd3", "\u1cd9")) == 1:
      if prev_bare in gati_bare_set and has_us_accents(prev.ref):
        continue
      w_plain = bare_devanagari(it.ref)
      if len(w_plain) >= 2:
        probe = w_plain[:-1] if len(w_plain) >= 4 else w_plain
        for _, sb, seg_syls in segs:
          m_pos = re.search(re.escape(probe), sb)
          if m_pos:
            prefix = sb[: m_pos.start()].strip()
            n_pre = len(syllables_with_marks(prefix)[0]) if prefix else 0
            if n_pre == 0 and seg_syls >= 5:
              hits.append(ln)
            elif n_pre == 8 and 15 <= seg_syls <= 17:
              hits.append(ln)
            elif n_pre == 11 and 21 <= seg_syls <= 23:
              hits.append(ln)
            elif n_pre == 12 and 23 <= seg_syls <= 25:
              hits.append(ln)
            break
  return hits


_ENCLITIC_8118_ALLOWLIST: frozenset[str] = frozenset({
  # Genuine Vedic enclitic particles (निपाताः) and anvādeśa/enclitic pronominals (पा॰ ८.१.१८ / ८.१.२१-२३ / २.४.३२-३४).
  "च", "वा", "ह", "उ", "ऊ", "स्म", "इव", "चित्", "चन", "नः", "वः", "पः", "मे", "ते", "मा", "त्वा", "नौ", "वाम्",
  "ईम्", "सीम्", "अह", "स्वित्", "कम्", "तु", "घ", "घा", "हि", "खलु", "किल", "इत्", "नु", "सु", "शम्",
  "वै", "एव", "अङ्ग", "उत", "स्य", "स", "सा", "तत्", "तम्", "ताम्", "तस्य", "तस्मै", "तस्मात्", "तस्मिन्",
  "तस्याः", "तस्याम्", "तस्या", "तस्यै", "तेन", "तया", "तयोः", "तेषाम्", "तासाम्", "तान्", "ताः", "तानि", "तौ",
  "अस्य", "अस्मै", "अस्मात्", "अस्मिन्", "अस्याः", "अस्याम्", "अस्या", "अस्यै", "अस्योः",
  "एनम्", "एनाम्", "एनत्", "एनान्", "एनेन", "एनया", "एनौ", "एने", "एनयोः", "एनाः", "एनानि",
  "एषाम्", "आसाम्", "एभ्यः", "आभ्यः", "एषु", "आसु", "एभिः", "आभिः",
  "एतम्", "एताम्", "एतत्", "एतस्य", "एतस्मै", "एतस्मात्", "एतस्मिन्", "एतस्याः", "एतस्याम्",
  "एतेन", "एतया", "एतयोः", "एतेषाम्", "एतासाम्", "एते", "एतान्", "एताः", "एतानि", "एतौ",
  "इमम्", "इमाम्", "इदम्", "इमान्", "इमाः", "इमानि", "अनेन", "अनया", "अनयोः",
  "अमुम्", "अमूम्", "अदः", "अमुष्य", "अमुष्मै", "अमुष्मात्", "अमुष्मिन्",
  "त्वः", "त्वम्", "त्वत्", "त्वे", "त्वाः", "बत", "वत", "समः", "समम्", "समे", "समस्य", "समान्", "समाः", "समानि", "नेमः",
})
_NON_8118_ANUDATTA_TAGS: tuple[str, ...] = tuple(t for t in VALID_ANUDATTA_RULE_TAGS if t != "८.१.१८")


def find_unlicensed_unaccented_padas(pp_lines: Sequence[str]) -> list[str]:
  """Return padapāṭha bullet lines whose target has 0 accents without a valid Pāṇini ``8.1.*``/``2.4.*`` nighāta license."""
  hits: list[str] = []
  for ln in pp_lines:
    it_list = parse_padapatha_items(ln)
    if not it_list:
      continue
    it = it_list[0]
    if "?" in it.ref or has_us_accents(it.ref):
      continue
    bare = bare_devanagari(it.ref)
    if bare in ("भूः", "ओम्"):
      continue
    if not any(tag in it.prov for tag in VALID_ANUDATTA_RULE_TAGS):
      hits.append(ln)
      continue
    # Anti-cheat guard: `पा॰ ८.१.१८` alone only licenses genuine enclitics/particles/anvādeśa pronouns,
    # never arbitrary unaccented nouns/compounds (e.g. `पुमास्तेन (अनुदात्तम्, पा॰ ८.१.१८)`).
    if "८.१.१८" in it.prov and not any(tag in it.prov for tag in _NON_8118_ANUDATTA_TAGS):
      if "-" in it.ref or bare not in _ENCLITIC_8118_ALLOWLIST:
        hits.append(ln)
  return hits


def find_unsplit_upasarga_tinantas(
  pp_lines: Sequence[str],
  *,
  forbid_compound_upasarga_tinanta: bool = False,
) -> list[str]:
  """Return tiṅanta bullets that retain an unseparated upasarga or misclassify a nominal.

  Catches:
  1. Unaccented ``पा॰ ८.१.२८`` bullets retaining a leading upasarga (including coalesced ``ऐतु``/``अवैत्``) or nominal ending.
  2. Accented ``upasarga + tiṅanta`` bullets (e.g. ``- प्रचोद᳓यात् (*TS*, *RV*; *TS*, *RV*, *TB*)``) whose provenance
     lacks an explicit subordinate-clause license (``पा॰ ८.१.६६``, ``८.१.३४``, ``८.१.३०``, ``८.१.५९``, ``८.१.६३``, ``८.१.७१``).
  3. When ``forbid_compound_upasarga_tinanta=True`` (auto-enabled on ŚB clusters), ANY accented upasarga+tiṅanta
     bullet — including subordinate-clause hyphenated or unhyphenated forms like ``उप-स्पृश᳓ति`` / ``उद्-य᳓च्छति`` /
     ``उप-आ-व᳓र्तते`` — so upasargas are always emitted as separate ``पा॰ ८.१.७१`` bullets while ``गतिकृदन्त``
     (participles, gerunds, infinitives, action nouns) remain hyphenated.
  """
  hits: list[str] = []
  nominal_8128_endings = ("तः", "ताः", "तौ", "तिः", "निः", "नीः", "लः", "रः", "णः", "कः", "शः", "षः", "नः", "भः", "यः", "हः", "भिः", "भ्यः", "षु", "सु", "स्य", "नाम्", "णाम्")
  finite_sip_allow = frozenset({
    "आः", "अकः", "अभूः", "अधाः", "अदाः", "अस्थाः", "अपाः", "अगाः", "अजाः", "आवाः", "अप्राः",
    "अहः", "वेत्थ", "आत्थ", "तारिषः", "मोषीः", "भैषीः", "शारीः", "अस्य", "सुवः", "कः", "वृहः",
    "रीरिषः", "अबिभः", "मांस्ताः", "जीह्वरः", "दहः", "उरुष्यः", "अवीः", "पूरिष्ठाः", "अहाः",
  })
  coalesced_up_tinantas = frozenset({
    "ऐतु", "ऐति", "अवैत्", "अवैति", "अवेति", "प्रैत्", "प्रैति", "प्रैतु", "प्रेति",
    "उपैत्", "उपैति", "उपैतु", "समेति", "समैति", "उदैति", "प्रेरते",
    "उपेहि", "अपेहि", "एहि", "परेहि", "परीहि",
    "प्रेयात्", "उपेयात्", "अवेयात्", "अपेयात्", "समेयात्",
  })
  subordinate_verb_tags = ("८.१.६६", "८.१.३४", "८.१.३०", "८.१.५९", "८.१.६३", "८.१.७१", "८.१.७२", "पादादि")
  extra_verb_tags = ("तिङन्त", "वाक्यादि", "८.१.२८", "लेट्", "लट्", "लङ्", "लोट्", "लिङ्", "लिट्", "लुङ्", "लृट्")
  nominal_prov_tags = (
    "६.२.", "६.१.२२३", "२.१.", "५.४.", "४.३.", "मयट्", "अव्ययीभाव", "बहुव्रीह", "तत्पुरुष", "कर्मधारय", "नञ्",
    "क्त्वा", "ल्यप्", "तुमुन्", "तवै", "शतृ", "शानच्", "निष्ठा", "क्त", "घञ्", "ल्युट्", "क्तिन्",
    "क्विप्", "तव्यत्", "अनीयर्", "ण्यत्", "यत्", "कप्", "प्रातिपदिकम्",
  )
  accented_verb_roots = frozenset({
    "चोदयात्", "चोदयाति", "मृध्यताम्", "मृद्ध्यताम्", "अगात्", "अहार्षम्", "विश", "भजासि",
    "प्यायय", "यच्छ", "वापय", "वापया", "तरेम", "रभेथाम्", "मृश", "स्पृश", "वह",
    "अगन्महि", "सृज", "सृजस्व", "स्रवन्तु", "शारीः", "ताप्तम्", "महेम", "महेमा",
    "एधिषीमहि", "नये", "जीवाथ", "गहि", "आध्वम्", "आद्ध्वम्", "असरत्", "दह", "अस्य",
    "राज", "वधिष्ठाः", "हर", "हरा", "अरुक्षम्", "स्रसत्",
  })
  for ln in pp_lines:
    it_list = parse_padapatha_items(ln)
    if not it_list:
      continue
    it = it_list[0]
    if "?" in it.ref:
      continue
    bare = bare_devanagari(it.ref)
    if (
      bare in SIMPLEX_TINANTA_ALLOWLIST
      or bare in ("अवद्यात्", "उपास्य")
      or bare.startswith((
        "विन्द", "विध्य", "विद्ध", "विवेश", "विविश", "विविच", "विविदिष", "विनक्", "विच्य", "विजत", "विजन्त", "विजे",
        "सुन्व", "सुनो", "सुनु", "सुण्व", "सुणो", "सुणु", "सुषाव", "सुषुव", "सुस्र", "सुषुप",
        "प्रथ", "प्रच्छ", "पृच्छ", "प्रीण", "प्रक्ष्य",
        "अवृण", "अवृध", "अवृज", "अवृत", "अवृह", "अववृत्र", "अववृत", "अतिष्ठ", "अप्रीण", "अपद्य", "अपादय", "अवप", "अपश्य", "अपत", "अपिब",
        "अवद", "अवह", "अभव", "अभज", "अनय", "अविन्द", "अविध्य", "अवर्त", "अवर्ध", "अवस",
        "अप्लव", "अपाव", "अपुना", "अपुन", "अपच", "अपृच्छ", "अपृण", "अप्रथ", "अवच", "अवोच", "अवर्ष्", "अवात्स", "अवादिष", "अवादी", "अपिपतिष",
        "अपूपुर", "अवेदिष", "अवेपय", "अभिषज्", "अध्याय", "अधुक्ष", "अप्लाव",
        "आप्न", "आप्य", "आदय", "आदित्य", "आश्नु", "आश्न", "आर्ध्य", "आञ्च", "आसात", "आसास", "आशिष", "निन्य", "निन्द", "शंसिष",
      ))
      or ("-" not in it.ref and bare not in coalesced_up_tinantas and _is_vidyut_simplex_tinanta(bare))
    ):
      continue
    if not has_us_accents(it.ref):
      if "८.१.२८" not in it.prov:
        continue
      if "-" in it.ref or bare in coalesced_up_tinantas:
        hits.append(ln)
        continue
      if bare not in finite_sip_allow and bare.endswith(nominal_8128_endings) and not bare.endswith(("थः", "तः")) or (
        bare.endswith("तः") and bare in ("स्मृतः", "कृतः", "भृतः", "धृतः", "श्रितः", "स्थितः", "जातः", "गतः", "हतः", "मतः", "युक्तः", "मुक्तः", "प्रोक्तः", "उक्तः")
      ):
        hits.append(ln)
        continue
      if any(
        bare.startswith(up)
        and len(bare) > len(up) + 1
        and not ("\u0915" <= up[-1] <= "\u0939" and bare[len(up)] in "ृॄॢॣ")
        for up in UPASARGA_PREFIXES
      ):
        hits.append(ln)
    else:
      # Catch missed पा॰ ८.१.२८ svara-nighāta on Vedic 2pl imperative -तन/-थन (e.g. युयोतन → **युयो᳓तन**)
      if "→ **" in ln and not has_us_accents(it.ar) and bare.endswith(("तन", "थन")) and not any(t in it.prov for t in subordinate_verb_tags):
        hits.append(ln)
        continue
      is_nominal_prov = any(t in it.prov for t in nominal_prov_tags)
      is_verb_prov = any(t in it.prov for t in subordinate_verb_tags) or any(t in it.prov for t in extra_verb_tags)
      if forbid_compound_upasarga_tinanta and not is_nominal_prov:
        if bare not in UPASARGA_PREFIXES and bare not in ("सम्", "निस्", "निर्", "दुस्", "दुर्", "उद्"):
          # पा॰ ८.१.७१ applies only to a separate anudātta upasarga bullet, never an accented compound tiṅanta.
          if "८.१.७१" in it.prov:
            hits.append(ln)
            continue
          if is_verb_prov:
            if "-" in it.ref and bare_devanagari(it.ref.split("-", 1)[0]) in _GATI_HYPHEN_PREFIXES:
              hits.append(ln)
              continue
            if bare in coalesced_up_tinantas:
              hits.append(ln)
              continue
            # Unhyphenated subordinate upasarga+tiṅanta leaves the leading upasarga anudātta (marks[0] == ""),
            # unlike augmented simplex past verbs (पा॰ ६.४.७१) which carry udātta on syllable 0 (`अ᳓वदत्`).
            _, ref_marks = syllables_with_marks(it.ref)
            if ref_marks and ref_marks[0] == "" and any(
              bare.startswith(up)
              and len(bare) > len(up) + 1
              and not ("\u0915" <= up[-1] <= "\u0939" and bare[len(up)] in "ृॄॢॣ")
              for up in UPASARGA_PREFIXES
            ):
              hits.append(ln)
              continue
      if any(t in it.prov for t in subordinate_verb_tags) or is_nominal_prov:
        continue
      if bare in UPASARGA_PREFIXES or bare in ("सम्", "निस्", "निर्", "दुस्", "दुर्", "उद्"):
        continue
      if "-" in it.ref and not is_verb_prov:
        continue
      if bare in coalesced_up_tinantas:
        hits.append(ln)
        continue
      for up in UPASARGA_PREFIXES:
        if bare.startswith(up) and len(bare) > len(up) + 1:
          rest = bare[len(up):]
          rest_cands = [rest]
          if up in ("आ", "सम", "उद", "निर", "दुर"):
            rest_cands.append("अ" + rest)
          elif up in ("प्र", "परा", "अव", "उप", "अप") and rest.startswith("ा"):
            rest_cands.extend(["अ" + rest[1:], "आ" + rest[1:]])
          if any(rc in accented_verb_roots for rc in rest_cands) or (
            bare == "अधिधाः"
            or (
              rest.endswith(("याताम्", "न्ताम्", "थाम्", "ध्वम्", "मसि", "महि", "ैषम्", "ार्षम्", "स्व", "र्षात्", "वपात्"))
              and not bare.endswith(("ताम्", "नाम्", "णाम्", "स्थाम्"))
            )
            or (rest.endswith("यात्") and is_verb_prov)
          ):
            hits.append(ln)
            break
  return hits


def find_multi_udatta_padas(pp_lines: Sequence[str]) -> list[str]:
  """Return padapāṭha bullets whose target ``ref`` carries >1 US accent, dependent marks, or illegal enclitic accents."""
  dual_accent_stems = ("बृहस्पति", "बृहस्पत", "ब्रह्मणस्पति", "ब्रह्मणस्पत", "वाचस्पति", "वाचस्पत", "शचीपति", "शचीपत", "वनस्पति", "वनस्पत", "सदसस्पति", "जगतस्पति", "रायस्पोष", "रायःपोष", "शुभस्पती", "शुभःपती", "नराशंस", "नराशँस", "तनूनपात्", "द्यावा", "मित्रावरुण", "मित्रा-वरुण", "इन्द्रावरुण", "इन्द्राग्नी", "इन्द्राविष्णू", "इन्द्राबृहस्पती", "इन्द्रासोमा", "अग्नीषोम", "सोमारुद्र", "अहोरात्र", "परिधातवै", "परि-धातवै")
  always_anudatta_enclitics = frozenset({"च", "मे", "नः", "वः", "त्वा", "ह", "स्म"})
  hits: list[str] = []
  for ln in pp_lines:
    it_list = parse_padapatha_items(ln)
    if not it_list:
      continue
    it = it_list[0]
    if "?" in it.ref:
      continue
    bare = bare_devanagari(it.ref)
    if not re.search(r"[\u0905-\u0939]", bare) or any(ch in it.ref for ch in ("\u0951", "\u0952", "।", "॥")):
      hits.append(ln)
      continue
    n_acc = sum(1 for ch in it.ref if ch in ("\u1cd3", "\u1cd9"))
    if "\u1cd9" in it.ref:
      # Keep ᳙ in padapāṭha only on lexical (jātya) svaritas (after ् + य/व, e.g. स्वः᳙, वीर्य᳙म्, तव्य᳙म्, नद्यः᳙).
      for m_sv in re.finditer(r"(.{0,6})\u1cd9", it.ref):
        if not re.search(r"्[यव][ािीुूृेैोौःंँ]*$", m_sv.group(1)):
          hits.append(ln)
          break
      if ln in hits:
        continue
    if n_acc >= 1 and bare in always_anudatta_enclitics:
      hits.append(ln)
      continue
    if n_acc >= 2:
      if (
        any(tag in it.prov for tag in ("६.२.१४०", "६.२.१४१", "६.१.२००", "अन्तश्च तवै", "देवताद्वन्द्व", "उभे वनस्पत्यादिषु"))
        or bare.endswith("तवै")
        or any(st in bare for st in dual_accent_stems)
      ):
        continue
      hits.append(ln)
  return hits


def find_suspect_homograph_accents(
  pp_lines: Sequence[str],
  mula_clean: str = "",
) -> list[str]:
  """Flag sense-sensitive homograph padas where a rare/wrong-sense accent or case was chosen without justification.

  Specifically guards against:
  1. Antodātta ``वेद᳓`` ('darbha-bunch / wealth') proposed via ``→ **वेद᳓...**`` or ``घञ्`` without ``दर्भ/मुष्टि/कुश/बर्हि/शिखा/धन`` sense (instead of ādyudātta ``वे᳓द`` 'Śruti/Veda', ``पा॰ ६.१.२०३``).
  2. Antodātta ``अन्तक᳓`` ('border/boundary') without ``सीम/पर्यन्त`` sense (instead of ādyudātta ``अ᳓न्तक`` 'Death/ender').
  3. Antodātta ``→ **महः᳓**`` (oblique of ``मह्``) without ``पा॰ ६.१.१६८`` / ``षष्ठ/पञ्चम/द्वितीयाबहु`` justification (instead of neuter ``म᳓हः`` 'greatness/light', ``पा॰ ६.१.१९७``).
  4. Antodātta ``→ **धर्म...᳓**`` / ``→ **धर्मा...᳓**`` ('bearer/supporter') without ``धर्त/धारयित/स्थूण`` agent sense (instead of ādyudātta ``ध᳓र्म`` 'duty/law', ``पा॰ ६.१.१९७``).
  5. Parasavarṇa ablative ``-आन् न`` (``सत्यान् न``, ``धर्मान् न``, ``कुशलान् न``) mis-restored as feminine accusative ``-आम्`` before ``न᳓`` instead of ablative ``-आत्``.
  """
  hits: list[str] = []
  parsed: list[tuple[str, object]] = []
  for ln in pp_lines:
    it_list = parse_padapatha_items(ln)
    if it_list:
      parsed.append((ln, it_list[0]))

  mula_bare_no_sp = re.sub(r"\s+", "", bare_devanagari(mula_clean)) if mula_clean else ""
  for idx, (ln, it) in enumerate(parsed):
    ref = it.ref
    bare = bare_devanagari(ref)
    prov = it.prov
    _, mks = syllables_with_marks(ref)

    # 1. वेद᳓म् / वेदः᳓ / वेदाः᳓ (antodātta grass-bunch/wealth vs ādyudātta वे᳓द Śruti)
    if bare in ("वेदम्", "वेदः", "वेदाः", "वेदेन", "वेदात्", "वेदस्य", "वेदे") and len(mks) == 2 and mks == ["", "U"]:
      if (it.vyat or "घञ्" in prov) and not any(
        kw in prov for kw in ("दर्भ", "मुष्टि", "कुश", "बर्हि", "शिखा", "धन", "धर्मसाधन")
      ):
        hits.append(ln)
        continue

    # 2. अन्तकः᳓ / अन्तक᳓म् / अन्तका᳓य (antodātta 'border' vs ādyudātta अ᳓न्तक 'Death')
    if bare in ("अन्तकः", "अन्तकम्", "अन्तकाय", "अन्तकात्") and len(mks) == 3 and mks == ["", "", "U"]:
      if not any(kw in prov for kw in ("सीम", "पर्यन्त")):
        hits.append(ln)
        continue

    # 3. म᳓हः᳓ → **महः᳓** without पा॰ ६.१.१६८ / oblique case justification
    if bare == "महः" and it.vyat and mks == ["", "U"]:
      if not any(kw in prov for kw in ("६.१.१६८", "षष्ठ", "पञ्चम", "द्वितीयाबहु")):
        hits.append(ln)
        continue

    # 4. → **धर्म...᳓** / → **धर्मा...᳓** without agent ('धर्ता/धारयिता') justification
    if bare in ("धर्मः", "धर्मम्", "धर्मात्", "धर्माम्", "धर्माय", "धर्मे") and it.vyat and len(mks) == 2 and mks == ["", "U"]:
      if not any(kw in prov for kw in ("धर्त", "धारयित", "स्थूण")):
        hits.append(ln)
        continue

    # 5. -आम् before न (parasavarṇa of ablative -आत् + न -> -आन् न)
    if bare in ("सत्याम्", "धर्माम्", "कुशलाम्") and idx + 1 < len(parsed):
      next_bare = bare_devanagari(parsed[idx + 1][1].ref)
      stem_prefix = bare[:-2]  # सत्य / धर्मा / कुशला -> strip आम् -> सत्या / धर्मा / कुशला
      if next_bare == "न" and (not mula_bare_no_sp or f"{stem_prefix}न्न" in mula_bare_no_sp):
        hits.append(ln)
        continue
  return hits


def find_tinanta_sutra_on_non_tinanta(pp_lines: Sequence[str]) -> list[str]:
  """Return bullets misapplying ``तिङ्``-adhikāra sūtras (``पा॰ ८.१.२८–६८``) to non-``तिङन्त`` padas or across ``हि`` boundaries."""
  tin_adhikara_re = re.compile(r"८\.१\.(?:२[८९]|[३४५][०-९]|६[०-८])(?![०-९])")
  negated_sutra_re = re.compile(r"८\.१\.[०-९]+\s*न\s*प्रवर्तते|न\s*पा॰\s*८\.१\.")
  pronoun_non_tin = frozenset({
    "अहम्", "माम्", "मा", "मया", "मह्यम्", "मे", "मत्", "मम", "मयि", "आवाम्", "नौ",
    "वयम्", "अस्मान्", "नः", "अस्माभिः", "अस्मभ्यम्", "अस्मत्", "अस्माकम्", "अस्मासु",
    "त्वम्", "त्वाम्", "त्वा", "त्वया", "तुभ्यम्", "ते", "त्वत्", "तव", "त्वयि", "युवाम्", "वाम्", "वान्",
    "यूयम्", "युष्मान्", "वः", "युष्माभिः", "युष्मभ्यम्", "युष्मत्", "युष्माकम्", "युष्मासु",
    "सः", "तम्", "तेन", "तस्मै", "तस्मात्", "तस्य", "तस्मिन्", "तौ", "तान्", "तैः", "तेभ्यः", "तेषाम्", "तेषु",
    "सा", "ताम्", "तया", "तस्यै", "तस्याः", "तस्याम्", "ताः", "ताभिः", "ताभ्यः", "तासाम्", "तासु", "तत्", "तद्", "तानि",
    "एषः", "एतम्", "एतेन", "एतस्मै", "एतस्मात्", "एतस्य", "एतस्मिन्", "एषा", "एताम्", "एतस्यै", "एतत्", "एतद्", "एते", "एताः", "एतानि", "एनम्", "एनाम्", "एनत्", "एनान्",
    "अयम्", "इमम्", "अनेन", "अस्मै", "अस्मात्", "अस्मिन्", "इयम्", "इमाम्", "अनया", "अस्यै", "अस्याः", "अस्याम्", "इदम्", "इमौ", "इमे", "इमान्", "एभिः", "एभ्यः", "एषाम्", "एषु", "इमाः", "आभिः", "आभ्यः", "आसाम्", "आसु", "इमानि",
    "असौ", "अमुम्", "अमुना", "अमुष्मै", "अमुष्मात्", "अमुष्य", "अमुष्मिन्", "अमू", "अमी", "अमून्", "अमूः", "अमूनि",
    "यः", "यम्", "येन", "यस्मै", "यस्मात्", "यस्य", "यस्मिन्", "या", "याम्", "यया", "यस्यै", "यस्याः", "यस्याम्", "यत्", "यद्", "यौ", "ये", "यान्", "यैः", "येभ्यः", "येषाम्", "येषु", "याः", "याभिः", "याभ्यः", "यासाम्", "यासु", "यावत्", "तावत्",
    "कम्", "केन", "कस्मै", "कस्मात्", "कस्य", "कस्मिन्", "का", "काम्", "किम्", "के", "काः", "कानि",
  })
  particle_gati_non_tin = frozenset({
    "च", "वा", "उ", "हि", "नहि", "ह", "अह", "इत्", "चित्", "स्म", "किल", "खलु", "वै", "एव", "इव",
    "न", "नो", "मो", "नेत्", "चेत्", "कुवित्", "कच्चित्", "स्विद्", "नु", "सु", "कम्", "शम्", "शमु",
    "नमः", "स्वस्ति", "स्वाहा", "स्वधा", "वषट्", "वट्",
    "इह", "चेह", "नेह", "अत्र", "तत्र", "यत्र", "कुत्र", "सर्वत्र", "यदा", "तदा", "कदा", "सदा",
    "यथा", "तथा", "कथम्", "एवम्", "इति", "अथ", "अथो", "उत", "उतो", "अद्य", "श्वः", "ह्यः", "पुरा", "पुनः",
    "प्रातः", "सायम्", "उच्चैः", "नीचैः", "शनैः", "अतः", "ततः", "यतः", "पुरस्तात्", "अभितः", "परितः", "सर्वतः", "विश्वतः",
    "प्र", "परा", "अप", "सम्", "सं", "सँ", "अनु", "अभि", "निस्", "निर्", "निः", "दुस्", "दुर्",
    "वि", "आ", "नि", "अधि", "अपि", "अति", "उत्", "उद्", "प्रति", "परि", "उप",
  })
  asya_upasargas = frozenset({"वि", "अप", "नि", "परा", "प्र", "उत्", "उद्", "अभि", "सम्", "सं", "परि", "अति"})
  nom_prov_tags = (
    "प्रातिपदिकम्", "तत्पुरुष", "बहुव्रीह", "कर्मधारय", "अव्ययीभाव", "द्वन्द्व", "समास", "नञ्",
    "क्तः", "क्तिन्", "शतृ", "शानच्", "ल्युट्", "घञ्", "ण्यत्", "तव्यत्", "तुमुन्", "क्त्वा", "ल्यप्", "ष्यञ्",
  )
  nom_endings = (
    "ायै", "ायाः", "ायाम्", "ाभ्याम्", "ेभ्यः", "ाभ्यः", "ृभ्यः", "िभ्यः", "ुभ्यः",
    "ेभिः", "ाभिः", "िभिः", "ुभिः", "ृभिः", "ेषु", "ासु", "िषु", "ुषु", "ृषु",
    "ानाम्", "ीनाम्", "ूनाम्", "ॄणाम्",
  )
  hi_clause_breakers = frozenset({"मा", "नो", "शमु", "उ", "तस्मै", "तत्", "सः", "अथ", "यत्र", "यः", "यत्"})

  parsed = [parse_padapatha_items(ln) for ln in pp_lines]
  items = [it_l[0] for it_l in parsed if it_l]
  if len(items) != len(pp_lines):
    return []
  bares = [bare_devanagari(it.ref) for it in items]

  hits: list[str] = []
  for i, (ln, it, bare) in enumerate(zip(pp_lines, items, bares)):
    if "?" in it.ref:
      continue
    if tin_adhikara_re.search(it.prov) and not negated_sutra_re.search(it.prov):
      prev_bare = bares[i - 1] if i > 0 else ""
      bad = False
      if bare in pronoun_non_tin or bare in particle_gati_non_tin:
        bad = True
      elif bare == "अस्य":
        _, mks = syllables_with_marks(it.ref)
        # 2sg loṭ of √अस् 4P (`अ᳓स्य`) is ādyudātta; antodātta `अस्य᳓` is always gen. sg. `इदम्`.
        if mks == ["", "U"]:
          bad = True
        elif len(items) > 1 and prev_bare not in asya_upasargas and not any(
          k in it.prov for k in ("अस्यत", "असन", "क्षिप", "लोट्")
        ):
          bad = True
      elif any(t in it.prov for t in nom_prov_tags):
        bad = True
      elif bare.endswith("स्य") and bare != "अस्य" and not bare.endswith(
        ("स्यति", "स्यते", "स्यसि", "स्यथ", "स्यामि", "स्यामः", "स्यन्ते", "स्यन्ति", "स्यस्व")
      ):
        bad = True
      elif bare.endswith(nom_endings):
        bad = True
      if bad:
        hits.append(ln)
        continue

    if "८.१.३४" in it.prov and not negated_sutra_re.search(it.prov):
      hi_indices = [k for k, b in enumerate(bares) if b in ("हि", "नहि")]
      if not hi_indices:
        hits.append(ln)
        continue
      last_hi = max((k for k in hi_indices if k < i), default=-1)
      if last_hi == -1:
        if (i + 1) in hi_indices:
          continue
        hits.append(ln)
        continue
      if it.vyat and not has_us_accents(it.ar) and has_us_accents(it.ref):
        between_b = bares[last_hi + 1 : i]
        between_it = items[last_hi + 1 : i]
        if any(b in hi_clause_breakers for b in between_b) or any(
          "६.१.१९८" in bi.prov or "पादाद" in bi.prov for bi in between_it
        ):
          hits.append(ln)
          continue
  return hits


def find_missing_aa_upasarga_splits(pp_lines: Sequence[str]) -> list[str]:
  """Return bullets where ``पा॰ ८.२.५`` ``आ᳓ + verb`` sandhi was mis-split as a fake arrow on ``i`` + ``अ-``verb or double-canceling ``आ`` arrows."""
  parsed = [parse_padapatha_items(ln) for ln in pp_lines]
  items = [it_l[0] for it_l in parsed if it_l]
  if len(items) != len(pp_lines):
    return []
  aa_verb_prefixes = (
    "अविश", "अगुः", "अगम", "अगा", "अगन्", "अगत", "अया", "अवृत्",
    "अस्था", "असद", "असीद", "अदा", "अधा", "अहर", "अवह", "अनी", "अनय", "अरोह", "अरुक्ष",
  )
  hits: list[str] = []
  for i in range(len(items) - 1):
    it1, it2 = items[i], items[i + 1]
    if "?" in it1.ref or "?" in it2.ref:
      continue
    b1, b2 = bare_devanagari(it1.ref), bare_devanagari(it2.ref)
    # 1. Double-canceling `आ → **आ᳓**` + `अ᳓... → **अ...**` (both yield identical `आ᳓...` by पा॰ ८.२.५)
    if b1 == "आ" and it1.vyat and not has_us_accents(it1.ar) and has_us_accents(it1.ref):
      if b2.startswith("अ") and it2.vyat and has_us_accents(it2.ar) and not has_us_accents(it2.ref):
        hits.append(pp_lines[i])
        continue
    # 2. Preceding `-अ/-आ` word strips final udātta before unaccented `पा॰ ८.१.२८` motion/entry `अ-`verb
    if it1.vyat and "८.१.२८" in it2.prov and not has_us_accents(it2.ref) and b2.startswith(aa_verb_prefixes):
      s1 = sanscript.transliterate(b1, sanscript.DEVANAGARI, sanscript.SLP1)
      if s1 and s1[-1] in ("a", "A"):
        _, m_ar = syllables_with_marks(it1.ar)
        _, m_ref = syllables_with_marks(it1.ref)
        if m_ar and m_ref and m_ar[-1] and not m_ref[-1]:
          hits.append(pp_lines[i])
  return hits


_ASHTADHYAYI_PADA_MAX: tuple[int, ...] = (
  75, 73, 93, 110,
  72, 38, 73, 85,
  150, 188, 176, 117,
  178, 145, 168, 144,
  136, 140, 119, 160,
  223, 199, 139, 175,
  103, 118, 120, 97,
  74, 108, 119, 68,
)
_DEVA_DIGIT_TRANS = str.maketrans("०१२३४५६७८९", "0123456789")
_BARE_CORPUS_TAG_RE = re.compile(r"\*(?:TS|RV|TB|TK|AV|ŚB|VS|KS|MS)\*(?!-\d)")
_SUTRA_CITE_RE = re.compile(r"पा॰\s*([०-९0-9]+)\.([०-९0-9]+)\.([०-९0-9]+)(?:[–\-]([०-९0-9]+))?")


def find_uncounted_corpus_tags(pp_lines: Sequence[str]) -> list[str]:
  """Return padapāṭha bullets citing ``*TS*``, ``*RV*``, ``*TB*``, ``*TK*``, ``*AV*``, ``*ŚB*``, ``*VS*``, ``*KS*``, or ``*MS*`` without a positive ``-N`` frequency count."""
  hits: list[str] = []
  for ln in pp_lines:
    it_list = parse_padapatha_items(ln)
    if not it_list:
      continue
    if _BARE_CORPUS_TAG_RE.search(it_list[0].prov):
      hits.append(ln)
  return hits


def find_invalid_or_rubberstamp_provenance(pp_lines: Sequence[str]) -> list[str]:
  """Return bullets with fake/out-of-bounds sūtras, bare ``समासस्वरः``, misaccented ``ल्यप्``/``ल्युट्``/``णिनि``, or rubber-stamped ``मूल-पाठः``/``अनाम्नातम्``."""
  fake_sutra_phrases = (
    "बहुव्रीहौ समासस्य",
    "अव्ययीभावे प्रकृत्या पूर्वपदम्",
    "द्वन्द्वे प्रकृत्या पूर्वपदम्",
    "णिनिः नित्",
    "णिनि नित्",
    "इनिः नित्",
    "इनि नित्",
  )
  lyut_re = re.compile(r"ल्यु(?:ट्|ः|(?![अ-ह\u093e-\u094d]))")
  lyut_antodatta_allow = (
    "६.२.१५०",
    "६.२.१५१",
    "६.२.१४८",
    "६.२.१४९",
    "६.२.१५३",
    "६.२.१५४",
    "६.२.१६०",
    "६.२.१७२",
    "५.४.",
    "द्वन्द्व",
    "स्वरव्यत्यय",
    "स्वरान्यत्व",
    "छान्दस",
  )
  hits: list[str] = []
  for ln in pp_lines:
    it_list = parse_padapatha_items(ln)
    if not it_list:
      continue
    it = it_list[0]
    prov = it.prov
    if not prov:
      continue

    # 1. Out-of-bounds पा॰ A.P.S reference or fake grammatical claims (e.g. `णिनिः नित्`)
    bad_sutra = False
    for sm in _SUTRA_CITE_RE.finditer(prov):
      a_n = int(sm.group(1).translate(_DEVA_DIGIT_TRANS))
      p_n = int(sm.group(2).translate(_DEVA_DIGIT_TRANS))
      s1 = int(sm.group(3).translate(_DEVA_DIGIT_TRANS))
      s2 = int(sm.group(4).translate(_DEVA_DIGIT_TRANS)) if sm.group(4) else s1
      if not (1 <= a_n <= 8 and 1 <= p_n <= 4):
        bad_sutra = True
        break
      pmax = _ASHTADHYAYI_PADA_MAX[(a_n - 1) * 4 + (p_n - 1)]
      if not (1 <= s1 <= pmax and s1 <= s2 <= pmax):
        bad_sutra = True
        break
    if bad_sutra or any(fp in prov for fp in fake_sutra_phrases):
      hits.append(ln)
      continue

    # 2. Bare `समासस्वरः` without an explicit samāsa/taddhita/uṇādi/phiṭ rule (`पा॰ ६.१.१५८` eka-svara alone does not count)
    if "समासस्वर" in prov:
      prov_no_61158 = re.sub(r"पा॰\s*६\.१\.१५८(?![०-९0-9])", "", prov)
      if not any(k in prov_no_61158 for k in ("पा॰", "उणादि", "फि॰")):
        hits.append(ln)
        continue

    # 3. Rubber-stamped `अनाम्नातम्` or bare `मूल-पाठः` / `आरण्यक-पाठः` without grammatical derivation
    if "अनाम्नातम्" in prov:
      hits.append(ln)
      continue
    if ("मूल-पाठः" in prov or "आरण्यक-पाठः" in prov) and not any(
      k in prov for k in ("पा॰", "उणादि", "फि॰", "सामगान", "स्तोभ", "व्याहृति")
    ):
      hits.append(ln)
      continue

    # 4. `ल्यप्` (`अनुदात्तौ सुप्पितौ पा॰ ३.१.४`, `गतिकारकोपपदात् कृत् पा॰ ६.२.१३९`):
    #    final `-य` syllable of `ल्यप्` is never udātta, and leading `गति` before `-` is never udātta (unless नञ्).
    if "ल्यप्" in prov and "नञ्" not in prov and "?" not in it.ref:
      _, mks = syllables_with_marks(it.ref)
      if mks and mks[-1]:
        hits.append(ln)
        continue
      if "-" in it.ref:
        first_mem = it.ref.split("-", 1)[0]
        if has_us_accents(first_mem) and bare_devanagari(first_mem) in _GATI_HYPHEN_PREFIXES:
          hits.append(ln)
          continue

    # 5. `ल्यु`/`ल्युट्` (`पा॰ ६.१.१९३ लिति` + `पा॰ ६.२.१३९ गतिकारकोपपदात् कृत्`) misanalyzed as `६.१.२२३` antodātta
    #    (e.g. `- वाल-बन्धनः᳓ (ल्युट्/समासस्य पा॰ ६.१.२२३)` instead of `वाल-ब᳓न्धनः`):
    #    in compounds whose uttarapada ends in `-न`/`-ण` + case ending, udātta cannot fall on that `-न`/`-ण` syllable
    #    unless licensed by `६.२.१५०` (`अनो भावकर्मवचनः`), `६.२.१५१`, `६.२.१७२`, or `द्वन्द्व`.
    prov_primary = prov.split(";", 1)[0]
    if lyut_re.search(prov_primary) and "?" not in it.ref and not any(al in prov for al in lyut_antodatta_allow):
      if "-" in it.ref or "६.१.२२३" in prov_primary or "समासस्य" in prov_primary:
        last_mem = it.ref.split("-")[-1]
        if re.search(
          r"[क-हअ-औ][^-\s]*?[नण](?:(?:ा\u1cd3(?:य|त्|ः|न्|नि|भिः|भ्यः|नाम्|सु|म्)?)|(?:े\u1cd3(?:न|भ्यः|भिः|षु)?)|(?:ो\u1cd3ः)|(?:ौ\u1cd3)|(?:ी\u1cd3(?:ः|म्|भिः|भ्यः|नाम्|षु)?)|(?:[ंँः]?\u1cd3(?:म्|स्य|योः)?))$",
          last_mem,
        ):
          hits.append(ln)
          continue
  return hits


def find_vp_integrity_issues(vp_body: str) -> list[str]:
  """Check a ``विश्वास-प्रस्तुतिः`` block for ``virama+vowel`` glitches or unbalanced ``[[|]]`` brackets."""
  issues: list[str] = []
  # Glitches like `्अ` (without intervening space) usually come from broken syl joining.
  for m in re.finditer(r".{0,10}्[अआइईउऊऋएऐओऔ].{0,10}", vp_body):
    issues.append(f"virama_vowel: {m.group(0)!r}")
  cleaned = re.sub(r"\[\[(?:\d+|P\d+|\?+|!+|[^\[\]\n|]+\|[^\[\]\n|]+)\]\]", "", vp_body)
  if "[[" in cleaned or "]]" in cleaned:
    issues.append(f"unbalanced_brackets: {cleaned.strip()[:120]!r}")
  return issues


def validate_padapatha_block(
  header: str,
  pp_body: str,
  mula_body: str = "",
  vp_body: str = "",
  *,
  verified_prakrtibhava_pairs: AbstractSet[tuple[str, str]] | None = None,
  check_hiatus: bool = True,
  check_zero_accent: bool = True,
  check_unresolved_arrows: bool = True,
  check_upasarga_tinanta: bool = True,
  forbid_compound_upasarga_tinanta: bool = False,
  forbid_zero_abbreviation: bool = True,
  forbid_dubious_sources: bool = True,
  forbid_uncounted_corpus_tags: bool = True,
  forbid_rubberstamp_provenance: bool = True,
  check_nighata_arrows: bool = True,
  check_gati_kta: bool = True,
  check_homographs: bool = True,
) -> list[AccentValidationIssue]:
  """Run all integrity checks on a single ``(VP, मूलम्, पद-पाठः)`` mantra tuple."""
  issues: list[AccentValidationIssue] = []
  hdr_err = check_padapatha_header(header, pp_body)
  if hdr_err:
    issues.append(hdr_err)

  pp_lines = [ln.strip() for ln in pp_body.splitlines() if ln.strip().startswith("- ")]
  for ln in find_virama_matra_glitches(pp_lines):
    issues.append(AccentValidationIssue("virama_matra_glitch", "Invalid virāma+mātrā in padapāṭha", ln))

  if forbid_zero_abbreviation:
    for ln in pp_lines:
      if re.search(r"[\u0905-\u0939][\u093e-\u094d\u0901-\u0903]*\u0966", ln):
        issues.append(
          AccentValidationIssue(
            "zero_abbrev_sign",
            "Use Devanagari abbreviation sign पा॰ (U+0970), never digit-zero पा\u0966 (U+0966)",
            ln,
          )
        )

  if forbid_dubious_sources:
    for ln in find_forbidden_accent_sources(pp_lines):
      issues.append(
        AccentValidationIssue(
          "forbidden_accent_source",
          "Dubious accent sources *TA* and *EK* are forbidden in पद-पाठः (यान्त्रिकः) (*ŚB* is allowed)",
          ln,
        )
      )

  for ln in pp_lines:
    bad_zero = bool(re.search(r"\*[A-Za-zŚś]+\*-0(?![/0-9])", ln))
    if not bad_zero:
      for m_slash in re.finditer(r"\*[A-Za-zŚś]+\*-(\d+)/(\d+)\b", ln):
        m_cnt, n_cnt = int(m_slash.group(1)), int(m_slash.group(2))
        if n_cnt <= 0 or n_cnt <= m_cnt:
          bad_zero = True
          break
    if bad_zero:
      issues.append(
        AccentValidationIssue(
          "zero_corpus_count",
          "Corpus occurrence count must be positive (-M with M>=1, or -M/N with N>M>=0 and N>=1), never bare *-0 or *-M/0",
          ln,
        )
      )

  if forbid_uncounted_corpus_tags:
    for ln in find_uncounted_corpus_tags(pp_lines):
      issues.append(
        AccentValidationIssue(
          "uncounted_corpus_tag",
          "Corpus tag (*TS*, *RV*, *TB*, *TK*, *AV*, *ŚB*, *VS*, *KS*, *MS*) lacks positive -N frequency count",
          ln,
        )
      )

  if forbid_rubberstamp_provenance:
    for ln in find_invalid_or_rubberstamp_provenance(pp_lines):
      issues.append(
        AccentValidationIssue(
          "invalid_or_rubberstamp_provenance",
          "Fake/out-of-bounds पा॰ sūtra, bare समासस्वरः, misaccented ल्यप्, or unanalyzed मूल-पाठः/अनाम्नातम् provenance",
          ln,
        )
      )

  for ln in find_malformed_arrows(pp_lines):
    issues.append(AccentValidationIssue("malformed_arrow", "Multiple arrows on a single padapāṭha bullet", ln))

  if check_unresolved_arrows:
    for ln in find_unresolved_question_arrows(pp_lines):
      issues.append(AccentValidationIssue("unresolved_arrow", "Unresolved → **?** placeholder in padapāṭha", ln))

  if check_gati_kta:
    for ln in find_bad_gati_kta_purvapadas(pp_lines):
      issues.append(
        AccentValidationIssue(
          "bad_gati_kta_purvapada",
          "Gati+kta pūrvapada places udātta on -ta instead of gati (पा॰ ६.२.४९ गतिरनन्तरः + ६.२.१)",
          ln,
        )
      )

  if check_zero_accent:
    for ln in find_unlicensed_unaccented_padas(pp_lines):
      issues.append(
        AccentValidationIssue(
          "unlicensed_anudatta",
          "Zero-accent pada violates पा॰ ६.१.१५८ without explicit पा॰ ८.१.* / २.४.* nighāta rule",
          ln,
        )
      )

  if check_upasarga_tinanta:
    for ln in find_unsplit_upasarga_tinantas(
      pp_lines,
      forbid_compound_upasarga_tinanta=forbid_compound_upasarga_tinanta,
    ):
      msg = (
        "Tiṅanta retains unseparated upasarga (must split upasarga into its own bullet) or misclassifies nominal/kṛdanta"
        if forbid_compound_upasarga_tinanta
        else "Main-clause पा॰ ८.१.२८ tiṅanta retains unseparated upasarga or misclassifies nominal/kṛdanta"
      )
      issues.append(AccentValidationIssue("unsplit_upasarga_tinanta", msg, ln))

  for ln in find_multi_udatta_padas(pp_lines):
    issues.append(
      AccentValidationIssue(
        "multi_udatta",
        "Pada carries >1 accent violating पा॰ ६.१.१५८ without पा॰ ६.२.१४०/१४१ license",
        ln,
      )
    )

  mula_clean = re.sub(r"(?m)^\[\^[^\]]+\]:.*$", "", mula_body.strip())
  mula_clean = re.sub(r"\[\^[^\]]+\]", "", mula_clean)
  mula_clean = re.sub(r"\+\+\+\([^)]*\)\+\+\+", "", mula_clean)
  mula_clean = re.sub(r"\[\[([^|\]]*)\|([^\]]*)\]\]", r"\1", mula_clean)
  for ln in find_false_post_udatta_svarita_arrows(pp_lines, mula_clean):
    issues.append(AccentValidationIssue("false_svarita_arrow", "Classical ॑ after udātta allows ᳙ without vyatyasta arrow", ln))

  if check_nighata_arrows:
    for ln in find_false_nighata_arrows(pp_lines, mula_clean):
      issues.append(
        AccentValidationIssue(
          "false_nighata_arrow",
          "False पा॰ ८.१.२८/८.१.१९ de-accenting arrow at पादादि (८.१.१८), after तिङ्, after पादादि-आमन्त्रित (८.१.७२), चवायोगे (८.१.५९), or in यद्वृत्त/हि clause (८.१.६६/८.१.३४)",
          ln,
        )
      )

  if check_homographs:
    for ln in find_suspect_homograph_accents(pp_lines, mula_clean):
      issues.append(
        AccentValidationIssue(
          "suspect_homograph_accent",
          "Sense-sensitive homograph or parasavarṇa ablative uses unjustified rare/wrong-sense accent or case",
          ln,
        )
      )

  for ln in find_tinanta_sutra_on_non_tinanta(pp_lines):
    issues.append(
      AccentValidationIssue(
        "tinanta_sutra_misapplied",
        "Tiṅ-adhikāra sūtra (पा॰ ८.१.२८–६८, e.g. हि च ८.१.३४ / यद्वृत्तान्नित्यम् ८.१.६६) misapplied to non-tiṅanta or across हि clause boundary",
        ln,
      )
    )

  for ln in find_missing_aa_upasarga_splits(pp_lines):
    issues.append(
      AccentValidationIssue(
        "missing_aa_upasarga_split",
        "Final udātta before अ-verb or double-canceling आ + अ-verb arrows indicates आ᳓ + verb sandhi (पा॰ ८.२.५)",
        ln,
      )
    )

  if check_hiatus:
    for w1, w2, span in find_unexplained_aa_hiatuses(pp_lines, mula_clean, verified_prakrtibhava_pairs=verified_prakrtibhava_pairs):
      issues.append(AccentValidationIssue("aa_hiatus", f"Uncoalesced -अ/-आ + vowel hiatus {w1} + {w2}", span))

  if vp_body:
    for msg in find_vp_integrity_issues(vp_body):
      issues.append(AccentValidationIssue("vp_integrity", msg))
  return issues


def validate_accented_markdown(
  text: str,
  *,
  verified_prakrtibhava_pairs: AbstractSet[tuple[str, str]] | None = None,
  check_html_balance: bool = True,
  check_hiatus: bool = True,
  check_vp: bool = True,
  forbid_compound_upasarga_tinanta: bool | None = None,
  forbid_zero_abbreviation: bool | None = None,
  forbid_uncounted_corpus_tags: bool | None = None,
  forbid_rubberstamp_provenance: bool = True,
) -> list[AccentValidationIssue]:
  """Validate all ``पद-पाठः (यान्त्रिकः)`` and ``विश्वास-प्रस्तुतिः`` blocks in one Markdown document."""
  issues: list[AccentValidationIssue] = []
  if check_html_balance:
    if text.count("<details") != text.count("</details>") or text.count("<div") != text.count("</div>"):
      issues.append(AccentValidationIssue("tag_unbalanced", "Mismatched <details> or <div> closing tags"))

  blocks = [(m.start(), m.end(), m.group(1).strip(), m.group(2)) for m in DETAILS_RE.finditer(text)]
  for i, (s, _, hdr, body) in enumerate(blocks):
    if not hdr.startswith("पद-पाठः (यान्त्रिकः"):
      continue
    mula_b = ""
    mula_prio = -1
    vp_b = ""
    is_sb_cluster = False
    for j in range(i - 1, -1, -1):
      _, je, jh, jb = blocks[j]
      if jh.startswith("पद-पाठः (यान्त्रिकः"):
        break
      if "\n##" in text[je:s]:
        break
      if s - je > 12000:
        break
      if jh in ("मूलम् - Weber", "मूलम् - श्रीधरादि"):
        is_sb_cluster = True
      if jh.startswith("मूलम्"):
        # Prefer accented मूलम् (Weber > श्रीधरादि > plain मूलम्) over unaccented विस्वरम् / Makoto.
        prio = 3 if "Weber" in jh else (2 if "श्रीधरादि" in jh else (0 if ("विस्वर" in jh or "Makoto" in jh) else 1))
        if prio > mula_prio:
          mula_b = jb
          mula_prio = prio
      if check_vp and not vp_b and jh.startswith("विश्वास-प्रस्तुतिः"):
        vp_b = jb
    forbid_up_tin = is_sb_cluster if forbid_compound_upasarga_tinanta is None else forbid_compound_upasarga_tinanta
    forbid_zero_ab = True if forbid_zero_abbreviation is None else forbid_zero_abbreviation
    forbid_unc_tags = (not is_sb_cluster) if forbid_uncounted_corpus_tags is None else forbid_uncounted_corpus_tags
    issues.extend(
      validate_padapatha_block(
        hdr,
        body,
        mula_b,
        vp_b,
        verified_prakrtibhava_pairs=verified_prakrtibhava_pairs,
        check_hiatus=check_hiatus,
        forbid_compound_upasarga_tinanta=forbid_up_tin,
        forbid_zero_abbreviation=forbid_zero_ab,
        forbid_uncounted_corpus_tags=forbid_unc_tags,
        forbid_rubberstamp_provenance=forbid_rubberstamp_provenance,
      )
    )
  return issues


def _strip_spans(text: str, spans: Sequence[tuple[int, int]]) -> str:
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


def validate_paired_vp_and_tk(
  vp_text: str,
  tk_text: str,
  *,
  verified_prakrtibhava_pairs: AbstractSet[tuple[str, str]] | None = None,
  check_html_balance: bool = True,
  check_hiatus: bool = True,
  forbid_zero_abbreviation: bool | None = None,
  forbid_uncounted_corpus_tags: bool = True,
  forbid_rubberstamp_provenance: bool = True,
) -> list[AccentValidationIssue]:
  """Validate a split ``vishvAsa-prastutiH`` (``vp``) + ``sarvASh_TIkAH`` (``tk`` = ``टीका``/``मूलम्``/``पद-पाठः``) file pair."""
  js_tk = find_js_include_spans(tk_text)
  tk_outer = _strip_spans(tk_text, js_tk)
  if check_html_balance and (tk_text.count("<details") != tk_text.count("</details>") or tk_text.count("<div") != tk_text.count("</div>")):
    issues = [AccentValidationIssue("tag_unbalanced", "Mismatched <details> or <div> closing tags")]
  else:
    issues = []
  issues.extend(
    validate_accented_markdown(
      tk_outer,
      verified_prakrtibhava_pairs=verified_prakrtibhava_pairs,
      check_html_balance=False,
      check_hiatus=check_hiatus,
      check_vp=False,
      forbid_zero_abbreviation=forbid_zero_abbreviation,
      forbid_uncounted_corpus_tags=forbid_uncounted_corpus_tags,
      forbid_rubberstamp_provenance=forbid_rubberstamp_provenance,
    )
  )
  vp_body = vp_text.split("+++", 2)[2] if vp_text.startswith("+++") and len(vp_text.split("+++", 2)) == 3 else vp_text
  js_vp = find_js_include_spans(vp_body)
  vp_outer = _strip_spans(vp_body, js_vp)
  for msg in find_vp_integrity_issues(vp_outer):
    issues.append(AccentValidationIssue("vp_integrity", msg))
  return issues
