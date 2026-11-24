import textwrap

import pytest

from doc_curation.sanskrit.accent.samhita_splitter import (
  banded_monotonic_align,
  count_inline_sandhi,
  cut_text_to_slices,
  dependent_to_us_preserving,
  extract_padapatha_words,
  hyphenate_samhita_with_padapatha,
  normalize_mAdhyandina_markdown,
  parse_pada_groups,
  parse_samhita_section,
  partition_padapatha_dp,
  render_interleaved_samhita_section,
  resolve_mula_seams,
  resolve_pausa_word_end,
  resolve_seam_boundaries,
  slice_mula_verbatim,
  split_aksharas,
  strip_vedic_accents,
  validate_samhita_markdown,
  validate_samhita_section,
)


def test_split_aksharas_and_preserving_us_conversion():
  aks = split_aksharas("इ॒षे त्वो॒र्जे त्वा॑")
  assert aks[0] == "इ॒"
  assert "र्जे" in aks
  assert "त्वा॑" in aks

  # Pre-existing ᳙ / ᳓ must survive dependent -> US conversion alongside classical marks
  mixed = "स्व᳙रभिवि॒ख्येषम्"
  us = dependent_to_us_preserving(mixed)
  assert "स्व᳙" in us
  assert "᳓" in us


@pytest.mark.parametrize(
  "vp_w,pada_w,expected",
  [
    ("प्रथितं", "प्रथितम्", "प्रथितम्"),
    ("देवा᳓ँश्", "देवान्", "देवा᳓न्"),
    ("पङ्क्ति᳓श्", "पङ्क्तिः", "पङ्क्ति᳓ः"),
    ("त्रिवृ᳓द्", "त्रिवृत्", "त्रिवृ᳓त्"),
    ("सुविद᳓त्रो", "सुविदत्रः", "सुविद᳓त्रः"),
    ("जुषाणा᳓ऽ", "जुषाणा", "जुषाणा᳓"),
    ("नमतामदऽ", "नमतामदः", "नमतामदः"),
    ("अस्य", "अस्ति", "अस्य"),
  ],
)
def test_resolve_pausa_word_end(vp_w, pada_w, expected):
  assert resolve_pausa_word_end(vp_w, pada_w) == expected


def test_extract_padapatha_words_guards_iti_and_avagraha():
  pada = (
    "इ॒षे। त्वा॒। ऊ॒र्ज्जे। वि॒ज्ञा॒ता॒येति॑ वि॒ऽज्ञा॒ता॒य। "
    "अ॒दि॒त्यै। अ॒ति॒ऽइ॒त्व॒रीम्। अपा॑ने॒नेत्य॑पऽआ॒नेन॑।"
  )
  words = extract_padapatha_words(pada)
  bare_words = [strip_vedic_accents(w) for w in words]
  assert "इषे" in bare_words
  assert "वि॒ऽज्ञा॒ता॒य" not in words  # ऽ stripped -> विज्ञाताय
  assert any("विज्ञाताय" in w for w in bare_words)
  assert any("अदित्यै" in w for w in bare_words)
  assert any("अतिइत्वरीम्" in w for w in bare_words)
  assert any("अपानेन" in w for w in bare_words)


def test_banded_monotonic_align_prevents_refrain_jump():
  # Identical repeated clauses separated along the diagonal should align monotonically
  source = "pracyaidisesvahapraticyaidisesvahaudicyaidisesvaha"
  target = "pracyaidisesvahapraticyaidisesvahaudicyaidisesvaha"
  j_to_i = banded_monotonic_align(source, target, band=16)
  assert j_to_i is not None
  assert j_to_i == list(range(len(target) + 1))


