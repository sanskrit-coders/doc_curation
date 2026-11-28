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

धेनुका मा मा आपम् आपाम् यावत् वा यावत् नमः यद् भवति तद् एति यदि कामयेत जुहुयात् यत्किञ्चित् विद्धि याः ताः मुञ्चति ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः - 5/22 व्यत्यस्त-स्वराः)</summary>

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
- य᳓दि (*TS*-10)
- काम᳓येत (निपातैर्यद्यदि... पा॰ ८.१.३०)
- जुहुया᳓त् → **जुहुयात्** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
- य᳓त् (*TS*-10)
- कि᳓म् (*TS*-10)
- चि᳓त् (*TS*-10)
- वि᳓द्धि → **विद्धि** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
- याः᳓ (*TS*-10)
- ताः᳓ (*TS*-10)
- मुञ्च᳓ति → **मुञ्चति** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
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


def test_auditor_guards_lut_8129_8156_57_8173_62116_61182():
  bad_md = """<details><summary>मूलम्</summary>

कर्ता पचति चित् पचति अग्ने गृहपते अमृतः गवा ब्रह्मबन्ध्वा ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः - 6/9 व्यत्यस्त-स्वराः)</summary>

- कर्ता᳓ → **कर्ता** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
- प᳓चति → **पचति** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
- चित् (*TS*-10)
- प᳓चति (यद्धितुपरं छन्दसि पा॰ ८.१.५६)
- अ᳓ग्ने (पादादिः आमन्त्रितम् आद्युदात्तम्, पा॰ ६.१.१९८)
- गृ᳓हपते → **गृहपते** (आमन्त्रितं पूर्वमविद्यमानवत् पा॰ ८.१.७२)
- अ-मृ᳓तः → **अ-मृतः᳓** (नञ्सुभ्याम् पा॰ ६.२.१७२)
- ग᳓वा → **गवा᳓** (सावेकाचस्तृतीयादिर्विभक्तिः पा॰ ६.१.१६८)
- ब्र᳓ह्मबन्ध्वा → **ब्रह्मबन्ध्वा᳓** (उदात्तयणो हल्पूर्वात् पा॰ ६.१.१७४)
</details>
"""
  bad_findings, _ = audit_padapatha_markdown(bad_md, path="bad_padasvara.md", include_validator_issues=False)
  anti = [f for f in bad_findings if f.category == "known_false_svara_antipattern"]
  assert any("८.१.२९" in f.detail and "कर्ता" in f.line for f in anti)
  assert any("८.१.५७" in f.detail and "पचति" in f.line for f in anti)
  assert any("८.१.५६" in f.detail and "प᳓चति" in f.line for f in anti)
  assert any("८.१.७३" in f.detail and "गृहपते" in f.line for f in anti)
  assert any("६.२.११६" in f.detail and "अ-मृतः᳓" in f.line for f in anti)
  assert any("६.१.१८२" in f.detail and "गवा᳓" in f.line for f in anti)
  assert any("६.१.१७५" in f.detail and "ब्रह्मबन्ध्वा᳓" in f.line for f in anti)

  good_md = """<details><summary>मूलम्</summary>

श्वः कर्ता । उदसृजो यद् अङ्गिरः । पचति चित् ।
अग्ने इन्द्र ।
अग्ने गृहपते अमृतः गवा ब्रह्मबन्ध्वा ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- श्वः᳓ (*TS*-10)
- कर्ता᳓ (न लुट् पा॰ ८.१.२९, *TS*-10)
- उद᳓सृजः (यद्धितुपरं छन्दसि पा॰ ८.१.५६, *RV*-1)
- य᳓त् (*TS*-10)
- अङ्गिरः (अपादादिः आमन्त्रितम् अनुदात्तम्, पा॰ ८.१.१९)
- प᳓चति (चनचिदिवगोत्रादितद्धिताम्रेडितेष्वगतेः पा॰ ८.१.५७)
- चित् (*TS*-10)
- अ᳓ग्ने (पादादिः आमन्त्रितम् आद्युदात्तम्, पा॰ ६.१.१९८)
- इ᳓न्द्र (आमन्त्रितं पूर्वमविद्यमानवत् पा॰ ८.१.७२, पा॰ ६.१.१९८)
- अ᳓ग्ने (पादादिः आमन्त्रितम् आद्युदात्तम्, पा॰ ६.१.१९८)
- गृहपते (नामन्त्रिते समानाधिकरणे सामान्यवचनम् पा॰ ८.१.७३, पा॰ ८.१.१९)
- अ-मृ᳓तः (नञो जरमरमित्रमृताः पा॰ ६.२.११६, *TS*-10)
- ग᳓वा (न गोश्वन्त्साववर्णराडङ्क्रुङ्कृद्भ्यः पा॰ ६.१.१८२, *TS*-10)
- ब्रह्मबन्ध्वा᳙ (नोङ्धात्वोः पा॰ ६.१.१७५, पा॰ ८.२.४)
</details>
"""
  good_findings, _ = audit_padapatha_markdown(good_md, path="good_padasvara.md", include_validator_issues=False)
  assert not [f for f in good_findings if f.category in ("known_false_svara_antipattern", "non_initial_61198_vocative")]


