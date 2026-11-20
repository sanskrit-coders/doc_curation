"""Unit tests for Śatapatha Brāhmaṇa accent analysis, auditing, and US conversion."""

from doc_curation.sanskrit.accent import (
  PadapathaItem,
  SbFileUpdateReport,
  apply_sb_kandika_updates,
  audit_padapatha_against_sb,
  build_sb_vp_from_padapatha,
  extract_sb_syllables,
  find_unsplit_upasarga_tinantas,
  format_suggested_vp_summary,
  normalize_sb_orthography,
  parse_padapatha_items,
  reconcile_markdown_blocks,
  us_marks_to_sb_marks,
  validate_accented_markdown,
  verify_mantra_sandhi,
)


def test_us_marks_to_sb_marks_all_nine_transitions():
  # Sequence exercising all 9 transitions: U->U, U->A, A->A, A->S, S->S, S->U, U->S, S->A, A->U, U->end
  us = ["U", "U", "", "", "S", "S", "U", "S", "", "U"]
  weber = us_marks_to_sb_marks(us, style="weber")
  shri = us_marks_to_sb_marks(us, style="shri")
  assert weber == ["", "H", "", "G", "G", "", "G", "", "", "H"]
  assert shri == ["", "H", "", "H", "H", "", "H", "", "", "H"]


def test_extract_sb_syllables_collapses_anunasika_double_marks_and_strips_pratikas():
  weber = "अ᳘थ स᳘ᳫं᳘स्थिते वि᳘सृजते॥ [^wbr_1]\n\n[^wbr_1]: note"
  shri = "(त्य᳘) अ᳘थ स᳘ᳫं᳘स्थिते व्वि᳘सृजते॥"
  ws = extract_sb_syllables(weber, source="weber")
  ss = extract_sb_syllables(shri, source="shri")
  assert [s.mark for s in ws] == ["H", "", "H", "", "", "H", "", "", ""]
  assert [s.mark for s in ss] == ["H", "", "H", "", "", "H", "", "", ""]


def test_normalize_sb_orthography():
  raw = "(न्न᳘) अ᳘न्तरेणाहवनी᳘यञ्च व्व्रत᳘म् ऽउ᳘पस्पृशति सो ऽग्नि᳘म् स᳘ᳫँ᳭स्थिते"
  clean = normalize_sb_orthography(raw)
  assert clean == "अन्तरेणाहवनीयञ्च व्रतम् उपस्पृशति सो ऽग्निम् संस्थिते"


def test_build_sb_vp_preserves_8_2_6_svarita_and_formats_summary():
  # यज्ञ᳓म् + एव᳓ + एत᳓त् -> यज्ञ᳓म् एवै᳙त᳓त् (Weber marks ॗ on मे!)
  pp_body = "\n".join([
    "- यज्ञ᳓म् (*RV*, *TS*)",
    "- एव᳓ (*RV*, *TS*)",
    "- एत᳓त् (*RV*, *TS*)",
  ])
  items = parse_padapatha_items(pp_body)
  weber = "यज्ञ᳘मेॗवैत᳘त्॥"
  shri = "यज्ञ᳘मे᳘वैत᳘त्॥"
  summary, vp_out, unmapped = build_sb_vp_from_padapatha(
    "यज्ञम् एवैतत् ॥", items, weber_text=weber, shri_text=shri
  )
  assert unmapped == []
  assert summary == "विश्वास-प्रस्तुतिः"
  assert vp_out == "यज्ञ᳓म् एवै᳙त᳓त् ॥"

  rep = audit_padapatha_against_sb("यज्ञम् एवैतत् ॥", items, weber, shri)
  assert rep.disagree_pada_indices == []
  assert all(s.status == "both_ok" for s in rep.syllables)


def test_audit_prefers_weber_when_shri_disagrees_and_flags_mutual_error():
  # SB 1.1.1.1 opening: Weber `व्रतमु᳘पैष्यन्` (right: व्रत᳓म् + उ᳓पैष्यन्) vs Shri `व्व्रत᳘मुपैष्यन्` (wrong)
  items_ok = parse_padapatha_items(
    "- व्रत᳓म् (*RV*, *TS*)\n- उ᳓पैष्यन् (पा॰ ६.२.४९ / Weber)"
  )
  rep = audit_padapatha_against_sb(
    "व्रतम् उपैष्यन् ।", items_ok, "व्रतमु᳘पैष्यन्॥", "व्व्रत᳘मुपैष्यन्।"
  )
  assert rep.disagree_pada_indices == []
  assert rep.weber_only_pada_indices == [0, 1]

  # Now test a mutual two-source error (both Weber and Shri misplace accent on `व्रतम्` as `व्र᳘तम्`).
  items_vyat = parse_padapatha_items(
    "- व्र᳓तम् → **व्रत᳓म्** (*RV*, *TS*)\n- उ᳓पैष्यन् (पा॰ ६.२.४९)"
  )
  rep2 = audit_padapatha_against_sb(
    "व्रतम् उपैष्यन् ।", items_vyat, "व्र᳘तमु᳘पैष्यन्॥", "व्व्र᳘तमु᳘पैष्यन्।"
  )
  assert rep2.disagree_pada_indices == [0]
  assert rep2.unflagged_vyatyasta_padas == []
  assert rep2.possibly_spurious_vyatyasta_padas == []

  summary, vp_out, _ = build_sb_vp_from_padapatha(
    "व्रतम् उपैष्यन् ।", items_vyat, weber_text="व्र᳘तमु᳘पैष्यन्॥", shri_text="व्व्र᳘तमु᳘पैष्यन्।"
  )
  assert summary == "विश्वास-प्रस्तुतिः (1/2 व्यत्यस्त-स्वराः)"
  assert vp_out == "[[व्र᳓तम्|व्रत᳓म्]] उ᳓पैष्यन् ।"


