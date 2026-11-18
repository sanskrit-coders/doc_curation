"""Validators for US/classical Vedic accent notation, ``पद-पाठः (यान्त्रिकः)`` blocks, and ``विश्वास-प्रस्तुतिः`` integrity."""

from __future__ import annotations

import dataclasses
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
)

SCHEME = sanscript.SCHEMES[sanscript.DEVANAGARI]
LINE_BREAK_PAUSES = r"[।॥,;]+"

VALID_ANUDATTA_RULE_TAGS: tuple[str, ...] = (
  "८.१.२८",
  "८.१.१८",
  "८.१.१९",
  "८.१.३",
  "८.१.७०",
  "८.१.७१",
  "२.४.३२",
  "२.४.३४",
  "६.१.१९१",
  "सर्वस्य सुपि",
  "सर्वानुदात्त",
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
  "अभवत्",
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
  "अविशताम्",
  "अवित्सि",
  "अविन्दन्",
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
  "अतीताम्",
  "सुवः",
  "अवीः",
  "ऐत्",
  "आयन्",
  "आस्यत्",
  "सुषुप्थाः",
  "अविदत्",
  "अविदम्",
  "अपतत्",
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
  ("ब्रह्म", "उत्तरा"),
  ("ऊत", "एकम्"),
  ("इन्द्रियाय", "ऋषिभ्यः"),
  ("सम्मा", "असि"),
  ("उन्मा", "असि"),
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
  mula_joined_bare = accent.strip_accents(re.sub(r"\s+", " ", flat_mula).strip())
  hits: list[tuple[str, str, str]] = []
  for pi in range(len(padas) - 1):
    w1, w2 = padas[pi], padas[pi + 1]
    if (w1, w2) in allow:
      continue
    s1 = sanscript.transliterate(w1.replace("-", ""), sanscript.DEVANAGARI, sanscript.SLP1)
    s2 = sanscript.transliterate(w2.replace("-", ""), sanscript.DEVANAGARI, sanscript.SLP1)
    if s1 and s2 and s1[-1] in ("a", "A") and s2[0] in ("a", "A", "i", "I", "u", "U", "f", "e", "E", "o", "O"):
      w1_c = w1.replace("-", "")
      w2_c = w2.replace("-", "")
      pat = rf"{re.escape(w1_c[-3:] if len(w1_c) >= 3 else w1_c)}\s+{re.escape(w2_c[:2])}"
      m_unm = re.search(pat, mula_joined_bare)
      if m_unm and not any(d in mula_joined_bare[m_unm.start():m_unm.end()] for d in "।॥;"):
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


def find_unlicensed_unaccented_padas(pp_lines: Sequence[str]) -> list[str]:
  """Return padapāṭha bullet lines whose target has 0 accents without a Pāṇini ``8.1.*``/``2.4.*`` nighāta license."""
  hits: list[str] = []
  for ln in pp_lines:
    it_list = parse_padapatha_items(ln)
    if not it_list:
      continue
    it = it_list[0]
    if "?" in it.ref or has_us_accents(it.ref):
      continue
    if bare_devanagari(it.ref) in ("भूः", "ओम्"):
      continue
    if not any(tag in it.prov for tag in VALID_ANUDATTA_RULE_TAGS):
      hits.append(ln)
  return hits


def find_unsplit_upasarga_tinantas(pp_lines: Sequence[str]) -> list[str]:
  """Return main-clause tiṅanta bullets that retain an unseparated upasarga or misclassify a nominal.

  Catches both:
  1. Unaccented ``पा० ८.१.२८`` bullets retaining a leading upasarga (including coalesced ``ऐतु``/``अवैत्``) or nominal ending.
  2. Accented ``upasarga + tiṅanta`` bullets (e.g. ``- प्रचोद᳓यात् (*TS*, *RV*; *TS*, *RV*, *TB*)``) whose provenance
     lacks an explicit subordinate-clause license (``पा० ८.१.६६``, ``८.१.३४``, ``८.१.३०``, ``८.१.५९``, ``८.१.६३``, ``८.१.७१``).
  """
  hits: list[str] = []
  nominal_8128_endings = ("तः", "ताः", "तौ", "तिः", "निः", "नीः", "लः", "रः", "णः", "कः", "शः", "षः", "नः", "भः", "यः", "हः", "भिः", "भ्यः", "षु", "सु", "स्य", "नाम्", "णाम्")
  finite_sip_allow = frozenset({
    "आः", "अकः", "अभूः", "अधाः", "अदाः", "अस्थाः", "अपाः", "अगाः", "अजाः", "आवाः", "अप्राः",
    "अहः", "वेत्थ", "आत्थ", "तारिषः", "मोषीः", "भैषीः", "शारीः", "अस्य", "सुवः", "कः", "वृहः",
    "रीरिषः", "अबिभः", "मांस्ताः", "जीह्वरः", "दहः", "उरुष्यः", "अवीः", "पूरिष्ठाः", "अहाः",
  })
  coalesced_up_tinantas = frozenset({"ऐतु", "अवैत्", "प्रैत्", "उपैत्", "उपैति", "प्रेरते", "उपेहि", "अपेहि", "एहि", "परेहि", "परीहि"})
  subordinate_verb_tags = ("८.१.६६", "८.१.३४", "८.१.३०", "८.१.५९", "८.१.६३", "८.१.७१", "८.१.७२", "पादादि")
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
    if bare in SIMPLEX_TINANTA_ALLOWLIST or bare in ("अवद्यात्", "उपास्य"):
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
      if any(bare.startswith(up) and len(bare) > len(up) + 1 for up in UPASARGA_PREFIXES):
        hits.append(ln)
    else:
      # Catch missed पा० ८.१.२८ svara-nighāta on Vedic 2pl imperative -तन/-थन (e.g. युयोतन → **युयो᳓तन**)
      if "→ **" in ln and not has_us_accents(it.ar) and bare.endswith(("तन", "थन")) and not any(t in it.prov for t in subordinate_verb_tags):
        hits.append(ln)
        continue
      if any(t in it.prov for t in subordinate_verb_tags) or any(t in it.prov for t in nominal_prov_tags):
        continue
      if bare in UPASARGA_PREFIXES or bare in ("सम्", "निस्", "निर्", "दुस्", "दुर्", "उद्"):
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
              rest.endswith(("यात्", "याताम्", "न्ताम्", "थाम्", "ध्वम्", "मसि", "महि", "ैषम्", "ार्षम्"))
              and not bare.endswith(("ताम्", "नाम्", "णाम्"))
            )
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
      if any(tag in it.prov for tag in ("६.२.१४०", "६.२.१४१", "देवताद्वन्द्व", "उभे वनस्पत्यादिषु")) or any(st in bare for st in dual_accent_stems):
        continue
      hits.append(ln)
  return hits