def test_seam_aware_splitting_ishe_tvorje_vp_and_mulam():
  # Regression guard: 'त्वोर्जे' split must become 'त्वा | ऊर्जे', never 'त्वो | र्जे'
  vp_full = "इषे᳓ त्वोर्जे᳓ त्वा वाय᳓व स्थ"
  hmul = "इ॒षे त्वो॒र्जे त्वा॑ वा॒यव॑ स्थ"
  hpada = "इ॒षे। त्वा॒। ऊ॒र्ज्जे। त्वा॒। वा॒यवः॑। स्थ॒। १।"
  ind_iast = "iṣé tvā ūrjé tvā vāyáva stha"
  target_vps = ["इषे᳓ त्वा", "ऊर्जे᳓ त्वा", "वाय᳓व स्थ"]

  raw_slices, cut_pos, _ = cut_text_to_slices(vp_full, target_vps)
  vps, logs = resolve_seam_boundaries(raw_slices, vp_full, cut_pos, hpada, ind_iast)
  assert vps == ["इषे᳓ त्वा", "ऊर्जे᳓ त्वा", "वाय᳓व स्थ"]
  assert any(kind == "FUSED" for _, _, kind in logs)

  muls = resolve_mula_seams(hmul, raw_slices, vps, hpada, ind_iast)
  assert muls == ["इ॒षे त्वा॑", "ऊ॒र्जे त्वा॑", "वा॒यव॑ स्थ"]
  assert all(not m.startswith("र्जे") for m in muls)

  padas, flags = partition_padapatha_dp(hpada, vps)
  assert flags == []
  assert padas is not None
  assert len(padas) == 3
  assert "ऊ॒र्ज्जे।" in padas[1]


def test_seam_aware_avagraha_and_sha_cha_restoration():
  vp_full = "श᳓र्मासि प्रथमे᳓ऽहन्"
  hmul = "शर्मा॑सि प्रथ॒मेऽह॑न्"
  hpada = "शर्म॑। अ॒सि॒। प्र॒थ॒मे। अह॑न्।"
  ind_iast = "śármāsi prathamé áhan"
  target = ["श᳓र्मा", "अ᳓सि", "प्रथमे᳓", "अहन्"]

  raw_slices, cut_pos, _ = cut_text_to_slices(vp_full, target)
  vps, _ = resolve_seam_boundaries(raw_slices, vp_full, cut_pos, hpada, ind_iast)
  assert vps[0] == "श᳓र्म" or vps[0].startswith("श")
  assert not any(v.startswith("ऽ") for v in vps)

  muls = resolve_mula_seams(hmul, raw_slices, vps, hpada, ind_iast)
  assert muls[3].startswith("अ")
  assert not any(m.startswith("ऽ") for m in muls)


def test_parse_render_and_validate_unsplit_and_interleaved():
  unsplit = textwrap.dedent("""\
    ## ०१ इषे त्वोर्जे
    <details open><summary>विश्वास-प्रस्तुतिः</summary>

    इषे᳓ त्वोर्जे᳓ त्वा
    </details>

    <details open><summary>विश्वास-प्रस्तुतिः</summary>

    वाय᳓व स्थ
    </details>

    <details><summary>सर्वाष् टीकाः</summary>
    <details><summary>Griffith</summary>

    THEE for food. Thee for vigour. Ye are breezes.
    </details>

    <details><summary>मूलम्</summary>

    इ॒षे त्वो॒र्जे त्वा॑ वा॒यव॑ स्थ
    </details>

    <details><summary>पदपाठः - दयानन्दादि</summary>

    इ॒षे। त्वा॒। ऊ॒र्ज्जे। त्वा॒। वा॒यवः॑। स्थ॒।
    </details>
    <details><summary>महीधरः</summary>

    म० व्याख्यानम् ॥
    </details>
    </details>
  """)
  parsed_orig = parse_samhita_section(unsplit)
  assert parsed_orig.head_full == "इषे᳓ त्वोर्जे᳓ त्वा वाय᳓व स्थ"
  assert len(parsed_orig.residual_blocks) == 1

  raw_slices, cut_pos, _ = cut_text_to_slices(parsed_orig.head_full, ["इषे᳓ त्वा", "ऊर्जे᳓ त्वा", "वाय᳓व स्थ"])
  vps, _ = resolve_seam_boundaries(raw_slices, parsed_orig.head_full, cut_pos, parsed_orig.pada_full)
  muls = resolve_mula_seams(parsed_orig.mula_full, raw_slices, vps, parsed_orig.pada_full)
  padas, _ = partition_padapatha_dp(parsed_orig.pada_full, vps)
  grs = ["THEE for food.", "Thee for vigour.", "Ye are breezes."]

  rendered = render_interleaved_samhita_section(
    parsed_orig.heading, vps, grs, muls, padas, parsed_orig.residual_blocks
  )
  assert validate_samhita_section(rendered, "01.01", original_section=unsplit) == []

  # Re-parsing an already-interleaved section preserves all fields identically
  re_parsed = parse_samhita_section(rendered)
  assert re_parsed.vps == vps
  assert re_parsed.mulas == muls
  assert re_parsed.residual_blocks == parsed_orig.residual_blocks

  # Broken seam (like leading र्जे or leading ऽ or inline sandhi regression) is caught
  bad_sec = rendered.replace("ऊ॒र्जे त्वा॑", "र्जे त्वा॑")
  issues = validate_samhita_section(bad_sec, "01.01", original_section=unsplit)
  assert any(i.kind == "repha_start_mula" for i in issues)

  bad_avagraha = rendered.replace("ऊ॒र्जे त्वा॑", "ऽऊर्जे त्वा॑")
  issues2 = validate_samhita_section(bad_avagraha, "01.01", original_section=unsplit)
  assert any(i.kind == "bad_start_mula" for i in issues2)


