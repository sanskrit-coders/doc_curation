"""Tests for Atharvaveda Paippalāda preparation, cross-corpus dedup helpers, and sandhi/ellipsis cleanup."""
from __future__ import annotations

from pathlib import Path

from doc_curation_projects.veda.atharva.paippalaadam.dedup import (
  _self_repeat_key,
  run_paippalada_dedup,
)
from doc_curation_projects.veda.atharva.paippalaadam.padapatha_accent import (
  _upsert_local_padapatha,
  run_paippalada_padapatha_and_accent,
  solve_avp_mantra,
)
from doc_curation_projects.veda.atharva.paippalaadam.prepare import (
  clean_gretil_vp_text,
  contract_gretil_line_hyphens,
  expand_paippalada_ellipses,
  prepare_paippalada_corpus,
)
from doc_curation_projects.veda.dedup import cascade
from doc_curation_projects.veda.dedup.commentary_merger import (
  _disambiguate_incoming_entry,
  merge_tika_additions,
  qualify_cross_corpus_sarva_tika,
)
from doc_curation_projects.veda.dedup.matcher import (
  InvertedVedaIndex,
  TargetEntry,
  classify_unit_kind,
)
from doc_curation_projects.veda.dedup.targets import VedaCorpusSpec, load_corpus_specs
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import normalize_phonetic


def test_contract_gretil_line_hyphens_and_typos():
  raw = (
    "अभिवृत्तः सपत्ना-  \n"
    "-अभि या नो अरातयः ।\n"
    "+++(PSK 20.1.1)+++प्रथमा-  \n"
    "-इदं नम +ऽस्तु ?विनशः? ॥"
  )
  cleaned = clean_gretil_vp_text(raw)
  assert "सपत्नाभि या नो अरातयः" in cleaned
  assert "प्रथमेदं" in cleaned
  assert "PSK" not in cleaned
  assert "+" not in cleaned
  assert "?" not in cleaned
  assert "विनशः" in cleaned

  assert "दुहानर्तस्य" in contract_gretil_line_hyphens("पयो दुहाना-  \n-र्तस्य नाभिर्")
  assert "तिष्ठतु" in clean_gretil_vp_text("अभि तिष्ट्ःअतु हरसा ॥")
  assert "स्थाग्नयश् च ॥" in clean_gretil_vp_text("परिचित स्थ्- +++(stha)+++  \n-आग्नयश् च ॥ प्रपाठक ॥")
  assert "वाराच् चर" in clean_gretil_vp_text("भ्रूणघ्नोविरिवारा(च्) चर ॥")


def test_expand_paippalada_ellipses_prefixes_and_same_sukta():
  raw = {
    (2, 86, 1): "प्राचीं दिशम् आस्थाम्  \nअग्निर् मावत्व् ओजसे बलाय  \nदिशां प्रियो भूयासम् ।  \nअनमित्रा मे दिशो भवन्तु घृतप्रतीकाः ॥",
    (2, 86, 2): "दक्षिणां दिशम् आस्थाम्  \nइन्द्रो मावत्व् ओजसे बलाय (…) ॥ +++(see 1bcd)+++",
    (4, 8, 1): "अग्नी रक्षोहा तिग्मस् तिग्मशृङ्ग ऋषिर् आर्षेयः ।  \nप्रत्यक् प्रतिहरणेन ॥",
    (4, 8, 2): "इन्द्रो रक्षोहा (…) ॥",
    (1, 84, 1): "यत् ते चतस्रः प्रदिशो  \nमनो जगाम दूरकम् ।  \nतत् त आ वर्तयामसि ॥",
    (1, 84, 2): "यत् ते भूमिम्  \nमनः (…) ॥ +++(see 1bc)+++",
  }
  xml_by_stanza = {
    (2, 86, 1): [
      ("a", "प्राचीं दिशम् आस्थाम्", ""),
      ("b", "अग्निर् मावत्व् ओजसे बलाय", ""),
      ("c", "दिशां प्रियो भूयासम् ।", ""),
      ("d", "अनमित्रा मे दिशो भवन्तु घृतप्रतीकाः ॥", ""),
    ],
    (1, 84, 1): [
      ("a", "यत् ते चतस्रः प्रदिशो", ""),
      ("b", "मनो जगाम दूरकम् ।", ""),
      ("c", "तत् त आ वर्तयामसि ॥", ""),
    ],
  }
  xml_by_id = {(k, s, v, p): (d, n) for (k, s, v), rows in xml_by_stanza.items() for p, d, n in rows}

  exp, _stats, unres = expand_paippalada_ellipses(raw, xml_by_stanza, xml_by_id)
  assert unres == []
  assert "इन्द्रो मावत्व् ओजसे बलाय" in exp[(2, 86, 2)]
  assert "दिशां प्रियो भूयासम् ।  \nअनमित्रा मे दिशो" in exp[(2, 86, 2)]
  assert "इन्द्रो रक्षोहा तिग्मस् तिग्मशृङ्ग" in exp[(4, 8, 2)]
  assert "मनो मनः" not in exp[(1, 84, 2)] and "मनः जगाम दूरकम्" in exp[(1, 84, 2)]
  assert "तत् त आ वर्तयामसि" in exp[(1, 84, 2)]


def test_avp_spec_commentary_disambiguation_and_avagraha_matcher():
  specs = load_corpus_specs()
  assert "AV-P" in specs
  avp = specs["AV-P"]
  rv = specs["RV"]

  assert _disambiguate_incoming_entry(
    "मूलम् (GR)", "शं नः", avp, rv, {"मूलम् - शाकलम्": ["शं॒ नः॑"]}, is_exact_reading=False
  ) == ("मूलम् - पैप्पलादम् (GR)", "शं नः")
  assert _disambiguate_incoming_entry(
    "मूलम् (GR)", "शं नः", avp, rv, {"मूलम् - शाकलम्": ["शं॒ नः॑"]}, is_exact_reading=True
  ) is None

  sarva = "<details><summary>सर्वाष् टीकाः</summary>\n\n<details><summary>मूलम् (GR)</summary>\n\nx\n</details>\n</details>"
  q = qualify_cross_corpus_sarva_tika(
    sarva,
    src_url="/vedAH/atharva/paippalAdam/saMhitA/Rk/sarvASh_TIkAH/01/01.md",
    caller_fp=Path("/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/shaunakam/rUDha-saMhitA/sarva-prastutiH/01/001.md"),
  )
  assert "<summary>मूलम् - पैप्पलादम् (GR)</summary>" in q

  # Leading avagraha line in chandas metric classification must never raise ValueError.
  kind = classify_unit_kind(
    "मूर्ध्नो देवस्य बृहतो  \nऽंशवः सप्त सप्ततीः ।  \nराज्ञः सोमस्याजायन्त  \nजातस्य पुरुषाद् अधि ॥",
    default_brahmana=True,
  )
  assert kind == "rk"


