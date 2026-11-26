"""Tests for VS-K saṁhitā repair, clause splitting, Padapāṭha sandhi verification, and bhāṣya alignment."""
from __future__ import annotations

import pathlib

from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva import samhitaa as vsk


def test_normalize_vsk_text_protects_mid_verse_newline():
  mula = "दे॒वीर्मे॑दसां \nपृथ॒क् स्वाहा॑ । आप्या॑यध्वं \nअघ्न्या॒ भा॒गं।"
  fixed = vsk.normalize_vsk_text(mula, is_vp=False)
  # Mid-verse consonant-followed `मेदसां \nपृथक्` keeps anusvāra, whereas pre-vowel & pausa turn to म्
  assert "र्मे॑दसां \nपृथ॒क्" in fixed
  assert "आप्या॑यध्वम्" in fixed
  assert "भा॒गम्।" in fixed

  vp = "बह्वी᳓ः पशू᳓न् प्र᳓त्युष्टाऽअ᳓रातयः भागं᳓।"
  fixed_vp = vsk.normalize_vsk_text(vp, is_vp=True)
  assert "बह्वीः᳓" in fixed_vp
  assert "प्र᳓त्युष्टा अ᳓रातयः" in fixed_vp
  assert "भाग᳓म्।" in fixed_vp


def test_to_devanagari_ordinal_and_heading():
  assert vsk.to_devanagari_ordinal(1) == "०१"
  assert vsk.to_devanagari_ordinal(9) == "०९"
  assert vsk.to_devanagari_ordinal(105) == "१०५"
  assert vsk.build_kandika_heading(1, "॥ ओ३म्॥ इषे᳓ त्वोर्जे᳓ त्वा") == "## ०१ इषे त्वोर्जे"


def test_split_kandika_clauses_prose_vs_verse():
  prose_rec = {
    "kind": "prose",
    "raw_pairs": [
      (
        "ध्रुवा᳓ अस्मि᳓न् गो᳓पतौ स्यात बह्वीः᳓।  \nय᳓जमानस्य पशू᳓न् पाहि व᳓सोः पवि᳓त्रम् असि ॥३॥ (१) ३ ॥",
        "ध्रु॒वा अ॒स्मिन् गोप॑तौ स्यात ब॒ह्वीः। \nयज॑मानस्य प॒शून् पा॑हि॒ वसोः॑ प॒वित्र॑मसि ॥३॥ (१) ३ ॥",
      )
    ],
  }
  clauses = vsk.split_kandika_clauses(prose_rec)
  assert len(clauses) == 2
  assert clauses[0][1].endswith("ब॒ह्वीः।")
  assert clauses[1][1].endswith("॥३॥ (१) ३ ॥")

  verse_rec = {
    "kind": "verse",
    "raw_pairs": [
      (
        "युञ्जा॒नः प्र॑थ॒मं मन॑ः त॒त्वाय॑ सवि॒ता धियः॑ ।  \nअ॒ग्नेर्ज्योति॑र्नि॒चाय्य॑ पृथि॒व्या अध्याभ॑रत् ॥१॥ १",
        "यु॒ञ्जा॒नः प्र॑थ॒मं मन॑स्त॒त्वाय॑ सवि॒ता धियः॑ । \nअ॒ग्नेर्ज्योति॑र्नि॒चाय्य॑ पृथि॒व्या अध्याभ॑रत् ॥१॥ १",
      )
    ],
  }
  v_clauses = vsk.split_kandika_clauses(verse_rec)
  assert len(v_clauses) == 1


