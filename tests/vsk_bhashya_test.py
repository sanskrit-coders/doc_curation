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


