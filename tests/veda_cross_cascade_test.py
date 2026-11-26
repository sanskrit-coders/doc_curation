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


def test_looks_prose_brahmana_blocks_ta_arthavada_cliches():
  from doc_curation_projects.veda.dedup.matcher import looks_prose_brahmana

  assert looks_prose_brahmana("य᳓देवा᳓द्भ्यो᳓ऽन्नञ्जा᳓यते ।  \nत᳓द᳓वरुन्धे ।", 22)
  assert looks_prose_brahmana("त᳓स्मात् त᳓र्हि ते᳓क्ष्णिष्ठन्+++(=बहुतीक्ष्णं)+++ तपति।", 22)
  assert not looks_prose_brahmana("प्रतितिष्ठामि राष्ट्रम् ॥", 20, summary="ऋक्")
