"""Unit tests for KS & MS mantra/brāhmaṇa splitting, viniyoga extraction, OCR repair, and padapāṭhas."""

from __future__ import annotations

import os
import pytest

from doc_curation.sanskrit.accent.provenance import VedicCorpusCounter
from doc_curation.sanskrit.accent.shatapatha_solver import UnifiedVedicLexicon
from doc_curation_projects.veda.yajuH.ks_ms.padapatha_builder import (
  build_block_padapatha_full,
  render_anuvaka_markdown,
)
from doc_curation_projects.veda.yajuH.ks_ms.pipeline import (
  DEFAULT_KS_SCHROEDER_ROOT,
  DEFAULT_MS_SARVA_ROOT,
  validate_rendered_markdown,
)
from doc_curation_projects.veda.yajuH.ks_ms.reference_index import (
  VedicReferenceIndex,
  norm_words,
  skeleton_key,
)
from doc_curation_projects.veda.yajuH.ks_ms.source_parser import (
  MsAnuvakaSource,
  clean_ms_titus_line,
  parse_ks_anuvaka,
  parse_ms_prapathaka,
)
from doc_curation_projects.veda.yajuH.ks_ms.splitter import (
  classify_is_brahmana,
  split_ks_anuvaka,
  split_ms_anuvaka,
)


@pytest.fixture(scope="module")
def shared_resources():
  idx = VedicReferenceIndex.load_or_build()
  lex = UnifiedVedicLexicon.load_or_build(include_sb_m=True)
  counter = VedicCorpusCounter.load_or_build()
  return idx, lex, counter


def test_ms_titus_encoding_repairs():
  assert clean_ms_titus_line("पितृ᳓̄न् ज᳓नम् अगन् यज्ञ᳓स्॥") == "पितॄ᳓न् ज᳓नम् अगन् यज्ञ᳓स्॥"
  assert clean_ms_titus_line("कॢप्तं᳓ च मे क्र्ŀ̥प्तिश् च मे॥") == "कॢप्तं᳓ च मे कॢप्तिश् च मे॥"
  assert clean_ms_titus_line("कृ᳓ष्णो ऽस्य् आखरेष्ठ᳓स् * ॥") == "कृ᳓ष्णो ऽस्य् आखरेष्ठ᳓स् ॥"
  assert "संपृञ्चाना᳓" in clean_ms_titus_line("रा᳓धाँसि संप्र्ञ्चाना᳓")
  assert "ध्रुवा᳓ अस्मि᳓न्" in clean_ms_titus_line("धुर्वा᳓ अस्मि᳓न् गो᳓पतौ")


def _make_ms_anu(kanda: str, prap: str, num: int, raw_lines: list[str]) -> MsAnuvakaSource:
  return MsAnuvakaSource(
    kanda=kanda,
    prapathaka=prap,
    anuvaka_num=num,
    title_dev=f"{num:02d}".translate(str.maketrans("0123456789", "०१२३४५६७८९")),
    raw_lines=raw_lines,
    clean_lines=[clean_ms_titus_line(ln) for ln in raw_lines],
  )