def test_reconciler_and_validator_sb_cluster_with_8_2_6():
  md = """## ०१

<details open><summary>विश्वास-प्रस्तुतिः</summary>

यज्ञ᳓म् एवै᳙त᳓त् ॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

यज्ञ᳘मे᳘वैत᳘त्॥
</details>

<details><summary>मूलम् - Weber</summary>

यज्ञ᳘मेॗवैत᳘त्॥
</details>

<details><summary>मूलम् - विस्वरम्</summary>

यज्ञमेवैतत् ॥
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- यज्ञ᳓म् (*RV*, *TS*)
- एव᳓ (*RV*, *TS*)
- एत᳓त् (*RV*, *TS*)
</details>
"""
  # Reconciler in SB cluster must preserve पा॰ ८.२.६ `एवै᳙त᳓त्` without flagging it!
  reconciled, logs = reconcile_markdown_blocks(md)
  assert reconciled == md
  assert logs == []
  assert validate_accented_markdown(md) == []
  ok, _, _, _ = verify_mantra_sandhi(["यज्ञ᳓म्", "एव᳓", "एत᳓त्"], "यज्ञ᳘मेॗवैत᳘त्॥")
  assert ok


def test_format_suggested_vp_summary():
  assert format_suggested_vp_summary("विश्वास-प्रस्तुतिः", 2, 15) == "विश्वास-प्रस्तुतिः (2/15 व्यत्यस्त-स्वराः)"
  assert format_suggested_vp_summary("विश्वास-प्रस्तुतिः (1/10 व्यत्यस्त-स्वराः)", 0, 10) == "विश्वास-प्रस्तुतिः"


def test_sb_sandhi_and_validator_regressions():
  # पा॰ १.१.१४ pragṛhya उ (`यद्य् उ अश्नाति`) and triple-consonant nasal sandhi (`तन् न्वेव`).
  assert verify_mantra_sandhi(["त᳓त्", "नु᳓", "एव᳓"], "तॗन्न्वेव")[0]
  assert verify_mantra_sandhi(["य᳓दि", "उ", "अश्ना᳓ति"], "य᳘द्यु अश्ना᳘ति")[0]
  # Feminine noun `सं-स्था᳓म्` must not be flagged as unsplit upasarga+tiṅanta ending in `-थाम्`.
  md = """<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- सं-स्था᳓म् (*TS*-1 सँ॒स्थाम्)
</details>
"""
  assert validate_accented_markdown(md) == []
  # `स वै + आरण्यम् -> स वा आरण्यम्` must not trigger a false `aa_hiatus` on coalesced `याः वा + आरण्याः -> या वारण्या`.
  md2 = """<details><summary>मूलम् - Weber</summary>

स वा᳘ आरण्य᳘मेॗवाश्नीयात्॥ या᳘ वारण्या ओ᳘षधयः॥
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- सः᳓ (*RV*)
- वै᳓ (*RV*)
- आरण्य᳓म् (*TS*)
- एव᳓ (*RV*)
- अश्नीयात् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
- याः᳓ (*RV*)
- वा (अनुदात्तम्, पा॰ ८.१.१८)
- आरण्याः᳓ (*TS*)
- ओ᳓षधयः (*RV*)
</details>
"""
  assert validate_accented_markdown(md2) == []