def test_prepare_paippalada_corpus_isolated(tmp_path):
  hugo = tmp_path / "vishvAsa"
  saMhitA_static = hugo / "vedAH" / "static" / "atharva" / "paippalAdam" / "saMhitA"
  saMhitA_content = hugo / "vedAH" / "content" / "atharva" / "paippalAdam" / "saMhitA" / "sarva-prastutiH"
  deva_content = hugo / "devaH" / "content" / "AryaH"

  # 1. Single-caller mantra 01/001/01 (with mUlam + blank sarvASh_TIkAH)
  rel1 = "01/001/01_shaM_no.md"
  for sub, body in [
    ("vishvAsa-prastutiH", "+++\ntitle = \"01\"\n+++\n\nशं नो देवीर् अभिष्टय-  \n-आपो भवन्तु पीतये ।  \nशं योर् अभि स्रवन्तु नः ॥\n"),
    ("mUlam", "+++\ntitle = \"01\"\n+++\n\n<details><summary>मूलम् (GR)</summary>\n\nशं नो देवीर् अभिष्टय-  \n-आपो भवन्तु पीतये ।  \nशं योर् अभि स्रवन्तु नः ॥\n</details>\n"),
    ("sarvASh_TIkAH", "+++\ntitle = \"01\"\n+++\n\n"),
  ]:
    fp = saMhitA_static / sub / rel1
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(body, encoding="utf-8")

  # 2. Multi-caller mantra 01/001/02 with manual accent in VP
  rel2 = "01/001/02_manual.md"
  for sub, body in [
    ("vishvAsa-prastutiH", "+++\ntitle = \"02\"\n+++\n\nआपः᳓ पृणीत भेषजम्  \nवरूथं तन्वे मम ॥\n"),
    ("mUlam", "+++\ntitle = \"02\"\n+++\n\n<details><summary>मूलम् (GR)</summary>\n\nआपः पृणीत भेषजम्  \nवरूथं तन्वे मम ॥\n</details>\n"),
    ("sarvASh_TIkAH", "+++\ntitle = \"02\"\n+++\n\n"),
  ]:
    fp = saMhitA_static / sub / rel2
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(body, encoding="utf-8")

  sukta_fp = saMhitA_content / "01" / "001.md"
  sukta_fp.parent.mkdir(parents=True, exist_ok=True)
  sukta_fp.write_text(
    '+++\ntitle = "001"\n+++\n\n'
    '<div class="js_include" newlevelforh1="6" title="सर्वाष् टीकाः" unfilled '
    'url="/vedAH/atharva/paippalAdam/saMhitA/sarvASh_TIkAH/01/001/_index.md">\n'
    '<details open><summary><h2>सर्वाष् टीकाः ...{Loading}...</h2></summary>\n</details>\n</div>\n\n'
    '## 01\n'
    '<div class="js_include" newlevelforh1="6" title="विश्वास-प्रस्तुतिः" unfilled '
    'url="/vedAH/atharva/paippalAdam/saMhitA/vishvAsa-prastutiH/01/001/01_shaM_no.md"></div>\n'
    '<div class="js_include collapsed" newlevelforh1="6" title="मूलम्" unfilled '
    'url="/vedAH/atharva/paippalAdam/saMhitA/mUlam/01/001/01_shaM_no.md"></div>\n'
    '<div class="js_include collapsed" newlevelforh1="6" title="सर्वाष् टीकाः" unfilled '
    'url="/vedAH/atharva/paippalAdam/saMhitA/sarvASh_TIkAH/01/001/01_shaM_no.md"></div>\n\n'
    '## 02\n'
    '<div class="js_include" newlevelforh1="6" title="विश्वास-प्रस्तुतिः" unfilled '
    'url="/vedAH/atharva/paippalAdam/saMhitA/vishvAsa-prastutiH/01/001/02_manual.md"></div>\n'
    '<div class="js_include collapsed" newlevelforh1="6" title="मूलम्" unfilled '
    'url="/vedAH/atharva/paippalAdam/saMhitA/mUlam/01/001/02_manual.md"></div>\n'
    '<div class="js_include collapsed" newlevelforh1="6" title="सर्वाष् टीकाः" unfilled '
    'url="/vedAH/atharva/paippalAdam/saMhitA/sarvASh_TIkAH/01/001/02_manual.md"></div>\n',
    encoding="utf-8",
  )

  deva_caller = deva_content / "caller.md"
  deva_caller.parent.mkdir(parents=True, exist_ok=True)
  deva_caller.write_text(
    '+++\ntitle = "caller"\n+++\n\n'
    '<div class="js_include" newlevelforh1="4" title="विश्वास-प्रस्तुतिः" '
    'url="/vedAH/atharva/paippalAdam/saMhitA/vishvAsa-prastutiH/01/001/02_manual.md">\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nstale\n</details>\n</div>\n',
    encoding="utf-8",
  )

  stats = prepare_paippalada_corpus(
    hugo_base_dir=hugo,
    xml_path=tmp_path / "missing.xml",
    wiki_dir=tmp_path / "missing_wiki",
    scan_roots=[saMhitA_content, saMhitA_static, deva_content],
    dry_run=False,
  )
  assert stats["inlined_mantras"] == 1
  assert stats["moved_multi_caller"] == 1
  assert stats["manual_vp_preserved"] == 1

  out_sukta = sukta_fp.read_text(encoding="utf-8")
  assert "01/001/_index.md" not in out_sukta
  assert "अभिष्टयापो" in out_sukta
  assert "</details>\n\n<details><summary>सर्वाष् टीकाः</summary>" in out_sukta
  assert "<details open><summary>विश्वास-प्रस्तुतिः - ऋक्</summary>" in out_sukta
  assert "/vedAH/atharva/paippalAdam/saMhitA/Rk/vishvAsa-prastutiH/01/001/02_manual.md" in out_sukta
  assert not (saMhitA_static / "mUlam").exists()
  assert not (saMhitA_static / "vishvAsa-prastutiH" / rel1).exists()
  assert (saMhitA_static / "Rk" / "vishvAsa-prastutiH" / rel2).is_file()

  out_deva = deva_caller.read_text(encoding="utf-8")
  assert "/vedAH/atharva/paippalAdam/saMhitA/Rk/vishvAsa-prastutiH/01/001/02_manual.md" in out_deva
  assert "आपः᳓ पृणीत भेषजम्" in out_deva


