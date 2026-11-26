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
    "- सः᳓ (*TS*-766)\n- इद᳓म् (*TS*-512)\n</details>\n"
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


def test_forbidden_ta_and_ek_sources_and_sb_allowed():
  from doc_curation.sanskrit.accent.validator import find_forbidden_accent_sources

  assert find_forbidden_accent_sources([
    "- एत᳓त् (*TS*-95, *RV*-41, *TA*-12)",
    "- स᳓मगन्महि (*EK* मूल-पाठः)",
    "- एत᳓त् (*TS*-95, *ŚB*-12)",
  ]) == [
    "- एत᳓त् (*TS*-95, *RV*-41, *TA*-12)",
    "- स᳓मगन्महि (*EK* मूल-पाठः)",
  ]

  issues_ta = validate_padapatha_block("पद-पाठः (यान्त्रिकः)", "- एत᳓त् (*TS*-95, *TA*-12)\n")
  assert any(i.kind == "forbidden_accent_source" for i in issues_ta)
  issues_ek = validate_padapatha_block("पद-पाठः (यान्त्रिकः)", "- अ᳓ग्निः (*EK* मूल-पाठः)\n")
  assert any(i.kind == "forbidden_accent_source" for i in issues_ek)
  assert validate_padapatha_block("पद-पाठः (यान्त्रिकः)", "- एत᳓त् (*TS*-95, *ŚB*-12)\n") == []


def test_provenance_excludes_ta_and_ek_keeps_sb():
  from doc_curation.sanskrit.accent.provenance import (
    CORPUS_TAGS,
    DEFAULT_CORPUS_DIRS,
    FORBIDDEN_CORPUS_TAGS,
    VedicCorpusCounter,
    annotate_padapatha_line_counts,
  )

  assert "TA" not in CORPUS_TAGS
  assert "EK" not in CORPUS_TAGS
  assert "ŚB" in CORPUS_TAGS
  assert "TA" not in DEFAULT_CORPUS_DIRS
  assert "ŚB" in DEFAULT_CORPUS_DIRS
  assert set(FORBIDDEN_CORPUS_TAGS) == {"TA", "EK"}

  counter = VedicCorpusCounter()
  counter._add("TA", "एतत्", ("", "U"), freq=5)
  counter._add("ŚB", "एतत्", ("", "U"), freq=7)
  counter._add("SB-M", "एतत्", ("", "U"), freq=7)
  counter._finalize_secondary_tables()
  assert counter.count("एत᳓त्", "TA") == 0
  assert counter.count("एत᳓त्", "EK") == 0
  assert counter.count("एत᳓त्", "ŚB") == 7
  assert counter.count("एत᳓त्", "SB-M") == 7

  cleaned, unres = annotate_padapatha_line_counts("- एत᳓त् (*ŚB*, *TA*-12, *EK* मूल-पाठः)", counter)
  assert cleaned == "- एत᳓त् (*ŚB*-7)"
  assert unres == []

  cured, unres_cured = annotate_padapatha_line_counts("- एत᳓त् (*TA*)", counter)
  assert cured == "- एत᳓त् (*SB-M*-7)"
  assert unres_cured == []

  only_bad, unres_bad = annotate_padapatha_line_counts("- अज्ञात᳓म् (*TA*)", counter)
  assert only_bad == "- अज्ञात᳓म् (*TA*)"
  assert ("TA", "अज्ञात᳓म्") in unres_bad