def test_separated_8_1_71_upasarga_tinanta_vyatyasta_and_double_upasarga():
  # 1. Subordinate-clause vyatyasta tiṅanta separated from पा॰ ८.१.७१ upasarga (`उत्` + `यच्छति → **य᳓च्छति**`).
  pp_lines = [
    "- व᳓ज्रम् (*RV*, *TS*; Weber-पाठः)",
    "- उत् (तिङि चोदात्तवति पा॰ ८.१.७१; Weber-पाठः; श्रीधरादि उ᳘त्)",
    "- यच्छति → **य᳓च्छति** (यद्वृत्तान्नित्यम् पा॰ ८.१.६६; Weber उद्यछति, श्रीधरादि उ᳘द्यछति)",
  ]
  items = parse_padapatha_items("\n".join(pp_lines))
  vp_clean = "वज्रम् उद्यच्छति ॥"
  weber = "व᳘ज्रमुद्यछति॥"
  shri = "व्वज्रमु᳘द्यछति॥"

  assert verify_mantra_sandhi([it.ref for it in items], vp_clean)[0]
  assert verify_mantra_sandhi([it.ref for it in items], weber)[0]
  vp_sum, vp_acc, unmapped = build_sb_vp_from_padapatha(vp_clean, items, weber_text=weber, shri_text=shri)
  assert unmapped == []
  assert vp_sum == "विश्वास-प्रस्तुतिः (1/3 व्यत्यस्त-स्वराः)"
  assert vp_acc == "व᳓ज्रम् [[उद्यच्छति|उद्य᳓च्छति]] ॥"

  rep = audit_padapatha_against_sb(vp_clean, items, weber, shri)
  assert rep.disagree_pada_indices == [2]
  assert rep.unflagged_vyatyasta_padas == []
  assert rep.possibly_spurious_vyatyasta_padas == []

  md = (
    f"<details open><summary>{vp_sum}</summary>\n\n{vp_acc}\n</details>\n\n"
    f"<details><summary>मूलम् - श्रीधरादि</summary>\n\n{shri}\n</details>\n\n"
    f"<details><summary>मूलम् - Weber</summary>\n\n{weber}\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः - 1/3 व्यत्यस्त-स्वराः)</summary>\n\n"
    + "\n".join(pp_lines)
    + "\n</details>\n"
  )
  assert validate_accented_markdown(md) == []
  rec_out, rec_logs = reconcile_markdown_blocks(md)
  assert rec_out == md
  assert rec_logs == []

  # 2. Double upasarga in subordinate clause (`उप` + `आ` + `व᳓र्तते`) with पा॰ ८.२.६ svarita (`एवो᳙पाव᳓र्तते`).
  pp_dbl = [
    "- सः᳓ (*RV*, *TS*)",
    "- या᳓न् (*RV*, *TS*)",
    "- एव᳓ (*RV*, *TS*)",
    "- उप (तिङि चोदात्तवति पा॰ ८.१.७१)",
    "- आ (तिङि चोदात्तवति पा॰ ८.१.७१)",
    "- व᳓र्तते (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, *TS* उ॒पाव॑र्तते)",
  ]
  items_dbl = parse_padapatha_items("\n".join(pp_dbl))
  vp_dbl = "स यान् एवोपावर्तते ॥"
  weber_dbl = "स या᳘नेॗवोपाव᳘र्तते॥"
  shri_dbl = "स या᳘ने᳘वोपाव᳘र्तते॥"
  assert verify_mantra_sandhi([it.ref for it in items_dbl], vp_dbl)[0]
  sum_dbl, acc_dbl, unm_dbl = build_sb_vp_from_padapatha(vp_dbl, items_dbl, weber_text=weber_dbl, shri_text=shri_dbl)
  assert unm_dbl == []
  assert sum_dbl == "विश्वास-प्रस्तुतिः"
  assert acc_dbl == "स᳓ या᳓न् एवो᳙पाव᳓र्तते ॥"
  rep_dbl = audit_padapatha_against_sb(vp_dbl, items_dbl, weber_dbl, shri_dbl)
  assert rep_dbl.disagree_pada_indices == []
  assert rep_dbl.unflagged_vyatyasta_padas == []
  assert rep_dbl.possibly_spurious_vyatyasta_padas == []

  # 3. Vowel-coalesced upasarga + vyatyasta tiṅanta (`उप` + `एति → **ए᳓ति**` -> `[[उपैति|उपै᳓ति]]`) must not falsely
  #    flag the non-vyatyasta `उप` partner as unflagged when both sources omit accent on the merged `पै` syllable.
  pp_coal = [
    "- व्रत᳓म् (*RV*, *TS*)",
    "- उप (तिङि चोदात्तवति पा॰ ८.१.७१)",
    "- एति → **ए᳓ति** (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, *TS* उ॒पैति॑)",
  ]
  items_coal = parse_padapatha_items("\n".join(pp_coal))
  sum_c, acc_c, unm_c = build_sb_vp_from_padapatha("व्रतम् उपैति ॥", items_coal, weber_text="व्रत᳘मुपैति॥", shri_text="व्व्रत᳘मुपैति॥")
  assert unm_c == []
  assert sum_c == "विश्वास-प्रस्तुतिः (1/3 व्यत्यस्त-स्वराः)"
  assert acc_c == "व्रत᳓म् [[उपैति|उपै᳓ति]] ॥"
  rep_c = audit_padapatha_against_sb("व्रतम् उपैति ॥", items_coal, "व्रत᳘मुपैति॥", "व्व्रत᳘मुपैति॥")
  assert rep_c.unflagged_vyatyasta_padas == []
  assert rep_c.possibly_spurious_vyatyasta_padas == []