def test_merge_tika_additions_avp_to_av_and_rv():
  specs = load_corpus_specs()
  avp, av, rv = specs["AV-P"], specs["AV"], specs["RV"]
  target_av = (
    "+++\ntitle = \"01\"\n+++\n\n"
    "<details><summary>Whitney</summary>\n\nEnglish text\n</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nशं नो॒ दे॒वीर॒भिष्ट॑ये\n</details>\n\n"
    "<details><summary>सायण-टीका</summary>\n\ncommentary\n</details>\n"
  )
  merged = merge_tika_additions(
    target_av,
    av,
    [(
      avp,
      False,
      [
        ("मूलम् (GR)", "शं नो देवीर् अभिष्टय"),
        ("पद-पाठः (यान्त्रिकः)", "शम् । नः । देवीः᳙ । अभिष्ट᳓ये ।"),
      ],
      "/tmp/avp.md",
    )],
  )
  assert "<summary>मूलम् - शौनकम्</summary>" in merged
  assert "<summary>मूलम् - पैप्पलादम् (GR)</summary>" in merged
  assert "<summary>पद-पाठः (यान्त्रिकः - पैप्पलादम्)</summary>" in merged
  assert merged.index("मूलम् - शौनकम्") < merged.index("मूलम् - पैप्पलादम् (GR)")
  assert merged.index("मूलम् - पैप्पलादम् (GR)") < merged.index("पद-पाठः (यान्त्रिकः - पैप्पलादम्)")
  assert merged.index("पद-पाठः (यान्त्रिकः - पैप्पलादम्)") < merged.index("सायण-टीका")

  target_rv = (
    "+++\ntitle = \"05\"\n+++\n\n"
    "<details><summary>Griffith</summary>\n\nEnglish text\n</details>\n\n"
    "<details><summary>मूलम् - शाकलम्</summary>\n\nपु᳓नर् नः पित᳓रो म᳓नो\n</details>\n\n"
    "<details><summary>सायण-टीका</summary>\n\ncommentary\n</details>\n"
  )
  merged_rv = merge_tika_additions(
    target_rv,
    rv,
    [(
      avp,
      False,
      [("पद-पाठः (यान्त्रिकः - पैप्पलादम्)", "- पु᳓नः (*RV*-1)\n- नः (*RV*-1)")],
      "/tmp/avp_19_024_12.md",
    )],
  )
  assert "<summary>पद-पाठः (यान्त्रिकः - पैप्पलादम्)</summary>" in merged_rv
  assert merged_rv.index("मूलम् - शाकलम्") < merged_rv.index("पद-पाठः (यान्त्रिकः - पैप्पलादम्)")
  assert merged_rv.index("पद-पाठः (यान्त्रिकः - पैप्पलादम्)") < merged_rv.index("सायण-टीका")


def test_matcher_avp_trust_cons():
  rv_vp = "शं नो᳓ देवी᳓र् अभि᳓ष्टय आपो᳓ भवन्तु पीत᳓ये । शं योर् अभि᳓ स्रवन्तु नः ॥"
  rv_pb = normalize_phonetic(rv_vp, include_accents=False, fold_orthography=True)
  rv_ent = TargetEntry(
    corpus="RV",
    kind="rk_2part",
    rel="10/009/04.md",
    vp=rv_vp,
    pb=rv_pb,
    vp_path="/tmp/rv_vp.md",
    sarva_path="/tmp/rv_sv.md",
    vp_url="/vedAH_Rk/shAkalam/saMhitA/Rk/vishvAsa-prastutiH/10/009/04.md",
    sarva_url="/vedAH_Rk/shAkalam/saMhitA/Rk/sarvASh_TIkAH/10/009/04.md",
    is_yantra_svara=False,
  )
  yantra_target = TargetEntry(
    corpus="AV",
    kind="rk_2part",
    rel="01/006/01.md",
    vp=rv_vp,
    pb=rv_pb,
    vp_path="/tmp/av_vp.md",
    sarva_path="/tmp/av_sv.md",
    vp_url="/vedAH/atharva/shaunakam/u/vp.md",
    sarva_url="/vedAH/atharva/shaunakam/u/sv.md",
    is_yantra_svara=True,
  )

  # Unaccented, non-bold AV-P block matches non-yantra RV verbatim on consonant/vowel skeleton.
  idx_rv = InvertedVedaIndex([rv_ent], corpus_priority=("RV", "AV"))
  clean_vp = "शं नो देवीर् अभिष्टय आपो भवन्तु पीतये । शं योर् अभि स्रवन्तु नः ॥"
  res_clean = idx_rv.find_best(clean_vp, src_summary="विश्वास-प्रस्तुतिः - ऋक्", src_corpus="AV-P", src_rel="01/001/01.md")
  assert res_clean is not None and res_clean[2] is True

  # Manual US accents or **bold** emphasis do NOT blindly treat bare equality as exact match.
  bold_vp = "**शं** नो देवीर् अभिष्टय आपो भवन्तु पीतये । शं योर् अभि स्रवन्तु नः ॥"
  res_bold = idx_rv.find_best(bold_vp, src_summary="विश्वास-प्रस्तुतिः - ऋक्", src_corpus="AV-P", src_rel="01/001/01.md")
  assert res_bold is not None and res_bold[2] is False

  # Target marked (यन्त्र-स्वरः) also never promotes unaccented AV-P as an exact accented match.
  idx_yantra = InvertedVedaIndex([yantra_target], corpus_priority=("AV",))
  res_yantra = idx_yantra.find_best(clean_vp, src_summary="विश्वास-प्रस्तुतिः - ऋक्", src_corpus="AV-P", src_rel="01/001/01.md")
  assert res_yantra is not None and res_yantra[2] is False