def test_tinanta_sutra_and_missing_aa_upasarga_guards():
  from doc_curation.sanskrit.accent.validator import (
    find_missing_aa_upasarga_splits,
    find_tinanta_sutra_on_non_tinanta,
  )

  # 1. पा॰ ८.१.२८–६८ (e.g. हि च ८.१.३४ / यद्वृत्तान्नित्यम् ८.१.६६) must never apply to non-tiṅantas (`अस्य`, `मम`, `उत्`)
  #    or bleed across clause boundaries (`मा रिषामा`).
  bad_hicha = [
    "- भद्रा᳓ (*TS*-2, *RV*-42)",
    "- हि᳓ (*TS*-456, *RV*-662)",
    "- नः (अनुदात्तम्, पा॰ ८.१.१८)",
    "- प्र᳓-मतिः (*TS*-1, *RV*-23)",
    "- अस्य → **अस्य᳓** (हि च पा॰ ८.१.३४)",
    "- सँ-स᳓दि (*TS*-2, *RV*-6)",
    "- अ᳓ग्ने (पादादावामन्त्रितम् आद्युदात्तम्, पा॰ ६.१.१९८)",
    "- सख्ये᳓ (*RV*-40)",
    "- मा᳓ (*TS*-205, *RV*-389)",
    "- रिषामा → **रि᳓षामा** (हि च पा॰ ८.१.३४)",
    "- वय᳓म् (*TS*-88, *RV*-297)",
    "- त᳓व (*TS*-25, *RV*-113)",
  ]
  hits = find_tinanta_sutra_on_non_tinanta(bad_hicha)
  assert len(hits) == 2
  assert any("अस्य᳓" in h for h in hits)
  assert any("रि᳓षामा" in h for h in hits)

  # Legitimate हि-clause verb and legitimate 2sg loṭ `वि` + `अस्य` pass cleanly
  good_hicha = [
    "- सः᳓ (*TS*-766)",
    "- हि᳓ (*TS*-456)",
    "- वे᳓द (हि च पा॰ ८.१.३४)",
    "- वि᳓ (*TS*-379)",
    "- अस्य (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- प्रा᳓ङ् (*SB-M*-62)",
    "- यायाः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, √या लिङ्)",
    "- प्रत्य᳓ङ् (*SB-M*-10)",
    "- याः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, √या लुङ्)",
  ]
  assert find_tinanta_sutra_on_non_tinanta(good_hicha) == []
  assert len(find_tinanta_sutra_on_non_tinanta(["- याः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)", "- यायाः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)"])) == 2
  assert validate_padapatha_block("पद-पाठः (यान्त्रिकः)", "- न᳓ (*SB-M*-2493)\n- हि᳓ (*SB-M*-2665)\n- व्यथा᳓म् (नामपदम् (स्त्रीलिङ्गम्), *MW*)") == []

  # 2. Missing `आ᳓` upasarga split (`जै᳓त्र्याय᳓ → **जै᳓त्र्याय**` + `अविशताम्`) and double-canceling `आ` + `अ-`verb arrows
  bad_aa = [
    "- हि᳓रण्यम् (*TS*-52, *RV*-18)",
    "- जै᳓त्र्याय᳓ → **जै᳓त्र्याय** (ष्यञ् पा॰ ६.१.१९७)",
    "- अविशताम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
  ]
  assert len(find_missing_aa_upasarga_splits(bad_aa)) == 1
  block_issues = validate_padapatha_block("पद-पाठः (यान्त्रिकः - 1/3 व्यत्यस्त-स्वराः)", "\n".join(bad_aa))
  assert any(i.kind == "missing_aa_upasarga_split" for i in block_issues)
  assert any(i.kind == "unsplit_upasarga_tinanta" for i in block_issues)

  good_aa = [
    "- हि᳓रण्यम् (*TS*-52, *RV*-18)",
    "- जै᳓त्र्याय (ष्यञ् पा॰ ६.१.१९७)",
    "- आ᳓ (*TS*-1107, *RV*-2810)",
    "- विशताम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *AV*-1)",
  ]
  assert validate_padapatha_block("पद-पाठः (यान्त्रिकः)", "\n".join(good_aa)) == []

  double_cancel = [
    "- नः (अनुदात्तम्, पा॰ ८.१.१८)",
    "- आ → **आ᳓** (*TS*-1107)",
    "- अ᳓गात् → **अगात्** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
  ]
  assert len(find_missing_aa_upasarga_splits(double_cancel)) == 1