def test_forbid_compound_upasarga_tinanta_sb_auto_and_ta_compat():
  unsplit_lines = [
    "- उप-स्पृश᳓ति (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, तिङि चोदात्तवति पा॰ ८.१.७१, तुदादिभ्यः शः पा॰ ३.१.७७)",
    "- उद्यच्छति → **उद्-य᳓च्छति** (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, तिङि चोदात्तवति पा॰ ८.१.७१)",
    "- उप-आ-व᳓र्तते (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, पा॰ ८.१.७१, *TS* उ॒पाव॑र्तते)",
    "- उपस्पृश᳓ति (यद्वृत्तान्नित्यम् पा॰ ८.१.६६)",
    "- उपै᳓ति (यद्वृत्तान्नित्यम् पा॰ ८.१.६६)",
  ]
  # Default (TA compatibility) allows subordinate-clause compound upasarga+tiṅanta
  assert find_unsplit_upasarga_tinantas(unsplit_lines) == []
  # ŚB strict mode catches all 5
  assert len(find_unsplit_upasarga_tinantas(unsplit_lines, forbid_compound_upasarga_tinanta=True)) == 5

  # Separated upasargas, simplex verbs (including augmented `अ᳓वदत्` and `आप᳓यति`), and गतिकृदन्त stay valid
  valid_sb_lines = [
    "- उप (तिङि चोदात्तवति पा॰ ८.१.७१)",
    "- स्पृश᳓ति (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, तुदादिभ्यः शः पा॰ ३.१.७७)",
    "- अभि (तिङि चोदात्तवति पा॰ ८.१.७१)",
    "- आप᳓यति (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, णिच् पा॰ ३.१.३)",
    "- ए᳓ति (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, *TS* उ॒पैति॑)",
    "- अ᳓वदत् (यद्वृत्तान्नित्यम् पा॰ ८.१.६६)",
    "- उप-एष्य᳓न् (*TS* ए॒ष्यन्, पा॰ ६.२.१३९ गतिकारकोपपदात् कृत्)",
    "- उत्-सि᳓च्य (लिति पा॰ ६.१.१९३)",
    "- अति-हृ᳓त्य (लिति पा॰ ६.१.१९३)",
    "- उ᳓द्-यन्तुम् (*TS* उद्य॑न्तुम्)",
    "- स᳓ं-स्थिते (*TS*, गतिरनन्तरः पा॰ ६.२.४९)",
    "- नि-वाते᳓ (*TS*, *AV*, *MW*)",
    "- सम्-प्र᳓ति (*TS*, *MW*)",
  ]
  assert find_unsplit_upasarga_tinantas(valid_sb_lines, forbid_compound_upasarga_tinanta=True) == []

  # validate_accented_markdown auto-enables forbid_compound_upasarga_tinanta on ŚB clusters (Weber/श्रीधरादि)
  sb_bad_md = (
    "<details><summary>मूलम् - Weber</summary>\n\nअप᳘ उपस्पृश᳘ति॥\n</details>\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- अपः᳓ (*RV*)\n"
    "- उप-स्पृश᳓ति (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, पा॰ ८.१.७१)\n"
    "</details>\n"
  )
  issues = validate_accented_markdown(sb_bad_md)
  assert any(iss.kind == "unsplit_upasarga_tinanta" for iss in issues)

  # Non-ŚB (TA) cluster keeps backward compatibility
  ta_ok_md = (
    "<details><summary>मूलम्</summary>\n\nप्र॒चोद॑यात् ॥\n</details>\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- प्र-चोद᳓यात् (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, तिङि चोदात्तवति पा॰ ८.१.७१)\n"
    "</details>\n"
  )
  assert validate_accented_markdown(ta_ok_md) == []


def test_audit_cross_pada_ripple_and_boundary_svarita():
  # 1. Cross-pada ripple: `त᳓त्` + `वदति → **व᳓दति**` against `त᳘द्वदति` must blame only `व᳓दति`, not `त᳓त्`.
  items1 = parse_padapatha_items(
    "- त᳓त् (*RV*, *TS*)\n- वदति → **व᳓दति** (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, *RV*)"
  )
  rep1 = audit_padapatha_against_sb("तद् वदति ॥", items1, "त᳘द्वदति॥", "त᳘द्वदति॥")
  assert rep1.disagree_pada_indices == [1]
  assert rep1.unflagged_vyatyasta_padas == []
  assert rep1.possibly_spurious_vyatyasta_padas == []

  # 2. Cross-pada ripple with monosyllabic vyat between two udāttas (`सः᳓` + `यत् → **य᳓त्**` + `त᳓त्`).
  items2 = parse_padapatha_items(
    "- सः᳓ (*RV*)\n- यत् → **य᳓त्** (*RV*)\n- त᳓त् (*RV*)"
  )
  rep2 = audit_padapatha_against_sb("स यत् तत् ॥", items2, "स᳘ यत्त᳘त्॥", "स᳘ यत्त᳘त्॥")
  assert rep2.disagree_pada_indices == [1]
  assert rep2.unflagged_vyatyasta_padas == []
  assert rep2.possibly_spurious_vyatyasta_padas == []

  # 3. Śrīdharādi-only `S -> S` (पा॰ ८.२.६ merger immediately after jātya svarita `S`).
  items3 = parse_padapatha_items(
    "- मनुष्ये᳙ (*TS*)\n- न᳓ (*RV*)\n- अस्ति (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)"
  )
  _, vp3, unm3 = build_sb_vp_from_padapatha("मनुष्ये नास्ति ॥", items3, shri_text="मनुष्ये᳘ नास्ति॥")
  assert unm3 == []
  assert vp3 == "मनुष्ये᳙ ना᳙स्ति ॥"

  # 4. Boundary `idx == n - 1` ending in `S` with unknown next_first_mark allows Weber G/"" and Shri H/"".
  items4 = parse_padapatha_items("- त᳓त् (*RV*)\n- वीर्य᳙म् (*RV*, *TS*)")
  rep4 = audit_padapatha_against_sb("तद् वीर्यम् ॥", items4, "त᳘द्वी᳘र्यॗम्॥", "त᳘द्वी᳘र्यं᳘॥")
  assert rep4.disagree_pada_indices == []


