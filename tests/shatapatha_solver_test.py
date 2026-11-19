"""Comprehensive unit & integration tests for ``doc_curation.sanskrit.accent.shatapatha_solver``."""
from __future__ import annotations

import json
import os
import re
import tempfile

import pytest

from doc_curation.sanskrit.accent.reconciler import (
  _extract_vp_pieces,
  apply_marks_to_token,
  bare_devanagari,
  syllables_with_marks,
)
from doc_curation.sanskrit.accent.sandhi_check import to_norm_slp, verify_mantra_sandhi
from doc_curation.sanskrit.accent.shatapatha import extract_sb_syllables
from doc_curation.sanskrit.accent.shatapatha_solver import (
  KandikaCluster,
  UnifiedVedicLexicon,
  _derive_paninian_tinanta_accent,
  _pause_norm_slp,
  _fast_apply_us_marks,
  _fast_extract_sb_syllables,
  _fast_extract_vp_pieces,
  _fast_syllable_count,
  _fast_syllables_with_marks,
  _mw_deva_to_us,
  _strip_leading_upasargas_tinanta,
  build_clean_vp_base,
  classical_padapatha_to_us,
  decode_sb_accents_viterbi,
  default_data_available,
  enrich_padapatha_corpus_counts,
  export_adjudication_jsonl,
  iast_accented_to_deva_us,
  lookup_corpus_counts,
  parse_sb_markdown_clusters,
  solve_kandika,
  solve_sb_file,
  split_vp_to_padas,
  split_vp_to_padas_with_clauses,
)


@pytest.fixture(scope="module")
def lex() -> UnifiedVedicLexicon:
  if not default_data_available():
    pytest.skip("indic-dict padasvara lexica / VS corpus not installed locally")
  return UnifiedVedicLexicon.load_or_build(force_rebuild=False)


# ---------------------------------------------------------------------------
# 1. Fast Devanagari syllable & US accent primitives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
  "tok,marks",
  [
    ("सं-स्थिते", ("U", "", "")),
    ("सँ-स्थिते", ("U", "", "")),
    ("अपः", ("", "U")),
    ("व्रतम्", ("", "U")),
    ("अग्निः", ("", "U")),
    ("आसीत्", ("U", "")),
    ("प्रणयति", ("U", "", "", "")),
    ("अन्-अशनम्", ("U", "", "", "")),
    ("स्वः", ("S",)),
    ("मनुष्याः", ("", "", "S")),
    ("गा᳓र्हपत्यम्", ("U", "", "", "")),
    ("अग्निहोत्र-हवणीम्", ("", "", "", "", "U", "", "")),
  ],
)
def test_fast_apply_us_marks_matches_reconciler_verbatim(tok: str, marks: tuple[str, ...]):
  expected = apply_marks_to_token(tok, marks)
  got = _fast_apply_us_marks(tok, marks)
  assert got == expected
  assert _fast_syllable_count(tok) == len(marks)


# ---------------------------------------------------------------------------
# 2. Classical padapāṭha, IAST, and MW accent converters
# ---------------------------------------------------------------------------


def test_classical_padapatha_to_us():
  # Monosyllables: unmarked = udātta, with anudātta `॒` = anudātta, TS `प्र॑` = udātta, `स्वः॑` = jātya svarita
  assert classical_padapatha_to_us("तत्")[:2] == ("तत्", ("U",))
  assert classical_padapatha_to_us("च॒")[:2] == ("च", ("",))
  assert classical_padapatha_to_us("प्र॑")[:2] == ("प्र", ("U",))
  assert classical_padapatha_to_us("स्वः॑")[:2] == ("स्वः", ("S",))

  # Polysyllables: anudātta before udātta, svarita after udātta
  assert classical_padapatha_to_us("अ॒ग्निः")[:2] == ("अग्निः", ("", "U"))
  assert classical_padapatha_to_us("स॒त्यम्")[:2] == ("सत्यम्", ("", "U"))
  assert classical_padapatha_to_us("पुरु॑षः")[:2] == ("पुरुषः", ("U", "", ""))
  assert classical_padapatha_to_us("प॒वि॒त्रम्")[:2] == ("पवित्रम्", ("", "", "U"))

  # All-anudātta finite verb
  assert classical_padapatha_to_us("भ॒व॒ति॒")[:2] == ("भवति", ("", "", ""))

  # Independent jātya svarita (preceded by anudātta, syllable has ्[यव])
  assert classical_padapatha_to_us("म॒नु॒ष्याः॑")[:2] == ("मनुष्याः", ("", "", "S"))
  assert classical_padapatha_to_us("वी॒र्य॑म्")[:2] == ("वीर्यम्", ("", "S"))

  # AV double-svarita `᳡` (U+1CE1): post-udātta (`वज्र᳡म्` -> `व᳓ज्रम्`) and jātya (`वी॒र्य᳡म्` -> `वीर्य᳙म्`)
  assert classical_padapatha_to_us("वज्र᳡म्")[:2] == ("वज्रम्", ("U", ""))
  assert classical_padapatha_to_us("वी॒र्य᳡म्")[:2] == ("वीर्यम्", ("", "S"))

  # Dual-accent devatā-dvandva (returned key uses `_normalize_lookup_key`: `न्द` -> `ंद`)
  res_dual = classical_padapatha_to_us("इन्द्रा॑ऽबृ॒हस्प॑ती")
  assert res_dual is not None
  bare, mks, hyph = res_dual
  assert bare == "इंद्राबृहस्पती"
  assert mks.count("U") >= 1


