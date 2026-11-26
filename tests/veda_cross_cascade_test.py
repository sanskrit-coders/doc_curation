"""Unit tests for cross-Veda deduplication cascade (matching, disambiguation, sweep, promotion)."""
from pathlib import Path

from doc_curation_projects.veda.dedup.cascade import (
  _detect_heading_level,
  _promote_inline_target,
  run_stage_cascade,
)
from doc_curation_projects.veda.dedup.commentary_merger import merge_tika_additions
from doc_curation_projects.veda.dedup.matcher import classify_match
from doc_curation_projects.veda.dedup.targets import load_corpus_specs


def test_classify_match_blocks_formulaic_tail_false_positives():
  # Same 55-char Yajuh prefix, totally different ending verb (`आ रभे` vs `प्रति गृह्णामि`).
  av_vp = "देव᳓स्य त्वा सवितुः᳓ प्रसवे᳓ऽश्वि᳓नोर्बाहु᳓भ्यां पूष्णो᳓ ह᳓स्ताभ्यां प्र᳓सूत आ᳓ रभे ॥"
  vs_vp = "देव᳓स्य त्वा सवितुः᳓ प्रसवे᳙ ऽश्वि᳓नोर् बाहु᳓भ्यां पूष्णो᳓ ह᳓स्ताभ्यां प्र᳓ति गृह्णामि ॥"
  from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import normalize_phonetic
  ok, _, _ = classify_match(
    av_vp, normalize_phonetic(av_vp), vs_vp, normalize_phonetic(vs_vp), allow_variant=True,
  )
  assert ok is False

  # Real exact match (spacing & US accents match after normalization) + minor pāṭha variant succeed.
  rv = "आ᳓पो हि᳓ ष्ठा᳓ मयो-भु᳓वस् ता᳓ न ऊर्जे᳓ दधातन । महे᳓ र᳓णाय च᳓क्षसे ॥"
  ts = "आ᳓पो हि᳓ ष्ठा᳓ मयोभु᳓वस् ता᳓ न ऊर्जे᳓ दधातन । महे᳓ र᳓णाय च᳓क्षसे ॥"
  ok2, rat2, eq2 = classify_match(rv, normalize_phonetic(rv), ts, normalize_phonetic(ts), allow_variant=True)
  assert ok2 is True and eq2 is True

  ts_var = "आ᳓पो हि᳓ ष्ठा᳓ मयो-भु᳓वस् ता᳓ न ऊर्जे᳓ दधातन । महे᳓ र᳓णाय सुच᳓क्षसे ॥"
  ok3, rat3, eq3 = classify_match(rv, normalize_phonetic(rv), ts_var, normalize_phonetic(ts_var), allow_variant=True)
  assert ok3 is True and eq3 is False and rat3 >= 0.88

  from doc_curation_projects.veda.dedup.matcher import InvertedVedaIndex, TargetEntry, looks_prose_brahmana
  prose = "शत᳓मानम् भवति शता᳓युᳶ पु᳓रुषश् शते᳓न्द्रिय आ᳓युष्य् एवे᳓न्द्रिये᳓ प्र᳓ति तिष्ठति ।"
  assert looks_prose_brahmana(prose, len(normalize_phonetic(prose)), summary="विश्वास-प्रस्तुतिः") is True
  idx_prose = InvertedVedaIndex(
    [TargetEntry(corpus="TS", kind="inline", rel="2.md", vp=prose, pb=normalize_phonetic(prose, include_accents=False, fold_orthography=True))],
    ("TS",),
  )
  assert idx_prose.find_best(prose, src_summary="विश्वास-प्रस्तुतिः", src_corpus="TB") is None
  yajuh = "म᳓नो ज्यो᳓तिर्जुषतामा᳓ज्यम् ।\nवि᳓च्छिन्नय्ँ यज्ञँ᳓ स᳓मिम᳓न्दधातु ।\nबृ᳓हस्प᳓तिस्तनुतामिम᳓न्नः ।"
  assert looks_prose_brahmana(yajuh, len(normalize_phonetic(yajuh)), summary="विश्वास-प्रस्तुतिः") is False


def test_merge_tika_additions_disambiguates_mulam_pada_and_commentators():
  specs = load_corpus_specs()
  rv_text = (
    '+++\ntitle = "01"\n+++\n\n'
    "<details><summary>Griffith</summary>\n\nYe Waters.\n</details>\n\n"
    "<details><summary>मूलम् - शाकलम्</summary>\n\nआपो॒ हि ष्ठा ।\n</details>\n\n"
    "<details><summary>पद-पाठः</summary>\n\nआपः॑ । हि । स्थ ।\n</details>\n"
  )
  merged = merge_tika_additions(
    rv_text,
    specs["RV"],
    [
      (
        specs["TS"],
        False,
        [
          ("Keith", "Ye waters."),
          ("मूलम्", "आपो॒ हि ष्ठा मयो॒भुवः॑ ।"),
          ("पद-पाठः", "आपः॑ । हि । स्थ । मयो॒भुवः॑ ।"),
          ("सायण-टीका", "तैत्तिरीयभाष्यम् ।"),
          ("भट्टभास्कर-टीका", "भास्करव्याख्या ।"),
        ],
        "/tmp/ts.md",
      )
    ],
  )
  assert "<summary>मूलम् - शाकलम्</summary>" in merged
  assert "<summary>मूलम् - तैत्तिरीयम्</summary>" in merged
  assert "<summary>पदपाठः - तैत्तिरीयः</summary>" in merged
  assert "<summary>Keith</summary>" in merged
  assert "<summary>भट्टभास्कर-टीका</summary>" in merged
  assert "<summary>सायण-टीका</summary>" in merged

  exact_merged = merge_tika_additions(
    rv_text,
    specs["RV"],
    [(specs["VS-M"], True, [("मूलम्", "आपो॒ हि ष्ठा ।"), ("उवट-टीका", "उवटः ।")], "/tmp/vsm.md")],
  )
  assert "<summary>मूलम् - माध्यन्दिनम्</summary>" not in exact_merged
  assert "<summary>उवट-टीका</summary>" in exact_merged

  # Adding VS-K on top qualifies Sāyaṇa collision cleanly!
  merged2 = merge_tika_additions(
    merged,
    specs["RV"],
    [
      (
        specs["VS-K"],
        False,
        [
          ("मूलम्", "आपो॒ हि ष्ठा काण्वम् ।"),
          ("पदपाठः", "आपः॑ । काण्वः ।"),
          ("सायण-टीका", "काण्वं भाष्यम् ।"),
        ],
        "/tmp/vsk.md",
      )
    ],
  )
  assert "<summary>मूलम् - काण्वम्</summary>" in merged2
  assert "<summary>पदपाठः - काण्वः</summary>" in merged2
  assert "<summary>सायण-टीका (काण्वी)</summary>" in merged2


def test_run_stage_cascade_end_to_end_promotion_sweep_and_static_migration(tmp_path: Path):
  v_root = tmp_path / "vishvasa"
  toml_p = tmp_path / "targets.toml"
  toml_p.write_text(
    f"""
[corpora.RV]
name = "RV"
shAkha_label = "शाकलम्"
pada_label = "पद-पाठः"
sayana_variant_label = "सायण-भाष्यम्"
has_two_part_rk = true
vp_dir = "{v_root}/vedAH_Rk/static/shAkalam/saMhitA/vishvAsa-prastutiH"
sarva_dir = "{v_root}/vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH"
vp_url_prefix = "/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH"
sarva_url_prefix = "/vedAH_Rk/shAkalam/saMhitA/sarvASh_TIkAH"

[corpora.VS-M]
name = "VS-M"
shAkha_label = "माध्यन्दिनम्"
pada_label = "पदपाठः - दयानन्दादि"
sayana_variant_label = "सायण-टीका (माध्यन्दिनी)"
content_dir = "{v_root}/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/saMhitA/sarva-prastutiH"
vp_dir = "{v_root}/vedAH_yajuH/static/vAjasaneyam/mAdhyandinam/saMhitA/Rk/vishvAsa-prastutiH"
sarva_dir = "{v_root}/vedAH_yajuH/static/vAjasaneyam/mAdhyandinam/saMhitA/Rk/sarvASh_TIkAH"
vp_url_prefix = "/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/Rk/vishvAsa-prastutiH"
sarva_url_prefix = "/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/Rk/sarvASh_TIkAH"
yajuh_sarva_prastuti_dir = "{v_root}/vedAH_yajuH/static/vAjasaneyam/mAdhyandinam/saMhitA/yajuH/sarva-prastutiH"
yajuh_sarva_prastuti_url = "/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/yajuH/sarva-prastutiH"

[corpora.TS]
name = "TS"
shAkha_label = "तैत्तिरीयम्"
pada_label = "पदपाठः - तैत्तिरीयः"
sayana_variant_label = "सायण-टीका (तैत्तिरीया)"
content_dir = "{v_root}/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/saMhitA/sarva-prastutiH"
vp_dir = "{v_root}/vedAH_yajuH/static/taittirIyam/sArasvata-vibhAgaH/saMhitA/Rk/vishvAsa-prastutiH"
sarva_dir = "{v_root}/vedAH_yajuH/static/taittirIyam/sArasvata-vibhAgaH/saMhitA/Rk/sarvASh_TIkAH"
vp_url_prefix = "/vedAH_yajuH/taittirIyam/sArasvata-vibhAgaH/saMhitA/Rk/vishvAsa-prastutiH"
sarva_url_prefix = "/vedAH_yajuH/taittirIyam/sArasvata-vibhAgaH/saMhitA/Rk/sarvASh_TIkAH"
""",
    encoding="utf-8",
  )
  specs = load_corpus_specs(toml_p)
  # Create RV target stanza (exact match with VS-M static + TS partial)
  rv_vp = specs["RV"].vp_dir / "10" / "009" / "01_Apo_hi.md"
  rv_tk = specs["RV"].sarva_dir / "10" / "009" / "01_Apo_hi.md"
  rv_vp.parent.mkdir(parents=True)
  rv_tk.parent.mkdir(parents=True)
  rv_vp.write_text('+++\ntitle = "01"\n+++\nआ᳓पो हि᳓ ष्ठा᳓ मयोभु᳓वस् ता᳓ न ऊर्जे᳓ दधातन ।\n', encoding="utf-8")
  rv_tk.write_text('+++\ntitle = "01"\n+++\n<details><summary>मूलम् - शाकलम्</summary>\n\nआपो॒ हि ष्ठा ।\n</details>\n', encoding="utf-8")

  # Create VS-M inline block for TS inline exact promotion test
  vsm_host = specs["VS-M"].content_dir / "01.md"
  vsm_host.parent.mkdir(parents=True)
  vsm_host.write_text(
    '+++\ntitle = "01"\n+++\n## ०१\n'
    '<details><summary>सर्वा अवतारिकाः</summary>\n<details><summary>उवटः</summary>\n\nviniyoga M\n</details>\n</details>\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nइषे᳓ त्वोर्जे᳓ त्वा वाय᳓वः स्थ दे᳓वो वः सविता᳓ प्रा᳓र्पयतु ।\n</details>\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>उवट-टीका</summary>\n\nuvata\n</details>\n</details>\n',
    encoding="utf-8",
  )

  # Create TS content with (a) partial RV include + leftover Keith, (b) inline block matching VS-M
  ts_host = specs["TS"].content_dir / "1" / "01.md"
  ts_host.parent.mkdir(parents=True)
  ts_host.write_text(
    '+++\ntitle = "01"\n+++\n'
    '<div class="js_include" newlevelforh1="4" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/10/009/01_Apo_hi.md">\n</div>\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>Keith</summary>\n\nYe waters\n</details>\n</details>\n\n'
    '<div class="js_include collapsed" newlevelforh1="4" title="सर्वाष् टीकाः" unfilled url="/vedAH_Rk/shAkalam/saMhitA/sarvASh_TIkAH/10/009/01_Apo_hi.md">\n</div>\n\n'
    '<details><summary>सर्वा अवतारिकाः</summary>\n<details><summary>भास्करोक्त-विनियोगः</summary>\n\nviniyoga T\n</details>\n</details>\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nइषे᳓ त्वोर्जे᳓ त्वा वाय᳓वः स्थ दे᳓वो वः सविता᳓ प्रा᳓र्पयतु ।\n</details>\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>भट्टभास्कर-टीका</summary>\n\nbhaskara\n</details>\n</details>\n',
    encoding="utf-8",
  )

  # Swap cached config temporarily using cascade internals
  load_corpus_specs.cache_clear()
  from doc_curation_projects.veda.dedup import cascade as cas_mod
  orig_loader = cas_mod.load_corpus_specs
  cas_mod.load_corpus_specs = lambda: specs
  try:
    res = run_stage_cascade(
      "TS", ("RV", "VS-M"),
      (v_root / "vedAH_yajuH" / "content", v_root / "vedAH_yajuH" / "static"),
      hugo_base_dir=str(v_root),
    )
  finally:
    cas_mod.load_corpus_specs = orig_loader

  assert res["partial_swept"] == 1
  assert res["content_exact"] == 1
  assert res["promoted_targets"] == 1
  assert "<summary>Keith</summary>" in rv_tk.read_text(encoding="utf-8")
  ts_txt = ts_host.read_text(encoding="utf-8")
  assert "viniyoga T" in ts_txt
  assert "/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/yajuH/sarva-prastutiH/" in ts_txt
  assert "/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/yajuH/sarva-prastutiH/" in vsm_host.read_text(encoding="utf-8")
  assert "viniyoga M" in vsm_host.read_text(encoding="utf-8")
  # Verify promoted static yajuH file holds BOTH uvata & bhaskara without अवतारिका!
  prom_files = list((specs["VS-M"].yajuh_sarva_prastuti_dir).rglob("*.md"))
  assert len(prom_files) == 1
  prom_txt = prom_files[0].read_text(encoding="utf-8")
  assert "uvata" in prom_txt and "bhaskara" in prom_txt and "अवतारिका" not in prom_txt