def test_apply_sb_kandika_updates_preserves_layers_existing_us_and_layouts(tmp_path):
  md_file = tmp_path / "sb_sample.md"
  initial = """+++
title = "१"
+++

<details open><summary>विश्वास-प्रस्तुतिः</summary>

हरिः-ओ३म्।
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

हरिः-ओ३म्।
</details>

##  ०१

<details open><summary>विश्वास-प्रस्तुतिः</summary>

यज्ञ᳘मे᳘वैत᳘त्॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

यज्ञ᳘मे᳘वैत᳘त्॥
</details>

<details><summary>मूलम् - Weber</summary>

यज्ञ᳘मेॗवैत᳘त्॥
</details>

<details><summary>मूलम् - विस्वरम्</summary>

यज्ञमेवैतत् ॥
</details>

<details><summary>सायणः</summary>

सायणभाष्यम्।
</details>

<details><summary>हरिस्वामी</summary>

हरिस्वामिभाष्यम्।
</details>

<details><summary>Eggeling</summary>

Eggeling translation.
</details>

<details><summary>मूलम् - Makoto</summary>

Makoto text.
</details>

## ०२

<details open><summary>विश्वास-प्रस्तुतिः</summary>

त᳓द् वै᳓[[!!]] अपः᳓ ॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

त᳘द्वै ऽअपः᳘॥
</details>

<details><summary>मूलम् - Weber</summary>

त᳘द्वै अपः᳘॥
</details>

## ०३

<details open><summary>विश्वास-प्रस्तुतिः</summary>

त᳘दपः᳘॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

त᳘दपः᳘॥
</details>

<details><summary>Eggeling</summary>

Eggeling before visvaram.
</details>

<details><summary>मूलम् - विस्वरम्</summary>

तदपः ॥
</details>

## ०४

<details open><summary>विश्वास-प्रस्तुतिः</summary>

त᳘त्॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

त᳘त्॥
</details>

<details open><summary>विश्वास-प्रस्तुतिः</summary>

यज्ञ᳘मे᳘वैत᳘त्॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

यज्ञ᳘मे᳘वैत᳘त्॥
</details>

<details><summary>मूलम् - Weber</summary>

यज्ञ᳘मेॗवैत᳘त्॥
</details>
## ०५ कथा-माया

<details open><summary>विश्वास-प्रस्तुतिः</summary>

यज्ञ᳘मे᳘वैत᳘त्॥
</details>

<details><summary>विश्वास-टिप्पनी</summary>

Editorial note between VP and mula.
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

यज्ञ᳘मे᳘वैत᳘त्॥
</details>

<details><summary>मूलम् - Weber</summary>

यज्ञ᳘मेॗवैत᳘त्॥
</details>

<details><summary>सायणः</summary>

सायणभाष्यम् ५।
</details>
"""
  md_file.write_text(initial, encoding="utf-8")

  kandika_map = {
    "०१": (
      "यज्ञम् एवैतत् ॥",
      ["- यज्ञ᳓म् (*RV*, *TS*)", "- एव᳓ (*RV*, *TS*)", "- एत᳓त् (*RV*, *TS*)"],
    ),
    "०२": (
      None,
      ["- त᳓त् (*RV*, *TS*)", "- वै᳓ (*RV*, *TS*)", "- अपः᳓ (*RV*, *TS*)"],
    ),
    "०३": (
      "तद् अपः ॥",
      ["- त᳓त् (*RV*, *TS*)", "- अपः᳓ (*RV*, *TS*)"],
    ),
    ("०४", 1): (
      "यज्ञम् एवैतत् ॥",
      ["- यज्ञ᳓म् (*RV*, *TS*)", "- एव᳓ (*RV*, *TS*)", "- एत᳓त् (*RV*, *TS*)"],
    ),
    "०५": (
      "यज्ञम् एवैतत् ॥",
      ["- यज्ञ᳓म् (*RV*, *TS*)", "- एव᳓ (*RV*, *TS*)", "- एत᳓त् (*RV*, *TS*)"],
    ),
  }

  # Ambiguous plain key on multi-VP section ०४ must fail safely before writing
  import pytest
  with pytest.raises(ValueError, match="Ambiguous section key"):
    apply_sb_kandika_updates(md_file, {"०४": ("तत् ॥", ["- त᳓त् (*RV*)"])})
  assert md_file.read_text(encoding="utf-8") == initial

  # Invalid unsplit upasarga+tiṅanta must fail validation BEFORE writing to disk
  with pytest.raises(ValueError, match="unsplit_upasarga_tinanta"):
    apply_sb_kandika_updates(
      md_file,
      {"०१": ("उपस्पृशति ॥", ["- उप-स्पृश᳓ति (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, पा॰ ८.१.७१)"])},
    )
  assert md_file.read_text(encoding="utf-8") == initial

  rep = apply_sb_kandika_updates(md_file, kandika_map, preserve_existing_us=True)
  assert isinstance(rep, SbFileUpdateReport)
  assert rep.wrote is True
  assert rep.validation_issues == []
  assert rep.reconcile_logs == []
  assert rep.updated_keys == ["०१", "०२", "०३", "०४[1]", "०५ कथा-माया"]
  assert rep.preserved_us_keys == ["०२"]

  out = md_file.read_text(encoding="utf-8")
  # Intro VP block untouched
  assert "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nहरिः-ओ३म्।\n</details>" in out
  # Already-US VP in ०२ preserved byte-for-byte verbatim (with [[!!]])
  assert "त᳓द् वै᳓[[!!]] अपः᳓ ॥" in out
  # ०१ has पा॰ ८.२.६ svarita and पद-पाठः placed BEFORE सायणः (not after Makoto!)
  assert "यज्ञ᳓म् एवै᳙त᳓त् ॥" in out
  sec1 = out.split("##  ०१")[1].split("## ०२")[0]
  assert sec1.index("पद-पाठः (यान्त्रिकः)") < sec1.index("सायणः") < sec1.index("हरिस्वामी") < sec1.index("मूलम् - Makoto")
  # ०३ places पद-पाठः right after मूलम् - श्रीधरादि, BEFORE Eggeling
  sec3 = out.split("## ०३")[1].split("## ०४")[0]
  assert sec3.index("मूलम् - श्रीधरादि") < sec3.index("पद-पाठः (यान्त्रिकः)") < sec3.index("Eggeling")
  # ०४[0] stays untouched while ०४[1] gets updated
  sec4 = out.split("## ०४")[1].split("## ०५")[0]
  assert "त᳘त्॥" in sec4
  assert "यज्ञ᳓म् एवै᳙त᳓त् ॥" in sec4
  # ०५ skips intervening विश्वास-टिप्पनी, reads Weber ॗ -> ᳙, and places पद-पाठः after मूलम् - Weber before सायणः
  sec5 = out.split("## ०५ कथा-माया")[1]
  assert "यज्ञ᳓म् एवै᳙त᳓त् ॥" in sec5
  assert sec5.index("विश्वास-टिप्पनी") < sec5.index("मूलम् - Weber") < sec5.index("पद-पाठः (यान्त्रिकः)") < sec5.index("सायणः")

  # Re-running is 100% idempotent
  rep2 = apply_sb_kandika_updates(md_file, kandika_map, preserve_existing_us=True)
  assert rep2.wrote is True
  assert md_file.read_text(encoding="utf-8") == out