def _make_inline_mantra(heading: str, vp_text: str, gr_text: str = "") -> str:
  gr = gr_text or vp_text
  return (
    f"## {heading}\n\n"
    f"<details open><summary>विश्वास-प्रस्तुतिः - ऋक्</summary>\n\n{vp_text}\n</details>\n\n"
    f"<details><summary>सर्वाष् टीकाः</summary>\n\n"
    f"<details><summary>मूलम् (GR)</summary>\n\n{gr}\n</details>\n</details>\n"
  )


def test_dedup_paippalada_cross_and_self_repeat_isolated(tmp_path, monkeypatch):
  hugo = tmp_path / "vishvAsa"

  rv_vp = hugo / "vedAH_Rk" / "static" / "shAkalam" / "saMhitA" / "Rk" / "vishvAsa-prastutiH" / "10" / "009" / "04.md"
  rv_sv = hugo / "vedAH_Rk" / "static" / "shAkalam" / "saMhitA" / "Rk" / "sarvASh_TIkAH" / "10" / "009" / "04.md"
  rv_vp.parent.mkdir(parents=True, exist_ok=True)
  rv_sv.parent.mkdir(parents=True, exist_ok=True)
  rv_vp.write_text('+++\ntitle = "04"\n+++\n\nशं नो᳓ देवी᳓र् अभि᳓ष्टय  \nआपो᳓ भवन्तु पीत᳓ये ।  \nशं योर् अभि᳓ स्रवन्तु नः ॥\n', encoding="utf-8")
  rv_sv.write_text('+++\ntitle = "04"\n+++\n\n<details><summary>मूलम् - शाकलम्</summary>\n\nशं नो᳓ देवी᳓र् अभि᳓ष्टय  \nआपो᳓ भवन्तु पीत᳓ये ।  \nशं योर् अभि᳓ स्रवन्तु नः ॥\n</details>\n', encoding="utf-8")

  av_vp = hugo / "vedAH" / "static" / "atharva" / "shaunakam" / "rUDha-saMhitA" / "vishvAsa-prastutiH" / "01" / "002" / "01.md"
  av_sv = hugo / "vedAH" / "static" / "atharva" / "shaunakam" / "rUDha-saMhitA" / "sarvASh_TIkAH" / "01" / "002" / "01.md"
  av_vp.parent.mkdir(parents=True, exist_ok=True)
  av_sv.parent.mkdir(parents=True, exist_ok=True)
  av_vp.write_text('+++\ntitle = "01"\n+++\n\nविद्मा᳓ श᳓रस्य पित᳓रं  \nपर्ज᳓न्यं भूरि᳓धायसम् ।  \nविद्मो᳓ ष्वस्य मात᳓रम् ॥\n', encoding="utf-8")
  av_sv.write_text('+++\ntitle = "01"\n+++\n\n<details><summary>मूलम्</summary>\n\nविद्मा᳓ श᳓रस्य पित᳓रं  \nपर्ज᳓न्यं भूरि᳓धायसम् ।  \nविद्मो᳓ ष्वस्य मात᳓रम् ॥\n</details>\n', encoding="utf-8")

  avp_content = hugo / "vedAH" / "content" / "atharva" / "paippalAdam" / "saMhitA" / "sarva-prastutiH"
  avp_static = hugo / "vedAH" / "static" / "atharva" / "paippalAdam" / "saMhitA"
  (avp_content / "01").mkdir(parents=True, exist_ok=True)
  (avp_content / "02").mkdir(parents=True, exist_ok=True)

  local_rep = "अग्न आ याहि वीतये  \nगृणानो हव्यदातये ।  \nनि होता सत्सि बर्हिषि ॥"
  manual_rep = "अग्न᳓ आ याहि वीत᳓ये  \nगृणा᳓नो हव्यदा᳓तये ।  \nनि होता᳓ सत्सि बर्हि᳓षि ॥"
  lacuna_rep = "अभि त्वोर्न (…)"

  s1 = avp_content / "01" / "001.md"
  s1.write_text(
    '+++\ntitle = "001"\n+++\n\n'
    + _make_inline_mantra("01 exact RV", "शं नो देवीर् अभिष्टय  \nआपो भवन्तु पीतये ।  \nशं योर् अभि स्रवन्तु नः ॥")
    + "\n"
    + _make_inline_mantra("02 variant AV", "विद्मा शस्य पितरं  \nपर्जन्यं भूरिधायसम् ।  \nविद्मो ष्वस्य मातरम् ॥")
    + "\n"
    + _make_inline_mantra("03 self repeat A", local_rep)
    + "\n"
    + _make_inline_mantra("04 self repeat same file", local_rep)
    + "\n"
    + _make_inline_mantra("05 manual accented", manual_rep)
    + "\n"
    + _make_inline_mantra("06 lacuna", lacuna_rep),
    encoding="utf-8",
  )

  s2 = avp_content / "02" / "001.md"
  s2.write_text(
    '+++\ntitle = "001"\n+++\n\n'
    + _make_inline_mantra("01 self repeat B", local_rep, "अग्न आ याहि वीतये  \nगृणानो हव्यदातये ।  \nनि होता सत्सि बर्हिषि ॥ +++(note)+++")
    + "\n"
    + _make_inline_mantra("02 lacuna 2", lacuna_rep),
    encoding="utf-8",
  )

  mock_specs = {
    "RV": VedaCorpusSpec(
      name="RV", shAkha_label="शाकलम्", pada_label="पद-पाठः", sayana_variant_label="सायणः (शाकलः)",
      has_two_part_rk=True,
      vp_dir=hugo / "vedAH_Rk" / "static" / "shAkalam" / "saMhitA" / "Rk" / "vishvAsa-prastutiH",
      sarva_dir=hugo / "vedAH_Rk" / "static" / "shAkalam" / "saMhitA" / "Rk" / "sarvASh_TIkAH",
      vp_url_prefix="/vedAH_Rk/shAkalam/saMhitA/Rk/vishvAsa-prastutiH",
      sarva_url_prefix="/vedAH_Rk/shAkalam/saMhitA/Rk/sarvASh_TIkAH",
      heading_level=6,
    ),
    "AV": VedaCorpusSpec(
      name="AV", shAkha_label="शौनकम्", pada_label="पदपाठः", sayana_variant_label="सायण-टीका (शौनकीया)",
      has_two_part_rk=True,
      vp_dir=hugo / "vedAH" / "static" / "atharva" / "shaunakam" / "rUDha-saMhitA" / "vishvAsa-prastutiH",
      sarva_dir=hugo / "vedAH" / "static" / "atharva" / "shaunakam" / "rUDha-saMhitA" / "sarvASh_TIkAH",
      vp_url_prefix="/vedAH/atharva/shaunakam/rUDha-saMhitA/vishvAsa-prastutiH",
      sarva_url_prefix="/vedAH/atharva/shaunakam/rUDha-saMhitA/sarvASh_TIkAH",
      heading_level=5,
    ),
    "AV-P": VedaCorpusSpec(
      name="AV-P", shAkha_label="पैप्पलादम्", pada_label="पद-पाठः (यान्त्रिकः - पैप्पलादम्)",
      sayana_variant_label="सायण-टीका (पैप्पलादम्)", has_two_part_rk=True,
      content_dir=avp_content,
      vp_dir=avp_static / "Rk" / "vishvAsa-prastutiH",
      sarva_dir=avp_static / "Rk" / "sarvASh_TIkAH",
      vp_url_prefix="/vedAH/atharva/paippalAdam/saMhitA/Rk/vishvAsa-prastutiH",
      sarva_url_prefix="/vedAH/atharva/paippalAdam/saMhitA/Rk/sarvASh_TIkAH",
      yajuh_vp_dir=avp_static / "yajuH" / "vishvAsa-prastutiH",
      yajuh_vp_url="/vedAH/atharva/paippalAdam/saMhitA/yajuH/vishvAsa-prastutiH",
      yajuh_sarva_dir=avp_static / "yajuH" / "sarvASh_TIkAH",
      yajuh_sarva_url="/vedAH/atharva/paippalAdam/saMhitA/yajuH/sarvASh_TIkAH",
      heading_level=6,
    ),
  }
  monkeypatch.setattr(cascade, "load_corpus_specs", lambda: mock_specs)

  roots = [
    hugo / "vedAH_Rk" / "content",
    hugo / "vedAH_Rk" / "static",
    hugo / "vedAH" / "content",
    hugo / "vedAH" / "static",
  ]
  res = run_paippalada_dedup(
    hugo_base_dir=hugo,
    upstream_targets=("RV", "AV"),
    caller_roots=roots,
    specs=mock_specs,
    dry_run=False,
    run_single_caller_cleanup=False,
  )

  assert res["cross_veda"]["content_exact"] == 1
  assert res["cross_veda"]["content_variant"] == 1
  assert res["self_repeat"]["self_repeat_clusters"] == 1
  assert res["self_repeat"]["self_repeat_callers"] == 3

  out_s1 = s1.read_text(encoding="utf-8")
  out_s2 = s2.read_text(encoding="utf-8")
  # Exact RV match links both VP & sarvASh_TIkAH to RV; AV variant keeps local VP and links sarvASh_TIkAH to AV.
  assert "/vedAH_Rk/shAkalam/saMhitA/Rk/vishvAsa-prastutiH/10/009/04.md" in out_s1
  assert "/vedAH/atharva/shaunakam/rUDha-saMhitA/sarvASh_TIkAH/01/002/01.md" in out_s1
  assert "विद्मा शस्य पितरं" in out_s1
  assert "मूलम् - पैप्पलादम् (GR)" in av_sv.read_text(encoding="utf-8")
  # Exact RV reading omits redundant unaccented GR block inside RV sarvASh_TIkAH.
  assert "पैप्पलादम् (GR)" not in rv_sv.read_text(encoding="utf-8")

  # Self-repeat extracted to 01/001/... and linked in both 01/001.md and 02/001.md; manual & lacuna remain inline.
  assert "/vedAH/atharva/paippalAdam/saMhitA/Rk/vishvAsa-prastutiH/01/001/" in out_s1
  assert "/vedAH/atharva/paippalAdam/saMhitA/Rk/vishvAsa-prastutiH/01/001/" in out_s2
  assert manual_rep in out_s1
  assert lacuna_rep in out_s1 and lacuna_rep in out_s2
  assert _self_repeat_key("हिरण्यवर्णा इति चतस्रः ॥") is None