def test_iast_accented_to_deva_us_preserves_palatal_sh():
  # Critical regression test: NFD must NOT strip acute off `ś` (`śámyā` -> `श᳓म्या`, NOT `सम्या`!)
  res1 = iast_accented_to_deva_us("śámyā")
  assert res1 is not None
  assert res1[0] == "शम्या"
  assert res1[1] == ("U", "")

  res2 = iast_accented_to_deva_us("śúci")
  assert res2 is not None
  assert res2[0] == "शुचि"
  assert res2[1] == ("U", "")

  # Grave/circumflex independent svarita
  res3 = iast_accented_to_deva_us("vīryàm")
  assert res3 is not None
  assert res3[0] == "वीर्यम्"
  assert res3[1] == ("", "S")

  # Etymological hyphenated IAST stem decodes exact bare Devanagari & US marks
  res4 = iast_accented_to_deva_us("gā́rha-patya")
  assert res4 is not None
  assert res4[0] == "गार्हपत्य"
  assert res4[1] == ("U", "", "", "")


def test_mw_deva_to_us_rejoins_virama_vowels():
  # `अ॑न्-अशन` -> bare `अनशन` (NOT `अन्अशन`!), hyphenated `अन्-अशन`, ādyudātta
  res = _mw_deva_to_us("अ॑न्-अशन")
  assert res is not None
  bare, mks, hyph = res
  assert bare == "अनशन"
  assert mks == ("U", "", "", "")
  assert hyph == "अन्-अशन"

  # Compound em-dash `—`
  res2 = _mw_deva_to_us("व्रत—प॑ति")
  assert res2 is not None
  assert res2[0] == "व्रतपति"
  assert res2[2] == "व्रत-पति"


# ---------------------------------------------------------------------------
# 3. Markdown cluster parser (all ŚB corpus quirks)
# ---------------------------------------------------------------------------


def test_parse_sb_markdown_clusters_handles_corpus_quirks():
  sample_md = """+++
title = "test"
+++

<details open><summary>विश्वास-प्रस्तुतिः</summary>

हरिः-ओ३म्।
</details>

##  ०१

<details open><summary>विश्वास-प्रस्तुतिः</summary>

स वै᳓
</details>

<details><summary>विश्वास-टिप्पनी</summary>

note here
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

स वै᳘
</details>

<details><summary>मूलम् - Weber</summary>

स वै᳘
</details>

<details><summary>मूलम् - विस्वरम्</summary>

स वै ॥ १ ॥
</details>

<details><summary>Eggeling</summary>

He indeed.
</details>

<details><summary>मूलम् - Makoto</summary>

sa vai
</details>

## ०२

<details open><summary>विश्वास-प्रस्तुतिः</summary>

अग्नि᳘र्वै
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

अग्नि᳘र्वै
</details>

<details><summary>मूलम् - Weber</summary>

अग्नि᳘र्वै
</details>

<details open><summary>विश्वास-प्रस्तुतिः</summary>

सो᳘मो वै
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

सो᳘मो वै
</details>
"""
  clusters = parse_sb_markdown_clusters(sample_md)
  # Pre-`##` intro skipped; `##  ०१` double-space parsed; `## ०२` yields TWO clusters (`०२` and `०२#1`)
  assert len(clusters) == 3
  assert clusters[0].key == "०१"
  assert clusters[0].is_already_us is True
  assert clusters[0].weber == "स वै᳘"
  assert clusters[0].shri == "स वै᳘"
  assert clusters[0].eggeling == "He indeed."

  assert clusters[1].key == "०२"
  assert clusters[1].is_already_us is False
  assert clusters[1].weber == "अग्नि᳘र्वै"

  assert clusters[2].key == "०२#1"
  assert clusters[2].sub_idx == 1
  assert clusters[2].weber == ""
  assert clusters[2].shri == "सो᳘मो वै"


# ---------------------------------------------------------------------------
# 4. 3-Witness clean VP builder
# ---------------------------------------------------------------------------


def test_build_clean_vp_base_three_witness_consensus():
  # Visvara preamble + trailing `॥ १ ॥` cleanly trimmed when matching W/S
  vp, src = build_clean_vp_base(
    weber="त᳘स्मादा᳘पो वै᳘॥",
    shri="त᳘स्मादा᳘पो वै᳘॥",
    visvara="प्रथमं ब्राह्मणम् ।\nतस्मादापो वै ॥ १ ॥",
  )
  assert src == "visvara"
  assert "प्रथमं" not in vp
  assert "१" not in vp
  assert vp.startswith("तस्मादापो")

  # Solo visvara OCR typo (`नैवाश्रीयात्` vs W==S `नैवाश्नीयात्`) MUST reject visvara!
  vp2, src2 = build_clean_vp_base(
    weber="तन्न्वे᳘वा᳘नवकॢप्तम्। तस्मा᳘दु नै᳘वाश्नीयात्॥",
    shri="तन्न्वे᳘वा᳘नवकॢप्तम्। तस्मा᳘दु नै᳘वाश्नीयात्॥",
    visvara="तन्वेवानवकॢप्तम् । तस्मादु नैवाश्रीयात् ॥",
  )
  assert src2 != "visvara"
  assert "नैवाश्नीयात्" in vp2

  # Solo Weber OCR typo (`प्रजा᳘पतिह्` vs S==V `प्रजापतिः`) prefers Shri/Visvara!
  vp3, src3 = build_clean_vp_base(
    weber="अनिरुक्तो वै᳘ प्रजा᳘पतिह्॥",
    shri="अनिरुक्तो वै᳘ प्रजा᳘पतिः॥",
    visvara="अनिरुक्तो वै प्रजापतिः ॥",
  )
  assert "प्रजापतिः" in vp3
  assert "प्रजापतिह्" not in vp3