def find_vp_integrity_issues(vp_body: str) -> list[str]:
  """Check a ``विश्वास-प्रस्तुतिः`` block for ``virama+vowel`` glitches or unbalanced ``[[|]]`` brackets."""
  issues: list[str] = []
  # Glitches like `्अ` (without intervening space) usually come from broken syl joining.
  for m in re.finditer(r".{0,10}्[अआइईउऊऋएऐओऔ].{0,10}", vp_body):
    issues.append(f"virama_vowel: {m.group(0)!r}")
  cleaned = re.sub(r"\[\[(?:\d+|P\d+|\?\?|[^\[\]\n|]+\|[^\[\]\n|]+)\]\]", "", vp_body)
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
) -> list[AccentValidationIssue]:
  """Run all integrity checks on a single ``(VP, मूलम्, पद-पाठः)`` mantra tuple."""
  issues: list[AccentValidationIssue] = []
  hdr_err = check_padapatha_header(header, pp_body)
  if hdr_err:
    issues.append(hdr_err)

  pp_lines = [ln.strip() for ln in pp_body.splitlines() if ln.strip().startswith("- ")]
  for ln in find_virama_matra_glitches(pp_lines):
    issues.append(AccentValidationIssue("virama_matra_glitch", "Invalid virāma+mātrā in padapāṭha", ln))

  if check_unresolved_arrows:
    for ln in find_unresolved_question_arrows(pp_lines):
      issues.append(AccentValidationIssue("unresolved_arrow", "Unresolved → **?** placeholder in padapāṭha", ln))

  if check_zero_accent:
    for ln in find_unlicensed_unaccented_padas(pp_lines):
      issues.append(
        AccentValidationIssue(
          "unlicensed_anudatta",
          "Zero-accent pada violates पा० ६.१.१५८ without explicit पा० ८.१.* / २.४.* nighāta rule",
          ln,
        )
      )

  if check_upasarga_tinanta:
    for ln in find_unsplit_upasarga_tinantas(pp_lines):
      issues.append(
        AccentValidationIssue(
          "unsplit_upasarga_tinanta",
          "Main-clause पा० ८.१.२८ tiṅanta retains unseparated upasarga or misclassifies nominal/kṛdanta",
          ln,
        )
      )

  for ln in find_multi_udatta_padas(pp_lines):
    issues.append(
      AccentValidationIssue(
        "multi_udatta",
        "Pada carries >1 accent violating पा० ६.१.१५८ without पा० ६.२.१४०/१४१ license",
        ln,
      )
    )

  mula_clean = re.sub(r"\+\+\+\([^)]*\)\+\+\+", "", mula_body.strip())
  mula_clean = re.sub(r"\[\[([^|\]]*)\|([^\]]*)\]\]", r"\1", mula_clean)
  for ln in find_false_post_udatta_svarita_arrows(pp_lines, mula_clean):
    issues.append(AccentValidationIssue("false_svarita_arrow", "Classical ॑ after udātta allows ᳙ without vyatyasta arrow", ln))

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
    vp_b = ""
    for j in range(i - 1, -1, -1):
      _, je, jh, jb = blocks[j]
      if s - je > 3500:
        break
      if not mula_b and jh.startswith("मूलम्"):
        mula_b = jb
      if check_vp and not vp_b and jh.startswith("विश्वास-प्रस्तुतिः"):
        vp_b = jb
      if mula_b and (vp_b or not check_vp):
        break
    issues.extend(
      validate_padapatha_block(
        hdr,
        body,
        mula_b,
        vp_b,
        verified_prakrtibhava_pairs=verified_prakrtibhava_pairs,
        check_hiatus=check_hiatus,
      )
    )
  return issues


def validate_paired_vp_and_tk(
  vp_text: str,
  tk_text: str,
  *,
  verified_prakrtibhava_pairs: AbstractSet[tuple[str, str]] | None = None,
  check_html_balance: bool = True,
  check_hiatus: bool = True,
) -> list[AccentValidationIssue]:
  """Validate a split ``vishvAsa-prastutiH`` (``vp``) + ``sarvASh_TIkAH`` (``tk`` = ``टीका``/``मूलम्``/``पद-पाठः``) file pair."""
  js_tk = find_js_include_spans(tk_text)
  tk_outer = "".join(tk_text[i : i + 1] for i in range(len(tk_text)) if not any(a <= i < b for a, b in js_tk))
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
    )
  )
  vp_body = vp_text.split("+++", 2)[2] if vp_text.startswith("+++") and len(vp_text.split("+++", 2)) == 3 else vp_text
  js_vp = find_js_include_spans(vp_body)
  vp_outer = "".join(vp_body[i : i + 1] for i in range(len(vp_body)) if not any(a <= i < b for a, b in js_vp))
  for msg in find_vp_integrity_issues(vp_outer):
    issues.append(AccentValidationIssue("vp_integrity", msg))
  return issues