def test_corpus_occurrence_count_provenance_accepted_by_validator_and_reconciler():
  md = """## ०१

<details open><summary>विश्वास-प्रस्तुतिः</summary>

यज्ञ᳓म् एवै᳙त᳓त् ॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

यज्ञ᳘मे᳘वैत᳘त्॥
</details>

<details><summary>मूलम् - Weber</summary>

यज्ञ᳘मेॗवैत᳘त्॥
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- यज्ञ᳓म् (*RV*-145, *TS*-82, *VS*-34, *TB*-19)
- एव᳓ (*RV*-310, *TS*-290, *AV*-120)
- एत᳓त् (*TS*-95, *RV*-41, *ŚB*-12)
</details>
"""
  items = parse_padapatha_items(md.split("पद-पाठः (यान्त्रिकः)</summary>")[1].split("</details>")[0])
  assert len(items) == 3
  assert all(it.solid for it in items)
  assert validate_accented_markdown(md) == []
  rec_out, rec_logs = reconcile_markdown_blocks(md)
  assert rec_out == md
  assert rec_logs == []


def test_panini_abbreviation_sign_guard_sb_vs_ta():
  # ŚB clusters require Devanagari abbreviation sign पा॰ (\u0970) and reject digit-zero पा\u0966
  sb_zero = (
    "<details><summary>मूलम् - Weber</summary>\n\nत᳘दस्ति॥\n</details>\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- त᳓त् (*RV*-100)\n"
    "- अस्ति (तिङन्तम् अनुदात्तम्, पा\u0966 ८.१.२८)\n"
    "</details>\n"
  )
  issues = validate_accented_markdown(sb_zero)
  assert any(iss.kind == "zero_abbrev_sign" for iss in issues)

  sb_ok = sb_zero.replace("पा\u0966", "पा॰")
  assert validate_accented_markdown(sb_ok) == []

  # `पा\u0966` is now rejected everywhere by default (user rule); legacy TA data can opt out explicitly
  ta_legacy = sb_zero.replace("मूलम् - Weber", "मूलम्")
  assert any(iss.kind == "zero_abbrev_sign" for iss in validate_accented_markdown(ta_legacy))
  assert validate_accented_markdown(ta_legacy, forbid_zero_abbreviation=False) == []






def test_weber_h_on_anudatta_before_8_2_6_svarita_is_preserved():
  # Real 01/09/2.md::२२ pattern: Weber/Shri print ᳘ (not ॗ) on `मे` before पा॰ ८.२.६ svarita `वै᳙`.
  pp = "- मिथुन᳓म् (*RV*)\n- एव᳓ (*RV*)\n- एत᳓त् (*RV*)"
  items = parse_padapatha_items(pp)
  _, vp, unm = build_sb_vp_from_padapatha(
    "मिथुनम् एवैतत् ॥", items, weber_text="मिथुन᳘मे᳘वैत᳘त्॥", shri_text="मिथुन᳘मे᳘वैत᳘त्॥"
  )
  assert unm == [] and vp == "मिथुन᳓म् एवै᳙त᳓त् ॥"
  # An aligned, unmarked Weber overrules a solo Śrīdharādi `᳘`
  _, vp2, _ = build_sb_vp_from_padapatha(
    "मिथुन᳓म् एवैतत् ॥", items, weber_text="मिथुन᳘मेवैत᳘त्॥", shri_text="मिथुन᳘मे᳘वैत᳘त्॥"
  )
  assert "ै᳙" not in vp2