def test_uncounted_tags_fake_sutras_and_rubberstamp_provenance_guards():
  from doc_curation.sanskrit.accent.validator import (
    find_invalid_or_rubberstamp_provenance,
    find_uncounted_corpus_tags,
  )

  # 1. Uncounted *CORPUS* tags
  assert len(find_uncounted_corpus_tags([
    "- शूल-हस्ता᳓न् (*AV*, बहुव्रीहौ समासस्य — हरदत्तः)",
    "- वायु᳓-रक्षितम् (*TS*, *RV*, *TB*)",
    "- शू᳓ल-हस्तान् (बहुव्रीहौ प्रकृत्या पूर्वपदम् पा॰ ६.२.१, शू᳓लम् *TS*-1, *RV*-1)",
  ])) == 2

  # 2. Fake/oxymoronic sūtra, out-of-bounds sūtra, bare समासस्वरः (even with पा॰ ६.१.१५८),
  #    rubber-stamped मूल-पाठः/अनाम्नातम्, misaccented ल्यप्, ल्यु/ल्युट् + ६.१.२२३ bug, and fake `णिनिः नित्`
  bad_prov = [
    "- शूल-हस्ता᳓न् (*AV*-1, बहुव्रीहौ समासस्य — हरदत्तः)",
    "- अ᳓ग्निः (पा॰ ६.१.२९९)",
    "- व᳓ह्नि-शिखा (व᳓ह्नि (*MW*) + शि᳓खा (*TB*-1), समासस्वरः)",
    "- स᳓प्त-इन्द्रियाणि᳓ → **सप्त-इन्द्रियाणि᳓** (अनेकोदात्त-दोषः पा॰ ६.१.१५८; सप्त᳓ (*TS*-74) + इन्द्रिया᳓णि (*TS*-3), समासस्वरः)",
    "- विधुर᳓म् (मूल-पाठः (अनाम्नातम्))",
    "- उरस्-पेशा᳓न् (मूल-पाठः — हरदत्तः)",
    "- नि᳓-विश्य (ल्यप् पा॰ ३.१.४, ६.२.१३९)",
    "- प्रति-गृह्य᳓ (ल्यप् पा॰ ६.२.१३९)",
    "- वाल-बन्धनः᳓ (ल्युट्/समासस्य पा॰ ६.१.२२३ — हरदत्तः)",
    "- अमृत-अपिधान᳓म् (करणे ल्युट् पा॰ ३.३.११७, समासस्य पा॰ ६.१.२२३)",
    "- लोक-धा᳓रिणी (णिनिः नित् पा॰ ६.१.१९७, गतिकारकोपपदात् कृत् पा॰ ६.२.१३९)",
    "- पुष्टि-व᳓र्धनः (ल्युः नित् पा॰ ६.१.१९७, ६.२.१३९)",
    "- आ-ख्यायिकाः᳓ (ण्वुल् पा॰ ३.१.३, ६.२.१३९)",
    "- अन्-अप-रो᳓द्ध्यः (ण्यत् यतोऽनावः पा॰ ६.१.२१३, ६.२.१३९)",
    "- भ्रूण-हत्या᳓म् (हनस्त च पा॰ ३.१.१०८ क्यप्, उदात्तं शुनः पा॰ ६.१.१६१, ६.२.१३९)",
  ]
  assert len(find_invalid_or_rubberstamp_provenance(bad_prov)) == 15

  good_prov = [
    "- शूल-हस्ता᳓न् → **शू᳓ल-हस्तान्** (बहुव्रीहौ प्रकृत्या पूर्वपदम् पा॰ ६.२.१, शू᳓लम् *TS*-1, *RV*-1, *MW* — हरदत्तः)",
    "- विधुर᳓म् (कुरच् उणादि॰ १.५१, चितः पा॰ ६.१.१६३ — हरदत्तः)",
    "- नि᳓-विश्य → **नि-वि᳓श्य** (ल्यप् पा॰ ३.१.४, गतिकारकोपपदात् कृत् पा॰ ६.२.१३९)",
    "- प्रति-गृह्य᳓ → **प्रति-गृ᳓ह्य** (*TS*-1, *RV*-1, ल्यप् पा॰ ३.१.४, ६.२.१३९)",
    "- हा᳓वु (सामगाननिपात आद्युदात्तः, आरण्यक-पाठः — भास्करः)",
    "- वाल-बन्धनः᳓ → **वाल-ब᳓न्धनः** (कर्तरि ल्युः पा॰ ३.१.१३४, लिति पा॰ ६.१.१९३, गतिकारकोपपदात् कृत् पा॰ ६.२.१३९ — हरदत्तः)",
    "- वेद-अनुवचन᳓म् (भावे ल्युट् पा॰ ३.३.११५, अनो भावकर्मवचनः पा॰ ६.२.१५०)",
    "- स्रग्-अलङ्करणे᳓ (ल्युट् पा॰ ३.३.११७, द्वन्द्वः समासस्य पा॰ ६.१.२२३)",
    "- पाद-अवने᳓जनीः (करणे ल्युट् पा॰ ३.३.११७, लिति पा॰ ६.१.१९३, गतिकारकोपपदात् कृत् पा॰ ६.२.१३९ — हरदत्तः)",
    "- लोक-धारि᳓णी᳓ → **लोक-धारि᳓णी** (अनेकोदात्त-दोषः पा॰ ६.१.१५८; णिनिः पा॰ ३.२.७८, प्रत्ययस्वरः पा॰ ३.१.३, गतिकारकोपपदात् कृत् पा॰ ६.२.१३९)",
    "- आ-ख्यायि᳓काः᳓ → **आ-ख्या᳓यिकाः** (संज्ञायां ण्वुल् पा॰ ३.३.१०९, लिति पा॰ ६.१.१९३, गतिकारकोपपदात् कृत् पा॰ ६.२.१३९ — भास्करः)",
    "- अन्-अप-रोद्ध्य᳙ः (ण्यत् पा॰ ३.१.१२४, तित्स्वरितम् पा॰ ६.१.१८५, मूले ऽनप॒रोद्ध्यः॑)",
    "- भ्रूण-हत्या᳓म् (हनस्त च पा॰ ३.१.१०८ क्यप्, ध्यपूर्वस्य स्त्रीविषयस्य फि॰ १.५, गतिकारकोपपदात् कृत् पा॰ ६.२.१३९)",
  ]
  assert validate_padapatha_block("पद-पाठः (यान्त्रिकः - 6/13 व्यत्यस्त-स्वराः)", "\n".join(good_prov)) == []


