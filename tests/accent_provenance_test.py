from doc_curation.sanskrit.accent.provenance import (
  VedicCorpusCounter,
  annotate_padapatha_line_counts,
  annotate_padapatha_markdown_counts,
  normalize_panini_abbreviations,
  word_to_key_and_marks,
)
from doc_curation.sanskrit.accent.validator import validate_padapatha_block


def _make_mock_counter() -> VedicCorpusCounter:
  c = VedicCorpusCounter()
  for corp, word, freq in [
    ("TS", "सर्व᳓तः", 12),
    ("RV", "सर्व᳓तः", 2),
    ("TB", "सर्व᳓तः", 3),
    ("TS", "ते", 541),
    ("RV", "ते", 1280),
    ("TS", "ते᳓", 451),
    ("RV", "ते᳓", 282),
    ("TS", "सप्त᳓", 74),
    ("RV", "सप्त᳓", 122),
    ("TB", "अर्चिः᳓", 2),
    ("AV", "वे᳓दम्", 8),
    ("RV", "वे᳓दः", 14),
    ("TS", "वेदः᳓", 4),
    ("TS", "उ᳓द्", 210),
    ("RV", "उ᳓त्", 340),
  ]:
    km = word_to_key_and_marks(word)
    assert km is not None
    c._add(corp, km[0], km[1], freq=freq)
  c._finalize_secondary_tables()
  return c


def test_normalize_panini_abbreviations():
  assert normalize_panini_abbreviations("पा० ६.१.१९८, नपुं०, पुं०, *RV* १०.८५.४३") == (
    "पा॰ ६.१.१९८, नपुं॰, पुं॰, *RV* १०.८५.४३"
  )


def test_annotate_padapatha_line_counts_and_idempotence():
  counter = _make_mock_counter()

  # 1. Direct pada counts (hypothetical user example)
  ln1, unres1 = annotate_padapatha_line_counts("- सर्व᳓तः (*TS*, *RV*, *TB*)", counter)
  assert ln1 == "- सर्व᳓तः (*TS*-12, *RV*-2, *TB*-3)"
  assert unres1 == []
  # Idempotent on re-run
  assert annotate_padapatha_line_counts(ln1, counter)[0] == ln1

  # 2. Enclitic ते vs tonic ते᳓ never conflate, and पा० -> पा॰
  ln_enc, _ = annotate_padapatha_line_counts("- ते (अनुदात्तम्, पा० ८.१.१८, *TS*, *RV*)", counter)
  assert ln_enc == "- ते (अनुदात्तम्, पा॰ ८.१.१८, *TS*-541, *RV*-1280)"
  ln_ton, _ = annotate_padapatha_line_counts("- ते᳓ (*TS*, *RV*)", counter)
  assert ln_ton == "- ते᳓ (*TS*-451, *RV*-282)"

  # 3. Nested compound member parens
  ln_comp, unres_c = annotate_padapatha_line_counts(
    "- सप्त᳓-अर्चिः (सप्त᳓ (*TS*, *RV*) + अर्चिः᳓ (*TB*), बहुव्रीहौ पा० ६.२.१)",
    counter,
  )
  assert ln_comp == "- सप्त᳓-अर्चिः (सप्त᳓ (*TS*-74, *RV*-122) + अर्चिः᳓ (*TB*-2), बहुव्रीहौ पा॰ ६.२.१)"
  assert unres_c == []

  # 4. Homograph disambiguation with inline parallel form & `;` alternative clause
  ln_veda, unres_v = annotate_padapatha_line_counts(
    "- वे᳓द᳓म् → **वे᳓दम्** (श्रुत्यर्थे वे᳓दम् आद्युदात्तम् श्रेयः, पा० ६.१.२०३, *AV*, *RV* वे᳓दः; दर्भमुष्टौ वेद᳓म्, *TS* वेदः᳓, *MW*)",
    counter,
  )
  assert ln_veda == (
    "- वे᳓द᳓म् → **वे᳓दम्** (श्रुत्यर्थे वे᳓दम् आद्युदात्तम् श्रेयः, पा॰ ६.१.२०३, *AV*-8, *RV*-14 वे᳓दः; दर्भमुष्टौ वेद᳓म्, *TS*-4 वेदः᳓, *MW*)"
  )
  assert unres_v == []

  # 5. Final stop voicing equivalence (`उ᳓त्` matches Taittirīya `उ᳓द्`) and unparenthesized `WORD *TS*, *RV*`
  ln_ut, unres_u = annotate_padapatha_line_counts("- उ᳓त् (*TS*, *RV*)", counter)
  assert ln_ut == "- उ᳓त् (*TS*-210, *RV*-340)"
  assert unres_u == []

  ln_prec, unres_p = annotate_padapatha_line_counts(
    "- सप्त᳓-अर्चिः (बहुव्रीहौ प्रकृत्या पूर्वपदम् पा॰ ६.२.१, सप्त᳓ *TS*, *RV*)",
    counter,
  )
  assert ln_prec == "- सप्त᳓-अर्चिः (बहुव्रीहौ प्रकृत्या पूर्वपदम् पा॰ ६.२.१, सप्त᳓ *TS*-74, *RV*-122)"
  assert unres_p == []