def test_render_host_include_pair_two_part_exact_and_variant():
  from doc_curation_projects.veda.dedup.block_parser import render_host_include_pair
  vp_ex, tk_ex = render_host_include_pair(
    exact_reading=True, vp_url="/a/vp.md", sarva_url="/a/tk.md", heading_level=4,
  )
  assert vp_ex and 'newlevelforh1="4"' in vp_ex and 'url="/a/vp.md"' in vp_ex
  assert tk_ex and 'collapsed' in tk_ex and 'url="/a/tk.md"' in tk_ex

  vp_var, tk_var = render_host_include_pair(
    exact_reading=False, local_vp_text="मन्त्रः", vp_url="/a/vp.md", sarva_url="/a/tk.md", heading_level=4,
  )
  assert vp_var and "<details open><summary>विश्वास-प्रस्तुतिः</summary>" in vp_var
  assert tk_var and 'newlevelforh1="4"' in tk_var and 'url="/a/tk.md"' in tk_var


def test_ms_and_ks_stage_cascade_with_yantra_svara_and_schroeder(tmp_path: Path):
  from doc_curation_projects.veda.dedup.matcher import looks_prose_brahmana

  assert looks_prose_brahmana("अमावास्या᳙ वै᳓ स᳓रस्वती पूर्ण᳓मासः स᳓रस्वान्॥", 35)

  v_root = tmp_path / "vishvAsa"
  toml_p = tmp_path / "targets.toml"
  toml_p.write_text(
    f"""
[repos]
vishvasa_root = "{v_root}"

[corpora.TS]
name = "TS"
shAkha_label = "तैत्तिरीयम्"
pada_label = "पदपाठः - तैत्तिरीयः"
sayana_variant_label = "सायण-टीका (तैत्तिरीया)"
content_dir = "{v_root}/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/saMhitA/sarva-prastutiH"
yajuh_sarva_prastuti_dir = "{v_root}/vedAH_yajuH/static/taittirIyam/sArasvata-vibhAgaH/saMhitA/yajuH/sarva-prastutiH"
yajuh_sarva_prastuti_url = "/vedAH_yajuH/taittirIyam/sArasvata-vibhAgaH/saMhitA/yajuH/sarva-prastutiH"

[corpora.MS]
name = "MS"
shAkha_label = "मैत्रायणीयम्"
pada_label = "पद-पाठः (यान्त्रिकः - मैत्रायणीयम्)"
sayana_variant_label = "सायण-टीका (मैत्रायणीया)"
content_dir = "{v_root}/vedAH_yajuH/content/maitrAyaNIyam/saMhitA/sarva-prastutiH"
vp_dir = "{v_root}/vedAH_yajuH/static/maitrAyaNIyam/saMhitA/Rk/vishvAsa-prastutiH"
sarva_dir = "{v_root}/vedAH_yajuH/static/maitrAyaNIyam/saMhitA/Rk/sarvASh_TIkAH"
vp_url_prefix = "/vedAH_yajuH/maitrAyaNIyam/saMhitA/Rk/vishvAsa-prastutiH"
sarva_url_prefix = "/vedAH_yajuH/maitrAyaNIyam/saMhitA/Rk/sarvASh_TIkAH"
yajuh_sarva_prastuti_dir = "{v_root}/vedAH_yajuH/static/maitrAyaNIyam/saMhitA/yajuH/sarva-prastutiH"
yajuh_sarva_prastuti_url = "/vedAH_yajuH/maitrAyaNIyam/saMhitA/yajuH/sarva-prastutiH"
yajuh_vp_dir = "{v_root}/vedAH_yajuH/static/maitrAyaNIyam/saMhitA/yajuH/vishvAsa-prastutiH"
yajuh_vp_url = "/vedAH_yajuH/maitrAyaNIyam/saMhitA/yajuH/vishvAsa-prastutiH"
yajuh_sarva_dir = "{v_root}/vedAH_yajuH/static/maitrAyaNIyam/saMhitA/yajuH/sarvASh_TIkAH"
yajuh_sarva_url = "/vedAH_yajuH/maitrAyaNIyam/saMhitA/yajuH/sarvASh_TIkAH"

[corpora.KS]
name = "KS"
shAkha_label = "काठकम्"
pada_label = "पद-पाठः (यान्त्रिकः - काठकम्)"
sayana_variant_label = "सायण-टीका (काठकी)"
content_dir = "{v_root}/vedAH_yajuH/content/kAThakam/kaTha-kapiShTalAH/saMhitA/sarva-prastutiH"
vp_dir = "{v_root}/vedAH_yajuH/static/kAThakam/kaTha-kapiShTalAH/saMhitA/Rk/vishvAsa-prastutiH"
sarva_dir = "{v_root}/vedAH_yajuH/static/kAThakam/kaTha-kapiShTalAH/saMhitA/Rk/sarvASh_TIkAH"
vp_url_prefix = "/vedAH_yajuH/kAThakam/kaTha-kapiShTalAH/saMhitA/Rk/vishvAsa-prastutiH"
sarva_url_prefix = "/vedAH_yajuH/kAThakam/kaTha-kapiShTalAH/saMhitA/Rk/sarvASh_TIkAH"
yajuh_sarva_prastuti_dir = "{v_root}/vedAH_yajuH/static/kAThakam/kaTha-kapiShTalAH/saMhitA/yajuH/sarva-prastutiH"
yajuh_sarva_prastuti_url = "/vedAH_yajuH/kAThakam/kaTha-kapiShTalAH/saMhitA/yajuH/sarva-prastutiH"
yajuh_vp_dir = "{v_root}/vedAH_yajuH/static/kAThakam/kaTha-kapiShTalAH/saMhitA/yajuH/vishvAsa-prastutiH"
yajuh_vp_url = "/vedAH_yajuH/kAThakam/kaTha-kapiShTalAH/saMhitA/yajuH/vishvAsa-prastutiH"
yajuh_sarva_dir = "{v_root}/vedAH_yajuH/static/kAThakam/kaTha-kapiShTalAH/saMhitA/yajuH/sarvASh_TIkAH"
yajuh_sarva_url = "/vedAH_yajuH/kAThakam/kaTha-kapiShTalAH/saMhitA/yajuH/sarvASh_TIkAH"
""",
    encoding="utf-8",
  )
  specs = load_corpus_specs(toml_p)
  ts_host = specs["TS"].content_dir / "1" / "01.md"
  ts_host.parent.mkdir(parents=True)
  ts_host.write_text(
    '+++\ntitle = "01"\n+++\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअमावास्या᳙ वै᳓ स᳓रस्वती पूर्ण᳓मासः स᳓रस्वान्॥\n</details>\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>मूलम्</summary>\n\nअमावास्या।</details>\n</details>\n',
    encoding="utf-8",
  )

  ms_host = specs["MS"].content_dir / "1" / "01.md"
  ms_host.parent.mkdir(parents=True)
  ms_host.write_text(
    '+++\ntitle = "01"\n+++\n'
    # 1. Brāhmaṇa prose matching TS -> must NOT match
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअमावास्या᳙ वै᳓ स᳓रस्वती पूर्ण᳓मासः स᳓रस्वान्॥\n</details>\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>मूलम्</summary>\n\nअमावास्या MS</details>\n</details>\n\n'
    # 2. Yajuḥ mantra shared with KS (यन्त्र-स्वरः)
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nदेव᳓स्य त्वा सवितुः᳓ प्रसवे᳙ ऽश्वि᳓नोर् बाहु᳓भ्याम् पूष्णो᳓ ह᳓स्ताभ्याम् ॥\n</details>\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>Gemini 3.8 Flash</summary>\n\nAt the impulse of god Savitr, with the arms of the Asvins.\n</details>\n'
    '<details><summary>मूलम्</summary>\n\nदेव᳓स्य त्वा सवितुः᳓\n</details>\n</details>\n\n'
    # 3. Real-accent MS Ṛk matching KS real-accent variant
    '<details open><summary>विश्वास-प्रस्तुतिः - ऋक्</summary>\n\nव्रजं᳓ कृणुध्वँ स᳓ हि᳓ वो नृपा᳓णः।\nपृथू᳓नि पु᳓रः कृणुध्वम् ॥\n</details>\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>मूलम्</summary>\n\nव्रजं᳓ MS।\n</details>\n'
    '<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- व्रज᳓म् (*RV*-1)\n</details>\n</details>\n\n'
    # 4. MS synthetic yantra-svara -> never promoted
    '<details open><summary>विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)</summary>\n\nइ᳓त्य् उ᳓परिकाण्डे जु᳓हूमग्रीयः प्र᳓पाठकः ॥\n</details>\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>मूलम्</summary>\n\nइत्यु।</details>\n</details>\n',
    encoding="utf-8",
  )

  ks_host = specs["KS"].content_dir / "1" / "01.md"
  ks_host.parent.mkdir(parents=True)
  ks_host.write_text(
    '+++\ntitle = "01"\n+++\n'
    # Matches MS #1 with synthetic yantra-svara accent diff on same consonants -> upgrade to exact!
    '<details open><summary>विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)</summary>\n\nदेव᳓स्य त्वा᳓ सवितुः प्रसवे᳙ऽश्वि᳓नोर्बाहु᳓भ्यां पूष्णो᳓ ह᳓स्ताभ्याम् ॥\n</details>\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>Gemini 3.8 Flash</summary>\n\nAt the impulse of god Savitr, with the arms of the Asvins.\n</details>\n'
    '<details><summary>मूलम्</summary>\n\nदेवस्य त्वा\n</details>\n'
    '<details><summary>Schroeder - टिप्पणी</summary>\n\n- **[1_1]** Ms note\n</details>\n</details>\n\n'
    # Matches MS #2 with real accent diff -> variant!
    '<details open><summary>विश्वास-प्रस्तुतिः - ऋक्</summary>\n\nव्रजं᳓ कृणुध्वँ स᳓ हि वो᳓ नृपा᳓णः।\nपृथू᳓नि पु᳓रः कृणुध्वम् ॥\n</details>\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>मूलम्</summary>\n\nव्रजं᳓ KS।\n</details>\n'
    '<details><summary>पद-पाठः (यान्त्रिकः - 1/3 व्यत्यस्त-स्वराः)</summary>\n\n- व्रज᳓म् (*KS_note*)\n</details>\n</details>\n\n'
    # Matches MS #3 yantra-svara colophon -> must NOT promote MS yantra-svara!
    '<details open><summary>विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)</summary>\n\nइ᳓त्य् उ᳓परिकाण्डे जु᳓हूमग्रीयः प्र᳓पाठकः ॥\n</details>\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>मूलम्</summary>\n\nइत्यु।</details>\n</details>\n',
    encoding="utf-8",
  )

  load_corpus_specs.cache_clear()
  from doc_curation_projects.veda.dedup import cascade as cas_mod
  orig_loader = cas_mod.load_corpus_specs
  cas_mod.load_corpus_specs = lambda: specs
  try:
    res_ms = run_stage_cascade(
      "MS", ("TS",), (v_root / "vedAH_yajuH" / "content", v_root / "vedAH_yajuH" / "static"),
      hugo_base_dir=str(v_root),
    )
    assert res_ms["content_exact"] == 0 and res_ms["content_variant"] == 0

    res_ks = run_stage_cascade(
      "KS", ("TS", "MS"), (v_root / "vedAH_yajuH" / "content", v_root / "vedAH_yajuH" / "static"),
      hugo_base_dir=str(v_root),
    )
  finally:
    cas_mod.load_corpus_specs = orig_loader

  assert res_ks["content_exact"] == 1
  assert res_ks["content_variant"] == 1
  assert res_ks["promoted_targets"] == 2
  ks_txt = ks_host.read_text(encoding="utf-8")
  assert "/vedAH_yajuH/maitrAyaNIyam/saMhitA/yajuH/sarva-prastutiH/" in ks_txt
  assert "/vedAH_yajuH/maitrAyaNIyam/saMhitA/Rk/sarvASh_TIkAH/" in ks_txt
  assert "/vedAH_yajuH/maitrAyaNIyam/saMhitA/Rk/vishvAsa-prastutiH/" not in ks_txt
  assert list(specs["MS"].vp_dir.rglob("*.md")) == []
  assert "<summary>विश्वास-प्रस्तुतिः - ऋक्</summary>" in ms_host.read_text(encoding="utf-8")
  assert "<summary>विश्वास-प्रस्तुतिः - ऋक्</summary>" in ks_txt
  assert "विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)" in ks_txt  # colophon stayed local!
  # Promoted static Yajuḥ should carry MS's authentic VP + single Gemini + Schroeder note!
  yaj_files = list(specs["MS"].yajuh_sarva_prastuti_dir.rglob("*.md"))
  assert len(yaj_files) == 1
  yaj_txt = yaj_files[0].read_text(encoding="utf-8")
  assert "सवितुः᳓ प्रसवे᳙" in yaj_txt
  assert yaj_txt.count("<summary>Gemini 3.8 Flash") == 1
  assert "<summary>Schroeder - टिप्पणी</summary>" in yaj_txt
  # Promoted variant Ṛk should separate MS & KS mūlam & padapāṭha labels cleanly!
  rk_tk_files = list(specs["MS"].sarva_dir.rglob("*.md"))
  assert len(rk_tk_files) == 1
  rk_tk = rk_tk_files[0].read_text(encoding="utf-8")
  assert "<summary>मूलम् - मैत्रायणीयम्</summary>" in rk_tk
  assert "<summary>मूलम् - काठकम्</summary>" in rk_tk
  assert "<summary>पद-पाठः (यान्त्रिकः - काठकम्)</summary>" in rk_tk