def test_split_and_verify_padapatha_vs_sandhi_check():
  sub_mulas = [
    "इ॒षे त्वो॒र्जे त्वा॑ वा॒यव॑ स्थ।",
    "दे॒वो वः॑ सवि॒ता प्रार्प॑यतु॒ श्रेष्ठ॑तमाय॒ कर्म॑णे॥१॥ १",
  ]
  vsm_matches = [
    {"vsm_pada": "इ॒षे। त्वा॒। ऊ॒र्जे। त्वा॒। वा॒यवः॑। स्थ॒।", "exact_pada_ok": True},
    {"vsm_pada": "दे॒वः। वः॒। स॒वि॒ता। प्र। अर्प॑यतु। श्रेष्ठ॑तमाय। कर्म॑णे।", "exact_pada_ok": True},
  ]
  padas, ok_flags = vsk.reconcile_and_split_padapatha("", sub_mulas, vsm_matches)
  assert ok_flags == [True, True]
  assert "वा॒यवः॑।" in padas[0]
  assert "प्र।" in padas[1]


def test_render_vsk_kandika_section_skips_dayananda_and_groups_blocks():
  plan = [
    {
      "sayana": {"avatarika": "अवतारिका वाक्यम्।", "viniyoga": "कात्यायनः — ‘इषे त्वा’ इति।", "tika": "इषे अन्नाय।"},
      "anandabodha": {"tika": "अन्नार्थाय।"},
      "anantacharya": {},
    },
  ]
  rendered = vsk.render_vsk_kandika_section(
    "## ०१ इषे त्वा",
    ["इषे᳓ त्वा"],
    ["इ॒षे त्वा॑"],
    ["THEE for food."],
    ["इ॒षे। त्वा॒।"],
    plan,
  )
  assert "## ०१ इषे त्वा" in rendered
  assert "<details><summary>सर्वा अवतारिकाः</summary>" in rendered
  assert "<summary>सायणः - अवतारिका</summary>" in rendered
  assert "<summary>सायणः - विनियोगः</summary>" in rendered
  assert "<summary>सर्वाष् टीकाः</summary>" in rendered
  assert "<summary>Griffith</summary>" in rendered
  assert "<summary>पदपाठः</summary>" in rendered
  assert "<summary>सायण-टीका</summary>" in rendered
  assert "<summary>आनन्दबोध-टीका</summary>" in rendered
  assert "दयानन्द" not in rendered
  assert rendered.count("<details") == rendered.count("</details>")


def test_verify_pada_tokens_iti_and_avagraha():
  mula_1 = "प्रत्यु॑ष्टँ॒ रक्षः॒ प्रत्यु॑ष्टा॒ अरा॑तयो॒ निष्ट॑प्तँ॒ रक्षो॒ निष्ट॑प्ता॒ अरा॑तयः।"
  toks_1 = vsk._clean_pada_tokens(
    "प्रत्यु॑ष्ट॒मिति॒ प्रति॑ऽउष्टम्। रक्षः॑। प्रत्यु॑ष्टा॒ इति॒ प्रति॑ऽउष्टाः। अरा॑तयः। "
    "निष्ट॑प्त॒मिति॒ निःऽत॑प्तम्। रक्षः॑। निष्ट॑प्ता॒ इति॒ निःऽत॑प्ताः। अरा॑तयः।"
  )
  assert vsk._verify_pada_tokens(toks_1, mula_1)

  mula_21_6 = "नाना॒ हि वां॑ दे॒वहि॑तँ॒ सद॑स्कृ॒तं मा सँ सृ॑क्षाथां पर॒मे व्यो॑मन् ॥ ६ ॥"
  toks_21_6 = vsk._clean_pada_tokens(
    "नाना॑। हि। वा॒म्। दे॒वहि॑त॒मिति॑ दे॒वऽहि॑तम्। सदः॑। कृ॒तम्। मा। सम्। सृ॒क्षाथाम्। प॒र॒मे। व्यो॑म॒न्निति॒ विऽओ॑मन्।"
  )
  assert vsk._verify_pada_tokens(toks_21_6, mula_21_6)