def test_solve_avp_mantra_manual_bold_lacuna_and_parallel():
  from doc_curation.sanskrit.accent.provenance import VedicCorpusCounter
  from doc_curation.sanskrit.accent.shatapatha_solver import UnifiedVedicLexicon

  lex = UnifiedVedicLexicon.load_or_build(include_sb_m=True)
  counter = VedicCorpusCounter.load_or_build()

  # 1. Manual US-accented mantra with inline gloss & jihvāmūlīya/upadhmānīya must keep VP verbatim.
  man_vp = "पु᳓नर् नᳶ पित᳓रो +++(तान् अनुगतं)+++ म᳓नो  \nद᳓दातु दै᳓व्यो ज᳓नः  ॥"
  res_man = solve_avp_mantra(man_vp, lex, counter, None, unit_kind="rk")
  assert res_man.was_manual is True
  assert res_man.vp_body == man_vp
  assert "(यन्त्र-स्वरः)" not in res_man.vp_summary
  assert res_man.pp_lines and all(ln.startswith("- ") for ln in res_man.pp_lines)

  # 2. Bold + inline gloss + unaccented Mode B preserves `**bold**` & `+++(...)+++` and adds US accents.
  bold_vp = (
    "अहं **सत्येन** सयुजा **चराम्य्**  \n"
    "**सध्रीचीनं**+++(←सध्र्यङ् = सहचरं)+++ वो **मनो** ऽस्तूग्रम् ॥"
  )
  res_bold = solve_avp_mantra(bold_vp, lex, counter, None, unit_kind="rk")
  assert res_bold.was_manual is False
  assert "(यन्त्र-स्वरः)" in res_bold.vp_summary
  assert "**" in res_bold.vp_body and "+++(←सध्र्यङ् = सहचरं)+++" in res_bold.vp_body
  assert "\u1cd3" in res_bold.vp_body or "\u1cd9" in res_bold.vp_body

  # 3. Unresolved MS lacuna `(…)` does not crash and remains intact.
  lac_vp = "अभि त्वोर्न (…)"
  res_lac = solve_avp_mantra(lac_vp, lex, counter, None, unit_kind="rk")
  assert "(…)" in res_lac.vp_body

  # 4. Parallel linked witness alignment transfers matching accents directly.
  par_us = "विद्मा᳓ श᳓रस्य पित᳓रं  \nपर्ज᳓न्यं भूरि᳓धायसम् ।  \nविद्मो᳓ ष्वस्य मात᳓रम् ॥"
  avp_var = "विद्मा शस्य पितरं  \nपर्जन्यं भूरिधायसम् ।  \nविद्मो ष्वस्य मातरम् ॥"
  res_par = solve_avp_mantra(
    avp_var, lex, counter, None, unit_kind="rk", linked_vp_us=par_us, linked_corpus="AV"
  )
  assert res_par.par_aligned_padas >= 4
  assert "पर्ज᳓न्यं" in res_par.vp_body and "पित᳓रं" in res_par.vp_body

  # 5. Upsert padapāṭha places `पद-पाठः (यान्त्रिकः)` cleanly after `मूलम्*` and before `मानसतरङ्गिणीकृत्`.
  updated_tika = _upsert_local_padapatha(
    [("मूलम् (GR)", "x"), ("मानसतरङ्गिणीकृत्", "y")],
    res_par.pp_markdown,
  )
  assert [t for t, _ in updated_tika] == ["मूलम् (GR)", "पद-पाठः (यान्त्रिकः)", "मानसतरङ्गिणीकृत्"]

  # 6. Audit hardening: no अनाम्नातम्, proper पा॰ ८.१.२८ on Vedic finite verbs, पा॰ ८.२.६ abhinihita,
  # chhatva restoration, and `च इह` splitting.
  from doc_curation.sanskrit.accent import validator

  hard_vp = "पञ्चौदनं निषेचनं नयामसि ये ऽमावास्यां तत् छिरः चेह मा हिंसीः ॥"
  res_hard = solve_avp_mantra(hard_vp, lex, counter, None, unit_kind="rk")
  assert "अनाम्नातम्" not in res_hard.pp_markdown
  assert "तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८" in res_hard.pp_markdown
  assert "ये᳙ ऽमावास्यां" in res_hard.vp_body
  assert validator.validate_accented_markdown(
    f"<details open><summary>{res_hard.vp_summary}</summary>\n\n{res_hard.vp_body}\n</details>\n\n"
    f"<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n{res_hard.pp_markdown}\n</details>\n"
  ) == []