def test_format_static_title_and_stem_ignores_accents():
  from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import format_static_title_and_stem

  title, stem = format_static_title_and_stem("प्र᳓ति त्वा वर्ष᳓-वृद्धं वेत्तु", num_prefix="81")
  assert title == "८१ प्रति त्वा वर्ष"
  assert stem == "prati_tvA_varSha"

  title2, stem2 = format_static_title_and_stem("रोहि᳓त्कुण्डृणा᳓ची गोल᳓त्तिका ता᳓ अप्सर᳓साम् ।", num_prefix="05")
  assert title2 == "०५ रोहित्कुण्डृणाची गोलत्तिका ता"
  assert stem2 == "rohitkuNDRNAchI_golattikA_tA"


def test_fix_static_titles_and_accent_filenames(tmp_path: Path):
  from doc_curation_projects.veda.dedup.static_fixer import fix_static_titles_and_accent_filenames

  repo = tmp_path / "vedAH_yajuH"
  comb = repo / "static" / "vAjasaneyam" / "mAdhyandinam" / "saMhitA" / "yajuH" / "sarva-prastutiH" / "01" / "81_pra_ti_tvA.md"
  comb.parent.mkdir(parents=True, exist_ok=True)
  comb.write_text(
    '+++\ntitle = "pra_ti_tvA"\nunicode_script = "devanagari"\n+++\n\n'
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nप्र᳓ति त्वा वर्ष᳓-वृद्धं वेत्तु\n</details>\n",
    encoding="utf-8",
  )

  rk_vp = repo / "static" / "taittirIyam" / "Rk" / "vishvAsa-prastutiH" / "01" / "02_prajA_pataye_tvA.md"
  rk_tk = repo / "static" / "taittirIyam" / "Rk" / "sarvASh_TIkAH" / "01" / "02_prajA_pataye_tvA.md"
  rk_vp.parent.mkdir(parents=True, exist_ok=True)
  rk_tk.parent.mkdir(parents=True, exist_ok=True)
  rk_vp.write_text('+++\ntitle = "prajA_pataye_tvA"\nunicode_script = "devanagari"\n+++\n\nप्रजा᳓पतये त्वा ज्यो᳓तिष्मते।\n', encoding="utf-8")
  rk_tk.write_text('+++\ntitle = "prajA_pataye_tvA"\nunicode_script = "devanagari"\n+++\n\n<details><summary>मूलम्</summary>\n\nप्रजापतये</details>\n', encoding="utf-8")

  # Legacy hand-named file: convert Latin title to Devanāgarī, keep original slug filename.
  legacy = repo / "static" / "taittirIyam" / "ek" / "vishvAsa-prastutiH" / "2_17" / "tebhyo_vo_namaH.md"
  legacy.parent.mkdir(parents=True, exist_ok=True)
  legacy.write_text(
    '+++\ntitle = "Tebhyo vo nama H"\n+++\n\nते᳓भ्यो वो न᳓मस्।\n'
    '<div class="js_include" includetitle="false" newlevelforh1="4" unfilled url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/yajuH/sarva-prastutiH/01/81_pra_ti_tvA.md"></div>\n',
    encoding="utf-8",
  )

  caller = repo / "content" / "test" / "01.md"
  caller.parent.mkdir(parents=True, exist_ok=True)
  caller.write_text(
    '+++\ntitle = "01"\n+++\n\n'
    '<div class="js_include" includetitle="false" newlevelforh1="4" unfilled url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/yajuH/sarva-prastutiH/01/81_pra_ti_tvA.md"></div>\n'
    '<div class="js_include" includetitle="true" newlevelforh1="4" unfilled url="/vedAH_yajuH/taittirIyam/Rk/vishvAsa-prastutiH/01/02_prajA_pataye_tvA.md"></div>\n'
    '<div class="js_include" includetitle="false" newlevelforh1="4" unfilled url="/vedAH_yajuH/taittirIyam/Rk/sarvASh_TIkAH/01/02_prajA_pataye_tvA.md"></div>\n',
    encoding="utf-8",
  )

  res = fix_static_titles_and_accent_filenames(
    [repo / "static"],
    caller_roots=(repo / "content", repo / "static"),
    hugo_base_dir=str(tmp_path),
    dry_run=False,
  )
  assert res["titles_fixed"] == 4
  assert res["files_renamed"] == 3
  new_comb = comb.with_name("81_prati_tvA_varSha.md")
  assert not comb.exists() and new_comb.is_file()
  assert 'title = "८१ प्रति त्वा वर्ष"' in new_comb.read_text(encoding="utf-8")
  assert rk_vp.with_name("02_prajApataye_tvA_jyotiShmate.md").is_file()
  assert rk_tk.with_name("02_prajApataye_tvA_jyotiShmate.md").is_file()
  assert legacy.is_file()
  leg_txt = legacy.read_text(encoding="utf-8")
  assert 'title = "तेभ्यो वो नमस्"' in leg_txt
  assert "81_prati_tvA_varSha.md" in leg_txt
  c_txt = caller.read_text(encoding="utf-8")
  assert "81_prati_tvA_varSha.md" in c_txt
  assert "02_prajApataye_tvA_jyotiShmate.md" in c_txt
  assert "81_pra_ti_tvA.md" not in c_txt and "02_prajA_pataye_tvA.md" not in c_txt