def test_annotate_markdown_skips_js_include_and_validator_rejects_zero_abbrev():
  counter = _make_mock_counter()
  md = (
    '<div class="js_include" url="/foo.md">\n'
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- सर्व᳓तः (*TS*)\n</details>\n"
    "</div>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- ते (अनुदात्तम्, पा\u0966 ८.१.१८, *TS*, *RV*)\n</details>\n"
  )
  out, unres = annotate_padapatha_markdown_counts(md, counter, skip_js_includes=True)
  assert unres == []
  assert "- सर्व᳓तः (*TS*)\n" in out
  assert "- ते (अनुदात्तम्, पा॰ ८.१.१८, *TS*-541, *RV*-1280)\n" in out

  # Validator rejects पा\u0966 and *-0
  bad_issues = validate_padapatha_block(
    "पद-पाठः (यान्त्रिकः)",
    "- ते (अनुदात्तम्, पा\u0966 ८.१.१८, *TS*-0)\n",
  )
  kinds = {i.kind for i in bad_issues}
  assert "zero_abbrev_sign" in kinds
  assert "zero_corpus_count" in kinds


def test_samhita_snippet_and_spaced_yan_8_2_4():
  from doc_curation.sanskrit.accent.reconciler import reconcile_vprastuti_and_tiikaa_texts

  # 1. Classical saṁhitā snippets with unmarked leading anudātta syllables keep only genuine final udātta
  assert word_to_key_and_marks("अप॒घ्नन्") == ("अपघ्नन्", ("", "", "U"))
  assert word_to_key_and_marks("प्रथम॒जाः") == ("प्रथमजाः", ("", "", "", "U"))
  assert word_to_key_and_marks("पृत॒ना॒ऽजित॑म्") == ("पृतनाजितम्", ("", "", "", "U", ""))

  # 2. `ः-प` after `-अ` produces `स्` (`वाचस्पतये`), while after `-इ/-उ/-ओ` produces `ष्` (`वास्तोष्पते`),
  # and `count()` matches Śākala visarga-retaining compounds (`जाःपत्यम्`, `विश्वतःपात्`) across `-` or `स्`
  assert word_to_key_and_marks("वाचः᳓-प᳓तये") == ("वाचस्पतये", ("", "U", "U", "", ""))
  assert word_to_key_and_marks("वा᳓स्तोः-पते") == ("वास्तोष्पते", ("U", "", "", ""))
  c = VedicCorpusCounter()
  c._add("RV", "जाःपत्यम्", ("", "", "U"), freq=1, mode="sum")
  c._add("RV", "विश्वतःपात्", ("", "U", "", ""), freq=1, mode="sum")
  c._finalize_secondary_tables()
  assert c.count("जाः-पत्य᳓म्", "RV") == 1
  assert c.count("जास्पत्य᳓म्", "RV") == 1
  assert c.count("विश्व᳓तः-पात्", "RV") == 1
  assert c.count("विश्व᳓तस्पात्", "RV") == 1

  # 3. Spaced `ends_semi` yaṇ sandhi (`उच्चैश्-श्राव्य् अ-कर्ण᳓कः` from `उच्चैः-श्रावी᳓ + अ-कर्ण᳓कः`) yields svarita `अ᳙` by पा॰ ८.२.४
  vp = "+++\ntitle = \"test\"\n+++\n\nउच्चै᳓श्-श्राव्य् अ-कर्ण᳓कः ।\n"
  tk = (
    "<details><summary>मूलम्</summary>\n\nउ॒च्चैश्श्रा॑व्यक॒र्णकः॑ ।\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः - 1/2 व्यत्यस्त-स्वराः)</summary>\n\n"
    "- उच्चैः᳓-श्रावी → **उच्चैः-श्रावी᳓** (णिनिः पा॰ ३.२.७८, ३.१.३, गतिकारकोपपदात् कृत् पा॰ ६.२.१३९)\n"
    "- अ-कर्ण᳓कः (नञ्-बहुव्रीहौ कपि पूर्वम् पा॰ ६.२.१७३)\n"
    "</details>\n"
  )
  reconciled, _ = reconcile_vprastuti_and_tiikaa_texts(vp, tk)
  assert "[[उच्चै᳓श्-श्राव्य्|उच्चैश्-श्राव्य्]] [[अ-कर्ण᳓कः|अ᳙-कर्ण᳓कः]]" in reconciled