def test_fake_sandhi_svara_arrows_guard():
  from doc_curation.sanskrit.accent.validator import (
    find_fake_sandhi_svara_arrows,
    validate_padapatha_block,
  )

  # 1. Yaṇ udātta + udātta (`पोषयित्नु᳓` + `आ᳓` -> `पोषयि॒त्न्वा`, पा॰ ६.१.७७ + ८.२.४ अनुदात्तस्य)
  mula_posha = "गामश्व॑म्पोषयि॒त्न्वा स नः॑ ।"
  pp_posha_fake = [
    "- गा᳓म् (*TS*-55)",
    "- अ᳓श्वम् (*TS*-40)",
    "- पोषयित्नु᳓ (*TS*-2, *RV*-3)",
    "- आ → **आ᳓** (*TS*-1107)",
    "- सः᳓ (*TS*-766/4763)",
    "- नः (अनुदात्तम्, पा॰ ८.१.१८, *TS*-587)",
  ]
  assert find_fake_sandhi_svara_arrows(pp_posha_fake, mula_posha) == ["- आ → **आ᳓** (*TS*-1107)"]
  blk_iss = validate_padapatha_block("पद-पाठः (यान्त्रिकः - 1/6 व्यत्यस्त-स्वराः)", "\n".join(pp_posha_fake), mula_posha)
  assert any(i.kind == "fake_sandhi_svara_arrow" for i in blk_iss)

  # Clean version without the fake arrow passes completely
  pp_posha_clean = [
    "- गा᳓म् (*TS*-55)",
    "- अ᳓श्वम् (*TS*-40)",
    "- पोषयित्नु᳓ (*TS*-2, *RV*-3)",
    "- आ᳓ (*TS*-1107)",
    "- सः᳓ (*TS*-766/4763)",
    "- नः (अनुदात्तम्, पा॰ ८.१.१८, *TS*-587)",
  ]
  assert validate_padapatha_block("पद-पाठः (यान्त्रिकः)", "\n".join(pp_posha_clean), mula_posha) == []

  # 2. Compound-internal ekādeśa (`शत-अ᳓ङ्कुरा → **शत᳓-अङ्कुरा**` on `श॒ताङ्कु॑रा`) and hyphen-only arrow (`वि᳓धृते → **वि᳓-धृते**`)
  mula_shata = "श॒तमू॑ला श॒ताङ्कु॑रा ।"
  pp_shata_fake = [
    "- शत᳓-मूला (बहुव्रीहौ प्रकृत्या पूर्वपदम् पा॰ ६.२.१)",
    "- शत-अ᳓ङ्कुरा → **शत᳓-अङ्कुरा** (बहुव्रीहौ प्रकृत्या पूर्वपदम् पा॰ ६.२.१)",
  ]
  assert find_fake_sandhi_svara_arrows(pp_shata_fake, mula_shata) == [pp_shata_fake[1]]
  assert find_fake_sandhi_svara_arrows(["- वि᳓धृते → **वि᳓-धृते** (*TS*-2/5, पा॰ ६.२.४९)"], "") == [
    "- वि᳓धृते → **वि᳓-धृते** (*TS*-2/5, पा॰ ६.२.४९)"
  ]

  # 2b. Spaced virāma-yaṇ boundary (`दुरि॒तात्य् अ॒ग्निः` = `दुः-इता᳓` + `अ᳓ति` + `अग्निः᳓`)
  mula_durita = "अति॑ दुरि॒तात्य् अ॒ग्निः॥"
  pp_durita_fake = [
    "- अ᳓ति (*TS*-75)",
    "- दुः-इता᳓ (*TS*-4/7)",
    "- अति → **अ᳓ति** (*TS*-75)",
    "- अग्निः᳓ (*TS*-403/1195)",
  ]
  assert find_fake_sandhi_svara_arrows(pp_durita_fake, mula_durita) == ["- अति → **अ᳓ति** (*TS*-75)"]

  # 3. Genuine vyatyasta after virāma-final word (`तान॒न्वेति॑` = `ता᳓न्` + `अनु` + `ए᳓ति` in मूलम्, vs `ता᳓न्` + `अ᳓नु` + `एति`) MUST NOT be flagged as fake!
  mula_tan = "तान॒न्वेति॑ ।"
  pp_tan_real_vyat = [
    "- ता᳓न् (*TS*-94/4763)",
    "- अनु → **अ᳓नु** (*TS*-471, *RV*-475)",
    "- ए᳓ति → **एति** (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *TS*-166)",
  ]
  assert find_fake_sandhi_svara_arrows(pp_tan_real_vyat, mula_tan) == []