def test_ms_1_1_1_and_1_1_2_viniyoga_splits_and_rk_merging(shared_resources):
  idx, lex, counter = shared_resources
  anu1 = _make_ms_anu("1", "01", 1, [
    "इषे᳓ त्वा सुभूता᳓य॥",
    "वाय᳓वः स्थ॥",
    "देवो᳓ वः सविता᳓ प्रा᳓र्पयतु श्रे᳓ष्ठतमाय क᳓र्मणे ॥",
    "आ᳓प्यायध्वम् अघ्न्या देवे᳓भ्या इ᳓न्द्राय भाग᳓म् ॥",
    "मा᳓ वः स्तेन᳓ ईशत मा᳓घ᳓शँसो धुर्वा᳓ अस्मि᳓न् गो᳓पतौ स्यात बह्वी᳓स् ॥",
    "य᳓जमानस्य पशू᳓न् पाहि ॥",
  ])
  anu2 = _make_ms_anu("1", "01", 2, [
    "गोष᳓द् असि॥",
    "प्र᳓त्युष्टँ र᳓क्षः॥",
    "प्र᳓त्युष्टा᳓रातिः ॥",
    "प्रे᳓य᳓म् अगाद् धिष᳓णा बर्हि᳓र् अ᳓छ म᳓नुना कृता᳓ स्वध᳓या वि᳓तष्टा ॥",
    "त᳓या᳓वहन्ते कव᳓यः पुर᳓स्तात् ॥",
    "देवा᳓नां परिषूत᳓म् असि॥",
    "वि᳓ष्णोः स्तुप᳓स् ॥",
    "अ᳓तिसृष्टो ग᳓वां भाग᳓स् ॥",
    "देव᳓स्य त्वा सवितुः᳓ प्रसवे᳙ ऽश्वि᳓नोर् बाहु᳓भ्यां पूष्णो᳓ ह᳓स्ताभ्यां बर्हि᳓र् देवस᳓दनं दामि ॥",
    "अ᳓तस् त्वं᳓ बर्हिः शत᳓वल्शँ वि᳓रोह॥",
    "सह᳓स्रवल्शा वि᳓ वयँ᳓ रुहेम ॥",
  ])
  cursors: dict[str, int] = {}

  # MS 1.1.1: must split `इषे᳓ त्वा` vs `सुभूता᳓य` (MŚS 1.1.13 vs 1.1.15) and `मा᳓ वः स्तेन᳓...` vs `ध्रुवा᳓ अस्मि᳓न्...` (MŚS 1.1.21)
  b1 = split_ms_anuvaka(anu1, idx, cursors=cursors)
  vps1 = [b.vp_text for b in b1]
  assert vps1[0] == "इषे᳓ त्वा"
  assert vps1[1] == "सुभूता᳓य"
  assert vps1[2] == "वाय᳓वः स्थ"
  assert any("ध्रुवा᳓ अस्मि᳓न्" in v for v in vps1)
  assert any(v.source.startswith("मानव") and v.ref == "१.१.१३" for v in b1[0].viniyogas)
  assert any(v.source.startswith("मानव") and v.ref == "१.१.१५" for v in b1[1].viniyogas)
  assert not b1[2].is_rk  # `वायवः स्थ` must NOT be tagged as Ṛk

  built1 = [build_block_padapatha_full(b, lex, counter, corpus="MS") for b in b1]
  assert all(b.sandhi_ok for b in built1), [(b.vp_body, b.sandhi_detail) for b in built1 if not b.sandhi_ok]
  md1 = render_anuvaka_markdown(anu1.title_dev, built1)
  assert validate_rendered_markdown(md1) == []
  assert "*MS*" not in md1  # Never self-cite *MS* inside MS!
  assert "*TA*" not in md1 and "*EK*" not in md1

  # MS 1.1.2: must MERGE 3-pāda Ṛk `प्रे᳓य᳓म् अगाद् ... / त᳓या᳓वहन्ते ...`, keep `देव᳓स्य त्वा ... दामि` unbroken,
  # and SPLIT `अ᳓तस् त्वं᳓ बर्हिः शत᳓वल्शँ वि᳓रोह` (MŚS 1.1.38) vs `सह᳓स्रवल्शा वि᳓ वयँ᳓ रुहेम` (MŚS 1.1.39)!
  b2 = split_ms_anuvaka(anu2, idx, cursors=cursors)
  assert any(b.is_rk and "प्रे᳓य᳓म् अगाद्" in b.vp_text and "त᳓या᳓वहन्ते" in b.vp_text for b in b2)
  assert any("देव᳓स्य त्वा" in b.vp_text and "दामि" in b.vp_text for b in b2)
  assert any("शत᳓वल्शँ वि᳓रोह" in b.vp_text and "सह᳓स्रवल्शा" not in b.vp_text for b in b2)
  assert any("सह᳓स्रवल्शा" in b.vp_text and "शत᳓वल्शँ" not in b.vp_text for b in b2)
  built2 = [build_block_padapatha_full(b, lex, counter, corpus="MS") for b in b2]
  assert all(b.sandhi_ok for b in built2)
  assert validate_rendered_markdown(render_anuvaka_markdown(anu2.title_dev, built2)) == []


def test_ms_brahmana_correlatives_and_quotes(shared_resources):
  idx, lex, counter = shared_resources
  anu_br = _make_ms_anu("1", "08", 1, [
    "प्रजा᳓पतिः प्रजा᳓ असृजत॥",
    "स᳓ स्वं᳓ च᳓क्षुर् आदा᳓याजुहोत् ॥ अग्नि᳓र् ज्यो᳓तिर् ज्यो᳓तिर् अग्निः᳓ स्वा᳓हा ॥ इ᳓ति॥",
    "त᳓स्माद् उदुम्ब᳓रः प्राजापत्य᳓स्॥",
    "य᳓त् सायं᳓ जुहो᳓ति॥",
    "रा᳓त्र्यै ते᳓न दाधा᳓र॥",
    "क᳓स्मै क᳓म् अग्निहोत्रँ᳓ हूयता इ᳓ति ब्रह्मवादि᳓नो वदन्ति ॥",
  ])
  assert classify_is_brahmana(" ".join(anu_br.clean_lines))
  blks = split_ms_anuvaka(anu_br, idx)
  assert any("सायं᳓ जुहो᳓ति" in b.vp_text and "दाधा᳓र" in b.vp_text for b in blks)
  assert any("च᳓क्षुर् आदा᳓याजुहोत्" in b.vp_text and "इ᳓ति" in b.vp_text for b in blks)


