from doc_curation.sanskrit.accent.validator import (
  check_padapatha_header,
  find_bad_gati_kta_purvapadas,
  find_false_nighata_arrows,
  find_false_post_udatta_svarita_arrows,
  find_malformed_arrows,
  find_unexplained_aa_hiatuses,
  find_unlicensed_unaccented_padas,
  find_unresolved_question_arrows,
  find_unsplit_upasarga_tinantas,
  find_virama_matra_glitches,
  find_vp_integrity_issues,
  validate_accented_markdown,
  validate_padapatha_block,
  validate_paired_vp_and_tk,
)


def test_check_padapatha_header():
  body_ok = "- त᳓त् (*TS*)\n- एव᳓ → **ए᳓व** (*TS*)\n"
  assert check_padapatha_header("पद-पाठः (यान्त्रिकः - 1/2 व्यत्यस्त-स्वराः)", body_ok) is None
  assert check_padapatha_header("पद-पाठः (यान्त्रिकः - 0/2 व्यत्यस्त-स्वराः)", body_ok) is not None
  body_zero = "- त᳓त् (*TS*)\n- एव᳓ (*TS*)\n"
  assert check_padapatha_header("पद-पाठः (यान्त्रिकः)", body_zero) is None
  assert check_padapatha_header("पद-पाठः (यान्त्रिकः - 0/2 व्यत्यस्त-स्वराः)", body_zero) is not None


def test_find_virama_matra_glitches():
  assert find_virama_matra_glitches(["- सव्ँ (*TS*)", "- शय्ँ (*TB*)"]) == []
  glitches = find_virama_matra_glitches([
    "- कृत्ा (*MW*)",
    "- युयोतन+ → **युयो᳓तन+** (*RV*)",
    "- दर्,शत᳓म् (*TS*)",
  ])
  assert len(glitches) == 3


def test_find_false_post_udatta_svarita_arrows():
  mula = "पर॒मे व्यो॑मन्न् ॥"
  # Classical ॑ on व्यो immediately follows udātta मे, so व्योमन्न् → **व्यो᳙मन्न्** is false-vyatyasta
  false_hits = find_false_post_udatta_svarita_arrows(["- व्योमन्न् → **व्यो᳙मन्न्** (*TS*)"], mula)
  assert len(false_hits) == 1
  # Clean bullet without arrow is valid
  assert find_false_post_udatta_svarita_arrows(["- व्यो᳙मन्न् (*TS*)"], mula) == []


def test_find_unexplained_aa_hiatuses():
  bad = find_unexplained_aa_hiatuses(["- आ (*TS*)", "- इद᳓म् (*TS*)"], "आ इ॒दम्")
  assert len(bad) == 1
  # Explicit daṇḍa or verified prakṛtibhāva pairs are permitted
  assert find_unexplained_aa_hiatuses(["- आ (*TS*)", "- इद᳓म् (*TS*)"], "आ । इ॒दम्") == []
  assert find_unexplained_aa_hiatuses(["- सप्त᳓ (*TS*)", "- इमे᳓ (*TS*)"], "स॒प्त इ॒मे") == []


def test_find_vp_integrity_issues():
  assert find_vp_integrity_issues("**[[ये᳓नावृत᳓ङ्|ये᳓ना᳓वृतङ्]]**[[12]]") == []
  bad_vv = find_vp_integrity_issues("स्अग्निर्")
  assert any("virama_vowel" in x for x in bad_vv)
  bad_br = find_vp_integrity_issues("[[अग्नि|अ᳓ग्नि")
  assert any("unbalanced_brackets" in x for x in bad_br)


def test_validate_accented_markdown_and_paired():
  clean_md = (
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "स᳓ इद᳓म् ॥\n</details>\n"
    "<details><summary>मूलम्</summary>\n\n"
    "स इ॒दम् ॥\n</details>\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- सः᳓ (*TS*)\n- इद᳓म् (*TS*)\n</details>\n"
  )
  assert validate_accented_markdown(clean_md) == []

  bad_tags = clean_md + "<details>"
  assert any(iss.kind == "tag_unbalanced" for iss in validate_accented_markdown(bad_tags))

  issues_pair = validate_paired_vp_and_tk("+++\ntitle=\"x\"\n+++\n[[bad|x\n", clean_md)
  assert any(iss.kind == "vp_integrity" for iss in issues_pair)