# ---------------------------------------------------------------------------
# 5. Padapāṭha splitter & CRITICAL RULE #1 (upasarga + tiṅanta separation)
# ---------------------------------------------------------------------------


def test_rule1_upasarga_tinanta_always_separated_and_krdantas_hyphenated(lex: UnifiedVedicLexicon):
  # Single and double upasarga + finite tiṅanta MUST be separated into individual bullets
  assert _strip_leading_upasargas_tinanta("upaspfSati", lex) == ["उप", "स्पृशति"]
  assert _strip_leading_upasargas_tinanta("udyacCati", lex) == ["उत्", "यच्छति"]
  assert _strip_leading_upasargas_tinanta("upAvartate", lex) == ["उप", "आ", "वर्तते"]
  assert _strip_leading_upasargas_tinanta("udAharati", lex) == ["उत्", "आ", "हरति"]
  assert _strip_leading_upasargas_tinanta("aBisampAdayati", lex) == ["अभि", "सम्", "पादयति"]

  # Pronouns, adverbs, and nouns MUST NOT be split as prefixed tiṅantas!
  assert _strip_leading_upasargas_tinanta("etam", lex) is None
  assert _strip_leading_upasargas_tinanta("upavasaTaH", lex) is None
  assert _strip_leading_upasargas_tinanta("uttarataH", lex) is None
  assert _strip_leading_upasargas_tinanta("antarataH", lex) is None

  # Gatikṛdantas (participles, gerunds, infinitives) stay hyphenated as ONE bullet!
  padas_krt = split_vp_to_padas("व्रतमुपैष्यन् संस्थिते अतिहृत्य उद्यन्तुम्", lex)
  assert "उप-एष्यन्" in padas_krt
  assert any(p in ("सं-स्थिते", "सम्-स्थिते") for p in padas_krt)
  assert "अति-हृत्य" in padas_krt
  assert any(p in ("उद्-यन्तुम्", "उत्-यन्तुम्") for p in padas_krt)

  # Complex ŚB sandhi chains: `उपावर्तते`, `तन्न्वेव`, `नो अनाप्ताः`, `यद्वेवास्यात्र`, `तच्छकेयम्`
  p1 = split_vp_to_padas("तन्न्वेवानवकॢप्तम्", lex)
  assert p1[:3] == ["तत्", "नु", "एव"]
  assert verify_mantra_sandhi(p1, "तन्न्वेवानवकॢप्तम्")[0]

  p2 = split_vp_to_padas("नो अनाप्ताः सादयेत्", lex)
  assert p2[:2] == ["न", "उ"]
  assert verify_mantra_sandhi(p2, "नो अनाप्ताः सादयेत्")[0]

  p3 = split_vp_to_padas("तच्छकेयम्", lex)
  assert p3 == ["तत्", "शकेयम्"]

  p4 = split_vp_to_padas("मेध्या वा आपः", lex)
  assert p4 == ["मेध्याः", "वै", "आपः"]

  p5 = split_vp_to_padas("स यदप उपस्पृशति य उपावर्तते", lex)
  assert ["उप", "स्पृशति"] == [p5[3], p5[4]]
  assert ["उप", "आ", "वर्तते"] == p5[6:9]

  # Precision-audit regressions:
  # 1) Prefixed perfect `अन्वाह` -> `अनु + आह` (Rule #1)
  assert _strip_leading_upasargas_tinanta("anvAha", lex) == ["अनु", "आह"]
  assert _strip_leading_upasargas_tinanta("prAha", lex) == ["प्र", "आह"]
  # 2) `अन्तर्धाय` MUST NOT split into `अन्तः + धाय`
  p6 = split_vp_to_padas("अथ तृणमन्तर्धाय प्रहरति", lex)
  assert "धाय" not in p6
  # 3) `ऋतवः` MUST NOT get bogus plural hyphen `ऋत-वः`
  p7 = split_vp_to_padas("सर्व ऋतवः", lex)
  assert "ऋतवः" in p7 and "ऋत-वः" not in p7
  # 4) `अनुमन्त्रयामहा इति` -> `-आमहै`, never bogus `मन्त्रयाम + हाः`
  p8 = split_vp_to_padas("ऋतूनेवानुमन्त्रयामहा इति", lex)
  assert "हाः" not in p8
  # 5) Particle `वै` MUST NEVER be tagged as vocative (`पा॰ ८.१.१९`)
  cl_vai = KandikaCluster(
    heading="१९", sub_idx=0, vp_summary="विश्वास-प्रस्तुतिः", vp_body="", is_already_us=False,
    weber="ब्रह्म वै पलाशः॥", shri="ब्र᳘ह्म वै पला᳘शः॥", visvara="ब्रह्म वै पलाशः ॥",
  )
  r_vai = solve_kandika(cl_vai, lex, kandika_id="test::vai")
  assert not any("८.१.१९" in it.prov for it in r_vai.items)


# ---------------------------------------------------------------------------
# 6. 3-State Viterbi decoder & self-certification precision gates
# ---------------------------------------------------------------------------