def test_ks_schroeder_ocr_repair_fused_splits_and_apparatus(shared_resources):
  idx, lex, counter = shared_resources
  p1 = os.path.join(DEFAULT_KS_SCHROEDER_ROOT, "1_iThimikA", "01_puroDAshasthAnakam", "01.md")
  ks1 = parse_ks_anuvaka(p1, DEFAULT_KS_SCHROEDER_ROOT, lex=lex)
  assert ks1.visvara_matched
  # Schroeder OCR typos repaired in VP while raw Schroeder preserved in `raw_mula`!
  assert "त्वोर्जे᳓" in ks1.pieces[0].repaired_vp
  assert "त्वोजे᳓" in ks1.pieces[0].raw_mula
  assert "मघ्न्या" in ks1.pieces[0].repaired_vp
  assert "मग्न्या" in ks1.pieces[0].raw_mula

  blks1 = split_ks_anuvaka(ks1, idx, lex=lex)
  vps1 = [b.vp_text for b in blks1]
  assert any(v == "इषे᳓ त्वा" for v in vps1)
  assert any(v == "ऊर्जे᳓ त्वा" for v in vps1)
  # Verify ZERO char-drift in `mula_text` after OCR length-changing repair (`त्वोजे᳓` -> `त्वोर्जे᳓`)!
  urje_blk = next(b for b in blks1 if b.vp_text == "ऊर्जे᳓ त्वा")
  assert urje_blk.mula_text == "ऊजे᳓ त्वा"
  vayu_blk = next(b for b in blks1 if b.vp_text.startswith("वाय᳓व"))
  assert vayu_blk.mula_text.startswith("वाय᳓व")
  # Verify ZERO char-drift on KS 6.1 Brāhmaṇa after OCR length-changing repair (`अध्सृज्यत` -> `अध्यसृज्यत`)!
  p6 = os.path.join(DEFAULT_KS_SCHROEDER_ROOT, "1_iThimikA", "06_agnihotrabrAhmaNam", "01.md")
  ks6 = parse_ks_anuvaka(p6, DEFAULT_KS_SCHROEDER_ROOT, lex=lex)
  blks6 = split_ks_anuvaka(ks6, idx, lex=lex)
  so_blk = next(b for b in blks6 if b.vp_text.startswith("सो᳙ ऽस्य"))
  assert so_blk.mula_text.startswith("सो᳙ ऽस्य")
  built6_so = build_block_padapatha_full(so_blk, lex, counter, corpus="KS")
  assert any("अस्य (अन्वादेशे अनुदात्तम्, पा॰ २.४.३२" in ln for ln in built6_so.pp_lines), built6_so.pp_lines
  built1 = [build_block_padapatha_full(b, lex, counter, corpus="KS") for b in blks1]
  # `ब᳓ह्वीः᳓` double-udātta must be caught as vyatyasta, NOT split into `ब᳓ह् + वीः᳓`!
  bahvi_blk = next(b for b in built1 if "ब᳓ह्वीः᳓" in b.mula_body or "ब᳓ह्वीः᳓" in b.vp_body)
  assert any("ब᳓ह्वीः᳓ → **बह्वीः᳓**" in ln for ln in bahvi_blk.pp_lines), bahvi_blk.pp_lines
  # `अघ्न्या` vocative must NOT be falsely flagged as `अघ्न्या᳓`!
  assert not any("अघ्न्या → **अघ्न्या᳓**" in ln for b in built1 for ln in b.pp_lines)

  md1 = render_anuvaka_markdown(ks1.title, built1)
  assert validate_rendered_markdown(md1) == []
  assert "*KS*" not in md1  # Never self-cite *KS* inside KS!
  assert "*MS*-" in md1     # Sister-śākhā MS counts present!