def test_slice_vsm_volume_chapters_skips_anuvaka_wraps():
  lines = ["preamble"] * 160 + [
    "तस्याः पर्णवृक्षशाखायाः व्याख्यानम्",
    "प्रथमो ऽध्यायः आरभ्यते",
    "इति प्रथमाध्याये द्वितीयोऽ",
    "नुवाकः ॥ (२) ॥",
  ] + ["अग्ने व्रतपते चरिष्यामि"] * 35 + [
    "इति काण्वसंहिताभाष्यसंग्रहे",
    "प्रथमो ऽध्यायः समाप्तः ॥ १ ॥",
    "इति वेदार्थदीपिकायां प्रथमो ऽध्यायः ॥",
    "अथ द्वितीयोऽध्यायः",
    "समिधा अग्निं दुवस्यत",
  ]
  slices = vsk.slice_vsm_volume_chapters(lines, range(1, 3))
  assert any("अग्ने व्रतपते" in l for l in slices[1])
  assert not any("समिधा अग्निं" in l for l in slices[1])
  assert any("समिधा अग्निं" in l for l in slices[2])


def test_match_vsm_clauses_one_to_n_and_containment():
  # Fake minimal index matching 1 VS-M clause containing 2 VS-K clauses (1-to-N)
  mula_full = "ध्रु॒वा अ॒स्मिन् गोप॑तौ स्यात ब॒ह्वीर्यज॑मानस्य प॒शून् पा॑हि।"
  pada_full = "ध्रुवाः। अस्मिन्। गोप॑ता॒विति॒ गोऽप॑तौ। स्या॒त॒। ब॒ह्वीः। यज॑मानस्य। प॒शून्। पा॒हि॒।"
  sec = {
    "ch": 1,
    "v": 3,
    "sk": vsk._norm_skel(mula_full),
    "subs": [
      {
        "sk": vsk._norm_skel(mula_full),
        "mula": mula_full,
        "griffith": "Be constant to this lord of kine. Guard the cattle of the Sacrificer.",
        "pada": pada_full,
      }
    ],
  }
  grams = {}
  for i in range(0, max(1, len(sec["sk"]) - 5), 2):
    grams.setdefault(sec["sk"][i : i + 6], set()).add(0)
  vsm_idx = {"secs": [sec], "grams": grams, "clause_exact": {}}

  k_clauses = [
    ("ध्रुवा᳓ अस्मि᳓न् गो᳓पतौ स्यात बह्वीः᳓।", "ध्रु॒वा अ॒स्मिन् गोप॑तौ स्यात ब॒ह्वीः।"),
    ("य᳓जमानस्य पशू᳓न् पाहि।", "यज॑मानस्य प॒शून् पा॑हि।"),
  ]
  res = vsk.match_vsm_clauses(k_clauses, vsm_idx, ch_hint=1)
  assert len(res) == 2
  assert res[0]["exact_pada_ok"] and "गोऽप॑तौ" in res[0]["vsm_pada"]
  assert res[1]["exact_pada_ok"] and "प॒शून्" in res[1]["vsm_pada"]
  assert "cattle" in res[1]["griffith"]


def test_build_indike_sayana_fallback_skips_pranava_in_alignment(tmp_path):
  say_json = tmp_path / "ind_say.json"
  say_json.write_text(
    '{"segments": ['
    '{"loc": "1.p1", "text": "अवतारिका वाक्यम्।"}, '
    '{"loc": "1.1.1", "text": "इषे त्वा ऊर्जे त्वा अन्नाय त्वा छिनद्मि।"}'
    ']}',
    encoding="utf-8",
  )
  kby = {
    1: [
      {"ch": 1, "k": 1, "loc": "1.1.1", "mula_full": "॥ ओ३म्॥ इ॒षे त्वो॒र्जे त्वा॑ वा॒यव॑ स्थ।"},
    ]
  }
  fb = vsk.build_indike_sayana_fallback(say_json, kby)
  assert (1, 1) in fb
  assert "अवतारिका वाक्यम्" in fb[(1, 1)]
  assert "अन्नाय" in fb[(1, 1)]

  plan = vsk.plan_kanva_kandika_alignment(
    {"sayana": fb[(1, 1)]},
    ["॥ ओ३म्॥", "इ॒षे त्वो॒र्जे त्वा॑ वा॒यव॑ स्थ।"],
    kandika_key="1.1.1",
  )
  assert plan[0]["sayana"] == {}
  assert plan[1]["sayana"]