def test_ek_stage_preserves_vp_only_callers_and_merges_haradatta(tmp_path: Path):
  from doc_curation_projects.veda.dedup.targets import VedaCorpusSpec

  v_root = tmp_path
  ts_c = v_root / "vedAH_yajuH" / "content" / "ts"
  ts_rk_vp = v_root / "vedAH_yajuH" / "static" / "ts" / "Rk" / "vishvAsa-prastutiH"
  ts_rk_tk = v_root / "vedAH_yajuH" / "static" / "ts" / "Rk" / "sarvASh_TIkAH"
  ts_y_comb = v_root / "vedAH_yajuH" / "static" / "ts" / "yajuH" / "sarva-prastutiH"
  ts_y_vp = v_root / "vedAH_yajuH" / "static" / "ts" / "yajuH" / "vishvAsa-prastutiH"
  ts_y_tk = v_root / "vedAH_yajuH" / "static" / "ts" / "yajuH" / "sarvASh_TIkAH"

  ek_vp = v_root / "vedAH_yajuH" / "static" / "ek" / "vishvAsa-prastutiH"
  ek_tk = v_root / "vedAH_yajuH" / "static" / "ek" / "sarvASh_TIkAH"
  ek_c = v_root / "vedAH_yajuH" / "content" / "ek"

  for d in (ts_c, ts_rk_vp, ts_rk_tk, ts_y_comb / "01", ts_y_vp, ts_y_tk, ek_vp / "1_01", ek_tk / "1_01", ek_c):
    d.mkdir(parents=True, exist_ok=True)

  # 1. Existing TS combined yajuH target with combined caller.
  ts_comb_file = ts_y_comb / "01" / "01_deva_savitH.md"
  ts_comb_file.write_text(
    '+++\ntitle = "०१ देव सवितः"\n+++\n\n'
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nदेव᳓ सवितः प्र᳓ सुव यज्ञं प्र᳓ सुव यज्ञ᳓पतिं भ᳓गाय ॥\n</details>\n\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>मूलम्</summary>\n\nदेव सवितः\n</details>\n</details>\n",
    encoding="utf-8",
  )
  ts_comb_caller = ts_c / "01.md"
  ts_comb_caller.write_text(
    '+++\ntitle = "01"\n+++\n\n'
    '<div class="js_include" includetitle="false" newlevelforh1="4" unfilled url="/vedAH_yajuH/ts/yajuH/sarva-prastutiH/01/01_deva_savitH.md"></div>\n\n'
    # 2. Inline TS yajuH target to be promoted on EK match with VP-only caller -> must force 2-part!
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nप्र᳓जापते न᳓ त्व᳓देतान्यन्यो विश्वा जा᳓तानि परि ता᳓ बभूव ॥\n</details>\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>मूलम्</summary>\n\nप्रजापते\n</details>\n</details>\n",
    encoding="utf-8",
  )

  # EK #1: matches ts_comb_file and has a VP-only caller (`madhuparkaH.md`) + 2-part caller (`sarva.md`).
  (ek_vp / "1_01" / "01_deva_savitH.md").write_text(
    '+++\ntitle = "०१ देव सवितः"\n+++\n\nदेव᳓ सवितः प्र᳓ सुव यज्ञं प्र᳓ सुव यज्ञ᳓पतिं भ᳓गाय ॥\n',
    encoding="utf-8",
  )
  (ek_tk / "1_01" / "01_deva_savitH.md").write_text(
    '+++\ntitle = "०१ देव सवितः"\n+++\n\n<details><summary>हरदत्तः</summary>\n\nहे सवितः प्रसुव अनुजानीहि।\n</details>\n',
    encoding="utf-8",
  )
  # EK #2: matches inline TS target and has a VP-only caller (`madhuparkaH.md`).
  (ek_vp / "1_01" / "02_prajApate.md").write_text(
    '+++\ntitle = "०२ प्रजापते"\n+++\n\nप्र᳓जापते न᳓ त्व᳓देतान्यन्यो विश्वा जा᳓तानि परि ता᳓ बभूव ॥\n',
    encoding="utf-8",
  )
  (ek_tk / "1_01" / "02_prajApate.md").write_text(
    '+++\ntitle = "०२ प्रजापते"\n+++\n\n<details><summary>हरदत्तः</summary>\n\nहरदत्तभाष्यम्।</details>\n',
    encoding="utf-8",
  )
  # EK #3: wrapper VP with js_include must be skipped completely.
  (ek_vp / "1_01" / "03_wrapper.md").write_text(
    '+++\ntitle = "०३ आवरणम्"\n+++\n\n<div class="js_include" url="/vedAH_yajuH/ek/vishvAsa-prastutiH/1_01/01_deva_savitH.md"></div>\n',
    encoding="utf-8",
  )
  (ek_tk / "1_01" / "03_wrapper.md").write_text('+++\ntitle = "०३ आवरणम्"\n+++\n\n<details><summary>मूलम्</summary>\n\nदेव\n</details>\n', encoding="utf-8")

  vp_only_caller = ek_c / "madhuparkaH.md"
  vp_only_caller.write_text(
    '+++\ntitle = "मधुपर्कः"\n+++\n\n'
    '<div class="js_include" newlevelforh1="4" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH_yajuH/ek/vishvAsa-prastutiH/1_01/01_deva_savitH.md"></div>\n'
    '<div class="js_include" newlevelforh1="4" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH_yajuH/ek/vishvAsa-prastutiH/1_01/02_prajApate.md"></div>\n',
    encoding="utf-8",
  )
  both_caller = ek_c / "1_01.md"
  both_caller.write_text(
    '+++\ntitle = "१.१"\n+++\n\n'
    '<div class="js_include" newlevelforh1="4" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH_yajuH/ek/vishvAsa-prastutiH/1_01/01_deva_savitH.md"></div>\n'
    '<div class="js_include" collapsed newlevelforh1="4" title="सर्वाष् टीकाः" unfilled url="/vedAH_yajuH/ek/sarvASh_TIkAH/1_01/01_deva_savitH.md"></div>\n'
    '<div class="js_include" newlevelforh1="4" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH_yajuH/ek/vishvAsa-prastutiH/1_01/02_prajApate.md"></div>\n'
    '<div class="js_include" collapsed newlevelforh1="4" title="सर्वाष् टीकाः" unfilled url="/vedAH_yajuH/ek/sarvASh_TIkAH/1_01/02_prajApate.md"></div>\n',
    encoding="utf-8",
  )

  specs = {
    "TS": VedaCorpusSpec(
      name="TS", shAkha_label="तैत्तिरीयम्", pada_label="पदपाठः - तैत्तिरीयः", sayana_variant_label="सायण-टीका (तैत्तिरीया)",
      content_dir=ts_c, vp_dir=ts_rk_vp, sarva_dir=ts_rk_tk,
      vp_url_prefix="/vedAH_yajuH/ts/Rk/vishvAsa-prastutiH", sarva_url_prefix="/vedAH_yajuH/ts/Rk/sarvASh_TIkAH",
      yajuh_vp_dir=ts_y_vp, yajuh_vp_url="/vedAH_yajuH/ts/yajuH/vishvAsa-prastutiH",
      yajuh_sarva_dir=ts_y_tk, yajuh_sarva_url="/vedAH_yajuH/ts/yajuH/sarvASh_TIkAH",
      yajuh_sarva_prastuti_dir=ts_y_comb, yajuh_sarva_prastuti_url="/vedAH_yajuH/ts/yajuH/sarva-prastutiH",
    ),
    "EK": VedaCorpusSpec(
      name="EK", shAkha_label="एकाग्निकाण्डम्", pada_label="पद-पाठः (एकाग्निकाण्डम्)", sayana_variant_label="सायण-टीका (एकाग्निकाण्डम्)",
      vp_dir=ek_vp, sarva_dir=ek_tk,
      vp_url_prefix="/vedAH_yajuH/ek/vishvAsa-prastutiH", sarva_url_prefix="/vedAH_yajuH/ek/sarvASh_TIkAH",
    ),
  }

  from doc_curation_projects.veda.dedup import cascade as cas_mod
  orig_loader = cas_mod.load_corpus_specs
  cas_mod.load_corpus_specs = lambda: specs
  try:
    res = run_stage_cascade("EK", ("TS",), (v_root / "vedAH_yajuH" / "content", v_root / "vedAH_yajuH" / "static"), hugo_base_dir=str(v_root))
  finally:
    cas_mod.load_corpus_specs = orig_loader

  assert res["static_exact"] == 2
  # VP-only caller MUST receive TS 2-part VP URLs, NEVER combined yajuH/sarva-prastutiH!
  vp_txt = vp_only_caller.read_text(encoding="utf-8")
  assert "/vedAH_yajuH/ts/yajuH/vishvAsa-prastutiH/" in vp_txt
  assert "/yajuH/sarva-prastutiH/" not in vp_txt
  assert "/sarvASh_TIkAH/" not in vp_txt
  # Original TS combined caller should have been cleanly split to 2-part.
  assert "/vedAH_yajuH/ts/yajuH/vishvAsa-prastutiH/" in ts_comb_caller.read_text(encoding="utf-8")
  assert "/yajuH/sarva-prastutiH/" not in ts_comb_caller.read_text(encoding="utf-8")
  # Haradatta should have been merged into both split TS sarvASh_TIkAH files.
  ts_tk1 = (ts_y_tk / "01" / "01_deva_savitH.md").read_text(encoding="utf-8")
  assert "<summary>हरदत्तः</summary>" in ts_tk1
  # Notice EK wrapper stayed untouched (not falsely matched/deleted).
  assert (ek_vp / "1_01" / "03_wrapper.md").is_file()


def test_ta_sweeps_multiple_inline_tikas_and_merges_tribhuvana(tmp_path: Path):
  from doc_curation_projects.veda.dedup.targets import VedaCorpusSpec

  v_root = tmp_path
  rv_vp = v_root / "vedAH_Rk" / "static" / "shAkalam" / "vishvAsa-prastutiH" / "01" / "089"
  rv_tk = v_root / "vedAH_Rk" / "static" / "shAkalam" / "sarvASh_TIkAH" / "01" / "089"
  ta_c = v_root / "vedAH_yajuH" / "content" / "ta"
  rv_vp.mkdir(parents=True, exist_ok=True)
  rv_tk.mkdir(parents=True, exist_ok=True)
  ta_c.mkdir(parents=True, exist_ok=True)

  (rv_vp / "06_svasti_na.md").write_text('+++\ntitle = "006"\n+++\n\nस्वस्ति᳓ न इ᳓न्द्रो वृद्ध᳓श्रवाः।\n', encoding="utf-8")
  (rv_tk / "06_svasti_na.md").write_text(
    '+++\ntitle = "006"\n+++\n\n<details><summary>सायण-भाष्यम्</summary>\n\nRV Sāyaṇa.\n</details>\n\n'
    "<details><summary>सायण-टीका</summary>\n\nतैत्तिरीयसंहितायां सायणभाष्यम् अतिविस्तरेण।</details>\n",
    encoding="utf-8",
  )

  ta_host = ta_c / "00_bhadraM.md"
  ta_host.write_text(
    '+++\ntitle = "00"\n+++\n\n'
    '<div class="js_include" newlevelforh1="4" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH_Rk/shAkalam/vishvAsa-prastutiH/01/089/06_svasti_na.md"></div>\n\n'
    "<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>त्रिभुवनः</summary>\n\nTribhuvana note.\n</details>\n</details>\n\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>सायण-टीका</summary>\n\nअथ शान्त्यर्थं द्वितीयमृचमाह वृद्धश्रवा इन्द्रो नः स्वस्ति दधातु।\n</details>\n</details>\n\n"
    '<div class="js_include" includetitle="true" newlevelforh1="4" unfilled url="/vedAH_Rk/shAkalam/sarvASh_TIkAH/01/089/06_svasti_na.md"></div>\n',
    encoding="utf-8",
  )

  specs = {
    "RV": VedaCorpusSpec(
      name="RV", shAkha_label="शाकलम्", pada_label="पदपाठः", sayana_variant_label="सायण-भाष्यम्",
      vp_dir=v_root / "vedAH_Rk" / "static" / "shAkalam" / "vishvAsa-prastutiH",
      sarva_dir=v_root / "vedAH_Rk" / "static" / "shAkalam" / "sarvASh_TIkAH",
      vp_url_prefix="/vedAH_Rk/shAkalam/vishvAsa-prastutiH",
      sarva_url_prefix="/vedAH_Rk/shAkalam/sarvASh_TIkAH",
    ),
    "TA": VedaCorpusSpec(
      name="TA", shAkha_label="तैत्तिरीयारण्यकम्", pada_label="पद-पाठः (तैत्तिरीयारण्यकम्)", sayana_variant_label="सायण-टीका (आरण्यकी)",
      content_dir=ta_c,
    ),
  }

  from doc_curation_projects.veda.dedup import cascade as cas_mod
  orig_loader = cas_mod.load_corpus_specs
  cas_mod.load_corpus_specs = lambda: specs
  try:
    res = run_stage_cascade("TA", ("RV",), (ta_c,), hugo_base_dir=str(v_root))
  finally:
    cas_mod.load_corpus_specs = orig_loader

  assert res["partial_swept"] == 1
  rv_txt = (rv_tk / "06_svasti_na.md").read_text(encoding="utf-8")
  assert "<summary>त्रिभुवनः</summary>" in rv_txt
  assert "<summary>सायण-टीका (आरण्यकी)</summary>" in rv_txt
  ta_txt = ta_host.read_text(encoding="utf-8")
  assert "सर्वाष् टीकाः</summary>" not in ta_txt  # both inline tika blocks swept!
  assert "/vedAH_Rk/shAkalam/sarvASh_TIkAH/01/089/06_svasti_na.md" in ta_txt


