"""Tests for VS-M <-> VS-K Rk/Yajuḥ deduplication, merging, hemistich handling, and validation."""
from __future__ import annotations

import pathlib

from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup import (
  VskSubBlock,
  extract_and_link_shared_yajuh,
  is_no_patha_bheda,
  load_rk_index,
  match_and_rewrite_vsk_sections,
  merge_kanva_into_rk_tiikaa,
  merge_vsk_hemistich_pair,
  normalize_phonetic,
  refresh_all_prefills,
  strip_trailing_refs,
  validate_dedup_integrity,
)


def test_phonetic_normalization_and_no_patha_bheda():
  assert strip_trailing_refs("स्वा᳓हा ॥१०॥ ॥ (४) २२ ॥") == "स्वा᳓हा"
  # Ignore numbering, spacing, hyphens, avagraha orthography, repha gemination, bold & inline glosses.
  vp_m = "अग्नि᳓र्मूर्द्धा᳓ दिवः᳓ ककु᳓त्प᳓तिः पृथिव्या᳓ऽअय᳓म् +++(=अग्निः)+++। **अपाँ᳓** रे᳓ताँसि जिन्वति ॥१२॥"
  vp_k = "अग्नि᳓र् मूर्धा᳓ दिवः᳓ ककु᳓त् प᳓तिः पृथिव्या᳓ अय᳓म् ।\nअपाँ᳓ रे᳓ताँसि जिन्वति ॥२॥ १८"
  assert is_no_patha_bheda(vp_m, vp_k)

  # Accent difference or ड/ळ or pluta २/३ counts as real pāṭha variant.
  assert not is_no_patha_bheda("मही᳓ द्यौः᳓ पृथिवी᳓ च नः", "मही᳓ द्यौः पृ᳙थिवी᳓ च नः")
  assert not is_no_patha_bheda("हवि᳓ष्माँ२", "हवि᳓ष्माँ३")
  assert normalize_phonetic("उपप्रयन्तो ऽअध्वरम्") == normalize_phonetic("उपप्रयन्तो ऽध्वरम्")


def test_phonetic_normalization_ms_ks_orthography():
  # MS/KS orthographic differences: ँ/ं, ꣳ/ं, [वयल]्ँ, pause स्/र्->ः, ayogavāha accent order, छ/च्छ, TITUS ृ̄.
  assert is_no_patha_bheda("अपाँ᳓ रे᳓ताँसि पितृ᳓̄न् बह्वी᳓स् ।", "अपां᳓ रे᳓तांसि पितॄ᳓न् बह्वीः᳓ ॥")
  assert is_no_patha_bheda("देवो᳓ वः सवितो᳓त्पुनात्व् अ᳓छिद्रेण", "देवो᳓ वस् सवितो᳓त्पुनात्व् अ᳓च्छिद्रेण")
  # Reconciler [[OLD|NEW]] compares on actual OLD reading (so differing OLD accents stay variants, not overwritten).
  assert not is_no_patha_bheda("[[चि᳓द्|चिद्]] असि", "चिद् असि")
  assert is_no_patha_bheda("[[चिद्|चि᳓द्]] असि", "चिद् असि")
  # Superscript footnotes stripped without disturbing Vedic pluta digits २/३.
  assert is_no_patha_bheda("हवि᳓ष्माँ२¹³", "हवि᳓ष्माँ२")


def test_hemistich_merge_relocates_h2_avatarika():
  b1 = VskSubBlock(
    av_blocks=[("अनन्ताचार्यः - विनियोगः", "ब्रह्म क्षत्रम् इति पयः पुनाति।")],
    vp="ब्र᳓ह्म क्षत्रं᳓ पवते।",
    tika_blocks=[("मूलम्", "ब्रह्म॑ क्ष॒त्रम्।"), ("सायण-टीका", "प्रथमो भागः।")],
    kandika_ref="21.5",
  )
  b2 = VskSubBlock(
    av_blocks=[("आनन्दबोधः - विनियोगः", "पयोग्रहान् गृह्णाति - 'कुविद्-अङ्ग' इति।")],
    vp="शुक्रे᳓ण देव।",
    tika_blocks=[("मूलम्", "शु॒क्रेण॑ देव।"), ("सायण-टीका", "द्वितीयो भागः।")],
    kandika_ref="21.5",
  )
  b3 = VskSubBlock(
    av_blocks=[],
    vp="कुवि᳓द्-अङ्ग᳓।",
    tika_blocks=[("मूलम्", "कु॒विद॒ङ्ग।")],
    kandika_ref="21.5",
  )
  merged, b3_upd = merge_vsk_hemistich_pair(b1, b2, b3)
  assert "ब्र᳓ह्म क्षत्रं᳓ पवते।  \nशुक्रे᳓ण देव।" == merged.vp
  assert len(merged.av_blocks) == 1
  assert b3_upd is not None and any("कुविद्" in b for _, b in b3_upd.av_blocks)
  assert dict(merged.tika_blocks)["सायण-टीका"] == "प्रथमो भागः।  \nद्वितीयो भागः।"