def test_strip_pune_margin_numbers_preserves_citations():
  s = 'कण्वा- १५ भिमतो मन्त्रः । यदा १० कदाचिद् ( तैब्रा ३.२.१ ) ५ इति ॥ ५ ॥'
  cleaned = vsk.strip_pune_margin_numbers(s)
  assert "कण्वाभिमतो" in cleaned
  assert "यदा कदाचिद्" in cleaned
  assert "( तैब्रा ३.२.१ ) इति ॥ ५ ॥" in cleaned
  assert vsk.strip_pune_margin_numbers(r"शा ( श्या \! ) मायनीयाः") == "शा ( श्या ! ) मायनीयाः"
  assert vsk._pada_tok_eff_skel("सपत्नानिति सपत्नान्") == "सपत्नान्"


def test_padapatha_eff_len_does_not_truncate_after_iti():
  raw_p = "सहसा। जातान्। प्र। नुद। नः। सपत्नानिति सपत्नान्। प्रति। अजातान्। नुद। जातवेदः। अधि। नः। ब्रूहि।"
  sub_mulas = [
    "सहसा जातान्प्रणुदा नः सपत्नान्प्रत्यजातान्नुद जातवेदः ।",
    "अधि नो ब्रूहि ॥",
  ]
  padas, ok = vsk.reconcile_and_split_padapatha(raw_p, sub_mulas, [{"vsm_pada": "", "exact_pada_ok": False}] * 2)
  assert "जातवेदः।" in padas[0]
  assert "अधि।" in padas[1]


def test_carve_sub_pada_single_vowel_preverb():
  p_raw = "स॒मिधेति॑ स॒म्ऽइधा॑। अ॒ग्निम्। दु॒व॒स्य॒त॒। घृ॒तैः। बो॒ध॒य॒त॒। अति॑थिम्। आ। अ॒स्मि॒न्। ह॒व्या। जु॒हो॒त॒न॒।"
  carved = vsk._carve_sub_pada(p_raw, "आस्मि॑न् ह॒व्या जु॑होतन ॥१॥ १")
  assert carved is not None
  assert carved.startswith("आ। अ॒स्मि॒न्।") and "१।" in carved


def test_strip_pune_margin_numbers_ocr_noise_and_dir_clean(tmp_path):
  raw = (
    "सोमक्रयणी - २० मित्य्-अर्थः\n"
    "१० ' इमं मे *(* काश्रौ ७.६.१५ *)* इति\n"
    "-१५\n"
    "काण्व - संहिता\n"
    "V..\n"
    "Hi om.\n"
    "ㄓ\n"
    "भ\n"
    "अध्यायः ]\n"
    "for 'निवासा; B1 H2-3\n"
    "(७) ৷\n"
    "८.५.२.६ ) ।\n"
    "समाप्तः ॥ १० ॥"
  )
  cleaned = vsk.strip_pune_margin_numbers(raw)
  assert "सोमक्रयणीमित्य्-अर्थः" in cleaned
  assert "' इमं मे ( काश्रौ ७.६.१५ ) इति" in cleaned
  assert "(७) ৷" in cleaned
  assert "८.५.२.६ ) ।" in cleaned
  assert "समाप्तः ॥ १० ॥" in cleaned
  for noise in ("-१५", "काण्व - संहिता", "V..", "Hi om.", "ㄓ", "अध्यायः ]", "B1 H2-3"):
    assert noise not in cleaned

  md_p = tmp_path / "01.md"
  md_p.write_text(
    "<details><summary>सर्वा अवतारिकाः</summary>\n"
    "<details><summary>सायणः - विनियोगः</summary>\n\nV..\n</details>\n"
    "</details>\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअ᳓ग्ने - १५ न᳓य\n</details>\n"
    "<details><summary>सायण-टीका</summary>\n\nV..\nकण्वा- १५ भिमतो\n</details>\n",
    encoding="utf-8",
  )
  res = vsk.clean_vsk_commentary_blocks_in_dir(tmp_path)
  assert res == {"files_changed": 1, "blocks_changed": 2}
  out = md_p.read_text(encoding="utf-8")
  assert "अ᳓ग्ने - १५ न᳓य" in out
  assert "सर्वा अवतारिकाः" not in out
  assert "V.." not in out and "कण्वाभिमतो" in out