def test_stem_across_cases_enrichment_zero_slash_n_and_validator():
  c = VedicCorpusCounter()
  for corp, word, freq in [
    ("TS", "न᳓क्षत्रैः", 2),
    ("TS", "न᳓क्षत्रम्", 28),
    ("TS", "न᳓क्षत्राणि", 9),
    ("RV", "न᳓क्षत्रम्", 5),
    ("TB", "न᳓क्षत्रेभ्यः", 7),
    ("TS", "रो᳓हितः", 1),
    ("TS", "रो᳓हिताय", 2),
    ("AV", "रो᳓हितम्", 10),
    ("TS", "इ᳓ति", 1796),
    ("RV", "इ᳓ति", 83),
  ]:
    km = word_to_key_and_marks(word)
    assert km is not None
    c._add(corp, km[0], km[1], freq=freq)
  c._finalize_secondary_tables()

  assert c.count_with_stem("न᳓क्षत्रैः", "TS") == (2, 39)
  assert c.count_with_stem("न᳓क्षत्रैः", "RV") == (0, 5)
  assert c.count_with_stem("न᳓क्षत्रैः", "TB") == (0, 7)

  # 1. Existing tag enriched to M/N + newly surfaced 0/N major corpora, idempotent on re-run
  ln_nak, unres_n = annotate_padapatha_line_counts("- न᳓क्षत्रैः (*TS*)", c)
  assert ln_nak == "- न᳓क्षत्रैः (*TS*-2/39, *RV*-0/5, *TB*-0/7)"
  assert unres_n == []
  assert annotate_padapatha_line_counts(ln_nak, c)[0] == ln_nak

  # 2. Bullet with only *MW* note surfaces 0/N major corpora automatically
  ln_roh, unres_r = annotate_padapatha_line_counts("- रो᳓हितान् (प्रातिपदिकम् रो᳓हित (*MW*))", c)
  assert ln_roh == "- रो᳓हितान् (*TS*-0/3, *AV*-0/10, प्रातिपदिकम् रो᳓हित (*MW*))"
  assert unres_r == []
  assert annotate_padapatha_line_counts(ln_roh, c)[0] == ln_roh

  # 3. Indeclinables keep single -M without stem expansion
  ln_iti, _ = annotate_padapatha_line_counts("- इ᳓ति (*TS*)", c)
  assert ln_iti == "- इ᳓ति (*TS*-1796)"

  # 4. Validator accepts *-0/N and *-M/N (N > M >= 0, N >= 1) and rejects bare *-0, *-0/0, *-5/5, *-5/3
  assert validate_padapatha_block("पद-पाठः (यान्त्रिकः)", f"{ln_nak}\n{ln_roh}\n") == []
  for bad_ln in ("- रो᳓हितान् (*TS*-0)\n", "- रो᳓हितान् (*TS*-0/0)\n", "- रो᳓हितान् (*TS*-5/5)\n", "- रो᳓हितान् (*TS*-5/3)\n"):
    errs = validate_padapatha_block("पद-पाठः (यान्त्रिकः)", bad_ln)
    assert any(e.kind == "zero_corpus_count" for e in errs)


