"""Unit tests for doc_curation.sanskrit.accent.auditor."""

from __future__ import annotations

import json
from pathlib import Path

from doc_curation.sanskrit.accent.auditor import (
  audit_directory_trees,
  audit_padapatha_markdown,
  audit_vp_file_for_tiikaa_includes,
  extract_canonical_padapatha_blocks,
  main as auditor_main,
)


def test_extract_canonical_blocks_skips_js_include():
  md = """
<div class="js_include" url="/foo/bar.md">
<details><summary>मूलम्</summary>

अ॒ग्निम् ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- अग्नि᳓म् (*TS*-293)
</details>
</div>

<details><summary>मूलम्</summary>

इ॒मम् ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- इम᳓म् (*TS*-107)
</details>
<details><summary>हरदत्तः</summary>

इमम् इति ।
</details>
"""
  blocks = extract_canonical_padapatha_blocks(md)
  assert len(blocks) == 1
  assert "इम᳓म्" in blocks[0].pp_body
  assert "हरदत्तः" in blocks[0].commentaries


def test_commentator_missing_and_unstated_svara_checks():
  md = """
<details><summary>मूलम्</summary>

अ॒ग्निम् आ॒र्द्रया॑ ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- अग्नि᳓म् (*TS*-293 — भास्करः)
- आर्द्र᳓या (*TB*-1, पा॰ ३.१.३ — हरदत्तः)
- एजा᳓य (छान्दसो जकारः — हरदत्तः)
</details>
<details><summary>हरदत्तः</summary>

आर्द्रया आज्याक्तया । एजाय एतेर्लिटि छान्दसो जकारः ।
</details>
"""
  findings, n_blocks = audit_padapatha_markdown(md, path="test.md", include_validator_issues=False)
  assert n_blocks == 1
  cats = [(f.category, f.line) for f in findings]
  assert any(c == "commentator_missing_block" and "अग्नि᳓म्" in ln for c, ln in cats)
  assert any(c == "commentator_unstated_svara" and "आर्द्र᳓या" in ln for c, ln in cats)
  # Genuine Haradatta remark ("छान्दसो जकारः") must NOT be flagged
  assert not any("एजा᳓य" in ln for _, ln in cats)


def test_ekadesha_vocative_mw_svarita_and_false_compound_diagnostics():
  md = """
<details><summary>मूलम्</summary>

अ॒प्सुजा॑त आर्द्रया॑रण्य॒ देवि॑ दि॒श्याः॑ ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः - 5/5 व्यत्यस्त-स्वराः)</summary>

- अप्सु-जात → **अप्सु᳓-जात** (पा॰ ६.१.१९८)
- आर्द्र᳓या᳓ → **आर्द्र᳓या** (*TB*-1)
- अरण्या (प्रातिपदिकम् अ᳓रण्य (*MW*))
- देवि → **दे᳓वि** (पा॰ ६.१.१९८, *TS*-1)
- दिश्याः᳓ → **दि᳓श्याः** (प्रातिपदिकम् दि᳓श्य (*MW*))
</details>
<details><summary>भट्टभास्कर-टीका</summary>

हे देवि!
</details>
"""
  vp = "अप्सु᳓ जात आर्द्र᳓याऽरण्या देवि! दिश्याः᳙ ।"
  findings, _ = audit_padapatha_markdown(md, path="diag.md", paired_vp_text=vp, include_validator_issues=False)
  cats = {f.category for f in findings}
  assert "false_compound_candidate" in cats
  assert "ekadesha_multi_accent_ar" in cats
  assert "non_initial_61198_vocative" in cats
  assert "possible_missed_vocative" in cats
  assert "mw_only_arrow" in cats
  assert "mula_svarita_misread" in cats


def test_svarita_824_placement_check():
  md = """
<details><summary>मूलम्</summary>

श्व॑श्र्वः ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- श्व᳙श्र्वः (उदात्तस्वरितयोर्यणः स्वरितोऽनुदात्तस्य पा॰ ८.२.४)
- त᳙त्र (उदात्तस्वरितयोर्यणः स्वरितोऽनुदात्तस्य पा॰ ८.२.४)
</details>
"""
  findings, _ = audit_padapatha_markdown(md, path="yan.md", include_validator_issues=False)
  hits = [f for f in findings if f.category == "svarita_824_placement"]
  assert len(hits) == 1
  assert "त᳙त्र" in hits[0].line