def test_viterbi_main_vs_subordinate_upasarga_and_8_2_6_svarita(lex: UnifiedVedicLexicon):
  # Main clause: `अप उपस्पृशति` -> `अपः᳓`, `उ᳓प`, `स्पृशति` (पा॰ ८.१.२८)
  items_main, _, unm_main = decode_sb_accents_viterbi(
    "अप उपस्पृशति",
    ["अपः", "उप", "स्पृशति"],
    weber_text="अप᳘ उ᳘पस्पृशति",
    shri_text="अप᳘ उ᳘पस्पृशति",
    lex=lex,
  )
  assert not unm_main
  assert [it.ref for it in items_main] == ["अपः᳓", "उ᳓प", "स्पृशति"]

  # Subordinate clause: `यदप उपस्पृशति` -> `य᳓त्`, `अपः᳓`, `उप`, `स्पृश᳓ति` (पा॰ ८.१.७१ + पा॰ ८.१.६६)
  items_sub, _, unm_sub = decode_sb_accents_viterbi(
    "यदप उपस्पृशति",
    ["यत्", "अपः", "उप", "स्पृशति"],
    weber_text="य᳘दप᳘ उपस्पृश᳘ति",
    shri_text="य᳘दप᳘ उपस्पृश᳘ति",
    lex=lex,
  )
  assert not unm_sub
  assert [it.ref for it in items_sub] == ["य᳓त्", "अपः᳓", "उप", "स्पृश᳓ति"]
  assert "८.१.७१" in items_sub[2].prov
  assert "८.१.६६" in items_sub[3].prov


def test_preserve_already_us_vp_verbatim(lex: UnifiedVedicLexicon):
  gold_vp = "स᳓ वै᳓ अपः᳓ उ᳓पस्पृशति ॥"
  cl = KandikaCluster(
    heading="०१",
    sub_idx=0,
    vp_summary="विश्वास-प्रस्तुतिः (स्वराङ्किता)",
    vp_body=gold_vp,
    is_already_us=True,
    weber="स वै᳘ अप᳘ उ᳘पस्पृशति॥",
    shri="स वै᳘ अप᳘ उ᳘पस्पृशति॥",
    visvara="स वै अप उपस्पृशति ॥",
  )
  res = solve_kandika(cl, lex, kandika_id="test::०१")
  assert res.preserve_vp is True
  assert res.vp_accented == gold_vp
  assert [it.ref for it in res.items] == ["सः᳓", "वै᳓", "अपः᳓", "उ᳓प", "स्पृशति"]


def _unelide(text: str) -> str:
  """Restore prodelided `अ` (`ते ऽपः` → `ते अपः`): gold may un-elide at clause breaks."""
  return text.replace("ऽ", "अ")


def _marks(text: str) -> list[str]:
  return syllables_with_marks(_unelide(text))[1]


def _word_norm(text: str) -> str:
  """Pause/sandhi-insensitive word identity (also folds ङमुट् `पा॰ ८.३.३२` doubling `न्न् अ` → `न् अ`)."""
  # `to_norm_slp` renders the doubled `न्न्` as anusvāra+`n` (`Mn`).
  slp = re.sub(r"(?<=[aiuf])Mn(?=[aAiIuUfFeEoO])", "n", to_norm_slp(_unelide(text)))
  return _pause_norm_slp(slp)


