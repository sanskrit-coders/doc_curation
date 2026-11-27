"""Unit tests for Taittirīya mechanical US padapāṭha builder (TB / TK)."""

from __future__ import annotations

import pytest

from doc_curation.sanskrit.accent import taittiriya_padapatha as tp
from doc_curation.sanskrit.accent.shatapatha_solver import UnifiedVedicLexicon, default_data_available


@pytest.fixture(scope="module")
def lex() -> UnifiedVedicLexicon:
  if not default_data_available():
    pytest.skip("indic-dict padasvara lexica / VS corpus not installed locally")
  return UnifiedVedicLexicon.load_or_build(include_sb_m=True, force_rebuild=False)


def test_normalize_taittiriya_orthography_preserves_accents():
  assert tp.normalize_taittiriya_orthography("सं॒ज्ञानव्ँ॑ वि॒ज्ञानं॑") == "सं॒ज्ञानं॑ वि॒ज्ञानं॑"
  assert tp.normalize_taittiriya_orthography("पत्नीसय्ंयाजा᳓नाम्") == "पत्नीसंयाजा᳓नाम्"
  assert tp.normalize_taittiriya_orthography("चि॒त्रᳵ के॒तुᳶ") == "चि॒त्रः के॒तुः"
  assert tp.normalize_taittiriya_orthography("क्ष॒त्त्रँ सन्ध॑त्तम्") == "क्ष॒त्रं सन्ध॑त्तम्"
  assert tp.normalize_taittiriya_orthography("आ॒तपँ॒ स्तप॑न्") == "आ॒तपं॒स्तप॑न्"


def test_build_block_padapatha_tk_and_tb_samples(lex: UnifiedVedicLexicon):
  r1 = tp.build_block_padapatha(
    "सं॒ज्ञानव्ँ॑ वि॒ज्ञानं॑ प्र॒ज्ञान॑ञ्जा॒नद॑भिजा॒नत् ।",
    "संज्ञा᳓नव्ँ विज्ञा᳓नं प्रज्ञा᳓नञ्जान᳓दभिजान᳓त् ।",
    lex,
  )
  assert r1.sandhi_ok
  assert r1.unmapped_syllables == 0
  assert r1.multi_udatta_padas == []
  assert r1.padas_us == ["सम्-ज्ञा᳓नम्", "वि-ज्ञा᳓नम्", "प्र-ज्ञा᳓नम्", "जान᳓त्", "अभि-जान᳓त्"]

  r2 = tp.build_block_padapatha(
    "ब्रह्म॒ सन्ध॑त्त॒न्तन्मे॑ जिन्वतम् ।",
    "ब्र᳓ह्म स᳓न्धत्तम् +++(मया सह)+++। त᳓न् +++(ब्रह्म)+++ मे जिन्वतम्+++(=प्रीणयतम्)+++ ।",
    lex,
  )
  assert r2.sandhi_ok
  assert r2.unmapped_syllables == 0
  assert r2.padas_us == ["ब्र᳓ह्म", "स᳓म्", "धत्तम्", "त᳓त्", "मे", "जिन्वतम्"]

  # All-udātta phrase lacking classical ॒/॑ falls back to US VP cleanly
  r3 = tp.build_block_padapatha("त्रिः ।", "त्रिः᳓ ।", lex)
  assert r3.used_vp_fallback
  assert r3.padas_us == ["त्रिः᳓"]


def test_add_padapathas_to_markdown_idempotent_and_skips_js_include(lex: UnifiedVedicLexicon):
  md = (
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "ब्र᳓ह्म स᳓न्धत्तम् । त᳓न् मे जिन्वतम् ।\n"
    "</details>\n\n"
    "<details><summary>मूलम्</summary>\n\n"
    "ब्रह्म॒ सन्ध॑त्त॒न्तन्मे॑ जिन्वतम् ।\n"
    "</details>\n\n"
    "<details><summary>भट्टभास्कर-टीका</summary>\n\n"
    "ब्रह्म ब्राह्मणजातिम्।\n"
    "</details>\n\n"
    '<div class="js_include" url="/vedAH_yajuH/foo.md">\n'
    "<details><summary>मूलम्</summary>\n\n"
    "अ॒ग्निमी॑ळे ।\n"
    "</details>\n"
    "</div>\n"
  )
  out1, res1 = tp.add_padapathas_to_markdown(md, lex)
  assert len(res1) == 1
  assert "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\nब्र᳓ह्म । स᳓म् । धत्तम् । त᳓त् । मे । जिन्वतम् ।\n</details>\n\n<details><summary>भट्टभास्कर-टीका</summary>" in out1
  # Must not touch inside js_include
  assert out1.count("पद-पाठः (यान्त्रिकः)") == 1
  # Idempotent on second pass
  out2, _ = tp.add_padapathas_to_markdown(out1, lex)
  assert out2 == out1