def test_zero_accent_unresolved_and_upasarga_tinanta_guards():
  assert find_unresolved_question_arrows(["- उ᳓पासितव्य᳓म् → **?** (अनेकोदात्त-दोषः)"]) != []
  assert find_unresolved_question_arrows(["- उ᳓पासितव्य᳓म् → **उप-आसितव्य᳙म्** (पा॰ ३.१.९६)"]) == []

  # Catches zero-accent nominals/compounds like प्रसूती without पा॰ ८.१.* / २.४.* license
  assert find_unlicensed_unaccented_padas([
    "- प्रसूती (आरण्यक-पाठः (अनाम्नातम्))",
    "- दन्तिः (पा॰ ६.१.१९९ — भास्करः)",
    "- महा-ज्ञेयम् (महा᳓ (*MW*), समासस्वरः)",
  ]) != []
  assert len(find_unlicensed_unaccented_padas([
    "- प्रसूती (आरण्यक-पाठः (अनाम्नातम्))",
    "- दन्तिः (पा॰ ६.१.१९९ — भास्करः)",
    "- महा-ज्ञेयम् (महा᳓ (*MW*), समासस्वरः)",
  ])) == 3

  # Licensed anudāttas pass cleanly
  assert find_unlicensed_unaccented_padas([
    "- च (अनुदात्तम्, पा॰ ८.१.१८, *TS*, *RV*)",
    "- विद्यते (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *RV*)",
    "- अग्ने (आमन्त्रितम् अनुदात्तम्, पा॰ ८.१.१९)",
    "- अस्य (अनुदात्तम्, पा॰ २.४.३२, *TS*, *RV*)",
    "- शान्तिः (द्विर्वचने परस्यानुदात्तत्वम्, पा॰ ८.१.३)",
    "- भूः (*TS*)",
  ]) == []

  # Catches unsplit upasarga + tiṅanta or misclassified nominal under पा॰ ८.१.२८
  assert find_unsplit_upasarga_tinantas([
    "- प्रदुघे (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- प्रसूती (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- सं-तापयति (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
  ]) != []
  assert len(find_unsplit_upasarga_tinantas([
    "- प्रदुघे (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- प्रसूती (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- सं-तापयति (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- प्रचोद᳓यात् (*TS*, *RV*; *TS*, *RV*, *TB*)",
    "- ऐतु (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- स᳓ञ्चरेमहि → **सञ्चरेमहि** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- स᳓मगन्महि (*EK* मूल-पाठः)",
    "- उ᳓च्छेषि → **उच्छेषि** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- व्यू᳓हध्वम् → **व्यूहध्वम्** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- युयोतन → **युयो᳓तन** (*RV*)",
    "- दधातन → **द᳓धातन** (*RV*)",
  ])) == 11
  # Non-jātya svaritas in padapāṭha are caught, while genuine jātya svaritas pass
  from doc_curation.sanskrit.accent.validator import find_multi_udatta_padas
  assert find_multi_udatta_padas(["- बा᳓धते → **बा᳙धते** (पा॰ ८.१.६६)", "- ए᳙व (*TB*)"]) != []
  assert find_multi_udatta_padas(["- स्वः᳙ (*TS*)", "- मनुष्याः᳙ (*TS*)", "- नद्यः᳙ (*TS*)"]) == []
  # Subordinate-clause पा॰ ८.१.६६ / ८.१.७१ verbs pass cleanly
  assert find_unsplit_upasarga_tinantas([
    "- प्र-चोद᳓यात् (यद्वृत्तान्नित्यम् पा॰ ८.१.६६, तिङि चोदात्तवति पा॰ ८.१.७१)",
  ]) == []
  # Simplex verbs starting with अ-/आ-/वि- and 1st-pl -मः pass cleanly
  assert find_unsplit_upasarga_tinantas([
    "- विद्यते (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *RV*)",
    "- अभवत् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *TS*)",
    "- आनशुः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *RV*)",
    "- आसीत (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अप्राः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *TS*, *RV*)",
    "- विशेत् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- स्मः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- ख्यास्यामः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- वह (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अवृत्रन् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अवादिषुः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अस्य (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
  ]) == []
  # Genuine vyatyasta svarita (e.g. tavyat) where ar carries wrong udāttas is NOT flagged as false_svarita_arrow
  assert find_false_post_udatta_svarita_arrows(
    ["- प्र᳓-मदितव्य᳓म् → **प्र-मदितव्य᳙म्** (तव्यत् पा॰ ३.१.९६, ६.१.१८५)"],
    "सत्यान् न प्रम॑दित॒व्यम् ।",
  ) == []

  issues = validate_padapatha_block(
    "पद-पाठः (यान्त्रिकः)",
    "- प्रसूती (आरण्यक-पाठः (अनाम्नातम्))\n",
  )
  assert any(i.kind == "unlicensed_anudatta" for i in issues)