def test_validate_samhita_markdown_preserves_js_include_and_groups():
  doc_orig = textwrap.dedent("""\
    +++
    title = "०१"
    +++

    ## ०१ मन्त्रः
    <details open><summary>विश्वास-प्रस्तुतिः</summary>

    वा᳓यव स्थ
    </details>

    <details><summary>सर्वाष् टीकाः</summary>
    <details><summary>Griffith</summary>

    Ye are breezes.
    </details>

    <details><summary>मूलम्</summary>

    वा॒यव॑ स्थ
    </details>

    <details><summary>पदपाठः - दयानन्दादि</summary>

    वा॒यवः॑। स्थ॒।
    </details>
    </details>

    ## ०२ ऋक्
    <div class="js_include" url="/foo/bar.md">
    <details open><summary><h3>विश्वास-प्रस्तुतिः</h3></summary>
    foo
    </details>
    </div>
  """)
  rendered_sec1 = render_interleaved_samhita_section(
    "## ०१ मन्त्रः", ["वा᳓यव स्थ"], ["Ye are breezes."], ["वा॒यव॑ स्थ"], ["वा॒यवः॑। स्थ॒।"]
  )
  # Reconstruct cleanly from original section 2
  sec2 = "## ०२ ऋक्" + doc_orig.split("## ०२ ऋक्", 1)[1]
  doc_rebuilt = "+++\ntitle = \"०१\"\n+++\n\n" + rendered_sec1 + sec2
  assert validate_samhita_markdown(doc_rebuilt, original_md_text=doc_orig, doc_id="01") == []

  # Altering a js_include section fails validation
  doc_bad_inc = doc_rebuilt.replace("foo\n", "bar\n")
  issues = validate_samhita_markdown(doc_bad_inc, original_md_text=doc_orig, doc_id="01")
  assert any(i.kind == "js_include_altered" for i in issues)

  # Verbatim slicing keeps concatenated text lossless and pada group parsing merges iti analyses
  v_slices, _ = slice_mula_verbatim("अ॒ग्नये॒ स्वाहा॒ सोमा॑य॒ स्वाहा॑", ["अग्न᳓ये स्वा᳓हा", "सो᳓माय स्वा᳓हा"])
  assert len(v_slices) == 2
  assert parse_pada_groups("प्रजाव॑ती॒रिति॑। प्र॒जाऽव॑तीः। कर्म्म॑णे।") == [
    "प्रजाव॑ती॒रिति॑। प्र॒जाऽव॑तीः।",
    "कर्म्म॑णे।",
  ]
  assert parse_pada_groups("सु॒ते। सु॒तऽइति॑ सु॒ते।") == [
    "सु॒ते। सु॒तऽइति॑ सु॒ते।",
  ]
  assert count_inline_sandhi(["ताम् गच्छ", "तद् त्वा", "सा असि"]) == {"ma_hal": 1, "ta_hal": 1, "hiatus": 1}

  # Visarga restoration places 'ः' before trailing US accent marks
  assert resolve_pausa_word_end("पञ्चदशो᳓", "पञ्चदशः") == "पञ्चदशः᳓"
  assert resolve_pausa_word_end("पञ्चविँश᳓ऽ", "पञ्चविँशः") == "पञ्चविँशः᳓"