def test_clean_kanva_sayana_block_and_corpus_soft_breaks(tmp_path):
  raw = (
    "सायणाचार्य - आनन्दबोध- माष्य-समेता\n"
    "सा - कात्यायन: 'इषे त्वा' इति ।\n\n"
    "[ प्रथमो ऽनुवाकः १-१० ]\n\n"
    "हे देव:\u200d! अत्र अग्निर् यजमानस्य\nरक्षिता भवति ।\n\n"
    "द्वितीयो ऽपि मन्त्रः ।\n\n"
    "अथ पञ्चमी-\n"
    "क्षत्रेण ।\n\nअग्ने ।\n\nसु ।\n\nआयुः ।\n\n"
    "इति प्रथमाध्याये द्वितीयो ऽनुवाकः ।\n\n"
    "अग्रे व्याख्यायते ।"
  )
  cleaned = vsk.clean_kanva_sayana_block(raw)
  assert "माष्य-समेता" not in cleaned
  assert "सा -" not in cleaned
  assert "\u200d" not in cleaned
  assert "कात्यायनः" in cleaned and "हे देवः!" in cleaned
  assert "रक्षिता भवति ।  \nद्वितीयो ऽपि मन्त्रः ।" in cleaned
  assert "अथ पञ्चमी —  \nक्षत्रेण ।  \nअग्ने । सु । आयुः ।" in cleaned
  assert "\n\n[ प्रथमो ऽनुवाकः १-१० ]\n\n" in cleaned
  assert "इति प्रथमाध्याये द्वितीयो ऽनुवाकः ।\n\nअग्रे व्याख्यायते ।" in cleaned

  md_file = tmp_path / "canonical.md"
  md_file.write_text(
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nइषे᳓ त्वा।\n</details>\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n\n"
    "<details><summary>सायण-टीका</summary>\n\nतैत्तिरीयम्।\n\nद्वितीयम्।\n</details>\n"
    "<details><summary>सायण-टीका (काण्वी)</summary>\n\n"
    "प्रथम: ।\n\nद्वितीयः ।\n</details>\n"
    "</details>\n"
    '<div class="js_include" url="/some/path" newLevelForH1="2"><details><summary>सायण-टीका (काण्वी)</summary>\n\n'
    "अन्तः:\n\nमिरर् ।\n</details></div>\n",
    encoding="utf-8",
  )
  stats = vsk.clean_canonical_kanva_sayana_in_roots([tmp_path])
  assert stats == {"files_scanned": 1, "files_changed": 1, "blocks_changed": 1, "blocks_seen": 1}
  result = md_file.read_text(encoding="utf-8")
  assert "प्रथमः ।  \nद्वितीयः ।" in result
  assert "तैत्तिरीयम्।\n\nद्वितीयम्।" in result
  assert "अन्तः:\n\nमिरर् ।" in result
  assert result.count("<details") == result.count("</details>")