def test_run_paippalada_padapatha_and_accent_isolated(tmp_path):
  from doc_curation.sanskrit.accent.provenance import VedicCorpusCounter
  from doc_curation.sanskrit.accent.shatapatha_solver import UnifiedVedicLexicon
  from doc_curation_projects.veda.yajuH.ks_ms.reference_index import VedicReferenceIndex

  hugo = tmp_path / "vishvAsa"
  rv_sv = hugo / "vedAH_Rk" / "static" / "shAkalam" / "saMhitA" / "Rk" / "sarvASh_TIkAH" / "10" / "057" / "05.md"
  rv_sv.parent.mkdir(parents=True, exist_ok=True)
  rv_sv.write_text(
    '+++\ntitle = "05"\n+++\n\n<details><summary>मूलम् - शाकलम्</summary>\n\nपु᳓नर् नः पित᳓रो म᳓नो द᳓दातु दै᳓व्यो ज᳓नः\n</details>\n',
    encoding="utf-8",
  )

  av_vp = hugo / "vedAH" / "static" / "atharva" / "shaunakam" / "rUDha-saMhitA" / "vishvAsa-prastutiH" / "01" / "002" / "01.md"
  av_sv = hugo / "vedAH" / "static" / "atharva" / "shaunakam" / "rUDha-saMhitA" / "sarvASh_TIkAH" / "01" / "002" / "01.md"
  av_vp.parent.mkdir(parents=True, exist_ok=True)
  av_sv.parent.mkdir(parents=True, exist_ok=True)
  av_vp.write_text('+++\ntitle = "01"\n+++\n\nविद्मा᳓ श᳓रस्य पित᳓रं  \nपर्ज᳓न्यं भूरि᳓धायसम् ।\n', encoding="utf-8")
  av_sv.write_text('+++\ntitle = "01"\n+++\n\n<details><summary>मूलम् - शौनकम्</summary>\n\nविद्मा᳓ श᳓रस्य पित᳓रं\n</details>\n', encoding="utf-8")

  avp_static = hugo / "vedAH" / "static" / "atharva" / "paippalAdam" / "saMhitA"
  avp_content = hugo / "vedAH" / "content" / "atharva" / "paippalAdam" / "saMhitA" / "sarva-prastutiH"
  (avp_content / "01").mkdir(parents=True, exist_ok=True)

  # Static unaccented self-repeat 01/001/03
  rep_vp = avp_static / "Rk" / "vishvAsa-prastutiH" / "01" / "001" / "03_agni.md"
  rep_sv = avp_static / "Rk" / "sarvASh_TIkAH" / "01" / "001" / "03_agni.md"
  rep_vp.parent.mkdir(parents=True, exist_ok=True)
  rep_sv.parent.mkdir(parents=True, exist_ok=True)
  rep_vp.write_text('+++\ntitle = "03"\n+++\n\nअग्न आ याहि वीतये  \nगृणानो हव्यदातये ॥\n', encoding="utf-8")
  rep_sv.write_text('+++\ntitle = "03"\n+++\n\n<details><summary>मूलम् (GR)</summary>\n\nअग्न आ याहि वीतये\n</details>\n', encoding="utf-8")

  # Static manual accented 19/024/12 whose sarva merged into RV 10/057/05
  man_vp = avp_static / "Rk" / "vishvAsa-prastutiH" / "19" / "024" / "12_punar.md"
  man_vp.parent.mkdir(parents=True, exist_ok=True)
  man_vp.write_text('+++\ntitle = "12"\n+++\n\nपु᳓नर् नᳶ पित᳓रो म᳓नो  \nद᳓दातु दै᳓व्यो ज᳓नः ॥\n', encoding="utf-8")

  sukta = avp_content / "01" / "001.md"
  sukta.write_text(
    '+++\ntitle = "001"\n+++\n\n'
    + _make_inline_mantra("01 local", "अयं देवानाम् असुरो वि राजति ।")
    + "\n## 02 variant\n\n"
    + '<details open><summary>विश्वास-प्रस्तुतिः - ऋक्</summary>\n\nविद्मा शस्य पितरं  \nपर्जन्यं भूरिधायसम् ।\n</details>\n\n'
    + '<div class="js_include collapsed" newlevelforh1="5" title="सर्वाष् टीकाः" unfilled '
    + 'url="/vedAH/atharva/shaunakam/rUDha-saMhitA/sarvASh_TIkAH/01/002/01.md"></div>\n\n'
    + "## 03 static self repeat\n\n"
    + '<div class="js_include" newlevelforh1="6" title="विश्वास-प्रस्तुतिः" unfilled '
    + 'url="/vedAH/atharva/paippalAdam/saMhitA/Rk/vishvAsa-prastutiH/01/001/03_agni.md"></div>\n'
    + '<div class="js_include collapsed" newlevelforh1="6" title="सर्वाष् टीकाः" unfilled '
    + 'url="/vedAH/atharva/paippalAdam/saMhitA/Rk/sarvASh_TIkAH/01/001/03_agni.md"></div>\n\n'
    + "## 12 manual static -> RV sarva\n\n"
    + '<div class="js_include" newlevelforh1="6" title="विश्वास-प्रस्तुतिः" unfilled '
    + 'url="/vedAH/atharva/paippalAdam/saMhitA/Rk/vishvAsa-prastutiH/19/024/12_punar.md"></div>\n'
    + '<div class="js_include collapsed" newlevelforh1="6" title="सर्वाष् टीकाः" unfilled '
    + 'url="/vedAH_Rk/shAkalam/saMhitA/Rk/sarvASh_TIkAH/10/057/05.md"></div>\n',
    encoding="utf-8",
  )

  mock_specs = {
    "RV": VedaCorpusSpec(
      name="RV", shAkha_label="शाकलम्", pada_label="पद-पाठः", sayana_variant_label="सायणः (शाकलः)",
      has_two_part_rk=True,
      vp_dir=hugo / "vedAH_Rk" / "static" / "shAkalam" / "saMhitA" / "Rk" / "vishvAsa-prastutiH",
      sarva_dir=hugo / "vedAH_Rk" / "static" / "shAkalam" / "saMhitA" / "Rk" / "sarvASh_TIkAH",
      vp_url_prefix="/vedAH_Rk/shAkalam/saMhitA/Rk/vishvAsa-prastutiH",
      sarva_url_prefix="/vedAH_Rk/shAkalam/saMhitA/Rk/sarvASh_TIkAH",
      heading_level=6,
    ),
    "AV": VedaCorpusSpec(
      name="AV", shAkha_label="शौनकम्", pada_label="पदपाठः", sayana_variant_label="सायण-टीका (शौनकीया)",
      has_two_part_rk=True,
      vp_dir=hugo / "vedAH" / "static" / "atharva" / "shaunakam" / "rUDha-saMhitA" / "vishvAsa-prastutiH",
      sarva_dir=hugo / "vedAH" / "static" / "atharva" / "shaunakam" / "rUDha-saMhitA" / "sarvASh_TIkAH",
      vp_url_prefix="/vedAH/atharva/shaunakam/rUDha-saMhitA/vishvAsa-prastutiH",
      sarva_url_prefix="/vedAH/atharva/shaunakam/rUDha-saMhitA/sarvASh_TIkAH",
      heading_level=5,
    ),
    "AV-P": VedaCorpusSpec(
      name="AV-P", shAkha_label="पैप्पलादम्", pada_label="पद-पाठः (यान्त्रिकः - पैप्पलादम्)",
      sayana_variant_label="सायण-टीका (पैप्पलादम्)", has_two_part_rk=True,
      content_dir=avp_content,
      vp_dir=avp_static / "Rk" / "vishvAsa-prastutiH",
      sarva_dir=avp_static / "Rk" / "sarvASh_TIkAH",
      vp_url_prefix="/vedAH/atharva/paippalAdam/saMhitA/Rk/vishvAsa-prastutiH",
      sarva_url_prefix="/vedAH/atharva/paippalAdam/saMhitA/Rk/sarvASh_TIkAH",
      heading_level=6,
    ),
  }
  roots = [hugo / "vedAH_Rk" / "static", hugo / "vedAH" / "content", hugo / "vedAH" / "static"]
  lex = UnifiedVedicLexicon.load_or_build(include_sb_m=True)
  cnt = VedicCorpusCounter.load_or_build()
  empty_ref = VedicReferenceIndex([], [], [], [])

  res = run_paippalada_padapatha_and_accent(
    hugo_base_dir=hugo, specs=mock_specs, caller_roots=roots, lex=lex, counter=cnt, ref_idx=empty_ref, dry_run=False,
  )
  assert res["content_local_accented"] == 1
  assert res["content_variant_accented"] == 1
  assert res["static_accented"] == 1
  assert res["static_manual_processed"] == 1
  assert res["upstream_sarva_merged"] == 2

  out_s = sukta.read_text(encoding="utf-8")
  assert "<summary>विश्वास-प्रस्तुतिः - ऋक् (यन्त्र-स्वरः)</summary>" in out_s
  assert "<summary>पद-पाठः (यान्त्रिकः)</summary>" in out_s
  assert "title=\"विश्वास-प्रस्तुतिः - ऋक् (यन्त्र-स्वरः)\"" in out_s
  assert "<summary>पद-पाठः (यान्त्रिकः - पैप्पलादम्)</summary>" in av_sv.read_text(encoding="utf-8")
  assert "<summary>पद-पाठः (यान्त्रिकः - पैप्पलादम्)</summary>" in rv_sv.read_text(encoding="utf-8")
  assert "<summary>पद-पाठः (यान्त्रिकः)</summary>" in rep_sv.read_text(encoding="utf-8")
  assert "\u1cd3" in rep_vp.read_text(encoding="utf-8") or "\u1cd9" in rep_vp.read_text(encoding="utf-8")
  # Manual static VP remains untouched verbatim.
  assert "पु᳓नर् नᳶ पित᳓रो म᳓नो" in man_vp.read_text(encoding="utf-8")