def test_full_dedup_rk_and_yajuh_synthetic(tmp_path: pathlib.Path):
  repo = tmp_path / "vedAH_yajuH"
  rk_vp = repo / "static/vAjasaneyam/mAdhyandinam/saMhitA/Rk/vishvAsa-prastutiH"
  rk_tk = repo / "static/vAjasaneyam/mAdhyandinam/saMhitA/Rk/sarvASh_TIkAH"
  yj_dir = repo / "static/vAjasaneyam/mAdhyandinam/saMhitA/yajuH/sarva-prastutiH"
  vsm_dir = repo / "content/vAjasaneyam/mAdhyandinam/saMhitA/sarva-prastutiH"
  vsk_dir = repo / "content/vAjasaneyam/kANvam/saMhitA/sarva-prastutiH"
  for d in (rk_vp / "01", rk_tk / "01", vsm_dir, vsk_dir):
    d.mkdir(parents=True)

  # 1. Rk exact match (only numbering & virama-join differ)
  (rk_vp / "01/01_exact.md").write_text('+++\ntitle = "०१"\n+++\nसमि᳓धाग्निं᳓ दुवस्यत घृतै᳓र्बोधयता᳓तिथिम्। आ᳓स्मिन्हव्या᳓ जुहोतन ॥१॥\n', encoding="utf-8")
  (rk_tk / "01/01_exact.md").write_text(
    '+++\ntitle = "०१"\n+++\n'
    '<details><summary>मूलम्</summary>\n\nस॒मिधा॒ग्निं दु॑वस्यत।\n</details>\n'
    '<details><summary>पदपाठः - दयानन्दादि</summary>\n\nस॒मिधा॑।\n</details>\n'
    '<details><summary>उवट-टीका</summary>\n\nउवटः।\n</details>\n'
    '<details><summary>सायण-टीका</summary>\n\nतैत्तिरीय-सायणः।\n</details>\n'
    '<details><summary>दयानन्द-सरस्वती (सं)</summary>\n\nदयानन्दः।\n</details>\n',
    encoding="utf-8",
  )
  # 2. Rk minor variant (यज्ञपतिम् vs इमम्)
  (rk_vp / "01/02_var.md").write_text('+++\ntitle = "०२"\n+++\nदे᳓व सवितः प्र᳓सुव यज्ञं᳓ प्र᳓सुव यज्ञ᳓पतिं भ᳓गाय ॥२॥\n', encoding="utf-8")
  (rk_tk / "01/02_var.md").write_text(
    '+++\ntitle = "०२"\n+++\n'
    '<details><summary>मूलम्</summary>\n\nदे॒व स॑वितः प्र॒सुव॑ य॒ज्ञम्।\n</details>\n'
    '<details><summary>उवट-टीका</summary>\n\nउवटः २।\n</details>\n',
    encoding="utf-8",
  )

  # Fill 40 chapter stubs cleanly
  for ch in range(1, 41):
    if ch == 1:
      (vsm_dir / "01.md").write_text(
        '+++\ntitle = "०१"\n+++\n\n'
        '## ०१ समिधाग्निम्\n'
        '<details><summary>सर्वा अवतारिकाः</summary>\n<details><summary>उवटः - विनियोगः</summary>\n\nमाध्यन्दिनविनियोगः।\n</details>\n</details>\n'
        '<div class="js_include" newlevelforh1="3" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/Rk/vishvAsa-prastutiH/01/01_exact.md">\n'
        '<details open><summary><h3>विश्वास-प्रस्तुतिः ...{Loading}...</h3></summary>\n</details>\n</div>\n'
        '<div class="js_include collapsed" newlevelforh1="3" title="सर्वाष् टीकाः" unfilled url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/Rk/sarvASh_TIkAH/01/01_exact.md">\n'
        '<details><summary><h3>सर्वाष् टीकाः ...{Loading}...</h3></summary>\n</details>\n</div>\n\n'
        '## ०२ देव सवितः\n'
        '<div class="js_include" newlevelforh1="3" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/Rk/vishvAsa-prastutiH/01/02_var.md">\n'
        '<details open><summary><h3>विश्वास-प्रस्तुतिः ...{Loading}...</h3></summary>\n</details>\n</div>\n'
        '<div class="js_include collapsed" newlevelforh1="3" title="सर्वाष् टीकाः" unfilled url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/Rk/sarvASh_TIkAH/01/02_var.md">\n'
        '<details><summary><h3>सर्वाष् टीकाः ...{Loading}...</h3></summary>\n</details>\n</div>\n\n'
        '## ०३ इदमहम्\n'
        '<details><summary>सर्वा अवतारिकाः</summary>\n<details><summary>महीधरः - विनियोगः</summary>\n\nमाध्यन्दिन-यजुर्विनियोगः।\n</details>\n</details>\n'
        '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nइद᳓म् अह᳓म् अ᳓नृतात् सत्य᳓म् उ᳓पैमि ॥३॥\n</details>\n'
        '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>मूलम्</summary>\n\nइ॒दम॒हमनृ॑तात्।</details>\n'
        '<details><summary>उवट-टीका</summary>\n\nउवटयजुः।\n</details>\n</details>\n',
        encoding="utf-8",
      )
      (vsk_dir / "01.md").write_text(
        '+++\ntitle = "०१"\n+++\n\n'
        '## ०१ समिधाग्निम्\n'
        '<details><summary>सर्वा अवतारिकाः</summary>\n<details><summary>सायणः - विनियोगः</summary>\n\nकाण्वविनियोगः १।\n</details>\n</details>\n'
        '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nसमि᳓धाग्निं᳓ दुवस्यत घृतै᳓र् बोधयता᳓तिथिम् ।\n</details>\n'
        '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>मूलम्</summary>\n\nस॒मिधा॒ग्निं दु॑वस्यत ।\n</details>\n'
        '<details><summary>सायण-टीका</summary>\n\nप्रथमः खण्डः।\n</details>\n</details>\n'
        '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nआ᳓स्मिन् हव्या᳓ जुहोतन ॥१॥\n</details>\n'
        '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>मूलम्</summary>\n\nआस्मि॑न्ह॒व्या जु॑होतन ॥\n</details>\n'
        '<details><summary>सायण-टीका</summary>\n\nद्वितीयः खण्डः।\n</details>\n</details>\n\n'
        '## ०२ देव सवितः\n'
        '<details><summary>सर्वा अवतारिकाः</summary>\n<details><summary>सायणः - विनियोगः</summary>\n\nकाण्वविनियोगः २।\n</details>\n</details>\n'
        '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nदे᳓व सवितः प्र᳓सुव यज्ञं᳓ प्र᳓सुवेमं᳓ भ᳓गाय ॥२॥\n</details>\n'
        '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>मूलम्</summary>\n\nदेव॑ सवितः इमम्।\n</details>\n'
        '<details><summary>पदपाठः</summary>\n\nदेव॑। स॒वि॒तः॒।\n</details>\n'
        '<details><summary>सायण-टीका</summary>\n\nकाण्वसायणः २।\n</details>\n'
        '<details><summary>आनन्दबोध-टीका</summary>\n\nआनन्दबोधः २।\n</details>\n</details>\n\n'
        '## ०३ इदमहम्\n'
        '<details><summary>सर्वा अवतारिकाः</summary>\n<details><summary>सायणः - विनियोगः</summary>\n\nकाण्व-यजुर्विनियोगः।\n</details>\n</details>\n'
        '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nइद᳓म् अह᳓म् अ᳓नृतात् सत्य᳓म् उ᳓पैमि ॥३॥\n</details>\n'
        '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>मूलम्</summary>\n\nइ॒दम॒हमनृ॑तात् ॥३॥\n</details>\n'
        '<details><summary>सायण-टीका</summary>\n\nकाण्वयजुःसायणः।\n</details>\n</details>\n',
        encoding="utf-8",
      )
    else:
      for d in (vsm_dir, vsk_dir):
        (d / f"{ch:02d}.md").write_text(f'+++\ntitle = "{ch:02d}"\n+++\n', encoding="utf-8")

  rk_entries, grams = load_rk_index(repo / "static/vAjasaneyam/mAdhyandinam/saMhitA/Rk")
  merged_by_rk, rk_st = match_and_rewrite_vsk_sections(vsk_dir, rk_entries, grams)
  assert rk_st["hemistich_pairs_merged"] == 1
  assert rk_st["rk_exact_blocks"] == 1
  assert rk_st["rk_variant_blocks"] == 1
  for rel, ents in merged_by_rk.items():
    merge_kanva_into_rk_tiikaa(rk_tk / rel, ents)

  yj_st = extract_and_link_shared_yajuh(
    vsm_dir=vsm_dir, vsk_dir=vsk_dir, yajuh_dir=yj_dir, rk_norm_set={e["pb"] for e in rk_entries},
  )
  assert yj_st["yajuh_shared_files"] == 1
  assert yj_st["vsk_yajuh_blocks_linked"] == 1

  refresh_all_prefills(roots=(repo / "content",), rk_dir=repo / "static/vAjasaneyam/mAdhyandinam/saMhitA/Rk", hugo_base_dir=str(tmp_path))

  # Assertions on shared files and host pages
  exact_tk = (rk_tk / "01/01_exact.md").read_text(encoding="utf-8")
  assert "<summary>मूलम्</summary>" in exact_tk and "<summary>मूलम् - माध्यन्दिनम्</summary>" not in exact_tk
  assert "<summary>सायण-टीका</summary>" in exact_tk and "<summary>सायण-टीका (काण्वी)</summary>" in exact_tk
  assert exact_tk.index("<summary>सायण-टीका (काण्वी)</summary>") < exact_tk.index("<summary>दयानन्द-सरस्वती (सं)</summary>")

  var_tk = (rk_tk / "01/02_var.md").read_text(encoding="utf-8")
  assert "<summary>मूलम् - माध्यन्दिनम्</summary>" in var_tk
  assert "<summary>मूलम् - काण्वम्</summary>" in var_tk
  assert "<summary>पदपाठः - काण्वः</summary>" in var_tk
  assert "<summary>सायण-टीका (काण्वी)</summary>" in var_tk
  assert "<summary>आनन्दबोध-टीका</summary>" in var_tk

  vsk_01 = (vsk_dir / "01.md").read_text(encoding="utf-8")
  assert "Rk/vishvAsa-prastutiH/01/01_exact.md" in vsk_01
  assert "Rk/sarvASh_TIkAH/01/01_exact.md" in vsk_01
  assert "Rk/vishvAsa-prastutiH/01/02_var.md" not in vsk_01
  assert "प्र᳓सुवेमं᳓" in vsk_01
  assert "Rk/sarvASh_TIkAH/01/02_var.md" in vsk_01
  assert "yajuH/sarva-prastutiH/01/03_idam_aham_anRtAt.md" in vsk_01
  assert "काण्व-यजुर्विनियोगः" in vsk_01

  vsm_01 = (vsm_dir / "01.md").read_text(encoding="utf-8")
  assert "yajuH/sarva-prastutiH/01/03_idam_aham_anRtAt.md" in vsm_01
  assert "माध्यन्दिन-यजुर्विनियोगः" in vsm_01

  yj_file = yj_dir / "01/03_idam_aham_anRtAt.md"
  assert yj_file.is_file()
  yj_txt = yj_file.read_text(encoding="utf-8")
  assert "<details open><summary>विश्वास-प्रस्तुतिः</summary>" in yj_txt
  assert "<summary>उवट-टीका</summary>" in yj_txt and "<summary>सायण-टीका (काण्वी)</summary>" in yj_txt
  assert "विनियोगः" not in yj_txt

  integrity = validate_dedup_integrity(
    vsm_sarva_dir=vsm_dir, vsk_sarva_dir=vsk_dir,
    vsm_rk_dir=repo / "static/vAjasaneyam/mAdhyandinam/saMhitA/Rk",
    vsm_yajuh_dir=yj_dir, hugo_base_dir=tmp_path,
  )
  assert integrity["issue_count"] == 0, integrity["issues"]


def test_format_static_title_and_stem_strips_quotes():
  from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import format_static_title_and_stem

  title, stem = format_static_title_and_stem('तदा᳓हुः । "द्वाद᳓शारत्नी रशना᳓"', num_prefix="14")
  assert '"' not in title
  assert "'" not in title
  assert title == "१४ तदाहुः द्वादशारत्नी रशना"
  assert stem == "tadAhuH_dvAdashAratnI_rashanA"