def test_ks_unaccented_ta_mode_yantra_svara(shared_resources):
  idx, lex, counter = shared_resources
  p5 = os.path.join(DEFAULT_KS_SCHROEDER_ROOT, "1_iThimikA", "05_yajamAnam", "01.md")
  ks5 = parse_ks_anuvaka(p5, DEFAULT_KS_SCHROEDER_ROOT, lex=lex)
  assert not ks5.has_accents
  blks5 = split_ks_anuvaka(ks5, idx, lex=lex)
  built5 = [build_block_padapatha_full(b, lex, counter, corpus="KS") for b in blks5]
  assert all(b.vp_summary.endswith("(यन्त्र-स्वरः)") for b in built5)
  assert all("व्यत्यस्त" not in b.pp_summary for b in built5)
  assert all(b.sandhi_ok for b in built5)
  # Ensure `प्रजनिषेयम्` was NOT split into 3 accents `प्र᳓जनिषे᳓य᳓म्`!
  for b in built5:
    assert "प्र᳓जनिषे᳓य᳓म्" not in b.vp_body
  md5 = render_anuvaka_markdown(ks5.title, built5)
  assert validate_rendered_markdown(md5) == []


def test_ks_ashvamedha_svaha_litany_lossless(shared_resources):
  idx, lex, counter = shared_resources
  p10 = os.path.join(DEFAULT_KS_SCHROEDER_ROOT, "5_ashvamedhaH", "01_panthAnuvachanam", "10.md")
  ks10 = parse_ks_anuvaka(p10, DEFAULT_KS_SCHROEDER_ROOT, lex=lex)
  blks10 = split_ks_anuvaka(ks10, idx, lex=lex)
  assert len(blks10) >= 75  # 82 distinct Ashvamedha `स्वाहा` offerings!
  assert blks10[0].vp_text == "इङ्काराय स्वाहा"
  assert blks10[1].vp_text in ("इङ्कृताय स्वाहा", "ईङ्कृताय स्वाहा")
  assert blks10[3].vp_text == "अवक्रन्दते स्वाहा"
  built10 = [build_block_padapatha_full(b, lex, counter, corpus="KS") for b in blks10]
  md10 = render_anuvaka_markdown(ks10.title, built10)
  assert validate_rendered_markdown(md10) == []


def test_ms_2_07_savitra_yv_rks_and_2_01_duplicate_heading_lossless(shared_resources, tmp_path):
  idx, lex, counter = shared_resources
  # Test duplicate-heading merging (mirroring MS 2/01 `## 2 -> ## 3 (stray) -> ## 2 -> ## 3`)
  p_dup = tmp_path / "01.md"
  p_dup.write_text(
    '+++\ntitle = "01"\n+++\n## १\nक\n## २\nख१\nख२\n## ३\nग_stray\n## २\nख३\n## ३\nग१\n',
    encoding="utf-8",
  )
  anus_dup = parse_ms_prapathaka(str(p_dup))
  nums = [a.anuvaka_num for a in anus_dup]
  assert nums == [1, 2, 3]
  assert anus_dup[1].raw_lines == ["ख१", "ख२", "ग_stray", "ख३"]
  assert anus_dup[2].raw_lines == ["ग१"]

  # Test Agnicayana Sāvitra YV-only Ṛks merging (`युञ्जानः प्रथमं मनः...` and `युक्तेन मनसा वयं...`)
  anu_2_07 = _make_ms_anu("2", "07", 1, [
    "युञ्जानः᳓ प्रथमं᳓ म᳓नस् तत्वा᳓य सविता᳓ धि᳓यः॥",
    "अग्निं᳓ ज्यो᳓तिर् निचा᳓य्य पृथिव्या᳓ अ᳓ध्य् आ᳓भरत् ॥",
    "युक्ते᳓न म᳓नसा वयं᳓ देव᳓स्य सवितुः᳓ सवे᳓॥",
    "स्वर्ग्या᳙य श᳓क्तये ॥",
  ])
  blks = split_ms_anuvaka(anu_2_07, idx)
  assert blks[0].is_rk and "युञ्जानः᳓" in blks[0].vp_text and "आ᳓भरत्" in blks[0].vp_text
  assert blks[1].is_rk and "युक्ते᳓न" in blks[1].vp_text and "श᳓क्तये" in blks[1].vp_text