def test_repeated_vocative_nighata_and_8173_samanadhikarana():
  from doc_curation.sanskrit.accent.validator import find_false_nighata_arrows

  # Repeated vocative (`सुश्रवः` at index 0 pādādi vs later non-pādādi occurrences) must NOT falsely match occurrence #0
  mula_sushravas = (
    "सु॒श्रव॑स्सु॒श्रव॑सं मा कुरु॒ यथा॒ त्वँ सु॒श्रव॑स्सु॒श्रवा॑ अ॒स्येव॑म॒हँ सु॒श्रव॑स्सु॒श्रवा॑ भूयासम् ।"
  )
  pp_sushravas = [
    "- सु-श्र᳓वः → **सु᳓-श्रवः** (आमन्त्रितम् — हरदत्तः; पादादावाद्युदात्तम्, पा॰ ६.१.१९८)",
    "- सु-श्र᳓वसम् (*TS*-1)",
    "- मा (अनुदात्तम्, पा॰ ८.१.१८, *TS*-202)",
    "- कुरु (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- य᳓था (*TS*-123)",
    "- त्व᳓म् (*TS*-158/313)",
    "- सु-श्र᳓वः → **सु-श्रवः** (अपादादौ आमन्त्रितम् अनुदात्तम्, पा॰ ८.१.१९)",
    "- सु-श्र᳓वाः (*TS*-1)",
    "- अ᳓सि (यद्वृत्तान्नित्यम्, पा॰ ८.१.६६)",
    "- एव᳓म् (*TS*-250)",
    "- अह᳓म् (*TS*-162/565)",
    "- सु-श्र᳓वः → **सु-श्रवः** (अपादादौ आमन्त्रितम् अनुदात्तम्, पा॰ ८.१.१९)",
    "- सु-श्र᳓वाः (*TS*-1)",
    "- भूयासम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
  ]
  assert find_false_nighata_arrows(pp_sushravas, mula_sushravas) == []

  # Samānādhikaraṇa vocative #1 citing पा॰ ८.१.७३ is blocked from पा॰ ८.१.७२ and properly de-accented by पा॰ ८.१.१९
  mula_devi = "देवी॑ द्यावापृथिवी॒ अनु॑ मे मँसाथाम् ।"
  pp_devi = [
    "- दे᳓वी (पादादावामन्त्रितम् आद्युदात्तम्, पा॰ ६.१.१९८)",
    "- द्या᳓वा-पृथिवी → **द्यावा-पृथिवी** (अपादादौ आमन्त्रितम् अनुदात्तम्, पा॰ ८.१.१९, ८.१.७३)",
    "- अ᳓नु (*TS*-471)",
    "- मे (अनुदात्तम्, पा॰ ८.१.१८, *TS*-585)",
    "- मँसाथाम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
  ]
  assert find_false_nighata_arrows(pp_devi, mula_devi) == []