def test_tokenize_does_not_overlap_details_wrapping_includes():
  from doc_curation_projects.veda.dedup.block_parser import render_tokens, tokenize_markdown_body
  from doc_curation_projects.veda.dedup.cascade import _balanced_tags

  body = (
    '<details open><summary>आन्ध्रपाठे ऽधिकाः</summary>\n'
    '<details><summary>विनियोगः</summary>\nnote\n</details>\n\n'
    '<div class="js_include" url="/vedAH_yajuH/x/vishvAsa-prastutiH/a.md"></div>\n'
    '<div class="js_include" url="/vedAH_yajuH/x/sarvASh_TIkAH/a.md"></div>\n'
    '</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>द्राविडपाठः</summary>\nfull\n</details>\n</details>\n'
  )
  toks = tokenize_markdown_body(body)
  rendered = render_tokens("", toks)
  assert _balanced_tags(rendered)
  assert rendered.count("a.md") == 2
  assert rendered == body


def test_replace_group_tokens_keeps_blank_line_between_blocks():
  from doc_curation_projects.veda.dedup.block_parser import (
    group_mantra_units, render_host_include_pair, render_tokens, replace_group_tokens, tokenize_markdown_body,
  )

  body = (
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअ᳓ग्निमीळे पु᳓रोहितम् ।\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>मूलम्</summary>\n\nअग्निम्\n</details>\n</details>\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nद्वितीयः मन्त्रः ।\n</details>\n'
  )
  toks = tokenize_markdown_body(body)
  grps = group_mantra_units(toks)
  nv, ns = render_host_include_pair(
    exact_reading=False, local_vp_text=grps[0].vp_text, sarva_url="/vedAH/x/sarvASh_TIkAH/a.md", heading_level=3,
  )
  replace_group_tokens(toks, grps[0], new_vp_raw=nv, new_sarva_stub=ns, drop_inline_tika=True)
  out = render_tokens("", toks)
  assert "</div><details" not in out
  assert "</div>\n\n<details open><summary>विश्वास-प्रस्तुतिः</summary>" in out


def test_looks_prose_brahmana_blocks_ta_arthavada_cliches():
  from doc_curation_projects.veda.dedup.matcher import classify_unit_kind, looks_prose_brahmana

  assert looks_prose_brahmana("य᳓देवा᳓द्भ्यो᳓ऽन्नञ्जा᳓यते ।  \nत᳓द᳓वरुन्धे ।", 22)
  assert looks_prose_brahmana("त᳓स्मात् त᳓र्हि ते᳓क्ष्णिष्ठन्+++(=बहुतीक्ष्णं)+++ तपति।", 22)
  assert not looks_prose_brahmana("प्रतितिष्ठामि राष्ट्रम् ॥", 20, summary="ऋक्")

  # Two-line Brāhmaṇa prose ending in ॥ or containing quoted स्वाहेति must never become rk/yajuh
  assert classify_unit_kind("एव᳓म् इव हि᳓ मिथुनं᳓ कॢप्त᳓म् —  \nउत्त᳓रतो हि᳓ स्त्री᳓ पु᳓मांसम् उपशे᳓ते ॥", default_brahmana=True) == "brahmana"
  assert classify_unit_kind("किं᳓ छ᳓न्दः का᳓ देव᳓ता यो᳙ ऽय᳓म᳓वाङ् प्राण᳓ इ᳓ति ।  \nयज्ञायज्ञि᳓यं छ᳓न्दो वैश्वानरो᳓ देव᳓तेति ॥", default_brahmana=True) == "brahmana"
  assert classify_unit_kind("वा᳓ग्वै᳓ स᳓रस्वती वाचै᳙वै᳙नमेत᳓दभि᳓षिञ्चति पूष्णे᳓ स्वा᳓हे᳓ति ।", default_brahmana=True) == "brahmana"
  assert classify_unit_kind("वषट्कारा᳓ ह्ये᳙त᳓मा᳓हुतिभिरभिषिञ्च᳓न्त्या᳓हुतयो मे का᳓मान्त्स᳓मर्धयन्तु भूः᳓ स्वा᳓हे᳓ति ।", default_brahmana=True) == "brahmana"
  assert classify_unit_kind("स᳓रस्वत्यै पूष्णे᳙ ऽग्न᳓ये स्वा᳓हे᳓ति ।", default_brahmana=True) == "yajuh"
  assert classify_unit_kind("य᳓स्मिन् प᳓ञ्च पञ्चजना᳓ आकाश᳓श्च प्र᳓तिष्ठितः ।  \nत᳓मेव᳓ मन्य आत्मा᳓नं विद्वा᳓न् ब्र᳓ह्मामृ᳓तो ऽमृ᳓तम् ॥", default_brahmana=True) == "rk"
  assert classify_unit_kind("मांसा᳓न्यस्य᳓ श᳓कराणि कि᳓नाटं स्ना᳓व त᳓त्स्थिर᳓म् ।  \nअ᳓स्थीन्य᳓न्तरतो दा᳓रूणि मज्जा᳓ मज्जोपमा᳓ कृता᳓ ॥", default_brahmana=True) == "rk"
  assert classify_unit_kind("प्राणे᳓न र᳓क्षन्न᳓परं कुलायं᳓ बहि᳓ष्कुलाया᳓दमृ᳓तश्चरित्वा᳓ ।  \nस᳓ ईयते अमृ᳓तो यत्रका᳓मं हिरण्म᳓यः पौरुष᳓ एक-हंसः᳓ ॥", default_brahmana=True) == "rk"


