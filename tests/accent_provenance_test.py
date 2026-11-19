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

  # 5. Final stop voicing equivalence (`उ᳓त्` matches Taittirīya `उ᳓द्`)
  ln_ut, unres_u = annotate_padapatha_line_counts("- उ᳓त् (*TS*, *RV*)", counter)
  assert ln_ut == "- उ᳓त् (*TS*-210, *RV*-340)"
  assert unres_u == []


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