def test_proofread_canonical_kanva_sayana_in_roots_mocked(tmp_path, monkeypatch):
  from types import SimpleNamespace
  from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa import prose_clean

  md = tmp_path / "mantra.md"
  md.write_text(
    "<details open><summary>मूलम्</summary>\n\nअ᳓ग्ने न᳓य।\n</details>\n"
    "<details><summary>सायण-टीका (काण्वी)</summary>\n\nहे अने नय।\n</details>\n",
    encoding="utf-8",
  )

  class _FakeModels:
    def generate_content(self, *, model, contents, config):
      return SimpleNamespace(text="<<<ITEM 0>>>\nहे [[अने|अग्ने]] नय ।\n\nद्वितीयम् ।\n\nतृतीयम् ।\n<<<END 0>>>")

  monkeypatch.setattr(prose_clean, "_load_working_gemini_clients", lambda m, t: [("k1", SimpleNamespace(models=_FakeModels()))])
  ckpt = tmp_path / "ckpt.jsonl"
  st1 = prose_clean.proofread_canonical_kanva_sayana_in_roots([tmp_path], checkpoint_path=ckpt, max_workers=1)
  assert st1 == {"targets": 1, "already_done": 0, "newly_proofread": 1, "files_changed": 1, "blocks_changed": 1}
  txt = md.read_text(encoding="utf-8")
  assert "हे [[अने|अग्ने]] नय ।  \nद्वितीयम् ।  \nतृतीयम् ।" in txt
  assert "अ᳓ग्ने न᳓य।" in txt

  # Re-run uses JSONL checkpoint with zero extra API calls
  st2 = prose_clean.proofread_canonical_kanva_sayana_in_roots([tmp_path], checkpoint_path=ckpt, max_workers=1)
  assert st2["already_done"] == 1 and st2["newly_proofread"] == 0


def test_export_and_ingest_kanvi_shards(tmp_path):
  md = tmp_path / "mantra2.md"
  md.write_text(
    "<details open><summary>मूलम्</summary>\n\nदे᳓वः सविता᳓।\n</details>\n"
    "<details><summary>सायण-टीका (काण्वी)</summary>\n\nहे देवः सविता पच सेवने ।\n</details>\n"
    "<details><summary>सायण-टीका (काण्वी)</summary>\n\nस्पष्टम् ॥\n</details>\n"
    "<details><summary>सायण-टीका (काण्वी)</summary>\n\n\n</details>\n",
    encoding="utf-8",
  )
  ckpt = tmp_path / "ckpt.jsonl"
  shard_dir = tmp_path / "shards"
  shards = vsk.export_pending_kanvi_shards([tmp_path], ckpt, shard_dir, max_shard_chars=5000)
  assert len(shards) == 1
  content = shards[0].read_text(encoding="utf-8")
  assert "<<<ITEM 0>>>" in content and "दे᳓वः सविता᳓।" in content
  (shard_dir / "shard_00.out.txt").write_text(
    "<<<ITEM 0>>>\nहे देवः सविता [[पच|षच]] [[नरदष्टिः|[[नरदष्टिः|जरदष्टिः]]]] [[१० |]][[ ' | ]]सेवने ।\n<<<END 0>>>\n"
    "<<<ITEM 1>>>\nस्पष्टम् ॥\n<<<END 1>>>\n"
    "<<<ITEM 2>>>\n\n<<<END 2>>>\n",
    encoding="utf-8",
  )
  res = vsk.ingest_kanvi_shards_and_apply([tmp_path], shard_dir, ckpt, apply_to_files=True)
  assert res["done_total"] == 3 and res["missing"] == 0 and res["rejected_short"] == 0 and res["files_changed"] == 1
  out_txt = md.read_text(encoding="utf-8")
  assert "[[पच|षच]]" in out_txt and "[[नरदष्टिः|जरदष्टिः]]" in out_txt and "[[१०" not in out_txt and "[[ '" not in out_txt
  # Re-running ingestion after applying [[OLD|NEW]] suggestions is a clean no-op
  res2 = vsk.ingest_kanvi_shards_and_apply([tmp_path], shard_dir, ckpt, apply_to_files=True)
  assert res2["newly_ingested"] == 0 and res2["files_changed"] == 0
  assert md.read_text(encoding="utf-8") == out_txt