def test_pilot_01_01_1_gold_precision_and_vyatyasta_rejection(lex: UnifiedVedicLexicon):
  pilot_path = (
    "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/"
    "mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH/01/01/1.md"
  )
  if not os.path.exists(pilot_path):
    pytest.skip("ŚB corpus not present in environment")

  txt = open(pilot_path, encoding="utf-8").read()
  clusters = parse_sb_markdown_clusters(txt)
  by_h = {c.heading: c for c in clusters}

  # 1. Clean kaṇḍikās (e.g. §01, §04, §16) achieve AUTO_CLEAN with BOTH exact text AND exact marks vs gold!
  # (§06 is deliberately NOT here: v2 flags `अमानुष इव` -ः/-ए ambiguity, masked `एवा᳘स्मि` and Shri `ब्रत`
  # typo → NEEDS_ADJUDICATION, which is the precision-safe outcome.)
  # (§16 `य᳘द्वेॗवापः᳘` splits `अपः᳓`/`आ᳓पः` with tied text cost; the deterministic pick is caught by
  # `disagree_syls` → NEEDS_ADJUDICATION, never a false AUTO_CLEAN — see the all-kaṇḍikā sweep below.)
  # (v2 `#31` gates send §01/§04 to adjudication for dictionary-only padas such as `पू᳓तिः`/`द्वय᳓म्`.)
  for h in ("१२",):
    c = by_h[h]
    sim = KandikaCluster(
      c.heading, c.sub_idx, "विश्वास-प्रस्तुतिः", "", False,
      c.weber, c.shri, c.visvara, c.sayana, c.harisvami, c.eggeling,
    )
    r = solve_kandika(sim, lex, kandika_id=f"01/01/1.md::{h}")
    assert r.status == "AUTO_CLEAN", f"Expected AUTO_CLEAN on §{h}, got {r.reasons}"
    assert _marks(r.vp_accented) == _marks(c.vp_body)
    # Gold may write uncoalesced pause forms (`व्रतम् उपैष्यन्न्`, `अन्तरतः ।`) where the solver keeps
    # Weber's continuous sandhi (`व्रतमुपैष्यन्`, `अन्तरतो`): compare words, not spacing/sandhi.
    assert verify_mantra_sandhi([it.ref for it in r.items], c.vp_body)[0]
    assert _word_norm(r.vp_accented) == _word_norm(c.vp_body)
    # Every Vedic corpus citation in padapāṭha MUST carry an exact `-N` count (`N > 0`), NEVER `*TA*`, and NEVER `पा\u0966`!
    for it in r.items:
      assert "पा\u0966" not in it.prov, f"Deprecated पा+digit-zero in {it.prov}"
      assert "*TA*" not in it.prov, f"Forbidden *TA* citation in {it.prov}"
      assert not re.search(r"\*(?:VS|TS|RV|AV|TB)\*(?!-\d+|\s+[\d०-९])", it.prov), f"Uncounted corpus tag: {it.prov}"
      assert not re.search(r"\*(?:VS|TS|RV|AV|TB)\*-0\b", it.prov), f"Zero corpus count: {it.prov}"

  # 1a. ZERO false AUTO_CLEAN and ZERO `*TA*` across ALL 22 gold kaṇḍikās!
  n_auto = 0
  for h, c in by_h.items():
    if not c.vp_body or not c.weber:
      continue
    sim = KandikaCluster(
      c.heading, c.sub_idx, "विश्वास-प्रस्तुतिः", "", False,
      c.weber, c.shri, c.visvara, c.sayana, c.harisvami, c.eggeling,
    )
    r = solve_kandika(sim, lex, kandika_id=f"01/01/1.md::{h}")
    for it in r.items:
      assert "*TA*" not in it.prov, f"Forbidden *TA* in §{h}: {it.prov}"
    if r.status == "AUTO_CLEAN":
      n_auto += 1
      assert _marks(r.vp_accented) == _marks(c.vp_body), f"False AUTO_CLEAN §{h}"
      assert _word_norm(r.vp_accented) == _word_norm(c.vp_body), f"False AUTO_CLEAN text §{h}"
  assert n_auto >= 1

  # 1b. §13 (`अनिरुक्तौ` solo Shri typo vs Weber `प्रजापतिह्`) MUST NOT certify AUTO_CLEAN!
  # Pause-normalized text comparison still catches real word drift (`अनिरुक्तौ` vs `अनिरुक्तो`).
  assert _word_norm("अनिरुक्तौ वै") != _word_norm("अनिरुक्तो वै")
  c13 = by_h["१३"]
  sim13 = KandikaCluster(
    c13.heading, c13.sub_idx, "विश्वास-प्रस्तुतिः", "", False,
    c13.weber, c13.shri, c13.visvara, c13.sayana, c13.harisvami, c13.eggeling,
  )
  r13 = solve_kandika(sim13, lex, kandika_id="01/01/1.md::१३")
  assert r13.status == "NEEDS_ADJUDICATION", "Solo-witness Shri typo `अनिरुक्तौ` must NOT pass AUTO_CLEAN!"

  # 2. Subordinate vyatyasta kaṇḍikās (§18 `उद्यच्छति`, §19 `सादयति`) MUST be caught as NEEDS_ADJUDICATION!
  for h in ("१८", "१९"):
    c = by_h[h]
    sim = KandikaCluster(
      c.heading, c.sub_idx, "विश्वास-प्रस्तुतिः", "", False,
      c.weber, c.shri, c.visvara, c.sayana, c.harisvami, c.eggeling,
    )
    r = solve_kandika(sim, lex, kandika_id=f"01/01/1.md::{h}")
    assert r.status == "NEEDS_ADJUDICATION", f"FALSE AUTO_CLEAN on vyatyasta §{h}!"
    assert any("subordinate_verb_anudatta" in rsn for rsn in r.reasons)

  # 3. Masked consecutive-udātta kaṇḍikā (§05 `ते᳓` vs `ते`) MUST be flagged as ambiguous!
  c05 = by_h["०५"]
  sim05 = KandikaCluster(
    c05.heading, c05.sub_idx, "विश्वास-प्रस्तुतिः", "", False,
    c05.weber, c05.shri, c05.visvara, c05.sayana, c05.harisvami, c05.eggeling,
  )
  r05 = solve_kandika(sim05, lex, kandika_id="01/01/1.md::०५")
  assert r05.status == "NEEDS_ADJUDICATION"
  assert any("ambiguous_padas" in rsn for rsn in r05.reasons)


def test_verifier_v2_precision_regressions(lex: UnifiedVedicLexicon):
  # #2: Velar nasal `वाङ्निरुक्तो` -> `वाक्` (NEVER `वाम्`!)
  p_vak = split_vp_to_padas("वाङ्निरुक्तो वै", lex)
  assert p_vak[0] == "वाक्" and "वाम्" not in p_vak

  # #4: Prefixed perfect `समीधे` -> `सम् + ईधे` (Rule #1, never `सम्-ईधे`!)
  assert _strip_leading_upasargas_tinanta("samIDe", lex) == ["सम्", "ईधे"]

  # #5: `उपहूतेडा` -> fem. `उप-हूता` + `इडा` (NEVER vocative `उप-हूत`!)
  p_ida = split_vp_to_padas("उपहूतेडा", lex)
  assert p_ida[0] in ("उप-हूता", "उपहूता") and p_ida[1] == "इडा"

  # #6: Never hyphenate plain pronoun `विश्वस्य` (`वि-श्वस्य`) or vṛddhi taddhita `नै—दाघ` (`नै-दाघ`)
  assert "विश्वस्य" in split_vp_to_padas("विश्वस्य", lex)
  mw_nai = _mw_deva_to_us("नै—दाघ॑")
  assert mw_nai is not None and mw_nai[2] is None

  # #7 (+ #31 B.6): Repair visvara quote-broken sandhi before `इति` (keeping its punctuation) instead of
  # falling back to unpunctuated Weber; still reject bogus `आ ऽ` avagraha; normalize Shri `व्व -> व`
  vp_q, src_q = build_clean_vp_base(
    weber="तं᳘ हवि᳘ष्मन्त ईडत इ᳘ति॥",
    shri="तं᳘ हवि᳘ष्मन्त ऽईडत इ᳘ति॥",
    visvara='\"तं हविष्मन्त ईडते\"- इति ॥',
  )
  assert src_q == "visvara" and "ईडत इति" in vp_q and '"' not in vp_q

  vp_vv, _ = build_clean_vp_base(
    weber="", shri="स᳘र्व्वे देवा᳘ व्वसन्ति॥", visvara="",
  )
  assert "व्व" not in vp_vv and "सर्वे देवा वसन्ति" in vp_vv

  # #8: Pāṇinian verb accent rules (`tudAdi` optative `स्पृशे᳓त्`, `ruDAdi` `युन᳓क्ति`, `BvAdi` excludes `li~w`)
  m_spr = lex.analyze_morph("स्पृशेत्")
  spr_mks = {m for m, _ in _derive_paninian_tinanta_accent("स्पृशेत्", m_spr, sub_rule="पा॰ ८.१.६६")}
  assert ("", "U") in spr_mks

  m_yun = lex.analyze_morph("युनक्ति")
  yun_mks = {m for m, _ in _derive_paninian_tinanta_accent("युनक्ति", m_yun, sub_rule="पा॰ ८.१.६६")}
  assert ("", "U", "") in yun_mks

  # Fast pure-Python primitives match official reconciler & shatapatha bit-for-bit on sample ŚB text
  w_txt = "व्रत᳘मुपै᳘ष्यन्नन्त᳘रेणाहवनी᳘यं च गा᳘र्हपत्यं च॥"
  vp_us = "व्रत᳓मुपैष्य᳓न्न᳓न्तरेणाहवनी᳓यं च गा᳓र्हपत्यं च ॥"
  assert _fast_syllables_with_marks(vp_us) == syllables_with_marks(vp_us)
  assert [(s.key, s.mark, s.before_pause) for s in _fast_extract_sb_syllables(w_txt, source="weber")] == [
    (s.key, s.mark, s.before_pause) for s in extract_sb_syllables(w_txt, source="weber")
  ]
  assert _fast_extract_vp_pieces(vp_us) == _extract_vp_pieces(vp_us)