def test_sb_m_sb_k_and_tb_brahmana_and_self_repeat_dedup(tmp_path: Path):
  from doc_curation_projects.veda.dedup.cascade import run_sb_dedup_cascade
  from doc_curation_projects.veda.dedup.targets import VedaCorpusSpec

  v_root = tmp_path / "vishvAsa"
  tb_c = v_root / "vedAH_yajuH" / "content" / "taittirIyam" / "brAhmaNam" / "sarva-prastutiH"
  tb_st = v_root / "vedAH_yajuH" / "static" / "taittirIyam" / "brAhmaNam"
  sbm_c = v_root / "vedAH_yajuH" / "content" / "vAjasaneyam" / "mAdhyandinam" / "shatapatha-brAhmaNam" / "sarva-prastutiH"
  sbm_st = v_root / "vedAH_yajuH" / "static" / "vAjasaneyam" / "mAdhyandinam" / "shatapatha-brAhmaNam"
  sbk_c = v_root / "vedAH_yajuH" / "content" / "vAjasaneyam" / "kANvam" / "shatapatha-brAhmaNam" / "sarva-prastutiH"

  for d in (
    tb_c / "3" / "9",
    tb_st / "Rk" / "vishvAsa-prastutiH",
    tb_st / "Rk" / "sarvASh_TIkAH",
    tb_st / "brAhmaNam" / "sarva-prastutiH",
    tb_st / "brAhmaNam" / "vishvAsa-prastutiH",
    tb_st / "brAhmaNam" / "sarvASh_TIkAH",
    sbm_c / "02" / "02",
    sbm_c / "04" / "03",
    sbm_c / "11" / "05",
    sbm_c / "13" / "03",
    sbm_c / "14" / "05",
    sbm_st / "Rk" / "vishvAsa-prastutiH",
    sbm_st / "Rk" / "sarvASh_TIkAH",
    sbm_st / "yajuH" / "sarva-prastutiH",
    sbm_st / "yajuH" / "vishvAsa-prastutiH",
    sbm_st / "yajuH" / "sarvASh_TIkAH",
    sbm_st / "brAhmaNam" / "sarva-prastutiH",
    sbm_st / "brAhmaNam" / "vishvAsa-prastutiH",
    sbm_st / "brAhmaNam" / "sarvASh_TIkAH",
    sbk_c / "01_ekapAtkANDam" / "02",
    sbk_c / "15_ashvamedhakANDam" / "03",
    sbk_c / "17_bRhadAraNyakam" / "02",
  ):
    d.mkdir(parents=True, exist_ok=True)

  # 1. Exact shared Brāhmaṇa sentence: TB 3/9/12 <-> SBM 13/03/6 <-> SBK 15/03/7
  tb_host = tb_c / "3" / "9" / "12.md"
  tb_host.write_text(
    '+++\ntitle = "१२"\n+++\n### ०१\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअ᳓श्वस्य वा᳓ आ᳓लब्धस्य मे᳓ध उ᳓दक्रामत् ।\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>मूलम्</summary>\n\nअश्व॑स्य॒ वा आल॑ब्धस्य॒ मेध॒ उद॑क्रामत् ।\n</details>\n</details>\n',
    encoding="utf-8",
  )

  sbm_13 = sbm_c / "13" / "03" / "6.md"
  sbm_13.write_text(
    '+++\ntitle = "६"\n+++\n## ०१\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअ᳓श्वस्य वा᳓ आ᳓लब्धस्य ।  \nमे᳓ध उ᳓दक्रामत् ।\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>Eggeling</summary>\n\n1. From the horse.\n</details>\n\n'
    '<details><summary>मूलम् - श्रीधरादि</summary>\n\nअ᳘श्वस्य वा ऽआ᳘लब्धस्य मे᳘ध उ᳘दक्रामत्\n</details>\n\n'
    '<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- अ᳓श्वस्य (*TS*)\n</details>\n\n'
    '<details><summary>सायणः</summary>\n\nSBM sayana on horse.\n</details>\n</details>\n',
    encoding="utf-8",
  )

  # 2. Kāṇḍa-alignment tie-breaker (`SBK 01` -> `SBM 02` rather than `SBM 11`) + `[[OLD|NEW]]` variant
  sbm_02 = sbm_c / "02" / "02" / "2.md"
  sbm_02.write_text(
    '+++\ntitle = "२"\n+++\n## ०१\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअ᳓थ देवा᳓श्च ह वा᳓ अ᳓सुराश्चोभ᳓ये प्राजापत्या᳓ अस्पर्धन्त ।\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>Eggeling</summary>\n\n1. Gods and Asuras strove (Kanda 2).\n</details>\n\n'
    '<details><summary>मूलम् - Weber</summary>\n\nअ᳘थ देवा᳘श्च\n</details>\n</details>\n',
    encoding="utf-8",
  )
  sbm_11 = sbm_c / "11" / "05" / "9.md"
  sbm_11.write_text(
    '+++\ntitle = "९"\n+++\n## ०१\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअ᳓थ देवा᳓श्च ह वा᳓ अ᳓सुराश्चोभ᳓ये प्राजापत्या᳓ अस्पर्धन्त ।\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>Eggeling</summary>\n\n1. Gods and Asuras strove (Kanda 11).\n</details>\n\n'
    '<details><summary>मूलम् - Weber</summary>\n\nअ᳘थ देवा᳘श्च\n</details>\n</details>\n',
    encoding="utf-8",
  )

  sbm_04 = sbm_c / "04" / "03" / "4.md"
  sbm_04.write_text(
    '+++\ntitle = "४"\n+++\n## ०१\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nघ्न᳓न्ति वा᳓ एत᳓द्यज्ञं᳓ य᳓देनं तन्व᳓ते य᳓द्रा᳓जानमभिषुण्व᳓न्ति त᳓त्तं᳓ घ्नन्ति᳓ ।\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>सायणः</summary>\n\nSoma Sāyaṇa.\n</details>\n</details>\n',
    encoding="utf-8",
  )

  # 3. Repeated zero-commentary exact BAU refrain across SBM & SBK (`self_static` test)
  sbm_14 = sbm_c / "14" / "05" / "5.md"
  sbm_14.write_text(
    '+++\ntitle = "५"\n+++\n## ०१\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअऽय᳓मेव᳓ स᳓ यो᳙ऽय᳓मात्मे᳙द᳓ममृ᳓तमिदं᳓ ब्र᳓ह्मेदं᳓ स᳓र्वम् ॥\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>मूलम् - श्रीधरादि</summary>\n\nअय᳘मेव स᳘ अयम्\n</details>\n</details>\n\n'
    '## ०२\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअऽय᳓मेव᳓ स᳓ यो᳙ऽय᳓मात्मे᳙द᳓ममृ᳓तमिदं᳓ ब्र᳓ह्मेदं᳓ स᳓र्वम् ॥\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>मूलम् - श्रीधरादि</summary>\n\nअय᳘मेव स᳘ अयम्\n</details>\n</details>\n',
    encoding="utf-8",
  )

  sbk_01 = sbk_c / "01_ekapAtkANDam" / "02" / "2.md"
  sbk_01.write_text(
    '+++\ntitle = "२"\n+++\n## ०१\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः (1/2 व्यत्यस्त-स्वराः)</summary>\n\n[[अथ|अ᳓थ]] देवा᳓श्च ह वा᳓ अ᳓सुराश्चोभ᳓ये प्राजापत्या᳓ अस्पर्धन्त ।\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>C R Swaminathan</summary>\n\nThe gods and demons contended.\n</details>\n\n'
    '<details><summary>मूलम्</summary>\n\nअथ देवा᳓श्च\n</details>\n\n'
    '<details><summary>पद-पाठः (यान्त्रिकः - 1/2 व्यत्यस्त-स्वराः)</summary>\n\n- अथ → **अ᳓थ** (*TB*-1)\n- देवाः᳓ (*RV*-1)\n</details>\n</details>\n\n'
    '## ०२\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nघ्न᳓न्ति ह वा᳓ एत᳓द्यज्ञं᳓ य᳓देनं तन्व᳓ते य᳓द्रा᳓जानमभिषुण्व᳓न्ति त᳓त्तं᳓ घ्नन्ति᳓ ।\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>C R Swaminathan</summary>\n\nIn Agnyādheya.\n</details>\n</details>\n',
    encoding="utf-8",
  )
  sbk_15 = sbk_c / "15_ashvamedhakANDam" / "03" / "7.md"
  sbk_15.write_text(
    '+++\ntitle = "७"\n+++\n## ०१\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअ᳓श्वस्य वा᳓ आ᳓लब्धस्य मे᳓ध उ᳓दक्रामत् ।\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>C R Swaminathan</summary>\n\nOut of the slaughtered horse...\n</details>\n\n'
    '<details><summary>मूलम्</summary>\n\nअ᳘श्वस्य वा आ᳘लब्धस्य मे᳘ध उ᳘दक्रामत्\n</details>\n\n'
    '<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- अ᳓श्वस्य (*SB-M*-48)\n</details>\n</details>\n',
    encoding="utf-8",
  )
  sbk_17 = sbk_c / "17_bRhadAraNyakam" / "02" / "5.md"
  sbk_17.write_text(
    '+++\ntitle = "५"\n+++\n## ०१\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअऽय᳓मेव᳓ स᳓ यो᳙ऽय᳓मात्मे᳙द᳓ममृ᳓तमिदं᳓ ब्र᳓ह्मेदं᳓ स᳓र्वम् ॥\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>मूलम्</summary>\n\nअऽय᳘मेव स᳘ अयम्\n</details>\n</details>\n',
    encoding="utf-8",
  )

  specs = {
    "TB": VedaCorpusSpec(
      name="TB", shAkha_label="तैत्तिरीय-ब्राह्मणम्", pada_label="पद-पाठः (यान्त्रिकः - तैत्तिरीय-ब्राह्मणम्)",
      sayana_variant_label="सायण-टीका (ब्राह्मणी)", content_dir=tb_c,
      vp_dir=tb_st / "Rk" / "vishvAsa-prastutiH", sarva_dir=tb_st / "Rk" / "sarvASh_TIkAH",
      vp_url_prefix="/vedAH_yajuH/taittirIyam/brAhmaNam/Rk/vishvAsa-prastutiH",
      sarva_url_prefix="/vedAH_yajuH/taittirIyam/brAhmaNam/Rk/sarvASh_TIkAH",
      brahmana_sarva_prastuti_dir=tb_st / "brAhmaNam" / "sarva-prastutiH",
      brahmana_sarva_prastuti_url="/vedAH_yajuH/taittirIyam/brAhmaNam/brAhmaNam/sarva-prastutiH",
      brahmana_vp_dir=tb_st / "brAhmaNam" / "vishvAsa-prastutiH",
      brahmana_vp_url="/vedAH_yajuH/taittirIyam/brAhmaNam/brAhmaNam/vishvAsa-prastutiH",
      brahmana_sarva_dir=tb_st / "brAhmaNam" / "sarvASh_TIkAH",
      brahmana_sarva_url="/vedAH_yajuH/taittirIyam/brAhmaNam/brAhmaNam/sarvASh_TIkAH",
    ),
    "SB-M": VedaCorpusSpec(
      name="SB-M", shAkha_label="माध्यन्दिन-ब्राह्मणम्", pada_label="पद-पाठः (यान्त्रिकः - माध्यन्दिन-ब्राह्मणम्)",
      sayana_variant_label="सायणः (माध्यन्दिन-ब्राह्मणम्)", heading_level=3, content_dir=sbm_c,
      vp_dir=sbm_st / "Rk" / "vishvAsa-prastutiH", sarva_dir=sbm_st / "Rk" / "sarvASh_TIkAH",
      vp_url_prefix="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/Rk/vishvAsa-prastutiH",
      sarva_url_prefix="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/Rk/sarvASh_TIkAH",
      yajuh_sarva_prastuti_dir=sbm_st / "yajuH" / "sarva-prastutiH",
      yajuh_sarva_prastuti_url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/yajuH/sarva-prastutiH",
      yajuh_vp_dir=sbm_st / "yajuH" / "vishvAsa-prastutiH",
      yajuh_vp_url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/yajuH/vishvAsa-prastutiH",
      yajuh_sarva_dir=sbm_st / "yajuH" / "sarvASh_TIkAH",
      yajuh_sarva_url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/yajuH/sarvASh_TIkAH",
      brahmana_sarva_prastuti_dir=sbm_st / "brAhmaNam" / "sarva-prastutiH",
      brahmana_sarva_prastuti_url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/brAhmaNam/sarva-prastutiH",
      brahmana_vp_dir=sbm_st / "brAhmaNam" / "vishvAsa-prastutiH",
      brahmana_vp_url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/brAhmaNam/vishvAsa-prastutiH",
      brahmana_sarva_dir=sbm_st / "brAhmaNam" / "sarvASh_TIkAH",
      brahmana_sarva_url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/brAhmaNam/sarvASh_TIkAH",
    ),
    "SB-K": VedaCorpusSpec(
      name="SB-K", shAkha_label="काण्व-ब्राह्मणम्", pada_label="पद-पाठः (यान्त्रिकः - काण्व-ब्राह्मणम्)",
      sayana_variant_label="सायणः (काण्व-ब्राह्मणम्)", heading_level=3, content_dir=sbk_c,
    ),
  }

  from doc_curation_projects.veda.dedup import cascade as cas_mod
  orig_loader = cas_mod.load_corpus_specs
  cas_mod.load_corpus_specs = lambda: specs
  roots = (v_root / "vedAH_yajuH" / "content", v_root / "vedAH_yajuH" / "static")
  try:
    res = run_sb_dedup_cascade(roots, upstreams=("TB",), hugo_base_dir=str(v_root))
    r1, r2, r3 = res["stages"]
  finally:
    cas_mod.load_corpus_specs = orig_loader

  # TB <-> SBM <-> SBK Aśvamedha exact Brāhmaṇa combined include (TB H4, SB H3), translations before मूलम्!
  assert r1["content_exact"] == 1
  tb_txt = tb_host.read_text(encoding="utf-8")
  assert 'newlevelforh1="4"' in tb_txt
  assert "/vedAH_yajuH/taittirIyam/brAhmaNam/brAhmaNam/sarva-prastutiH/" in tb_txt
  assert 'newlevelforh1="3"' in sbm_13.read_text(encoding="utf-8")
  assert 'newlevelforh1="3"' in sbk_15.read_text(encoding="utf-8")
  tb_comb = list((tb_st / "brAhmaNam" / "sarva-prastutiH").rglob("*.md"))
  assert len(tb_comb) == 1
  comb_txt = tb_comb[0].read_text(encoding="utf-8")
  assert comb_txt.index("<summary>Eggeling</summary>") < comb_txt.index("<summary>मूलम्")
  assert comb_txt.index("<summary>C R Swaminathan</summary>") < comb_txt.index("<summary>मूलम्")
  assert "<summary>सायणः (माध्यन्दिन-ब्राह्मणम्)</summary>" in comb_txt
  assert "<summary>पद-पाठः (यान्त्रिकः - काण्व-ब्राह्मणम्)</summary>" in comb_txt

  # SBK 01 [[OLD|NEW]] stays local, aligns to SBM 02 (not SBM 11!), and keeps - 1/2 व्यत्यस्त-स्वराः!
  assert r2["content_exact"] == 2  # Aśvamedha + BAU refrain
  assert r2["content_variant"] == 1
  sbk_01_txt = sbk_01.read_text(encoding="utf-8")
  assert "[[अथ|अ᳓थ]]" in sbk_01_txt
  assert "/vedAH_yajuH/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/brAhmaNam/sarvASh_TIkAH/02/02/2/" in sbk_01_txt
  assert "<summary>Gods and Asuras strove (Kanda 11)" not in sbk_01_txt
  assert "Soma Sāyaṇa." not in sbk_01_txt
  assert "/04/03/4/" not in sbk_01_txt
  sbm_02_tk = list((sbm_st / "brAhmaNam" / "sarvASh_TIkAH" / "02").rglob("*.md"))
  assert len(sbm_02_tk) == 1
  tk_txt = sbm_02_tk[0].read_text(encoding="utf-8")
  assert "<summary>C R Swaminathan</summary>" in tk_txt
  assert tk_txt.index("<summary>C R Swaminathan</summary>") < tk_txt.index("<summary>मूलम्")
  assert "<summary>पद-पाठः (यान्त्रिकः - काण्व-ब्राह्मणम् - 1/2 व्यत्यस्त-स्वराः)</summary>" in tk_txt

  # Self-repeat stage deduplicated ## ०२ in SBM 14 against its own promoted BAU static refrain!
  assert r3["content_exact"] == 1
  assert sbm_14.read_text(encoding="utf-8").count("/sarva-prastutiH/") == 2