def test_simplex_aa_initial_verbs_not_flagged_as_unsplit_upasarga():
  # Regression (01/01/2.md::०७): `आसुः` and other simplex `आ`-initial perfect/imperfect/aorist verbs
  # must NOT be flagged as unsplit `आ-` upasarga+tiṅanta.
  lines = [
    "- आसुः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *RV*-2, *TS*-1)",
    "- आसन् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *RV*-1)",
    "- आसीत् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *RV*-1)",
    "- आहुः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *RV*-1)",
    "- आपुः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आरुः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आस् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आसम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आर्षीत् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आसतुः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आवम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अवृणीत (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अवृणीध्वम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- सुस्राव (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- विनक्ति (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- विनक्तु (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- विच्य᳓ते (यद्वृत्तान्नित्यम् पा॰ ८.१.६६)",
    "- प्रथस्व (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- प्रथताम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- विन्दन्ति (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- विन्देत (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आजन्त (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- विद्युः᳓ (यद्वृत्तान्नित्यम् पा॰ ८.१.६६)",
    "- विजते (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अतिष्ठन् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अप्रीणन् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आ-शया᳓त् (*MW* ŚBr., *Macdonell*, *Lanman*)",
    "- अवृज्यत (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अपद्यत (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- निन्ये (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अपादयत (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अवपन् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- सुणोति (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- सुणुयात् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आदयन्ति (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आदित्या᳓त् (*TB*-1)",
  ]
  assert find_unsplit_upasarga_tinantas(lines, forbid_compound_upasarga_tinanta=True) == []
  assert verify_mantra_sandhi(["द्या᳓वा-पृथिव्योः", "र᳓सम्"], "द्यावापृथिव्यो रसं")[0]
  assert verify_mantra_sandhi(["च", "एव", "आ", "इत"], "चैवैत")[0]
  assert verify_mantra_sandhi(["भस्म", "अयातयाम्न्यः"], "भस्मायातयाम्न्यः")[0]
  assert verify_mantra_sandhi(["दधाति", "एतौ", "एव"], "दधाति एतावेव")[0]
  assert verify_mantra_sandhi(["अभाः", "उखा", "इति"], "अभारुखेति")[0]
  assert verify_mantra_sandhi(["उ᳓दङ्", "उ᳓त्"], "उदङ्ङुत्")[0]
  assert verify_mantra_sandhi(["तस्मात्", "सम्-राट्"], "तस्मात् सम्म्राट्")[0]
  assert verify_mantra_sandhi(["उभय᳓तः", "न्यू᳙नाम्"], "उभयतो न्यूनां")[0]
  assert verify_mantra_sandhi(["अभि᳓", "सुनोति"], "अभिषुणोति")[0]
  items_etad = parse_padapatha_items("- एत᳓त् (*RV*)\n- हि᳓ (*RV*)\n- अ᳓ग्रे (*RV*)")
  _, vp_etad, unm_etad = build_sb_vp_from_padapatha("एतद्ध्यग्रे ॥", items_etad)
  assert unm_etad == [] and vp_etad == "एत᳓द्ध्य᳓ग्रे ॥"


def test_fused_avagraha_token_preserves_later_pada_initial_accents():
  # Regression (#71): `_skip_elided_avagraha_lead` must only skip `vsi == 0` (the elided initial `अ`),
  # never the initial syllable (`si == 0`, `vsi > 0`) of subsequent padas fused inside an `ऽ...` token.
  items1 = parse_padapatha_items(
    "- यः᳓ (*RV*)\n"
    "- अस्मा᳓न् (*AV*, *RV*)\n"
    "- धू᳓र्वति (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, *TB*)\n"
  )
  _, vp1, unm1 = build_sb_vp_from_padapatha(
    "यो ऽस्मान्धूर्वति ॥", items1, weber_text="यो ऽस्मान्धू᳘र्वति॥", shri_text="यो ऽस्मान्धू᳘र्वति॥"
  )
  assert unm1 == []
  assert vp1 == "यो᳙ ऽस्मा᳓न्धू᳓र्वति ॥"
  rep1 = audit_padapatha_against_sb(
    "यो ऽस्मान्धूर्वति ॥", items1, "यो ऽस्मान्धू᳘र्वति॥", "यो ऽस्मान्धू᳘र्वति॥"
  )
  assert rep1.disagree_pada_indices == []
  assert rep1.unflagged_vyatyasta_padas == []

  items2 = parse_padapatha_items(
    "- त᳓तः (*RV*, *TS*)\n"
    "- अभि (तिङि चोदात्तवति पा॰ ८.१.७१)\n"
    "- वि᳓ (*RV*, *TS*)\n"
    "- पश्यति (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)\n"
  )
  _, vp2, unm2 = build_sb_vp_from_padapatha(
    "ततो ऽभिविपश्यति ॥", items2, weber_text="त᳘तो ऽभिवि᳘पश्यति॥", shri_text="त᳘तो ऽभिवि᳘पश्यति॥"
  )
  assert unm2 == []
  assert vp2 == "त᳓तो ऽभिवि᳓पश्यति ॥"
  rep2 = audit_padapatha_against_sb(
    "ततो ऽभिविपश्यति ॥", items2, "त᳘तो ऽभिवि᳘पश्यति॥", "त᳘तो ऽभिवि᳘पश्यति॥"
  )
  assert rep2.disagree_pada_indices == []
  assert rep2.unflagged_vyatyasta_padas == []