def test_exact_corpus_counts_and_enrichment(lex: UnifiedVedicLexicon):
  # Exact counts must be strictly positive, disjoint (`TB_VP` merged, `TA` excluded!), and ordered descending!
  c_vrata = lookup_corpus_counts(lex, "व्रत᳓म्")
  assert c_vrata, "Expected attested corpus counts for व्रत᳓म्"
  assert "TA" not in c_vrata
  assert all(k in ("VS", "TS", "RV", "AV", "TB") and isinstance(v, int) and v > 0 for k, v in c_vrata.items())
  vals = list(c_vrata.values())
  assert vals == sorted(vals, reverse=True)

  c_sarv = lookup_corpus_counts(lex, "सर्व᳓तः")
  assert c_sarv and "TA" not in c_sarv and all(v > 0 for v in c_sarv.values())

  # Enrich bare corpus citations while preserving editorial notes, Pāṇini sūtras, and explicit verse refs!
  enriched = enrich_padapatha_corpus_counts(lex, "व्रत᳓म्", "*RV*, *TS*, *AV*, *TA*-9, *TA*; श्रीधरादि-पाठः")
  assert "; श्रीधरादि-पाठः" in enriched
  assert "*TA*" not in enriched
  assert re.search(r"\*RV\*-\d+", enriched)
  assert re.search(r"\*TS\*-\d+", enriched)
  assert not re.search(r"\*(?:VS|TS|RV|AV|TB)\*(?!-\d+)", enriched)
  assert "-0" not in enriched

  # Zero `TA`/`TA_VP` sources anywhere in the v8 lexicon!
  assert not any(
    src in ("TA", "TA_VP")
    for by_m in lex.form_accents.values()
    for srcs in by_m.values()
    for src in srcs
  )

  # Explicit verse citations like `*VS* 1.5` and dictionary tags `*MW* ŚBr.` remain untouched/uncounted
  enriched_ref = enrich_padapatha_corpus_counts(lex, "व्रत᳓म्", "*VS* 1.5, *TS*, *MW* ŚBr.")
  assert "*VS* 1.5" in enriched_ref
  assert "*MW* ŚBr." in enriched_ref
  assert re.search(r"\*TS\*-\d+", enriched_ref)
  assert "*MW*-" not in enriched_ref


def test_export_adjudication_jsonl(lex: UnifiedVedicLexicon):
  cl = KandikaCluster(
    heading="१९",
    sub_idx=0,
    vp_summary="विश्वास-प्रस्तुतिः",
    vp_body="",
    is_already_us=False,
    weber="य᳘द्गार्ह᳘पत्ये सादयति॥",
    shri="य᳘द्गार्ह᳘पत्ये सादयति॥",
    visvara="यद्गार्हपत्ये सादयति ॥",
    sayana="सायण-भाष्यम्",
    eggeling="When he places it on the Gārhapatya.",
  )
  res = solve_kandika(cl, lex, kandika_id="test.md::१९")
  assert res.status == "NEEDS_ADJUDICATION"
  with tempfile.TemporaryDirectory() as td:
    out_p = os.path.join(td, "queue.jsonl")
    n = export_adjudication_jsonl([("test.md", [cl], [res])], out_p)
    assert n == 1
    lines = open(out_p, encoding="utf-8").read().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    for req_key in (
      "id", "file", "heading", "reasons", "weber", "shri", "visvara",
      "sayana_excerpt", "eggeling_excerpt", "draft_vp", "draft_padapatha",
      "disagree_syllables", "ambiguous_padas", "sandhi_ok", "lexicon_hits",
    ):
      assert req_key in rec
    assert rec["id"] == "test.md::१९"
    assert rec["rel_path"] == "test.md"
    assert rec["status"] == "NEEDS_ADJUDICATION"

    # Also verify `include_auto_clean=True` + `rel_root` for Phase 3 full-file export (`#41`).
    cl_ac = KandikaCluster(
      heading="०१", sub_idx=0, vp_summary="विश्वास-प्रस्तुतिः", vp_body="", is_already_us=False,
      weber="अ᳘थ सो᳘मं यजति॥", shri="अ᳘थ सो᳘मं यजति॥", visvara="अथ सोमं यजति ॥",
    )
    res_ac = solve_kandika(cl_ac, lex, kandika_id="01/09/2.md::०९")
    assert res_ac.status == "AUTO_CLEAN"
    out_all = os.path.join(td, "queue_all.jsonl")
    n_all = export_adjudication_jsonl(
      [("/root/01/09/2.md", [cl_ac, cl], [res_ac, res])],
      out_all,
      include_auto_clean=True,
      rel_root="/root",
    )
    assert n_all == 2
    recs_all = [json.loads(ln) for ln in open(out_all, encoding="utf-8").read().strip().splitlines()]
    assert [r["status"] for r in recs_all] == ["AUTO_CLEAN", "NEEDS_ADJUDICATION"]
    assert recs_all[0]["rel_path"] == "01/09/2.md"
    assert recs_all[0]["lexicon_hits"]