def test_padapatha_guided_hyphenation_and_markdown_normalization():
  # Padapatha guard fixes mid-word cuts and enforces space vs '-'
  assert (
    hyphenate_samhita_with_padapatha(
      "सजू᳓र्व᳓सुभिः ध्रुव᳓योनिर्ध्रुवा᳓सि",
      "स॒जूः। वसु॑ऽभिः। ध्रु॒वऽयो॑निः। ध्रु॒वा। अ॒सि॒।",
    )
    == "सजू᳓र् व᳓सुभिः ध्रुव᳓-योनिर् ध्रुवा᳓सि"
  )
  assert (
    hyphenate_samhita_with_padapatha(
      "ब्रह्मराजन्या᳙भ्याँ स᳓न्नते देवो᳓ऽनभिशस्त्यभिशस्तिपा᳙",
      "ब्र॒ह्म॒रा॒ज॒न्या॒ऽभ्या॒मिति॑ ब्रह्मऽराजन्याभ्याम्। सम्ऽन॑ते। दे॒वः। अ॒न॒भि॒श॒स्तीत्यन॑भिऽशस्ति। अ॒भि॒श॒स्ति॒पा इत्य॑भिऽशस्तिपाः।",
    )
    == "ब्रह्म-राजन्या᳙भ्याँ स᳓न्नते देवो᳓ ऽनभिशस्त्य् अभिशस्तिपाः᳙"
  )
  # Regressions: no false repha/stop splits and restore VPr 3.15 / nasal / stop seams
  assert (
    hyphenate_samhita_with_padapatha("मख᳓स्य शि᳓रो ऽसि", "म॒खस्य॑। शि॒रः। अ॒सि॒।")
    == "मख᳓स्य शि᳓रो ऽसि"
  )
  assert (
    hyphenate_samhita_with_padapatha("त᳓च् छुन्धामि", "तत्। शु॒न्धा॒मि॒।")
    == "त᳓च् छुन्धामि"
  )
  assert (
    hyphenate_samhita_with_padapatha("मनुष्या᳙न्त् सह᳓", "म॒नु॒ष्या॑न्। स॒ह।")
    == "मनुष्या᳙न्त् सह᳓"
  )
  assert (
    hyphenate_samhita_with_padapatha("य᳓च् छूद्रे᳓", "यत्। शू॒द्रे।")
    == "य᳓च् छूद्रे᳓"
  )
  assert (
    hyphenate_samhita_with_padapatha("मा᳓ व स्तेन᳓ ईशत", "मा। वः॒। स्ते॒नः। ई॒श॒त॒।")
    == "मा᳓ वः स्तेन᳓ ईशत"
  )
  assert (
    hyphenate_samhita_with_padapatha("नि᳓ष्टप्तँर᳓क्षो अ᳓हिँसन्नः", "निःऽत॑प्तम्। रक्षः॑। अहिँ॑सन्। नः॒।")
    == "नि᳓ष्टप्तँ र᳓क्षो अ᳓हिँसन् नः"
  )
  assert (
    hyphenate_samhita_with_padapatha(
      "शिति-र᳓न्ध्रो ऽन्य᳓तःशितिरन्ध्रः",
      "शि॒ति॒ऽरन्ध्रः। अ॒न्यतः॑ऽशितिरन्ध्रः।",
    )
    == "शिति-र᳓न्ध्रो ऽन्य᳓तः-शितिरन्ध्रः"
  )
  assert (
    hyphenate_samhita_with_padapatha("अमु᳓ष्मिँल्लोके᳓", "अमुष्मि॑न्। लो॒के।")
    == "अमु᳓ष्मिँल् लोके᳓"
  )
  assert (
    hyphenate_samhita_with_padapatha(
      "कृ᳓ष्णोऽस्याखरेष्ठो᳙ऽग्न᳓ये",
      "कृ॒ष्णः। अ॒सि॒। आ॒ख॒रे॒ऽस्थः। अ॒ग्नये॑।",
    )
    == "कृ᳓ष्णो ऽस्य् आखरे-ष्ठो᳙ ऽग्न᳓ये"
  )
  assert (
    hyphenate_samhita_with_padapatha(
      "त्वाऽन्तरिक्षस᳓दं",
      "त्वा॒। अ॒न्त॒रि॒क्ष॒ऽसद॑म्।",
    )
    == "त्वा ऽन्तरिक्ष-स᳓दं"
  )
  assert (
    hyphenate_samhita_with_padapatha(
      "य᳓त्कामः शम्भवा᳓य य᳓द᳓त्ति",
      "यत्ऽका॑मः। शम्ऽभ॑वाय। यत्। अ॒त्ति॒।",
    )
    == "य᳓त्-कामः शम्-भवा᳓य य᳓द᳓त्ति"
  )
  assert (
    hyphenate_samhita_with_padapatha(
      "प्रजा᳓वतीर् अनमीवा᳓ अयक्ष्मा᳓ मा᳓ व स्तेन᳓ ईशत मा᳓घ᳓शँसः",
      "प्र॒जाऽव॑तीः। अ॒न॒मी॒वाः। अ॒य॒क्ष्माः। मा। वः॒। स्ते॒नः। ई॒श॒त॒। मा अ॒घशँ॑सः।",
    )
    == "प्रजा᳓वतीर् अनमीवा᳓ अयक्ष्मा᳓ मा᳓ वः स्तेन᳓ ईशत मा᳓घ᳓शँसः"
  )
  assert (
    hyphenate_samhita_with_padapatha(
      "नि᳓ष्टप्तँर᳓क्षो वे᳓र्होत्रं᳓ मनुष्या᳙नु᳓दजयतां अ᳓हिँसन्नः",
      "निःऽत॑प्तम्। रक्षः॑। वेः। होत्र॑म्। म॒नु॒ष्यान्। उत्। अ॒ज॒य॒ता॒म्। अहिँ॑सन्। नः॒।",
    )
    == "नि᳓ष्टप्तँ र᳓क्षो वे᳓र् होत्रं᳓ मनुष्या᳙न् उ᳓दजयतां अ᳓हिँसन् नः"
  )

  md = textwrap.dedent("""\
    +++
    title = "०१"
    +++

    ## ०१ आवहनम्
    <details open><summary>विश्वास-प्रस्तुतिः</summary>

    आ᳓प्यायध्वमघ्न्याऽइ᳓न्द्राय बह्वी᳓ः भागं᳓
    </details>

    <details><summary>सर्वाष् टीकाः</summary>
    <details><summary>Griffith</summary>

    Swell his share for Indra.
    </details>

    <details><summary>मूलम्</summary>

    आप्या॑यध्वमघ्न्या॒ऽइन्द्रा॑य भा॒गं
    </details>

    <details><summary>पदपाठः - दयानन्दादि</summary>

    आ। प्या॒य॒ध्व॒म्। अ॒घ्न्याः॒। इन्द्रा॑य। ब॒ह्वीः। भा॒गं।
    </details>
    </details>
  """)
  out = normalize_mAdhyandina_markdown(md, hyphenate_vp=True)
  assert "आ᳓प्यायध्वम् अघ्न्या इ᳓न्द्राय बह्वीः᳓ भाग᳓म्" in out
  assert "आप्या॑यध्वमघ्न्या॒ऽइन्द्रा॑य भा॒गम्" in out
  assert "आ। प्या॒य॒ध्व॒म्। अ॒घ्न्याः॒। इन्द्रा॑य। ब॒ह्वीः। भा॒गम्।" in out