def test_ks_katha_svarita_litanies_brahmana_and_ms_whole_rk_rescue(shared_resources):
  idx, lex, counter = shared_resources

  # 1. KS 17.15 Śatarudrīya: Kaṭha under-hook svarita OCR (`सरस्यृाय` -> `सरस्या᳙य`) + namas litany split (no false Ṛk!)
  p17 = os.path.join(DEFAULT_KS_SCHROEDER_ROOT, "1_iThimikA", "17_dhruvaxitiH", "15.md")
  ks17 = parse_ks_anuvaka(p17, DEFAULT_KS_SCHROEDER_ROOT, lex=lex)
  assert "सरस्या᳙य" in ks17.pieces[0].repaired_vp
  assert "सरस्यृाय" in ks17.pieces[0].raw_mula
  blks17 = split_ks_anuvaka(ks17, idx, lex=lex)
  assert len(blks17) >= 30
  assert all(not b.is_rk for b in blks17)

  # 2. KS 18.10 Camaka: paired `X च मे Y च मे` litany split (no false Ṛk!)
  p18 = os.path.join(DEFAULT_KS_SCHROEDER_ROOT, "1_iThimikA", "18_chamA", "10.md")
  ks18 = parse_ks_anuvaka(p18, DEFAULT_KS_SCHROEDER_ROOT, lex=lex)
  blks18 = split_ks_anuvaka(ks18, idx, lex=lex)
  assert len(blks18) >= 12
  assert all(not b.is_rk for b in blks18)

  # 3. KS 15.1 unpunctuated Brāhmaṇa: `प्रत्यञ्व` -> `प्रत्यञ्च` OCR + clean sentence splits (>= 10 blocks)
  p15 = os.path.join(DEFAULT_KS_SCHROEDER_ROOT, "1_iThimikA", "15_shrIrAjasUyam", "01.md")
  ks15 = parse_ks_anuvaka(p15, DEFAULT_KS_SCHROEDER_ROOT, lex=lex)
  assert "प्रत्यञ्च" in ks15.pieces[0].repaired_vp
  blks15 = split_ks_anuvaka(ks15, idx, lex=lex)
  assert len(blks15) >= 12
  assert any(b.vp_text.startswith("आग्नावैष्णव") for b in blks15)

  # 4. KS 40.1 stray trailing accent after `॥` -> 0 validation errors, 8 clean Ṛks
  p40 = os.path.join(DEFAULT_KS_SCHROEDER_ROOT, "3_orimikA", "40_hiraNyagarbham", "01.md")
  ks40 = parse_ks_anuvaka(p40, DEFAULT_KS_SCHROEDER_ROOT, lex=lex)
  blks40 = split_ks_anuvaka(ks40, idx, lex=lex)
  assert len(blks40) == 8
  built40 = [build_block_padapatha_full(b, lex, counter, corpus="KS") for b in blks40]
  assert validate_rendered_markdown(render_anuvaka_markdown(ks40.title, built40)) == []

  # 5. KS 24.6 sparse stray single accent (`आहि᳙यते` in unaccented 250-word Brāhmaṇa) -> clean Mode B (0 vyat!)
  p24 = os.path.join(DEFAULT_KS_SCHROEDER_ROOT, "2_madhyamikA", "24_sAxIti", "06.md")
  ks24 = parse_ks_anuvaka(p24, DEFAULT_KS_SCHROEDER_ROOT, lex=lex)
  blks24 = split_ks_anuvaka(ks24, idx, lex=lex)
  assert len(blks24) >= 15
  # Embedded mantra quote `शुक्रं ते शुक्रेण क्रीणामि चन्द्रं... इति` stays intact (Test 2)!
  assert any("क्रीणामि चन्द्रं" in b.vp_text for b in blks24)
  built24 = [build_block_padapatha_full(b, lex, counter, corpus="KS") for b in blks24]
  assert all(b.n_vyat == 0 for b in built24)
  assert validate_rendered_markdown(render_anuvaka_markdown(ks24.title, built24)) == []

  # 6. MS 4.9.1 RV 1.40.1 whole-Ṛk viniyoga rescue + no false `पा॰ ८.१.७१` on nominal `सु` + `दा᳓नवाः`
  anu_4_9 = _make_ms_anu("4", "09", 1, [
    "उ᳓त्तिष्ठ ब्रह्मणस्पते देवय᳓न्तस् त्वेमहे ॥",
    "उ᳓प प्र᳓यन्तु मरु᳓तः सुदा᳓नवा इ᳓न्द्र प्राशू᳓र् भवा स᳓चा ॥",
  ])
  b_4_9 = split_ms_anuvaka(anu_4_9, idx)
  assert len(b_4_9) == 1 and b_4_9[0].is_rk
  built_4_9 = build_block_padapatha_full(b_4_9[0], lex, counter, corpus="MS")
  assert not any("- सु (तिङि चोदात्तवति" in ln for ln in built_4_9.pp_lines)