def test_clean_and_collect_inline_sayana_per_mantra_context(tmp_path):
  from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa import prose_clean

  md = tmp_path / "01.md"
  md.write_text(
    "## 01\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nइषे᳓ त्वा।\n</details>\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n"
    "<details><summary>मूलम्</summary>\n\nइषे त्वा।\n</details>\n"
    "<details><summary>सायण-टीका</summary>\n\nप्रथम: ।\n\nद्वितीयः ।\n</details>\n"
    "<details><summary>सायण-टीका (काण्वी)</summary>\n\nमा स्पृक्षः ।\n\nनानम् ।\n</details>\n"
    "</details>\n"
    "## 02\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nवाय᳓वः स्थ।\n</details>\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n"
    "<details><summary>मूलम्</summary>\n\nवायवः स्थ।\n</details>\n"
    "<details><summary>सायण-टीका</summary>\n\nतृतीय: ।\n\nचतुर्थः ।\n</details>\n"
    "</details>\n"
    '<div class="js_include" url="/some/shared" newLevelForH1="2"><details><summary>सायण-टीका</summary>\n\n'
    "अन्तः:\n\nमिरर् ।\n</details></div>\n",
    encoding="utf-8",
  )

  targets = prose_clean._collect_kanva_sayana_targets([tmp_path], summary_title="सायण-टीका")
  assert len(targets) == 2
  assert "इषे᳓ त्वा।" in targets[0]["ref_mantra"] and "वाय᳓वः स्थ।" not in targets[0]["ref_mantra"]
  assert "वाय᳓वः स्थ।" in targets[1]["ref_mantra"] and "इषे᳓ त्वा।" not in targets[1]["ref_mantra"]

  stats = prose_clean.clean_canonical_kanva_sayana_in_roots([tmp_path], summary_title="सायण-टीका")
  assert stats == {"files_scanned": 1, "files_changed": 1, "blocks_changed": 2, "blocks_seen": 2}
  out = md.read_text(encoding="utf-8")
  assert "प्रथमः ।  \nद्वितीयः ।" in out
  assert "तृतीयः ।  \nचतुर्थः ।" in out
  assert "मा स्पृक्षः ।\n\nनानम् ।" in out
  assert "अन्तः:\n\nमिरर् ।" in out