def test_nal_shanach_ekagnikanda_and_missing_commentator_guards():
  from doc_curation.sanskrit.accent.validator import (
    find_invalid_or_rubberstamp_provenance,
    find_missing_commentator_attributions,
    validate_accented_markdown,
  )

  bad = [
    "- ए᳓जाय → **एजा᳓य** (आङ्+इण् लिट् णल् पा॰ ३.१.३)",
    "- धिय᳓सान᳓स्य → **धियसान᳓स्य** (*RV*-1/2, शानच् पा॰ ३.१.३)",
    "- सेहाना᳓याः (*RV*-1/8, कानच् पा॰ ३.१.३)",
    "- नयामसि → **नयामसि᳓** (एकाग्निकाण्ड-पाठः)",
    "- शुन᳓न् → **शुनन्** (पारिभाषिकः स्वरव्यत्ययः)",
  ]
  assert len(find_invalid_or_rubberstamp_provenance(bad)) == 5

  good = [
    "- ए᳓जाय → **एजा᳓य** (आङ्+इण् लिट् णल्; लिति पूर्वम् पा॰ ६.१.१९३)",
    "- धिय᳓सान᳓स्य → **धियसान᳓स्य** (*RV*-1/2, शानच् चितः पा॰ ६.१.१६३)",
    "- सेहाना᳓याः (*RV*-1/8, कानच् पा॰ ३.२.१०६, चितः पा॰ ६.१.१६३)",
    "- करिष्य᳓माणः (स्यप्रत्ययः पा॰ ३.१.३३, प्रत्ययस्वरः पा॰ ३.१.३; अदुपदेशात् पा॰ ६.१.१८६)",
  ]
  assert find_invalid_or_rubberstamp_provenance(good) == []

  # Missing commentator attribution check at document level
  md_bad_comm = (
    "<details><summary>मूलम्</summary>\n\nअ॒ग्निम् ।\n</details>\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- अग्नि᳓म् (*TS*-293/1195 — भास्करः)\n"
    "</details>\n"
    "<details><summary>हरदत्तः</summary>\n\nअग्निम् इति ।\n</details>\n"
  )
  iss = validate_accented_markdown(md_bad_comm)
  assert any(i.kind == "missing_commentator_attribution" for i in iss)

  # Quoted external commentator or matching commentator passes cleanly
  assert find_missing_commentator_attributions(
    ['- दिश (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८; भास्करः "दिशो दिश प्रयच्छ")', "- अ᳓विदः (छान्दसो विसर्गलोपः — हरदत्तः)"],
    {"हरदत्तः"},
  ) == []