def test_sanskrit_package_reexports():
  import doc_curation.sanskrit as ds
  import doc_curation.sanskrit.accent as dsa
  for sym in dsa.__all__:
    assert hasattr(ds, sym), f"Missing {sym} in doc_curation.sanskrit"


def test_gati_kta_purvapada_and_false_nighata_guards():
  # 1. Gati+kta pūrvapada in bahuvrīhi (पा॰ ६.२.४९ गतिरनन्तरः + ६.२.१)
  assert len(find_bad_gati_kta_purvapadas([
    "- सङ्गत-उपस्थौ → **सङ्गत᳓-उपस्थौ** (बहुव्रीहौ पा॰ ६.२.१)",
  ])) == 1
  assert find_bad_gati_kta_purvapadas([
    "- सङ्गत-उपस्थौ → **स᳓ङ्गत-उपस्थौ** (गतिरनन्तरः पा॰ ६.२.४९, बहुव्रीहौ पा॰ ६.२.१)",
    "- मुक्त-किल्बि᳓षः᳓ → **मुक्त᳓-किल्बिषः** (बहुव्रीहौ पा॰ ६.२.१)",
    "- वि᳓शीर्ष्णी᳓म् → **वि-शीर्ष्णी᳓म्** (प्रादिबहुव्रीहौ पा॰ ६.२.१७७)",
  ]) == []

  # 2. Malformed double arrows
  assert len(find_malformed_arrows([
    "- श᳓म्-त᳓मा → **श᳓म्-तमा** (*TS*) → **श᳓न्तमः** (पा॰ ६.१.१५८)",
  ])) == 1

  # 3. False पा॰ ८.१.२८ / ८.१.१९ nighāta arrows:
  # (a) Unmarked 8-syllable anuṣṭubh pāda d (स᳓हस्व) while pāda c's तिष्ठ after अभि᳓ is NOT flagged
  mula_ashma = "आति॑ष्ठे॒ममश्मा॑न॒मश्मे॑व॒ त्वँ स्थि॒रा भ॑व ।\nअ॒भिति॑ष्ठ पृतन्य॒तस्सह॑स्व पृतनाय॒तः ।"
  pp_ashma = [
    "- आ᳓ (*TS*)",
    "- तिष्ठ (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- इम᳓म् (*TS*)",
    "- अ᳓श्मानम् (*TS*)",
    "- अ᳓श्मा (*TS*)",
    "- इव (अनुदात्तम्, पा॰ ८.१.१८)",
    "- त्व᳓म् (*TS*)",
    "- स्थिरा᳓ (*TS*)",
    "- भव (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अभि᳓ (*TS*)",
    "- तिष्ठ (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- पृतन्यतः᳓ (*TS*)",
    "- स᳓हस्व → **सहस्व** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- पृतनायतः᳓ (*TS*)",
  ]
  assert len(find_false_nighata_arrows(pp_ashma, mula_ashma)) == 1
  assert "सहस्व" in find_false_nighata_arrows(pp_ashma, mula_ashma)[0]

  # (b) Mantra-initial (#0), after पादादि-आमन्त्रित (८.१.७२), after तिङ् (अतिङः), चवायोगे (८.१.५९), and यद्वृत्त (८.१.६६)
  assert len(find_false_nighata_arrows(["- अ᳓पश्यम् → **अपश्यम्** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)"])) == 1
  assert len(find_false_nighata_arrows([
    "- अ᳓ग्ने (आमन्त्रितम् आद्युदात्तम्, पा॰ ६.१.१९८)",
    "- न᳓य → **नय** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
  ])) == 1
  assert len(find_false_nighata_arrows([
    "- स᳓म् (*TS*)",
    "- एत (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- प᳓श्यत → **पश्यत** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
  ])) == 1
  assert len(find_false_nighata_arrows([
    "- त᳓या (*TS*)",
    "- व᳓र्धस्व → **वर्धस्व** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- च (अनुदात्तम्, पा॰ ८.१.१८)",
    "- आ᳓ (*TS*)",
    "- प्यायस्व (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- च (अनुदात्तम्, पा॰ ८.१.१८)",
  ])) == 1
  assert len(find_false_nighata_arrows([
    "- या᳓साम् (*TS*)",
    "- रा᳓जा (*TS*)",
    "- व᳓रुणः (*TS*)",
    "- या᳓ति → **याति** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
  ])) == 1
  # Non-initial vocative after a finite verb (८.१.१९ has NO अतिङः) is valid and NOT flagged
  assert find_false_nighata_arrows([
    "- यम᳓म् (*TS*)",
    "- गाय (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- भङ्ग्य-श्र᳓वः → **भङ्ग्य-श्रवः** (आमन्त्रितम् अनुदात्तम्, पा॰ ८.१.१९)",
  ]) == []


