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