def test_vs_corpus_ingested_from_h3_wrapped_summaries(lex: UnifiedVedicLexicon):
  # VS sarva-prastutiH wraps summaries in `<h3>मूलम् ...{Loading}...</h3>`; these must be ingested.
  if not lookup_corpus_counts(lex, "यज्ञ᳓म्"):
    pytest.skip("Corpora not present in environment")
  assert lookup_corpus_counts(lex, "यज्ञ᳓म्").get("VS", 0) > 0
  assert lookup_corpus_counts(lex, "अग्नि᳓म्").get("VS", 0) > 0


def test_enrich_counts_no_duplicate_with_inline_form_citation(lex: UnifiedVedicLexicon):
  counts = lookup_corpus_counts(lex, "व्रत᳓म्")
  if "TS" not in counts:
    pytest.skip("Corpora not present in environment")
  j = enrich_padapatha_corpus_counts(lex, "व्रत᳓म्", "*TS* व्र॒तम्, *RV*; श्रीधरादि-पाठः")
  assert j.count("*TS*") == 1 and j.count("*RV*") == 1
  assert j.startswith(f"*TS*-{counts['TS']} व्र॒तम्")
  assert j.endswith("; श्रीधरादि-पाठः")
  assert enrich_padapatha_corpus_counts(lex, "व्रत᳓म्", j) == j  # idempotent


def test_verifier_31_gates(lex: UnifiedVedicLexicon):
  from doc_curation.sanskrit.accent import shatapatha_solver as ss
  # B.4: nañ never takes lyap → `अव-धाय`, never `अ-वधाय`; nañ on non-lyap words still allowed.
  assert ss._hyphenate_compound_pada("अवधाय", lex) == "अव-धाय"
  assert not ss._is_valid_compound_hyphenation("अ-वधाय", "अवधाय")
  # B.1: alternative vowel-sandhi resegmentations are enumerated (`तस्यै+तत्` ↔ `तस्य+एतत्`, augment `अघ्नन्`).
  labels = [lbl for _, _, _, lbl in ss._alternative_segmentations(["तस्यै", "तत्"], lex)]
  assert any("तस्य+एतत्" in lbl for lbl in labels)
  labels = [lbl for _, _, _, lbl in ss._alternative_segmentations(["राज्ञा", "घ्नन्"], lex)]
  assert any("अघ्नन्" in lbl for lbl in labels)
  # …but RV-only length variants (`एवा`) are not alternatives to ŚB `एव`.
  labels = [lbl for _, _, _, lbl in ss._alternative_segmentations(["एव", "एतत्"], lex)]
  assert not any("एवा+" in lbl for lbl in labels)
  # A: word-final virāma + independent vowel stays two tokens (no `र्ऋ` → `रृ` drift).
  assert "नाभिर् ऋतस्य" in ss._format_vp_clauses("नाभिर्ऋतस्य")
  # B.5: canonical sūtra names.
  src = open(ss.__file__, encoding="utf-8").read()
  assert "गतिर्गतावत्" not in src and "लिङ्सलोपौ" not in src
  # B.6: quote-broken `इति` repaired.
  assert ss._repair_visvara_quote_iti('सो ऽस्मि” इति') == "सो ऽस्मीति"


def test_verifier_31_live_cases_never_auto_clean(lex: UnifiedVedicLexicon):
  base = (
    "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/"
    "mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH/"
  )
  if not os.path.exists(base + "01/01/2.md"):
    pytest.skip("ŚB corpus not present in environment")
  cases = [
    ("01/01/2.md", "१४"), ("04/01/1.md", "२१"), ("11/01/1.md", "०१"), ("02/05/4.md", "०४"),
    ("05/05/5.md", "०२"), ("05/01/1.md", "१४"), ("01/03/3.md", "०९"), ("01/06/1.md", "१६"),
    ("01/02/2.md", "०१"),
  ]
  for f, h in cases:
    c = [c for c in parse_sb_markdown_clusters(open(base + f, encoding="utf-8").read()) if c.heading == h][0]
    r = solve_kandika(c, lex, kandika_id=f"{f}::{h}")
    assert r.status == "NEEDS_ADJUDICATION", f"{f}::{h} falsely AUTO_CLEAN"
  # A: the live crash file must solve without raising.
  crash = base + "14/01-05_bRhad-AraNyakopaniShat/03-04_muni-kANDaH/03/1.md"
  if os.path.exists(crash):
    assert isinstance(solve_sb_file(crash, lex), list)