def test_forward_avatarika_context_anandabodha_clean_and_split_wf(tmp_path):
  from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa import prose_clean

  md = tmp_path / "host.md"
  md.write_text(
    "## 01\n"
    "<details><summary>सर्वा अवतारिकाः</summary>\n"
    "<details><summary>सायणः - विनियोगः</summary>\n\n"
    "सायणाचार्य- आनन्दबोध- माष्य-समेता\n\n"
    "इषे त्वा प्रथम: ।\n\nद्वितीयः ।\n\nमध्य\n\nअपूर्णम्।\n</details>\n</details>\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nइषे᳓ त्वा।\n</details>\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n"
    "<details><summary>मूलम् - काण्वम्</summary>\n\nइषे᳓ त्वा।\n</details>\n"
    "<details><summary>आनन्दबोध-टीका</summary>\n\n"
    "आनन्दबोध-अनन्ताचार्य - माष्य-समेता\n\n"
    "अन्तः:\n\n" + ("इदं व्याख्यानं दीर्घम् अस्ति।\n\n" * 15) +
    "</details>\n</details>\n"
    "## 02\n"
    "<details><summary>सर्वा अवतारिकाः</summary>\n"
    "<details><summary>सायणः - विनियोगः</summary>\n\nवायवः स्थ विनियोगः ।\n</details>\n</details>\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nवाय᳓वः स्थ।\n</details>\n",
    encoding="utf-8",
  )

  st_v = prose_clean.clean_canonical_kanva_sayana_in_roots([tmp_path], summary_title="सायणः - विनियोगः")
  st_a = prose_clean.clean_canonical_kanva_sayana_in_roots([tmp_path], summary_title="आनन्दबोध-टीका")
  assert st_v["blocks_changed"] == 1
  assert st_a["blocks_changed"] == 1
  cleaned_txt = md.read_text(encoding="utf-8")
  assert "सायणाचार्य-" not in cleaned_txt
  assert "आनन्दबोध-अनन्ताचार्य" not in cleaned_txt
  assert "प्रथमः ।  \nद्वितीयः ।  \nमध्य अपूर्णम्।" in cleaned_txt

  # Check forward-looking context in सर्वा अवतारिकाः for both sections
  t_vin = prose_clean._collect_kanva_sayana_targets([tmp_path], summary_title="सायणः - विनियोगः")
  assert len(t_vin) == 2
  assert "इषे᳓ त्वा।" in t_vin[0]["ref_mantra"] and "वाय᳓वः स्थ।" not in t_vin[0]["ref_mantra"]
  assert "वाय᳓वः स्थ।" in t_vin[1]["ref_mantra"]

  # Check workflow export + split + ingest roundtrip on oversized Ānandabodha item
  batches_p = tmp_path / "batches.json"
  split_p = tmp_path / "split.json"
  ckpt_p = tmp_path / "ckpt.jsonl"
  out_dir = tmp_path / "out"
  out_dir.mkdir()
  exp_st = prose_clean.export_workflow_batches(
    [tmp_path], ckpt_p, batches_p, summary_title="आनन्दबोध-टीका", max_batch_chars=250, max_item_chars=200, split_map_path=split_p
  )
  assert exp_st["split_items"] == 1 and exp_st["work_units"] >= 2
  import json
  batches = json.loads(batches_p.read_text(encoding="utf-8"))
  for b_i, batch in enumerate(batches):
    lines = [f"<<<ITEM {u['id']}>>>\n{u['raw']}\n<<<END {u['id']}>>>" for u in batch]
    (out_dir / f"shard_wf_{b_i:03d}.out.txt").write_text("\n\n".join(lines), encoding="utf-8")
  ing_st = prose_clean.ingest_workflow_outputs(
    [tmp_path], out_dir, ckpt_p, summary_title="आनन्दबोध-टीका", split_map_path=split_p, apply_to_files=True
  )
  assert ing_st["done_total"] == 1 and ing_st["missing"] == 0

  abbrev_cleaned = prose_clean.clean_kanva_sayana_block("तत्र श० ब्रा० १०.१.२ (का० ४।२।९) पा० ६.१।")
  assert abbrev_cleaned == "तत्र श॰ ब्रा॰ १०.१.२ (का॰ ४।२।९) पा॰ ६.१।"
  assert prose_clean._postprocess_proofread_output("पा० १", "पा० १") == "पा॰ १"

  pref_wrap = tmp_path / "caller_incl.md"
  pref_wrap.write_text(
    "+++\ntitle = \"०१\"\n+++\n\n"
    "<div class=\"js_include\" url=\"/static/a.md\">\n\n"
    "<details><summary>महीधर-टीका</summary>\n\nपा० १.१।\n</details>\n</div>\n"
    "<details><summary>महीधर-टीका</summary>\n\nनिघ० ३.४। १०।\n</details>\n",
    encoding="utf-8",
  )
  ab_res = prose_clean.normalize_abbreviations_in_roots([tmp_path], dry_run=False)
  assert ab_res["files_changed"] >= 1
  pw_txt = pref_wrap.read_text(encoding="utf-8")
  assert "निघ॰ ३.४। १०।" in pw_txt
  assert "पा० १.१।" in pw_txt  # skipped prefilled js_include div!

  long_para = "  \n".join(f"वाक्यम् {i}।" for i in range(10))
  sp_chunks = prose_clean.split_text_for_llm(long_para, max_chars=45)
  assert len(sp_chunks) >= 2 and all("\n\n" not in c for c in sp_chunks)

  rel = prose_clean._collapse_relapsed_single_sentence_breaks("[[श्रुतेः|श्रुतेः।]]\n\nतत्र।")
  assert rel == "[[श्रुतेः|श्रुतेः।]]  \nतत्र।"
  pp = prose_clean._postprocess_proofread_output("’ क", "[[’ |]]क |।")
  assert pp == "क ।", f"unexpected pp={pp!r}"
  assert prose_clean._postprocess_proofread_output("अत्र।", "[[अत्र।|तत्र।]]") == "[[अत्र।|तत्र।]]"