def test_ekagnikanda_8170_8166_and_vocative_audits():
  md = """<details open><summary>विश्वास-प्रस्तुतिः</summary>

स᳓मा᳓ धावन्तु । अयं᳓ वाम् [[अश्विनौ|अश्वि᳓नौ]] । त᳓त् सत्यं᳓ य᳓द् अहं᳓ ब्र᳓वीम्य् अ᳓धरो म᳓द् असौ᳓ [[वदात्|व᳓दात्]] ।
</details>
<details><summary>मूलम्</summary>

सँस्र॑वन्तु॒ म॒हीस्समा धा॑वन्तु । अ॒यं वा॑म॒श्विनौ॒ रथो॒ । तत्स॒त्यं यद॒हं ब्रवी॒म्यध॑रो॒ मद॒सौ व॑दात् ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः - 2/11 व्यत्यस्त-स्वराः)</summary>

- स᳓म् (*TS*-13)
- आ᳓ → **आ** (गतिर्गतौ, पा॰ ८.१.७०)
- अनु → **अ᳓नु** (गतिर्गतौ पा॰ ८.१.७०, *RV*-475)
- अय᳓म् (*TS*-92/968)
- अश्वि᳓नौ (*TS*-21/63)
- त᳓त् (*TS*-687/4763)
- य᳓त् (*TS*-1461/3383)
- ब्र᳓वीमि (यद्वृत्तान्नित्यम् पा॰ ८.१.६६)
- अ᳓धरः (*TS*-0/10)
- म᳓त् (*TS*-3/565)
- वदात् → **व᳓दात्** (यद्वृत्तान्नित्यम्, पा॰ ८.१.६६)
</details>
<details><summary>हरदत्तः</summary>

हे अश्विना अश्विनौ अयं रथः ।
</details>
"""
  findings, _ = audit_padapatha_markdown(md, path="ek_regressions.md", include_validator_issues=False)
  anti = [f for f in findings if f.category == "known_false_svara_antipattern"]
  voc = [f for f in findings if f.category == "possible_missed_vocative"]
  assert any("de-accents preceding गति" in f.detail and "आ᳓ → **आ**" in f.line for f in anti)
  assert any("never restores an accent" in f.detail and "अनु → **अ᳓नु**" in f.line for f in anti)
  assert any("without same-clause यद्-word" in f.detail and "वदात्" in f.line for f in anti)
  assert any("अश्वि᳓नौ" in f.line for f in voc)

  ok_md = """<details open><summary>विश्वास-प्रस्तुतिः</summary>

अ᳓हिँस । या᳓म् ज᳓नाः प्रतिन᳓न्दन्ति । य᳓स्यै म᳓नः ता᳓साम् त्व᳓म् नि᳓र्दह ।
</details>
<details><summary>मूलम्</summary>

अहिँस । यां जनाः॑ प्रतिनन्द॒न्ति । यस्यै॒ मनः॑ तासां॒ निर्द॑ह ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः - 2/11 व्यत्यस्त-स्वराः)</summary>

- अ᳓-हिँस (पादादावामन्त्रितम् आद्युदात्तम्, पा॰ ६.१.१९८)
- या᳓म् (*TS*-29/3383)
- ज᳓नाः (*TS*-3/33)
- प्रति-नन्दन्ति᳓ → **प्रति-न᳓न्दन्ति** (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, तिङि चोदात्तवति पा॰ ८.१.७१)
- य᳓स्यै (*TS*-5/3383)
- म᳓नः (*TS*-65/141)
- ता᳓साम् (*TS*-25/4763)
- त्व᳓म् (*TS*-158/313)
- निः (*TS*-292)
- द᳓ह → **दह** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
- स्वा᳓हा (*TS*-875)
</details>
<details><summary>हरदत्तः</summary>

हे अहिँस मा हिंसीः ।
</details>
"""
  ok_findings, _ = audit_padapatha_markdown(ok_md, path="ek_ok.md", include_validator_issues=False)
  assert not [f for f in ok_findings if f.category in ("known_false_svara_antipattern", "possible_missed_vocative")]