def test_vp_includes_tiikaa_and_directory_cli(tmp_path: Path):
  vp_dir = tmp_path / "vishvAsa-prastutiH"
  tk_dir = tmp_path / "sarvASh_TIkAH"
  vp_dir.mkdir()
  tk_dir.mkdir()

  bad_vp = vp_dir / "01_test.md"
  bad_vp.write_text(
    '+++\ntitle = "01"\n+++\n'
    '<div class="js_include" url="/vedAH_yajuH/taittirIyam/foo/sarvASh_TIkAH/01_other.md"></div>\n',
    encoding="utf-8",
  )
  assert len(audit_vp_file_for_tiikaa_includes(bad_vp.read_text(encoding="utf-8"), path="01_test.md")) == 1

  tk_file = tk_dir / "01_test.md"
  tk_file.write_text(
    "<details><summary>मूलम्</summary>\n\nअ॒ग्निम् ।\n</details>\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- अग्नि᳓म् (*TS*-293)\n</details>\n",
    encoding="utf-8",
  )

  report = audit_directory_trees([str(tmp_path)], base_dir=str(tmp_path))
  assert report.files_scanned == 1
  assert report.blocks_scanned == 1
  assert report.counts() == {"vp_includes_tiikaa": 1}

  out_json = tmp_path / "report.json"
  rc = auditor_main([str(tmp_path), "--base-dir", str(tmp_path), "--json", str(out_json)])
  assert rc == 0
  payload = json.loads(out_json.read_text(encoding="utf-8"))
  assert payload["counts"] == {"vp_includes_tiikaa": 1}


def test_ek_external_padapatha_flagged_while_non_ek_and_intra_ek_allowed(tmp_path: Path):
  ek_vp = tmp_path / "ekAgnikANDam/vishvAsa-prastutiH/1_06"
  ek_tk = tmp_path / "ekAgnikANDam/sarvASh_TIkAH/1_06"
  ta_vp = tmp_path / "AraNyakam/Rk/vishvAsa-prastutiH/06"
  ta_tk = tmp_path / "AraNyakam/Rk/sarvASh_TIkAH/06"
  for d in (ek_vp, ek_tk, ta_vp, ta_tk):
    d.mkdir(parents=True)

  # 1. EK with external RV include + canonical padapatha -> flagged
  (ek_vp / "01_ext.md").write_text(
    '+++\ntitle = "01"\n+++\n<div class="js_include" url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/10/085/01.md">x</div>\n',
    encoding="utf-8",
  )
  (ek_tk / "01_ext.md").write_text(
    "<details><summary>मूलम्</summary>\n\nअ॒ग्निम् ।\n</details>\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- अग्नि᳓म् (*TS*-293)\n</details>\n",
    encoding="utf-8",
  )

  # 2. Intra-EK include + canonical padapatha -> allowed
  (ek_vp / "02_intra.md").write_text(
    '+++\ntitle = "02"\n+++\n<div class="js_include" url="/vedAH_yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/vishvAsa-prastutiH/1_06/01_ext.md">x</div>\n',
    encoding="utf-8",
  )
  (ek_tk / "02_intra.md").write_text(
    "<details><summary>मूलम्</summary>\n\nअ॒ग्निम् ।\n</details>\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- अग्नि᳓म् (*TS*-293)\n</details>\n",
    encoding="utf-8",
  )

  # 3. Non-EK (AraNyakam) with external RV include + canonical padapatha -> allowed
  (ta_vp / "01_ta.md").write_text(
    '+++\ntitle = "01"\n+++\n<div class="js_include" url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/10/085/01.md">x</div>\n',
    encoding="utf-8",
  )
  (ta_tk / "01_ta.md").write_text(
    "<details><summary>मूलम्</summary>\n\nअ॒ग्निम् ।\n</details>\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- अग्नि᳓म् (*TS*-293)\n</details>\n",
    encoding="utf-8",
  )

  report = audit_directory_trees([str(tmp_path)], include_validator_issues=False, base_dir=str(tmp_path / "ekAgnikANDam"))
  hits = [f for f in report.findings if f.category == "redundant_ek_external_padapatha"]
  assert len(hits) == 1
  assert hits[0].path.endswith("sarvASh_TIkAH/1_06/01_ext.md")
  wrapper_hits = [f for f in report.findings if f.category == "redundant_ek_external_wrapper"]
  assert len(wrapper_hits) == 1
  assert wrapper_hits[0].path.endswith("vishvAsa-prastutiH/1_06/01_ext.md")