def test_final_sprint_guards_and_pluta_and_pause_udatta():
  from doc_curation.sanskrit.accent.sandhi_check import verify_mantra_sandhi
  from doc_curation.sanskrit.accent.validator import (
    find_unexplained_aa_hiatuses,
    find_unlicensed_unaccented_padas,
    find_unsplit_upasarga_tinantas,
  )

  # 1. #285 item 1: `आ + अयम्` hiatus in 11/04/2.md::०१
  assert verify_mantra_sandhi(["प्र᳓ति-प्रतिम्", "नु᳓", "आ᳓", "अय᳓म्"], "प्रतिप्रतिं न्व् आ अयम्")[0]

  # 2. #285 item 2: `पा॰ ८.१.१८` anti-cheat rejects bogus nouns/compounds, keeps genuine enclitics
  assert len(find_unlicensed_unaccented_padas(["- पुमास्तेन (अनुदात्तम्, पा॰ ८.१.१८)"])) == 1
  assert len(find_unlicensed_unaccented_padas(["- अ-देवः (अनुदात्तम्, पा॰ ८.१.१८)"])) == 1
  assert find_unlicensed_unaccented_padas([
    "- च (अनुदात्तम्, पा॰ ८.१.१८)",
    "- इव (अनुदात्तम्, पा॰ ८.१.१८)",
    "- ह (अनुदात्तम्, पा॰ ८.१.१८)",
    "- ते (अनुदात्तम्, पा॰ ८.१.१८)",
    "- नः (अनुदात्तम्, पा॰ ८.१.१८)",
    "- बत (अनुदात्तम्, पा॰ ८.१.१८)",
    "- वत (अनुदात्तम्, पा॰ ८.१.१८)",
    "- त्वत् (अनुदात्तम्, पा॰ ८.१.१८)",
  ]) == []

  # 3. #302, #304, #308, #360: simplex verbs exempt from unsplit_upasarga_tinanta
  assert find_unsplit_upasarga_tinantas(
    [
      "- अववृत्रन् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
      "- अवृथाः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
      "- सुवाति (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
      "- आशिषुः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    ],
    forbid_compound_upasarga_tinanta=True,
  ) == []

  # 4. #305: final-udātta before `॥` followed by udātta (`next_first_mark="U"` or mid-kaṇḍikā `॥`)
  items_p = parse_padapatha_items("- स᳓र्वे (*RV*)\n- प्राणाः᳓ (*RV*)")
  rep_p = audit_padapatha_against_sb(
    "सर्वे प्राणाः ॥", items_p, "स᳘र्वे प्राणाः᳟॥", "स᳘र्व्वे प्प्राणाः᳘॥", next_first_mark="U"
  )
  assert rep_p.disagree_pada_indices == []
  items_mid = parse_padapatha_items("- आत्मा᳓ (*RV*)\n- अ᳓गृह्यः (*MW*)")
  rep_mid = audit_padapatha_against_sb(
    "आत्मा ॥ अगृह्यः ॥", items_mid, "आत्मा᳟॥ अ᳘गृह्यः॥", "आत्मा᳘॥ अ᳘गृह्यः॥"
  )
  assert rep_mid.disagree_pada_indices == []
  items_uu = parse_padapatha_items("- लोकाः᳓ (*RV*)\n- प्र᳓-तिष्ठिताः (*TS*)")
  rep_uu = audit_padapatha_against_sb(
    "लोकाः प्र-तिष्ठिताः ॥", items_uu, "लोकाः᳘ प्र᳘तिष्ठिताः॥", "लोकाः᳘ प्प्र᳘तिष्ठिताः॥"
  )
  assert rep_uu.disagree_pada_indices == []
  items_ma = parse_padapatha_items(
    "- उप (तिङि चोदात्तवति पा॰ ८.१.७१)\n"
    "- सम् (तिङि चोदात्तवति पा॰ ८.१.७१)\n"
    "- आ᳓ (*RV*)\n"
    "- अवर्तत (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)"
  )
  _, vp_ma, unm_ma = build_sb_vp_from_padapatha(
    "उपसमावर्तत ॥", items_ma, weber_text="उपसमा᳘वर्तत॥", shri_text="उपसमा᳘वर्तत॥"
  )
  assert unm_ma == [] and vp_ma == "उपसमा᳓वर्तत ॥"
  rep_ma = audit_padapatha_against_sb("उपसमावर्तत ॥", items_ma, "उपसमा᳘वर्तत॥", "उपसमा᳘वर्तत॥")
  assert rep_ma.disagree_pada_indices == []

  # 5. #306 & #307: word-medial pluta `३` does not split VP tokens
  items_arka = parse_padapatha_items("- अर्का᳓३न् (*RV*)\n- इ᳓ति (*TS*)")
  _, vp_arka, unm_arka = build_sb_vp_from_padapatha("अर्का३निति", items_arka)
  assert unm_arka == [] and vp_arka == "अर्का᳓३नि᳓ति"

  # 6. #309: `आसिथ + उप` ardharca hiatus
  assert find_unexplained_aa_hiatuses(["- आसिथ (*RV*)", "- उ᳓प (*RV*)"], "मन्द आसिथ उपमञ्घ्यति") == []

  # 7. #311 & #312: `एव + इदम् -> एवैदम्` and VS 19.2 `परि + इतः + सिञ्चता -> परीतो षिञ्चता`
  assert verify_mantra_sandhi(["य᳓था", "ह", "एव᳓", "इद᳓म्"], "यथा हैवैदम्")[0]
  assert verify_mantra_sandhi(["प᳓रि", "इतः᳓", "सिञ्चता", "सुत᳓म्", "इ᳓ति"], "परीतो षिञ्चता सुतमिति")[0]
  assert verify_mantra_sandhi(["प᳓रि", "इतः᳓", "षिञ्चता", "सुत᳓म्", "इ᳓ति"], "परीतो षिञ्चता सुतमिति")[0]