def test_rv_av_unhyphenated_attestation_blocks_mw_hyphenation(lex: UnifiedVedicLexicon):
  from doc_curation.sanskrit.accent import shatapatha_solver as ss
  if "RV" not in lookup_corpus_counts(lex, "अध्वरा᳓णाम्"):
    pytest.skip("Corpora not present in environment")
  assert ss._hyphenate_compound_pada("अध्वराणाम्", lex) == "अध्वराणाम्"  # never MW's `अ-ध्वराणाम्`
  assert ss._hyphenate_compound_pada("प्रजापतिम्", lex) == "प्रजा-पतिम्"


def test_verifier_40_gates(lex: UnifiedVedicLexicon):
  from doc_curation.sanskrit.accent import shatapatha_solver as ss
  if not lookup_corpus_counts(lex, "यज्ञ᳓म्"):
    pytest.skip("Corpora not present in environment")
  alt = lambda pr: [lbl for *_, lbl in ss._alternative_segmentations(pr, lex)]
  # (d) compound vs split with a masked extra udātta, and particle `अह` vs verb `आह`.
  assert any("दिवि-सदम्" in lbl or "दिविसदम्" in lbl for lbl in alt(["दिवि", "सदम्"]))
  assert any("अत्र+अह" in lbl for lbl in alt(["अत्र", "आह"]))
  # Visvara anusvāra respelled as the ŚB witnesses' homorganic nasal.
  assert ss._prefer_ws_nasal_spelling("पंचदश पर्यंग्याः", "प᳘ञ्चदश पर्यङ्ग्याः", "") == "पञ्चदश पर्यङ्ग्याः"
  # Weber-internal `॥` survives as `।` when visvara is unusable.
  vp, src = build_clean_vp_base(weber="अ᳘थ सो᳘मं यजति॥ रे᳘तो वै सो᳘मः॥", shri="", visvara="")
  assert src == "weber" and "।" in vp

  # Live `#40` cases must all route to NEEDS_ADJUDICATION (and `13/02/2.md::१०` respells `पंचदश` → `पञ्चदश`).
  base = (
    "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/"
    "mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH/"
  )
  if os.path.exists(base + "13/02/2.md"):
    for f, h in (("13/02/2.md", "१०"), ("05/01/2.md", "०६"), ("03/07/1.md", "१५"), ("09/04/2.md", "२१")):
      c = [c for c in parse_sb_markdown_clusters(open(base + f, encoding="utf-8").read()) if c.heading == h][0]
      r = solve_kandika(c, lex, kandika_id=f"{f}::{h}")
      assert r.status == "NEEDS_ADJUDICATION", f"{f}::{h} falsely AUTO_CLEAN"
      if (f, h) == ("13/02/2.md", "१०"):
        assert "प᳓ञ्चदश" in r.vp_accented and "पं᳓चदश" not in r.vp_accented


def test_visvara_pausal_visarga_resandhied():
  from doc_curation.sanskrit.accent import shatapatha_solver as ss
  f = ss._restore_visvara_visarga_sandhi
  assert f("सप्रथाः - इति ।") == "सप्रथा इति ।"
  assert f("अमानुषः इव") == "अमानुष इव"
  assert f("देवः अग्निः") == "देवो ऽग्निः"
  assert f("नाभिः ऋतस्य") == "नाभिर् ऋतस्य"
  assert f("मनुष्याः । अथ") == "मनुष्याः । अथ"  # never across a daṇḍa


def test_coordinator_64_deterministic_upgrades(lex: UnifiedVedicLexicon):
  # 1. `aa_hiatus` restoration (`-आ`/`-अ` before vowel hiatus -> `-आः`/`-अः`/`-ए`)
  p_hiat = split_vp_to_padas("निष्टप्ता अरातयः", lex)
  assert p_hiat[0] == "निष्टप्ताः" and p_hiat[1] == "अरातयः"
  p_nida = split_vp_to_padas("नीड एव", lex)
  assert p_nida[0] in ("नीडे", "नीडः") and p_nida[1] == "एव"
  # 2. Never split `प्राणः` into `प्र + आणः`
  p_prana = split_vp_to_padas("प्राणो वै", lex)
  assert p_prana[0] == "प्राणः" and "आणः" not in p_prana
  # 3. High-frequency ŚB sandhi splits (`अन्वेमि`/`अन्वेति`, `यद्यु`, `उतो`, `स्वरेव`, `प्रउगम्`, `बिभयाञ्चक्रुः`)
  assert _strip_leading_upasargas_tinanta("anvemi", lex) == ["अनु", "एमि"]
  assert _strip_leading_upasargas_tinanta("anveti", lex) == ["अनु", "एति"]
  assert split_vp_to_padas("यद्यु", lex) == ["यदि", "उ"]
  assert split_vp_to_padas("उतो", lex) == ["उत", "उ"]
  assert split_vp_to_padas("स्वरेव", lex) == ["स्वः", "एव"]
  assert split_vp_to_padas("प्रउगम्", lex) == ["प्रउगम्"]
  p_periph = split_vp_to_padas("बिभयाञ्चक्रुः", lex)
  assert p_periph == ["बिभयाम्", "चक्रुः"]
  # 4. Direct Weber+Śrīdharādi OOV accent candidate (`Weber-पाठः, श्रीधरादि-पाठः`)
  cl_oov = KandikaCluster(
    heading="०१", sub_idx=0, vp_summary="विश्वास-प्रस्तुतिः", vp_body="", is_already_us=False,
    weber="आ᳘रुणिरुवाच॥", shri="आ᳘रुणिरुवाच॥", visvara="आरुणिरुवाच ॥",
  )
  r_oov = solve_kandika(cl_oov, lex, kandika_id="test::oov")
  assert r_oov.items and r_oov.items[0].ref == "आ᳓रुणिः"