def test_auditor_recognizes_vs_m_and_vs_k_corpus_tags():
  from doc_curation.sanskrit.accent.auditor import CORPUS_COUNT_TAG_RE

  assert CORPUS_COUNT_TAG_RE.search("*VS-M*-12")
  assert CORPUS_COUNT_TAG_RE.search("*VS-K*-0/4")
  assert CORPUS_COUNT_TAG_RE.search("*VS*-3")


def test_auditor_flags_weak_rv_av_override_false_citations_and_antipatterns():
  from doc_curation.sanskrit.accent.provenance import VedicCorpusCounter, word_to_key_and_marks

  bad_md = """<details open><summary>विश्वास-प्रस्तुतिः (3/6 व्यत्यस्त-स्वराः)</summary>

[[अ᳓यशः|अयशः᳓]] मा हिंसीः᳓ [[प᳓रा|परा᳓]] तथा᳓ दीप्य᳓मानः ।
</details>

<details><summary>सर्वाष् टीकाः</summary>

<details><summary>मूलम्</summary>

अयशो मा हिंसीः परा तथा दीप्यमानः ।
</details>

<details><summary>पद-पाठः (यान्त्रिकः - 3/6 व्यत्यस्त-स्वराः)</summary>

- अ᳓यशः → **अयशः᳓** (*RV*-1)
- मा (अनुदात्तम्, पा॰ ८.१.१८, *TS*-202)
- हिंसीः᳓ (*SB-M*-15)
- प᳓रा → **परा᳓** (*AV*, *RV*)
- तथा᳓ (*AV*, *RV*, *TB*, *TS*)
- दीप्य᳓मानः (यक् पा॰ ३.१.६७, पा॰ ३.१.३)
</details>
</details>
"""
  # Offline mode (counter=None): catches weak RV/AV arrow and both antipatterns
  offline_findings, _ = audit_padapatha_markdown(bad_md, path="x.md", include_validator_issues=False)
  offline_cats = {f.category for f in offline_findings}
  assert "weak_rv_av_override" in offline_cats
  assert "known_false_svara_antipattern" in offline_cats
  assert sum(1 for f in offline_findings if f.category == "known_false_svara_antipattern") == 2

  # Online mode with VedicCorpusCounter: additionally catches false bare citations & missing YV counts
  stub = VedicCorpusCounter()
  stub._add("TS", *word_to_key_and_marks("अ᳓यशः"), freq=4)
  stub._add("AV", *word_to_key_and_marks("प᳓रा"), freq=86)
  stub._add("RV", *word_to_key_and_marks("प᳓रा"), freq=78)
  stub._add("TS", *word_to_key_and_marks("प᳓रा"), freq=90)
  stub._add("SB-K", *word_to_key_and_marks("तथा᳓"), freq=24)
  stub._finalize_secondary_tables()

  online_findings, _ = audit_padapatha_markdown(
    bad_md, path="x.md", include_validator_issues=False, counter=stub
  )
  online_cats = [f.category for f in online_findings]
  assert online_cats.count("weak_rv_av_override") == 2
  assert online_cats.count("false_corpus_citation") == 2  # *AV* and *RV* on प᳓रा → परा᳓
  assert online_cats.count("missing_yv_corpus_counts") == 1  # तथा᳓ (*SB-K*-24)
  assert online_cats.count("known_false_svara_antipattern") == 2

  good_md = """<details open><summary>विश्वास-प्रस्तुतिः</summary>

मा हिंसीः दी᳓प्यमानः ।
</details>

<details><summary>सर्वाष् टीकाः</summary>

<details><summary>मूलम्</summary>

मा हिंसीः दीप्यमानः ।
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- मा (अनुदात्तम्, पा॰ ८.१.१८, *TS*-202)
- हिंसीः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *TS*-28, *SB-M*-24)
- दी᳓प्यमानः (*SB-M*-11, दिवादिभ्यः श्यन् पा॰ ३.१.६९)
</details>
</details>
"""
  good_findings, _ = audit_padapatha_markdown(
    good_md, path="good.md", include_validator_issues=False, counter=stub
  )
  assert not good_findings