def test_suspect_homograph_accents_and_parasavarna_ablatives():
  from doc_curation.sanskrit.accent.validator import find_suspect_homograph_accents

  bad = [
    "- वे᳓द᳓म् → **वेद᳓म्** (*TS* वेदः᳓, घञ् पा॰ ३.३.१८)",
    "- अन्त᳓कः᳓ → **अन्तकः᳓** (प्रातिपदिकम् अन्तक᳓ (*MW*))",
    "- म᳓हः᳓ → **महः᳓** (*TS*)",
    "- ध᳓र्मा᳓म् → **धर्मा᳓म्** (प्रातिपदिकम् धर्म᳓न् (*MW*))",
    "- न᳓ (*TS*)",
  ]
  hits = find_suspect_homograph_accents(bad, "धर्मान् न प्रम॑दित॒व्यम् ।")
  assert len(hits) == 4

  good = [
    "- वे᳓द᳓म् → **वे᳓दम्** (श्रुत्यर्थे वे᳓दम् आद्युदात्तम् श्रेयः, पा॰ ६.१.२०३, *AV*; दर्भमुष्टौ धने वा वेद᳓म्, *TS* वेदः᳓, *MW*)",
    "- वेदः᳓ (धनधर्मसाधनार्थे वेदः᳓ अन्तोदात्तः मूलेऽत्र श्रेयान्, *TS* — हरदत्तः; श्रुत्यर्थे वे᳓दः पा॰ ६.१.२०३)",
    "- अन्त᳓कः᳓ → **अ᳓न्तकः** (मृत्यौ संहर्तरि च अ᳓न्तकः आद्युदात्तः श्रेयान्, *MW* — भास्करः; सीमार्थे त्व् अन्तकः᳓, *ŚB*, *MW*)",
    "- म᳓हः᳓ → **म᳓हः** (महत्त्वपूजार्थे नपुंसकम् म᳓हः आद्युदात्तम् श्रेयः, पा॰ ६.१.१९७, *TS*, *RV*, *TB*; मह्-शब्दस्य षष्ठ्यादौ तु महः᳓, पा॰ ६.१.१६८)",
    "- ध᳓र्मा᳓म् → **ध᳓र्मात्** (अनुष्ठेयधर्मे पञ्चम्यन्तम् ध᳓र्मात् आद्युदात्तम् श्रेयः, पा॰ ६.१.१९७, *TS*; धर्तरि पुंसि तु धर्म᳓न्, *RV*, *MW*)",
    "- न᳓ (*TS*)",
  ]
  assert find_suspect_homograph_accents(good, "धर्मान् न प्रम॑दित॒व्यम् ।") == []