def test_ingest_us_padasvara_babylon(tmp_path):
  from doc_curation.sanskrit.accent.shatapatha_solver import us_padasvara_to_entry

  assert us_padasvara_to_entry("र᳓राणः") == ("रराणः", ("U", "", ""), None)
  assert us_padasvara_to_entry("अभवः") == ("अभवः", ("", "", ""), None)
  assert us_padasvara_to_entry("उ") == ("उ", ("",), None)
  assert us_padasvara_to_entry("वा᳓व᳓") == ("वाव", ("U", "U"), None)
  assert us_padasvara_to_entry("अँहः-मु᳓चे") == ("अंहःमुचे", ("", "", "U", ""), "अंहः-मुचे")

  bab = tmp_path / "kyv-ts-padasvara.babylon"
  bab.write_text(
    "\n#bookname=kyv-ts-padasvara (sa-sa)\n\n"
    "रराणः\nर᳓राणः (3)<br>1.1.1\n\n"
    "रराणः\nरराणः᳓ (1)<br>2.1.1\n\n"
    "अँहःमुचे|अँहोमुचे|अंहःमुचे|अंहोमुचे\nअँहः-मु᳓चे (11)<br>1.6.12\n\n"
    "अत्भिः|अद्भिः\nअत्-भिः᳓ (14)<br>1.1.1\n\n"
    "अभवः\nअभवः (19)<br>1.1.1\n\n"
    "ते\nते (541)<br>1.1.1\n\n"
    "ते\nते᳓ (451)<br>1.1.1\n\n"
    "उ\nउ (96)<br>1.1.1\n\n"
    "वाव\nवा᳓व᳓ (80)<br>1.5.7\n\n",
    encoding="utf-8",
  )
  vc = VedicCorpusCounter()
  vc._ingest_babylon(str(bab), "TS")
  vc._finalize_secondary_tables()
  assert vc.exact_counts["TS"][("रराणः", ("U", "", ""))] == 3
  assert vc.exact_counts["TS"][("रराणः", ("", "", "U"))] == 1
  assert vc.exact_counts["TS"][("अंहोमुचे", ("", "", "U", ""))] == 11
  assert vc.exact_counts["TS"][("अद्भिः", ("", "U"))] == 14
  assert vc.exact_counts["TS"][("अभवः", ("", "", ""))] == 19
  assert vc.exact_counts["TS"][("ते", ("",))] == 541
  assert vc.exact_counts["TS"][("ते", ("U",))] == 451
  assert vc.exact_counts["TS"][("उ", ("",))] == 96
  assert vc.exact_counts["TS"][("वाव", ("U", "U"))] == 80


def test_major_corpora_skip_tags_and_slash_group():
  c = VedicCorpusCounter()
  for corp, word, freq in [
    ("TS", "अ᳓नृतम्", 3),
    ("RV", "अ᳓नृतम्", 18),
    ("TB", "अ᳓नृतात्", 1),
    ("TB", "अ᳓नृतम्", 6),
    ("AV", "अ᳓नृतम्", 13),
    ("ŚB", "अ᳓नृतात्", 20),
    ("ŚB", "मानुषः᳓", 21),
    ("TS", "मानुष᳓म्", 3),
    ("TS", "मानुषः᳓", 0),
  ]:
    if freq == 0:
      continue
    km = word_to_key_and_marks(word)
    assert km is not None
    c._add(corp, km[0], km[1], freq=freq)
  c._finalize_secondary_tables()

  # 1. Custom major_corpora omits ŚB auto-injection, and slash-joined *RV*/*TS* stays intact & idempotent
  ln1, _ = annotate_padapatha_line_counts(
    "- अ᳓नृतात् (*VS* १.५, *RV*/*TS* अ᳓नृतम्)",
    c,
    major_corpora=("TS", "RV", "TB", "AV", "VS"),
    skip_tags=frozenset({"ŚB"}),
  )
  assert "*ŚB*" not in ln1
  assert "*RV*-0/18/*TS*-3" in ln1
  assert "*TB*-1/7" in ln1 and "*AV*-0/13" in ln1
  assert annotate_padapatha_line_counts(
    ln1, c, major_corpora=("TS", "RV", "TB", "AV", "VS"), skip_tags=frozenset({"ŚB"})
  )[0] == ln1

  # 2. skip_tags preserves editorial *ŚB* verbatim without self-referential counts or pruning
  ln2, unres2 = annotate_padapatha_line_counts(
    "- मानुषः᳓ (*MW*; *ŚB*)",
    c,
    prune_unverified_standalone_tags=True,
    major_corpora=("TS", "RV", "TB", "AV", "VS"),
    skip_tags=frozenset({"ŚB"}),
  )
  assert ln2.endswith("; *ŚB*)")
  assert "*ŚB*-" not in ln2
  assert unres2 == []