def test_sb_simplex_tinanta_allowlist_verbs():
  assert find_unsplit_upasarga_tinantas([
    "- अवधोत् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अपिपत (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आशन् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आमते (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
  ]) == []


def test_vp_integrity_catches_bolding_splits_and_quadruple_stars():
  from doc_curation.sanskrit.accent.validator import find_vp_integrity_issues

  assert find_vp_integrity_issues("**मा᳓** ते गृहे᳓ +++(note)+++") == []
  assert any("split_combining_after_markup" in i for i in find_vp_integrity_issues("**[[मा|मा᳓]]**᳓ ते"))
  assert any("split_combining_after_markup" in i for i in find_vp_integrity_issues("**मा**᳓ ते"))
  assert any("malformed_bold_stars" in i for i in find_vp_integrity_issues("त᳓तो नो ****अ᳓भयं कृधि** ।"))


def test_tinanta_homograph_and_tas_adverbs_guards():
  from doc_curation.sanskrit.accent.validator import find_tinanta_sutra_on_non_tinanta

  bad = [
    "- अन्ततः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- देवताम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *TS*-0/15)",
    "- महताम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- बृहतः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- अन्त्ये (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- जीवताम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *AV*-0/2)",
    "- ईषतः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *TS*-0/1)",
  ]
  hits = find_tinanta_sutra_on_non_tinanta(bad)
  assert hits == bad

  good = [
    "- स्याताम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- भवतः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *TS*-51)",
    "- क्रामतः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *TS*-4)",
    "- हथः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- वहन्ताम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- विध्यतः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- विशताम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *AV*-1)",
  ]
  assert find_tinanta_sutra_on_non_tinanta(good) == []


def test_avp_enclitic_simplex_hiatus_and_augmented_dual_guards():
  from doc_curation.sanskrit.accent.validator import (
    find_tinanta_sutra_on_non_tinanta,
    find_unexplained_aa_hiatuses,
    find_unlicensed_unaccented_padas,
    find_unsplit_upasarga_tinantas,
  )

  assert find_unlicensed_unaccented_padas([
    "- णः (अनुदात्तम्, पा॰ ८.१.१८, *TS*-1)",
    "- समह (अनुदात्तम्, पा॰ ८.१.१८, *RV*-4)",
  ]) == []
  assert find_unsplit_upasarga_tinantas([
    "- रिषः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *RV*-1)",
    "- अभरः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आनिषुः (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *AV*-1)",
    "- अपद्रन् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
    "- आ᳓स्य (*Lanman*, *TS*-2, *AV*-3)",
    "- विव᳓स्व (*RV*-1/2, *KS*-1)",
  ]) == []
  assert find_tinanta_sutra_on_non_tinanta([
    "- अभि (उपसर्गः, पा॰ १.४.५९)",
    "- अरक्षताम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)",
  ]) == []
  assert find_unexplained_aa_hiatuses(["- न᳓ (*RV*-1)", "- उ (अनुदात्तम्, पा॰ ८.१.१८)"], "न उत्तरात्") == []