def test_auditor_guards_kan_amredita_and_yad_clause_8128():
  bad_md = """<details><summary>मूलम्</summary>

धेनुका ते मा नमः यस्माद् वै भूतानि जायन्ते ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः - 3/8 व्यत्यस्त-स्वराः)</summary>

- धेनुका᳓ (कन् पा॰ ३.१.३)
- ते (द्विर्वचने अनुदात्तम्, पा॰ ८.१.३)
- मा᳓ → **मा** (द्विर्वचने परस्यानुदात्तत्वम्, पा॰ ८.१.३)
- न᳓मः → **नमः** (द्विर्वचने परस्यानुदात्तत्वम्, पा॰ ८.१.३)
- य᳓स्मात् (*TS*-10)
- वै᳓ (*TS*-20)
- भूता᳓नि (*TS*-5)
- जा᳓यन्ते → **जायन्ते** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
</details>
"""
  findings, _ = audit_padapatha_markdown(bad_md, path="bad_guards.md", include_validator_issues=False)
  antipatterns = [f for f in findings if f.category == "known_false_svara_antipattern"]
  assert len(antipatterns) == 5
  assert any("धेनुका᳓" in f.line and "कन्" in f.detail for f in antipatterns)
  assert any("Enclitic 'ते'" in f.detail for f in antipatterns)
  assert any("Enclitic 'मा'" in f.detail for f in antipatterns)
  assert any("नमः" in f.line and "preceding repeated word" in f.detail for f in antipatterns)
  assert any("जायन्ते" in f.line and "relative यद्" in f.detail for f in antipatterns)

  good_md = """<details><summary>मूलम्</summary>

धेनुका मा मा आपम् आपाम् यावत् वा यावत् नमः यद् भवति तद् एति ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः - 3/10 व्यत्यस्त-स्वराः)</summary>

- धेनुका᳓ (स्वार्थे कः पा॰ ५.३.७०, प्रत्ययस्वरः पा॰ ३.१.३)
- मा᳓ (*TS*-10)
- मा (आबाधे च पा॰ ८.१.१०, आम्रेडितम् अनुदात्तम् पा॰ ८.१.३)
- आप᳓म् (*TS*-1)
- आपाम् (आम्रेडितम् अनुदात्तम्, पा॰ ८.१.३)
- या᳓वत् (*TS*-1)
- वा (*TS*-1, पा॰ ८.१.१८)
- यावत् (आम्रेडितम् अनुदात्तम्, पा॰ ८.१.३)
- न᳓मः᳓ → **न᳓मः** (वाक्यभेदात् न पा॰ ८.१.३)
- य᳓त् (*TS*-10)
- भ᳓वति (यद्वृत्तान्नित्यम्, पा॰ ८.१.६६)
- त᳓त् (*TS*-10)
- ए᳓ति → **एति** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
</details>
"""
  good_findings, _ = audit_padapatha_markdown(good_md, path="good_guards.md", include_validator_issues=False)
  assert not [f for f in good_findings if f.category == "known_false_svara_antipattern"]


def test_auditor_vp_line_boundary_and_concat_compound_guards():
  md = """<details open><summary>विश्वास-प्रस्तुतिः - ऋक्</summary>

इदं᳓ ह᳓विः ।  
व᳓रुत्र्य् उग्रा᳓ विराजः᳓ प्र᳓ वर्धय प्रवर्धन त्वोत्तुदः᳓ ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- इद᳓म् (*TS*-10)
- ह᳓विः (*TS*-10)
- व᳓रुत्रि (पादादिः आमन्त्रितम् आद्युदात्तम्, पा॰ ६.१.१९८)
- उग्रा᳓ (*RV*-1)
- वि-राजः᳓ (*TS*-3/61)
- प्र᳓ (*TS*-10)
- वर्धय (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
- प्र-वर्धन (*AV*-1)
- उत्-तुदः᳓ (*AV*-1)
</details>
"""
  findings, _ = audit_padapatha_markdown(md, path="avp_boundary.md", include_validator_issues=False)
  cats = {f.category for f in findings}
  assert "non_initial_61198_vocative" not in cats
  assert "false_compound_candidate" not in cats