def test_clause_boundary_precision_and_non_arrow_yantra_guards():
  bad_md = """<details open><summary>विश्वास-प्रस्तुतिः</summary>

स᳓मा᳓ हन्तासि । दीप्यते इव । र᳓क्षत दधासि द्विषते᳓ अस्यै वि᳓ ।
</details>
<details><summary>मूलम्</summary>

समा हन्तासि । दीप्यत इव । रक्षत दधासि द्विषते अस्यै वि ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः - 0/12 व्यत्यस्त-स्वराः)</summary>

- स᳓म् (*TS*-13)
- आ (गतिर्गतौ, पा॰ ८.१.७०)
- वि᳓ (गतिः, पा॰ ८.१.७०)
- हन्तासि (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
- दधासि (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
- दीप्यते (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
- इव (निपातः, पा॰ ८.१.१८)
- र᳓क्षत (यद्वृत्तान्नित्यम्, पा॰ ८.१.६६)
- द्विषते᳓ (शतृ, यद्वृत्तान्नित्यम्, पा॰ ८.१.६६)
- अस्यै (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
</details>
"""
  findings, _ = audit_padapatha_markdown(bad_md, path="non_arrow_bad.md", include_validator_issues=False)
  cats = [(f.category, f.line, f.detail) for f in findings]
  assert any(c == "known_false_svara_antipattern" and "de-accents preceding गति" in d for c, _, d in cats)
  assert any(c == "known_false_svara_antipattern" and "never restores an accent" in d for c, _, d in cats)
  assert any(c == "known_false_svara_antipattern" and "८.१.२९" in d and "हन्तासि" in l for c, l, d in cats)
  assert not any("दधासि" in l and c == "known_false_svara_antipattern" for c, l, _ in cats)
  assert any(c == "known_false_svara_antipattern" and "८.१.५७" in d and "दीप्यते" in l for c, l, d in cats)
  assert any(c == "non_arrow_8166_without_yad" and "र᳓क्षत" in l for c, l, _ in cats)
  assert any(c == "non_tinanta_8128_8166" and "द्विषते᳓" in l for c, l, _ in cats)
  assert any(c == "non_tinanta_8128_8166" and "अस्यै" in l for c, l, _ in cats)

  ok_md = """<details open><summary>विश्वास-प्रस्तुतिः</summary>

यः᳓ एवं᳓ वे᳓द याः᳓ ते प्र य᳓न्ति उ᳓प पर्या᳓वर्तन्ते य᳓त् कि᳓ञ् च गच्छति ।
</details>
<details><summary>मूलम्</summary>

य एवं वेद यास्ते प्रयन्त्युप पर्यावर्तन्ते यत्किञ्च गच्छति ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः - 4/14 व्यत्यस्त-स्वराः)</summary>

- यः᳓ (*TS*-10)
- एवम् → **एव᳓म्** (*TS*-10)
- वेद → **वे᳓द** (यद्वृत्तान्नित्यम्, पा॰ ८.१.६६)
- याः᳓ (*TS*-10)
- ते (अनुदात्तम्, पा॰ ८.१.१८)
- प्र (तिङि चोदात्तवति, पा॰ ८.१.७१)
- यन्ति → **य᳓न्ति** (यद्वृत्तान्नित्यम्, पा॰ ८.१.६६)
- उ᳓प (कर्मप्रवचनीयः, प्रादिप्रसङ्गे कर्मप्रवचनीयानां प्रतिषेधः)
- परि (गतिर्गतौ, पा॰ ८.१.७०)
- आ᳓ (*TS*-10)
- वर्तन्ते (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
- य᳓त् (*TS*-10)
- कि᳓म् (*TS*-10)
- च (निपातः, पा॰ ८.१.१८)
- ग᳓च्छति → **गच्छति** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
</details>
"""
  ok_findings, _ = audit_padapatha_markdown(ok_md, path="clause_ok.md", include_validator_issues=False)
  assert not [
    f for f in ok_findings
    if f.category in ("known_false_svara_antipattern", "non_arrow_8166_without_yad", "non_tinanta_8128_8166")
  ]


def test_yad_vai_tad_keeps_8166_in_same_clause():
  ok_md = """<details open><summary>विश्वास-प्रस्तुतिः</summary>

य᳓त् वै᳓ त᳓त् न᳓ रस᳓यते । वे᳓त्थ य᳓तिथ्याम् व᳓दन्ती३ ।
</details>
<details><summary>मूलम्</summary>

यद्वै तन्न रसयते । वेत्थ यतिथ्यां वदन्ती३ ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- य᳓त् (*SB-M*-10)
- वै᳓ (*TS*-10)
- त᳓त् (*TS*-10)
- न᳓ (*RV*-10)
- रसयते → **रस᳓यते** (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, णिच् पा॰ ३.१.३)
- वे᳓त्थ (*TS*-1)
- य᳓तिथ्याम् (*SB-K*-1)
- व᳓दन्ती३ (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, पा॰ ६.१.१९७, *TB*-1)
</details>
"""
  ok_findings, _ = audit_padapatha_markdown(ok_md, path="yad_vai_tad_ok.md", include_validator_issues=False)
  assert not [
    f for f in ok_findings
    if f.category in ("known_false_svara_antipattern", "non_arrow_8166_without_yad")
  ]

  bad_md = """<details open><summary>विश्वास-प्रस्तुतिः</summary>

य᳓त् ब्र᳓ह्म त᳓त् वे᳓द ।
</details>
<details><summary>मूलम्</summary>

यद्ब्रह्म तद्वेद ।
</details>
<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- य᳓त् (*SB-M*-10)
- ब्र᳓ह्म (*TS*-10)
- त᳓त् (*TS*-10)
- वेद → **वे᳓द** (यद्वृत्तान्नित्यम् पा॰ ८.१.६६)
</details>
"""
  bad_findings, _ = audit_padapatha_markdown(bad_md, path="yad_vai_tad_bad.md", include_validator_issues=False)
  assert any(
    f.category == "known_false_svara_antipattern" and "वे᳓द" in f.line
    for f in bad_findings
  )