def test_merge_tika_additions_never_concatenates_padapatha(tmp_path):
  from doc_curation_projects.veda.dedup.commentary_merger import merge_tika_additions
  from doc_curation_projects.veda.dedup.targets import VedaCorpusSpec

  sbm_spec = VedaCorpusSpec(
    name="SB-M", shAkha_label="माध्यन्दिन-ब्राह्मणम्", pada_label="पद-पाठः (यान्त्रिकः - माध्यन्दिन-ब्राह्मणम्)",
    sayana_variant_label="सायणः (माध्यन्दिन-ब्राह्मणम्)", heading_level=3, content_dir=tmp_path,
  )
  sbk_spec = VedaCorpusSpec(
    name="SB-K", shAkha_label="काण्व-ब्राह्मणम्", pada_label="पद-पाठः (यान्त्रिकः - काण्व-ब्राह्मणम्)",
    sayana_variant_label="सायणः (काण्व-ब्राह्मणम्)", heading_level=3, content_dir=tmp_path,
  )
  base = (
    '+++\ntitle = "test"\n+++\n\n'
    '<details><summary>मूलम् - Weber</summary>\n\nप्रजा᳘ ह्येव\n</details>\n\n'
    '<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- प्र-जाः᳓ (*TS*-10)\n- हि᳓ (*TS*-10)\n</details>\n'
  )
  merged = merge_tika_additions(
    base,
    sbm_spec,
    [
      # Same-corpus self-repeat with variant pada must NOT concatenate into SB-M's existing padapāṭha
      (sbm_spec, True, [("पद-पाठः (यान्त्रिकः)", "- प्र-जा᳓ (*TS*-5)\n- हि᳓ (*TS*-10)")], str(tmp_path / "a.md")),
      # Two SB-K callers differing only in a single ŚB accent mark in मूलम् preserve both readings despite >92% similarity
      (
        sbk_spec,
        False,
        [
          ("मूलम् - काण्व-ब्राह्मणम्", "नो वा᳘ एतत्क᳘स्यैचन᳘ देवतायै हवि᳘र्गृह्णन्नादिशति"),
          ("पद-पाठः (यान्त्रिकः)", "- प्र-जाः᳓ (*SB-M*-5)\n- हि᳓ (*TS*-10)"),
        ],
        str(tmp_path / "b.md"),
      ),
      (
        sbk_spec,
        False,
        [
          ("मूलम् - काण्व-ब्राह्मणम्", "नो वा᳘ एतत्क᳘स्यैचन᳘ देव᳘तायै हविर्गृह्णन्ना᳘दिशति"),
          ("पद-पाठः (यान्त्रिकः)", "- प्र-जा᳓ (*SB-M*-5)\n- हि᳓ (*TS*-10)"),
        ],
        str(tmp_path / "c.md"),
      ),
    ],
  )
  assert "- प्र-जा᳓" not in merged
  assert merged.count("<summary>पद-पाठः (यान्त्रिकः)</summary>") == 1
  assert merged.count("<summary>पद-पाठः (यान्त्रिकः - काण्व-ब्राह्मणम्)</summary>") == 1
  assert "देवतायै हवि᳘र्गृह्णन्नादिशति" in merged
  assert "देव᳘तायै हविर्गृह्णन्ना᳘दिशति" in merged


def test_format_vp_summary_with_kind():
  from doc_curation_projects.veda.dedup.block_parser import format_vp_summary_with_kind

  assert format_vp_summary_with_kind("विश्वास-प्रस्तुतिः", "rk") == "विश्वास-प्रस्तुतिः - ऋक्"
  assert format_vp_summary_with_kind("विश्वास-प्रस्तुतिः", "yajuh") == "विश्वास-प्रस्तुतिः - यजुः"
  assert format_vp_summary_with_kind("विश्वास-प्रस्तुतिः", "brahmana") == "विश्वास-प्रस्तुतिः - ब्राह्मणम्"
  assert (
    format_vp_summary_with_kind("विश्वास-प्रस्तुतिः (2/15 व्यत्यस्त-स्वराः)", "brahmana")
    == "विश्वास-प्रस्तुतिः - ब्राह्मणम् (2/15 व्यत्यस्त-स्वराः)"
  )
  assert (
    format_vp_summary_with_kind("विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)", "yajuh")
    == "विश्वास-प्रस्तुतिः - यजुः (यन्त्र-स्वरः)"
  )
  assert (
    format_vp_summary_with_kind("विश्वास-प्रस्तुतिः - ऋक् (1/11 व्यत्यस्त-स्वराः)", "rk")
    == "विश्वास-प्रस्तुतिः - ऋक् (1/11 व्यत्यस्त-स्वराः)"
  )


def test_variant_promotion_keeps_vp_inline_until_second_exact_caller(tmp_path: Path):
  from doc_curation_projects.veda.dedup.cascade import run_stage_cascade
  from doc_curation_projects.veda.dedup.targets import VedaCorpusSpec

  v_root = tmp_path
  sbm_c = v_root / "vedAH_yajuH" / "content" / "sbm"
  sbm_st = v_root / "vedAH_yajuH" / "static" / "sbm"
  sbk_c = v_root / "vedAH_yajuH" / "content" / "sbk"
  tb_c = v_root / "vedAH_yajuH" / "content" / "tb"
  for d in (
    sbm_c, sbk_c, tb_c,
    sbm_st / "brAhmaNam" / "sarva-prastutiH",
    sbm_st / "brAhmaNam" / "vishvAsa-prastutiH",
    sbm_st / "brAhmaNam" / "sarvASh_TIkAH",
  ):
    d.mkdir(parents=True, exist_ok=True)

  sbm_host = sbm_c / "01.md"
  sbm_host.write_text(
    '+++\ntitle = "01"\n+++\n\n'
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "त᳓स्मादु ह यज्ञो᳓ वै᳓ देवा᳓नां ह᳓विर्भवति स᳓र्वदा ।\n</details>\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>मूलम्</summary>\n\nत᳘स्मादु ह\n</details>\n</details>\n",
    encoding="utf-8",
  )
  sbk_host = sbk_c / "01.md"
  sbk_host.write_text(
    '+++\ntitle = "01"\n+++\n\n'
    "<details open><summary>विश्वास-प्रस्तुतिः (1/7 व्यत्यस्त-स्वराः)</summary>\n\n"
    "त᳓स्मादु वै᳓ यज्ञो᳓ देवा᳓नां ह᳓विर्भवति स᳓र्वदा ।\n</details>\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>मूलम्</summary>\n\nत᳘स्मादु वै\n</details>\n</details>\n",
    encoding="utf-8",
  )
  tb_host = tb_c / "01.md"
  tb_host.write_text(
    '+++\ntitle = "01"\n+++\n\n'
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "त᳓स्मादु ह यज्ञो᳓ वै᳓ देवा᳓नां ह᳓विर्भवति स᳓र्वदा ।\n</details>\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>मूलम्</summary>\n\nत᳘स्मादु ह\n</details>\n</details>\n",
    encoding="utf-8",
  )

  specs = {
    "SB-M": VedaCorpusSpec(
      name="SB-M", shAkha_label="माध्यन्दिन-ब्राह्मणम्", pada_label="पद-पाठः (यान्त्रिकः - माध्यन्दिन-ब्राह्मणम्)",
      sayana_variant_label="सायणः (माध्यन्दिन-ब्राह्मणम्)", heading_level=3, content_dir=sbm_c,
      brahmana_sarva_prastuti_dir=sbm_st / "brAhmaNam" / "sarva-prastutiH",
      brahmana_sarva_prastuti_url="/vedAH_yajuH/sbm/brAhmaNam/sarva-prastutiH",
      brahmana_vp_dir=sbm_st / "brAhmaNam" / "vishvAsa-prastutiH",
      brahmana_vp_url="/vedAH_yajuH/sbm/brAhmaNam/vishvAsa-prastutiH",
      brahmana_sarva_dir=sbm_st / "brAhmaNam" / "sarvASh_TIkAH",
      brahmana_sarva_url="/vedAH_yajuH/sbm/brAhmaNam/sarvASh_TIkAH",
    ),
    "SB-K": VedaCorpusSpec(
      name="SB-K", shAkha_label="काण्व-ब्राह्मणम्", pada_label="पद-पाठः (यान्त्रिकः - काण्व-ब्राह्मणम्)",
      sayana_variant_label="सायणः (काण्व-ब्राह्मणम्)", heading_level=3, content_dir=sbk_c,
    ),
    "TB": VedaCorpusSpec(
      name="TB", shAkha_label="तैत्तिरीय-ब्राह्मणम्", pada_label="पद-पाठः (तैत्तिरीय-ब्राह्मणम्)",
      sayana_variant_label="सायणः (तैत्तिरीय-ब्राह्मणम्)", heading_level=4, content_dir=tb_c,
    ),
  }

  from doc_curation_projects.veda.dedup import cascade as cas_mod
  orig_loader = cas_mod.load_corpus_specs
  cas_mod.load_corpus_specs = lambda: specs
  roots = (v_root / "vedAH_yajuH" / "content", v_root / "vedAH_yajuH" / "static")
  try:
    r1 = run_stage_cascade("SB-K", ("SB-M",), roots, hugo_base_dir=str(v_root))
    assert r1["content_variant"] == 1
    assert list((sbm_st / "brAhmaNam" / "vishvAsa-prastutiH").rglob("*.md")) == []
    assert len(list((sbm_st / "brAhmaNam" / "sarvASh_TIkAH").rglob("*.md"))) == 1
    assert "<summary>विश्वास-प्रस्तुतिः - ब्राह्मणम्</summary>" in sbm_host.read_text(encoding="utf-8")
    assert "<summary>विश्वास-प्रस्तुतिः - ब्राह्मणम् (1/7 व्यत्यस्त-स्वराः)</summary>" in sbk_host.read_text(encoding="utf-8")

    # Stage 2: TB exact match lazily promotes SB-M's inline VP into vishvAsa-prastutiH/ (>= 2 exact callers)
    r2 = run_stage_cascade("TB", ("SB-M",), roots, hugo_base_dir=str(v_root))
    assert r2["content_exact"] == 1
    vp_files = list((sbm_st / "brAhmaNam" / "vishvAsa-prastutiH").rglob("*.md"))
    assert len(vp_files) == 1
    assert "brAhmaNam/vishvAsa-prastutiH/" in sbm_host.read_text(encoding="utf-8")
    assert "brAhmaNam/vishvAsa-prastutiH/" in tb_host.read_text(encoding="utf-8")
    assert "brAhmaNam/vishvAsa-prastutiH/" not in sbk_host.read_text(encoding="utf-8")
  finally:
    cas_mod.load_corpus_specs = orig_loader