def test_avp_step4_repairs_ote_enclitics_verbs_and_par_map():
  from doc_curation.sanskrit.accent import validator
  from doc_curation.sanskrit.accent.provenance import VedicCorpusCounter
  from doc_curation.sanskrit.accent.shatapatha_solver import UnifiedVedicLexicon
  from doc_curation_projects.veda.atharva.paippalaadam.padapatha_accent import (
    _is_valid_par_map_entry,
    solve_avp_mantra,
  )

  lex = UnifiedVedicLexicon.load_or_build(include_sb_m=True)
  counter = VedicCorpusCounter.load_or_build()

  # 1. Manual VP `ओ᳓त᳓ आ᳓हितः` splits to `आ᳓` + `उत᳓`, preserving manual VP verbatim.
  ote_vp = "दिवो᳓ मू᳓लम् अ᳓वततम्  \nपृथिव्या᳓म् ओ᳓त᳓ आ᳓हितः ।  \nप᳓रि णः पातु विश्व᳓तः ॥"
  res_ote = solve_avp_mantra(ote_vp, lex, counter, None, unit_kind="rk")
  assert res_ote.was_manual is True
  assert res_ote.vp_body == ote_vp
  assert any("आ᳓" in ln for ln in res_ote.pp_lines) and any("उत᳓" in ln for ln in res_ote.pp_lines)
  assert not any("ओ᳓ते᳓" in ln for ln in res_ote.pp_lines)
  assert any("- णः (अनुदात्तम्, पा॰ ८.१.१८" in ln for ln in res_ote.pp_lines)

  # 2. Enclitic समह, missing finite verbs (रिषम्, अक्रन्), सु-sandhi ष्व्, and nominal homographs (अजानाम्, प्रजायै).
  mixed_vp = "मा रिषं समह प्रजायै अजानाम् मो ष्व् अक्रन् ॥"
  res_mix = solve_avp_mantra(mixed_vp, lex, counter, None, unit_kind="rk")
  assert "मूल-पाठः" not in res_mix.pp_markdown
  assert "- समह (अनुदात्तम्, पा॰ ८.१.१८" in res_mix.pp_markdown
  assert "- रिषम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८" in res_mix.pp_markdown
  assert "- अक्रन् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८" in res_mix.pp_markdown
  assert any(ln.startswith("- सु᳓ ") or ln.startswith("- सु ") for ln in res_mix.pp_lines)
  assert not any(ln.startswith("- ष्व् ") for ln in res_mix.pp_lines)
  assert validator.validate_accented_markdown(
    f"<details open><summary>{res_mix.vp_summary}</summary>\n\n{res_mix.vp_body}\n</details>\n\n"
    f"<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n{res_mix.pp_markdown}\n</details>\n"
  ) == []

  # 3. GRETIL typo त्रायैते -> त्रायेते without tinanta_sutra_misapplied on nominal.
  tr_vp = "याव् इमं त्रायैते अस्माद् आमयतः त्रायेतां स्वाहा ॥"
  res_tr = solve_avp_mantra(tr_vp, lex, counter, None, unit_kind="rk")
  assert "त्रा᳓येते" in res_tr.vp_body and "त्रायै" not in res_tr.pp_markdown
  assert validator.find_tinanta_sutra_on_non_tinanta(res_tr.pp_lines) == []

  # 4. Reject unlicensed 0-accent nominals from parallel alignment while keeping verbs/enclitics/non-init vocatives.
  assert _is_valid_par_map_entry("हस्तम्", ("", ""), lex, is_clause_start=False) is False
  assert _is_valid_par_map_entry("नः", ("",), lex, is_clause_start=False) is True
  assert _is_valid_par_map_entry("रिषम्", ("", ""), lex, is_clause_start=False) is True
  assert _is_valid_par_map_entry("अरुन्धति", ("", "", "", ""), lex, is_clause_start=False) is True
  assert _is_valid_par_map_entry("अरुन्धति", ("", "", "", ""), lex, is_clause_start=True) is False

  # 5. `मा यवम्` in manual VP gets पा॰ ८.१.२८, `भूत्वा अस्यावत` -> `अस्य + अवत`, and `विदेयम्` drops stale ᳙.
  yav_res = solve_avp_mantra("त᳓स्मान् मा᳓ यवम् ॥", lex, counter, None, unit_kind="rk")
  assert any("- यवम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८" in ln for ln in yav_res.pp_lines)
  bhu_res = solve_avp_mantra("भूत्वा अस्यावत वीर्यम् ॥", lex, counter, None, unit_kind="rk")
  assert any("अस्य᳓" in ln or ln.startswith("- अस्य ") for ln in bhu_res.pp_lines)
  assert validator.find_unexplained_aa_hiatuses(bhu_res.pp_lines, "भूत्वा अस्यावत वीर्यम्") == []
  vid_res = solve_avp_mantra("वेत्तासि विदेयम् ॥", lex, counter, None, unit_kind="yajuh")
  assert not any("वि᳙देयम्" in ln for ln in vid_res.pp_lines)

  # 6. Normalized-key OOV fragment joins (अम्बरीष्यम्, दृषद्-रथाम्, सुषूदिम, अद्वेष्य-प्रतीकाशः).
  oov_vp = "कर्णा दृषद्रथामहम् उरुकीं केशिनीं क्रकुम् खडुरीम् अम्बरीष्यं नाशयामः ॥"
  oov_res = solve_avp_mantra(oov_vp, lex, counter, None, unit_kind="rk")
  assert "अम्बरीष्य" in oov_res.pp_markdown and "अ᳓म्प्" not in oov_res.pp_markdown
  assert "दृषद्-रथा" in oov_res.pp_markdown and "क्रकु" in oov_res.pp_markdown
  su_res = solve_avp_mantra("गावो न हव्या सुषूदिम ॥", lex, counter, None, unit_kind="rk")
  assert "सु-षू" not in su_res.pp_markdown and "- सुषूदिम (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८" in su_res.pp_markdown
  adv_res = solve_avp_mantra("अद्वेष्यप्रतीकाशो जिगीवाँ अपराजितः ॥", lex, counter, None, unit_kind="rk")
  assert "अद्वेष्य-प्रतीकाश" in adv_res.pp_markdown and "अ᳓द्व " not in adv_res.pp_markdown