def test_inline_single_caller_veda_static_handles_all_edge_cases(tmp_path: Path):
  from doc_curation_projects.veda.dedup.static_fixer import inline_single_caller_veda_static

  v_root = tmp_path
  repo = v_root / "vedAH_yajuH"
  st = repo / "static"
  ct = repo / "content"

  # 1. Single-caller Brāhmaṇa VP + shared 2-caller sarvASh_TIkAH (must inline only VP with - ब्राह्मणम्)
  (st / "sb" / "brAhmaNam" / "vishvAsa-prastutiH" / "01").mkdir(parents=True, exist_ok=True)
  (st / "sb" / "brAhmaNam" / "sarvASh_TIkAH" / "01").mkdir(parents=True, exist_ok=True)
  sb_1_vp = st / "sb" / "brAhmaNam" / "vishvAsa-prastutiH" / "01" / "01_br.md"
  sb_1_vp.write_text('+++\ntitle = "01"\n+++\n\nत᳓स्मादु ह यज्ञः᳓ ।\n', encoding="utf-8")
  sb_1_tk = st / "sb" / "brAhmaNam" / "sarvASh_TIkAH" / "01" / "01_br.md"
  sb_1_tk.write_text('+++\ntitle = "01"\n+++\n\n<details><summary>मूलम्</summary>\n\nत᳘स्मादु\n</details>\n', encoding="utf-8")

  # 2. Single-caller Rk VP with [[|]] + companion sarvASh_TIkAH (prefixed by translation block, missing collapsed)
  (st / "ta" / "Rk" / "vishvAsa-prastutiH" / "06").mkdir(parents=True, exist_ok=True)
  (st / "ta" / "Rk" / "sarvASh_TIkAH" / "06").mkdir(parents=True, exist_ok=True)
  ta_vp = st / "ta" / "Rk" / "vishvAsa-prastutiH" / "06" / "01_rk.md"
  ta_vp.write_text('+++\ntitle = "01"\n+++\n\nत᳓देवर्तं [[तदु᳓|त᳓दु]] ।\n', encoding="utf-8")
  ta_tk = st / "ta" / "Rk" / "sarvASh_TIkAH" / "06" / "01_rk.md"
  ta_tk.write_text(
    '+++\ntitle = "01"\n+++\n\n'
    '<details><summary>पद-पाठः (यान्त्रिकः - 1/12 व्यत्यस्त-स्वराः)</summary>\n\n- त᳓त् (*RV*-1)\n</details>\n',
    encoding="utf-8",
  )

  # 3. Bare mūlam inside sarvASh_TIkAH (TB pattern) + no collapsed attr on caller
  (st / "tb" / "Rk" / "sarvASh_TIkAH" / "02").mkdir(parents=True, exist_ok=True)
  tb_tk = st / "tb" / "Rk" / "sarvASh_TIkAH" / "02" / "08_mUlam.md"
  tb_tk.write_text('+++\ntitle = "08"\n+++\n\nअग्निः᳓ पूर्वे᳓भिः।\n', encoding="utf-8")

  # 4. Forwarding Rk wrapper 17/70 -> shared 12/02 (2 callers including wrapper)
  (st / "vs" / "Rk" / "vishvAsa-prastutiH" / "12").mkdir(parents=True, exist_ok=True)
  (st / "vs" / "Rk" / "vishvAsa-prastutiH" / "17").mkdir(parents=True, exist_ok=True)
  vs_12 = st / "vs" / "Rk" / "vishvAsa-prastutiH" / "12" / "02_nak.md"
  vs_12.write_text('+++\ntitle = "02"\n+++\n\nन᳓क्तोषा᳓सा ।\n', encoding="utf-8")
  vs_17 = st / "vs" / "Rk" / "vishvAsa-prastutiH" / "17" / "70_nak.md"
  vs_17.write_text(
    '+++\ntitle = "70"\n+++\n\n<div class="js_include" url="/vedAH_yajuH/vs/Rk/vishvAsa-prastutiH/12/02_nak.md"></div>\n',
    encoding="utf-8",
  )

  # 5. Single-caller yajuH sarva-prastutiH with accidental includetitle="true"
  (st / "ts" / "yajuH" / "sarva-prastutiH" / "01").mkdir(parents=True, exist_ok=True)
  ts_yj = st / "ts" / "yajuH" / "sarva-prastutiH" / "01" / "05_yj.md"
  ts_yj.write_text(
    '+++\ntitle = "05"\n+++\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nस्वा᳓हा ।\n</details>\n\n'
    '<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>Keith</summary>\n\nHail!\n</details>\n</details>\n',
    encoding="utf-8",
  )

  # 6. Zero-caller dead file vs zero-include file still linked via Markdown link [ref](...)
  dead_st = st / "tb" / "Rk" / "sarvASh_TIkAH" / "02" / "99_dead.md"
  dead_st.write_text('+++\ntitle = "99"\n+++\n\n<details><summary>मूलम्</summary>\n\nx\n</details>\n', encoding="utf-8")
  md_linked_st = st / "tb" / "Rk" / "sarvASh_TIkAH" / "02" / "98_linked.md"
  md_linked_st.write_text('+++\ntitle = "98"\n+++\n\n<details><summary>मूलम्</summary>\n\ny\n</details>\n', encoding="utf-8")

  # 7. Excluded sUtram single-caller file (must remain untouched)
  (st / "ts" / "sUtram" / "ApastambaH" / "vishvAsa-prastutiH").mkdir(parents=True, exist_ok=True)
  sutra_vp = st / "ts" / "sUtram" / "ApastambaH" / "vishvAsa-prastutiH" / "01.md"
  sutra_vp.write_text('+++\ntitle = "01"\n+++\n\nसूत्रम्\n', encoding="utf-8")

  # Content hosts
  (ct / "host").mkdir(parents=True, exist_ok=True)
  h1 = ct / "host" / "01.md"
  h1.write_text(
    '+++\ntitle = "01"\n+++\n\n'
    '<div class="js_include" title="विश्वास-प्रस्तुतिः" newlevelforh1="3" unfilled url="/vedAH_yajuH/sb/brAhmaNam/vishvAsa-prastutiH/01/01_br.md"></div>\n'
    '<div class="js_include collapsed" title="सर्वाष् टीकाः" newlevelforh1="3" unfilled url="/vedAH_yajuH/sb/brAhmaNam/sarvASh_TIkAH/01/01_br.md"></div>\n\n'
    '<div class="js_include" title="विश्वास-प्रस्तुतिः" newlevelforh1="4" unfilled url="/vedAH_yajuH/ta/Rk/vishvAsa-prastutiH/06/01_rk.md"></div>\n\n'
    '<details><summary>Eggeling</summary>\n\nTrans</details>\n\n'
    '<div class="js_include" title="सर्वाष् टीकाः" newlevelforh1="4" unfilled url="/vedAH_yajuH/ta/Rk/sarvASh_TIkAH/06/01_rk.md"></div>\n\n'
    '<div class="js_include" title="सर्वाष् टीकाः" newlevelforh1="4" unfilled url="/vedAH_yajuH/tb/Rk/sarvASh_TIkAH/02/08_mUlam.md"></div>\n\n'
    '<div class="js_include" title="विश्वास-प्रस्तुतिः" newlevelforh1="3" unfilled url="/vedAH_yajuH/vs/Rk/vishvAsa-prastutiH/17/70_nak.md"></div>\n\n'
    '<div class="js_include" includetitle="true" newlevelforh1="3" unfilled url="/vedAH_yajuH/ts/yajuH/sarva-prastutiH/01/05_yj.md"></div>\n\n'
    '<div class="js_include" title="विश्वास-प्रस्तुतिः" url="/vedAH_yajuH/ts/sUtram/ApastambaH/vishvAsa-prastutiH/01.md"></div>\n'
    'See [note](/vedAH_yajuH/tb/Rk/sarvASh_TIkAH/02/98_linked.md).\n',
    encoding="utf-8",
  )
  h2 = ct / "host" / "02.md"
  h2.write_text(
    '+++\ntitle = "02"\n+++\n\n'
    '<div class="js_include collapsed" title="सर्वाष् टीकाः" newlevelforh1="3" unfilled url="/vedAH_yajuH/sb/brAhmaNam/sarvASh_TIkAH/01/01_br.md"></div>\n'
    '<div class="js_include" title="विश्वास-प्रस्तुतिः" newlevelforh1="3" unfilled url="/vedAH_yajuH/vs/Rk/vishvAsa-prastutiH/12/02_nak.md"></div>\n',
    encoding="utf-8",
  )

  stats = inline_single_caller_veda_static(
    static_roots=[st],
    all_vishvasa_root=v_root,
    hugo_base_dir=v_root,
    dry_run=False,
  )
  assert stats["forwarded"] == 1
  assert stats["inlined"] == 5  # sb_1_vp, ta_vp, ta_tk, tb_tk, ts_yj
  assert stats["pruned_zero_caller"] == 1  # dead_st

  assert not sb_1_vp.exists()
  assert sb_1_tk.is_file()  # 2 callers
  assert not ta_vp.exists() and not ta_tk.exists()
  assert not tb_tk.exists()
  assert not vs_17.exists() and vs_12.is_file()  # shared by h1 + h2
  assert not ts_yj.exists()
  assert not dead_st.exists()
  assert md_linked_st.is_file()  # protected by md link!
  assert sutra_vp.is_file()  # sUtram excluded!

  h1_out = h1.read_text(encoding="utf-8")
  assert "<details open><summary>विश्वास-प्रस्तुतिः - ब्राह्मणम्</summary>" in h1_out
  assert "<details open><summary>विश्वास-प्रस्तुतिः - ऋक् (1/12 व्यत्यस्त-स्वराः)</summary>" in h1_out
  assert "<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>मूलम्</summary>\n\nअग्निः᳓ पूर्वे᳓भिः।" in h1_out
  assert "<details open><summary>सर्वाष् टीकाः</summary>" not in h1_out
  assert 'url="/vedAH_yajuH/vs/Rk/vishvAsa-prastutiH/12/02_nak.md"' in h1_out
  assert "<details open><summary>विश्वास-प्रस्तुतिः - यजुः</summary>" in h1_out
  assert "<summary>05</summary>" not in h1_out  # includetitle="true" did not double-wrap sarva-prastutiH!
  assert "sUtram/ApastambaH/vishvAsa-prastutiH/01.md" in h1_out


