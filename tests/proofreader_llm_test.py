"""Unit tests for ``doc_curation.llm.proofreader``."""
import json
import random

from doc_curation.llm.proofreader import (
  DEFAULT_LOCAL_ADAPTER_DIR,
  INTERLEAVER_SYSTEM_PROMPT,
  PADAPATHA_ACCENT_SYSTEM_PROMPT,
  ProofreaderBackend,
  build_system_prompt,
  canonical_sandhi_skeleton,
  enforce_post_guards,
  mask_protected_blocks,
  rejoin_merger_violations,
  restore_protected_blocks,
  save_adapter_locally,
  wrap_silent_mutations,
)
from doc_curation.llm.proofreader.dataset import clean_prastuti_target, unsplit_sanskrit_to_raw
from doc_curation.llm.proofreader.dataset.text_normalizer import inject_realistic_ocr_typo
from doc_curation.llm.proofreader.interleave_helper import (
  annotate_translation_matcher_prompt,
  assemble_cluster_blocks,
  parse_interleave_json,
  split_quote_safe_segments,
  summary_for_role,
)


def test_prompts_toggle_clause_newlines_and_extra():
  p_off = build_system_prompt(clause_newlines=False, suggest_corrections=True)
  p_on = build_system_prompt(
    clause_newlines=True,
    suggest_corrections=False,
    extra_instructions="Always put each हेतुः phrase on a fresh line.",
  )
  assert "Inline-Only Line Flow" in p_off
  assert "Sentence & Syntactic Phrase / Clause Line Breaks" in p_on
  assert "Do NOT alter source characters" in p_on
  assert "Always put each हेतुः phrase on a fresh line." in p_on


def test_mask_and_restore_mulam_blocks():
  src = (
    "अथ जगत्कारणम्।\n\n"
    "<details><summary>मूलम्</summary>\nजगत्कारणं ब्रह्मेति।\n</details>\n\n"
    "इत्य् उक्तम्।"
  )
  masked, masks = mask_protected_blocks(src)
  assert "<<MULAM_0000>>" in masked
  assert "जगत्कारणं ब्रह्मेति" not in masked
  restored = restore_protected_blocks(masked, masks)
  assert restored == src


def test_canonical_sandhi_skeleton_equivalence():
  pairs = [
    ("इत्येवम्", "इत्य् एवम्"),
    ("मध्वरिः", "मध्व्-अरिः"),
    ("रामोऽस्ति", "रामो ऽस्ति"),
    ("फलमश्नुते", "फलम् अश्नुते"),
    ("जगत्कारणम्", "जगत्-कारणम्"),
    ("चिदचिद्विलक्षणस्य", "चिद्-अचिद्-विलक्षणस्य"),
    ("देवं सेवितुमेव", "देवं सेवितुम् एव"),
  ]
  for a, b in pairs:
    assert canonical_sandhi_skeleton(a) == canonical_sandhi_skeleton(b), f"{a} vs {b}"


def test_rejoin_merger_violations():
  raw = "धर्मार्थकामाः महोत्सवः स्वप्रकाशाद्वितीयम् मध्वरिः"
  bad_llm = "धर्म-अर्थ-कामाः महा-उत्सवः स्वप्रकाश-अद्वितीयम् मध्व्-अरिः"
  fixed = rejoin_merger_violations(raw, bad_llm)
  assert "धर्मार्थ-कामाः" in fixed
  assert "महोत्सवः" in fixed
  assert "स्वप्रकाशाद्वितीयम्" in fixed
  # Valid separable yaṇ split must remain split!
  assert "मध्व्-अरिः" in fixed


def test_wrap_silent_mutations():
  raw = "जगत्कारणे तषमपि अर्थस्वभावात् क्रियते।"
  # Suppose LLM hyphenated जगत्कारणे and अर्थस्वभावात् cleanly, but SILENTLY changed तषमपि -> तेषाम् अपि
  silent_out = "जगत्-कारणे तेषाम् अपि अर्थ-स्वभावात् क्रियते।"
  guarded = enforce_post_guards(raw, silent_out, allow_suggestions=True)
  assert "जगत्-कारणे" in guarded
  assert "अर्थ-स्वभावात्" in guarded
  assert "[[तषमपि|तेषाम् अपि]]" in guarded

  # With allow_suggestions=False, silent lexical edits revert to original token
  reverted = enforce_post_guards(raw, silent_out, allow_suggestions=False)
  assert "तषमपि" in reverted
  assert "[[" not in reverted


def test_clean_prastuti_and_unsplit_roundtrip():
  curated = (
    "शिलं+++(=पतितधान्यम्)+++ किम् अनलं भवेद्\n"
    "पेटिकाभेद--तत्-सङ्गती [[तषमपि|तेषाम् अपि]] आह।"
  )
  cleaned = clean_prastuti_target(curated)
  assert "+++" not in cleaned
  assert "पेटिकाभेद–तत्-सङ्गती" in cleaned
  raw = unsplit_sanskrit_to_raw(cleaned, random.Random(0), hard_wrap_prob=0.0)
  assert "पेटिकाभेदतत्सङ्गती" in raw
  assert "तषमपि" in raw
  assert "[[" not in raw


def test_interleave_helper_quote_safe_and_assembly():
  comm = 'अत्र "भद्रं कर्णेभिः । स्वस्ति नः" इति मन्त्रद्वयं पठति । ततः शूर्पम् आदत्ते ॥'
  segs = split_quote_safe_segments(comm)
  # Internal danda inside quotes must NOT split the quoted mantra!
  assert len(segs) == 2
  assert '"भद्रं कर्णेभिः । स्वस्ति नः"' in segs[0]

  clusters = [
    {
      "vp": "<details open><summary>विश्वास-प्रस्तुतिः</summary>\nवेषा᳓य त्वा।\n</details>",
      "mula": "<details><summary>मूलम्</summary>\nवेषा॑य त्वा ।\n</details>",
    }
  ]
  plan = parse_interleave_json(
    json.dumps({
      "assignments": [
        {"seg": 0, "core": 0, "role": "viniyoga"},
        {"seg": 1, "core": 0, "role": "tika"},
      ],
      "unmatched_from": 2,
    }),
    num_cores=1,
    num_segments=2,
  )
  md, withheld = assemble_cluster_blocks(
    clusters,
    ["शूर्पम् आदत्ते", "वेषाय त्वेति[^12] ॥"],
    plan,
    author_label="भट्टभास्करः",
    is_sarvash_tikah=False,
  )
  assert summary_for_role("भट्टभास्करः", "viniyoga") == "भास्करोक्त-विनियोगः"
  assert md.index("भास्करोक्त-विनियोगः") < md.index("विश्वास-प्रस्तुतिः") < md.index("मूलम्") < md.index("भट्टभास्कर-टीका")
  assert "[12]" in md and "[^12]" not in md
  assert withheld == []

  # In sarvASh_TIkAH, viniyoga blocks must be withheld for the host file!
  md_st, withheld_st = assemble_cluster_blocks(
    clusters,
    ["शूर्पम् आदत्ते", "वेषाय त्वेति ॥"],
    plan,
    author_label="भट्टभास्करः",
    is_sarvash_tikah=True,
  )
  assert "भास्करोक्त-विनियोगः" not in md_st
  assert len(withheld_st) == 1


def test_backend_monkeypatched_with_guards(monkeypatch):
  b = ProofreaderBackend(base_url="http://mock.local/v1")

  def fake_chat(messages, model_id=None):
    # Echo user text with one valid split, one bad dīrgha split, and one silent mutation
    return "<think>reasoning</think>\nधर्म-अर्थ जगत्-कारणे तेषाम् अपि <<MULAM_0000>>", {"total_tokens": 20}

  monkeypatch.setattr(b, "_chat_completion", fake_chat)
  inp = "धर्मार्थ जगत्कारणे तषमपि <details><summary>मूलम्</summary>जगत्कारणे</details>"
  chat = b.new_chat(build_system_prompt())
  out = chat.send_text(inp)
  assert "<think>" not in out
  assert "धर्मार्थ" in out  # merger veto restored!
  assert "जगत्-कारणे" in out  # valid samāsa split kept!
  assert "[[तषमपि|तेषाम् अपि]]" in out  # silent edit wrapped!
  assert "<details><summary>मूलम्</summary>जगत्कारणे</details>" in out  # मूलम् intact!


def test_us_accent_and_detail_split_preservation():
  raw = (
    "<!-- Proofreader-DETAIL-SPLIT 0001 -->\n"
    "विश्व᳓कर्मणः समवर्तता᳓धि । नान्यः᳓ प᳓न्था विद्यते᳓ऽयनाय ।"
  )
  hyp_out = (
    "<!-- Proofreader-DETAIL-SPLIT 0001 -->\n"
    "विश्व᳓-कर्मणः समवर्तता᳓धि । नान्यः᳓ प᳓न्था विद्यते᳓ ऽयनाय ।"
  )
  guarded = enforce_post_guards(raw, hyp_out, allow_suggestions=True)
  assert guarded == hyp_out


def test_cross_newline_sandhi_reversion_and_missing_danda_allowed():
  """Updated proofreader-hyphenator skill: reverting dīrgha/guṇa/vṛddhi/visarga
  sandhi across phrase/clause/quote newlines AND inserting missing sentence dandas
  must NOT be flagged as silent lexical mutations, while inline mergers stay joined."""
  raw = (
    "पित्रा सवित्रा निश्चिते सतीक्षणादयः प्रधानस्याचेतनस्यैवंरूपो "
    "पृष्टो मृत्युस्तस्यार्थस्य धर्म-अर्थ परमात्मेति सन्दिह्यते।"
  )
  raw_merged = raw.replace("धर्म-अर्थ", "धर्मार्थ")
  llm_out = (
    "पित्रा सवित्रा।  \n"
    "निश्चिते सति  \n"
    "ईक्षणादयः प्रधानस्याचेतनस्य  \n"
    "एवं-रूपो पृष्टो मृत्युः  \n"
    "तस्यार्थस्य धर्म-अर्थ परमात्मा\n\n"
    "इति सन्दिह्यते।"
  )
  guarded = enforce_post_guards(raw_merged, llm_out, allow_suggestions=True)
  # Inline dīrgha merger violation धर्म-अर्थ must snap back to धर्मार्थ:
  assert "धर्मार्थ" in guarded
  # Cross-newline dīrgha/vṛddhi/guṇa/visarga splits + inserted danda must stay clean (zero [[...|...]]):
  assert "[[" not in guarded
  assert "पित्रा सवित्रा।  \n" in guarded
  assert "निश्चिते सति  \nईक्षणादयः" in guarded
  assert "प्रधानस्याचेतनस्य  \nएवं-रूपो" in guarded
  assert "पृष्टो मृत्युः  \nतस्यार्थस्य" in guarded
  assert "परमात्मा\n\nइति" in guarded


def test_word_indexed_translation_matcher_and_multiline_typos(tmp_path):
  raw_tm = (
    "Match 2 Sanskrit cores to English words.\n\n"
    "TRANSLATION WORDS:\n"
    "Now therefore the inquiry into Brahman.\n\n"
    "Reply with ONLY this JSON: {}"
  )
  indexed = annotate_translation_matcher_prompt(raw_tm)
  assert "[0] Now [1] therefore [2] the [3] inquiry [4] into [5] Brahman." in indexed
  # Idempotent when called twice
  assert annotate_translation_matcher_prompt(indexed) == indexed

  multiline_curated = (
    "तत्र धर्मार्थ-कामानां कारण-विशेषे निश्चिते सति  \n"
    "ईक्षणादयः प्रवर्तन्ते  \n"
    "इति प्रारब्धं जगत्-कारणम्।"
  )
  res = inject_realistic_ocr_typo(multiline_curated, random.Random(7), max_typos=2)
  assert res is not None
  raw_in, target_out = res
  assert "  \n" in target_out
  assert "[[" in target_out and "|" in target_out
  assert all("\n" not in m for m in target_out.split("[[")[1:] if "]]" in m.split("]]")[0])
  assert "  \n" not in raw_in

  # Verify save_adapter_locally copies adapter + eval_report and writes .gitignore
  fake_kout = tmp_path / "kout"
  (fake_kout / "adapter").mkdir(parents=True)
  (fake_kout / "adapter" / "adapter_config.json").write_text('{"r": 16}', encoding="utf-8")
  (fake_kout / "adapter" / "README.md").write_text("# PEFT card", encoding="utf-8")
  (fake_kout / "eval_report.json").write_text('{"ok": true}', encoding="utf-8")
  dest = save_adapter_locally(str(fake_kout), str(tmp_path / "saved_lora"))
  assert (dest / "adapter_config.json").is_file()
  assert (dest / "MODEL_CARD.md").is_file()
  assert (dest / "eval_report.json").is_file()
  assert "*.safetensors" in (dest / ".gitignore").read_text(encoding="utf-8")
  assert DEFAULT_LOCAL_ADAPTER_DIR.endswith("qwen3-14b-sanskrit-lora")


def test_slp1_codec_roundtrip_accents_avagraha_and_clause_breaks():
  from doc_curation.sanskrit.hyphenator.slp1_codec import (
    apply_slp1_predictions_to_text,
    encode_curated_sentence,
  )

  # 1.Curated encoding -> oracle decoding round-trip with lost avagraha & samāsa
  curated = "रामो ऽर्थः मध्व्-अरिः विश्व᳓-कर्मणः"
  enc = encode_curated_sentence("रामो ऽर्थः मध्व्-अरिः विश्व-कर्मणः", random.Random(1))
  assert enc is not None

  # 2. Oracle predictor test on accented Vedic + lost avagraha + merger veto
  def mock_oracle(slp_s: str):
    # "rAmorTaH viSvakarmaRaH DarmArTa"
    sep = [0] * len(slp_s)
    cl = [0] * len(slp_s)
    if "rAmorTaH" in slp_s:
      idx = slp_s.index("rAmorTaH")
      sep[idx + 3] = 4  # 'o' -> SPACE_AVAGRAHA (" Z")
    if "viSvakarmaRaH" in slp_s:
      idx = slp_s.index("viSvakarmaRaH")
      sep[idx + 4] = 1  # 'a' -> HYPHEN
    if "DarmArTa" in slp_s:
      # Deliberately try illegal split inside dīrgha merger A -> must be vetoed!
      idx = slp_s.index("DarmArTa")
      sep[idx + 4] = 1
    return sep, cl

  out = apply_slp1_predictions_to_text("रामोर्थः विश्व᳓कर्मणः धर्मार्थ", mock_oracle)
  assert out == "रामो ऽर्थः विश्व᳓-कर्मणः धर्मार्थ"


def test_text_to_blocks_skill_both_local_and_14b_backend(monkeypatch):
  from doc_curation.llm.proofreader import (
    group_sense_unit_blocks,
    has_genuine_iti,
    split_into_danda_segments,
    text_to_vipra_mula_blocks,
  )

  # Test 4 √i ("eti") vs genuine "iti" discriminator
  for v_eti in ("उपैति", "पर्येति", "समवेति", "पुनरेति", "अध्येति", "आयुरेति"):
    assert not has_genuine_iti(f"स एतम् {v_eti} ।"), f"{v_eti} falsely matched iti"
  for real_iti in ("उपैतीति", "भिषज्यतमेति", "दानकामा मे प्रजाः स्युरिति", "प्रजापतिर् इति"):
    assert has_genuine_iti(real_iti), f"{real_iti} missed genuine iti"

  # Test 2(a): Protasis -> Apodosis
  t2a = split_into_danda_segments("यः का॒मये॑त॒ दान॑कामा मे प्र॒जाः स्यु॒रिति॑ । स पूर्व॑योः॒ फल्गु॑न्योर॒ग्निमाद॑धीत ॥")
  assert len(group_sense_unit_blocks(t2a)) == 1

  # Test 2(b): Main statement -> Explanatory yad
  t2b = split_into_danda_segments("अ॒र्य॒म्णो वा ए॒तन्नक्ष॑त्रम् । यत्पूर्वे॒ फल्गु॑नी ।")
  assert len(group_sense_unit_blocks(t2b)) == 1

  # Test 2 exception: Self-contained yad...tad sentence must NOT force-merge next sentence
  t2_self = split_into_danda_segments(
    "यदा ह्येवैष प्रतिष्ठां विन्दते, अथ सोऽभयं गतो भवति । तदेष श्लोको भवति ।"
  )
  assert len(group_sense_unit_blocks(t2_self)) == 2

  # Test 3: Quotation embedded inside conditional
  t3 = split_into_danda_segments(
    "स᳓ य᳓द् ब्रूया᳓त् ॥ क᳓स् ता᳓नि नि᳓रमिमी᳓त_इ᳓ति ॥ प्रजा᳓पतिर् इ᳓ति ब्रूयात् ॥"
  )
  assert len(group_sense_unit_blocks(t3)) == 1

  # Test 4: Multi-sentence quotation with sandhi-fused -meti + reference numbers kept attached
  t4 = split_into_danda_segments(
    "१। ५। ११। २॥ ५६ सो॑ऽब्रवीत् । स॒प्त॒द॒शेन॑ ह्रि॒यमा॑णो॒ व्य॑लेशिषि । भि॒षज्य॑त॒मेति॑ ।"
  )
  b4 = group_sense_unit_blocks(t4)
  assert len(b4) == 1 and b4[0].startswith("१। ५। ११।")

  # Test 5: Sequential -tvA absolutive with (33) ref + editorial gloss supplied verb vs bare atha/dative
  t5 = split_into_danda_segments("स तप॑स्त॒प्त्वा । (33) अन्नं॒ ब्रह्मेति॒ व्य॑जानात् ।")
  assert len(group_sense_unit_blocks(t5)) == 1

  t5_bare = split_into_danda_segments("केशान् प्रवपति । अथ श्मश्रूणि । रक्षसाम् अपहत्यै ।")
  assert len(group_sense_unit_blocks(t5_bare)) == 1

  t5_glossed = split_into_danda_segments("केशान् प्रवपति । अथ श्मश्रूणि +++(प्रवपति)+++ ।")
  assert len(group_sense_unit_blocks(t5_glossed)) == 2

  # End-to-end vipra + mula block generation: (A) Local hyphenator path
  bare_vedic = "सो॑ऽब्रवीत् । भि॒षज्य॑त॒मेति॑ +++(अवदत्)+++ ।"
  blocks_local = text_to_vipra_mula_blocks(bare_vedic, use_local_hyphenator=True)
  assert blocks_local.count("<summary>विश्वास-प्रस्तुतिः</summary>") == 1
  assert "+++(अवदत्)+++" in blocks_local.split("<summary>मूलम्</summary>")[0]
  assert "+++" not in blocks_local.split("<summary>मूलम्</summary>")[1]
  assert "\u1cd3" in blocks_local.split("<summary>मूलम्</summary>")[0]  # US accent ᳓ in VP
  assert "सो॑ऽब्रवीत्" in blocks_local.split("<summary>मूलम्</summary>")[1]  # original ॑ in मूलम्

  # End-to-end vipra + mula + translation-guided merge: (B) 14B ProofreaderBackend path
  b_llm = ProofreaderBackend(base_url="http://mock.local/v1")

  def fake_chat(messages, model_id=None):
    u = messages[-1]["content"]
    if "merge_after" in u:
      return '{"merge_after": [0]}', {}
    return u.replace("जगत्कारणम्", "जगत्-कारणम्"), {}

  monkeypatch.setattr(b_llm, "_chat_completion", fake_chat)
  segs_tr = split_into_danda_segments("अग्निर् ज्योतिः । इन्द्रो ज्योतिः ।")
  merged_tr = group_sense_unit_blocks(
    segs_tr, backend=b_llm, translation_hint="Agni is light and Indra is light (single invocation)."
  )
  assert len(merged_tr) == 1
  blocks_14b = text_to_vipra_mula_blocks("अथ जगत्कारणम् ।", backend=b_llm)
  assert "जगत्-कारणम्" in blocks_14b.split("<summary>मूलम्</summary>")[0]
  assert "जगत्कारणम्" in blocks_14b.split("<summary>मूलम्</summary>")[1]


def test_interleave_aligner_sandhi_roles_upcoming_and_end_to_end(monkeypatch):
  from doc_curation.llm.proofreader import (
    align_commentary_segments,
    interleave_source_into_markdown,
    refine_interleave_plan,
  )

  # 1. Prefix-sensitive derivative headwords + upcoming_cores cutoff
  cores_rain = ["वर्ष॑ते॒ स्वाहा॑ ।", "अ॒भि॒वर्ष॑ते॒ स्वाहा॑ ।", "प॒रि॒वर्ष॑ते॒ स्वाहा॑ ।"]
  segs_rain = [
    "वर्षणं धारापातनम् ।",
    "अभिवर्षणं उपर्युपरि वर्षणम् ।",
    "परिवर्षणं सर्वतो वर्षणम् ।",
    "संवर्षणं सङ्गतपटलवर्षणम् ।",
  ]
  plan_rain = align_commentary_segments(cores_rain, segs_rain, upcoming_cores=["सं॒वर्ष॑ते॒ स्वाहा॑ ।"])
  assert plan_rain["unmatched_from"] == 3
  assert [a["core"] for a in plan_rain["assignments"]] == [0, 1, 2]

  # 2. Multi-rk vs single-rk chandas + viniyoga kalpa continuation + sutra quote masking
  cores_ved = [
    "धा॒ता द॑दातु नो र॒यिम् ईशा॑नो॒ जग॑त॒स्पतिः॑ । स नः॑ पू॒र्णेन॑ वावनत् ।",
    "धा॒ता प्र॒जाया॑ उ॒त रा॒य ई॑शे धा॒ता पु॒त्रं यज॑मानाय॒ दाता॑ ।",
  ]
  segs_ved = [
    "तिस्रस्त्रिष्टुभः ॥",  # multi-rk chandas -> avatarika
    "सीमन्तोन्नयने होममन्त्राः - धाता ददात्विति ॥",  # -> viniyoga
    "तत्र पुरोनुवाक्यामाह-",  # kalpa continuation -> viniyoga
    "प्रथमा त्रिष्टुप् । धाता विश्वस्य धारयिता नो धनं ददातु ।",  # single-rk chandas + gloss -> tika (core 0)
    "'षष्ठ्याः पतिपुत्र' इति सत्वम् । स देवोस्मान् पूर्णेन वावनत् ॥",  # sutra quote 'पतिपुत्र' must NOT jump to core 1!
    "धाता प्रजायाः पुत्रादेः ईशे ईष्टे । धातेव पुत्रं यजमानाय दाता ॥",  # -> tika (core 1)
  ]
  plan_ved = align_commentary_segments(cores_ved, segs_ved)
  assert plan_ved["assignments"] == [
    {"seg": 0, "core": 0, "role": "avatarika"},
    {"seg": 1, "core": 0, "role": "viniyoga"},
    {"seg": 2, "core": 0, "role": "viniyoga"},
    {"seg": 3, "core": 0, "role": "tika"},
    {"seg": 4, "core": 0, "role": "tika"},
    {"seg": 5, "core": 1, "role": "tika"},
  ]

  # 3. Hyphenated samāsa pratīkas (`तत्-स्वरूप-...`), savarṇadīrgha (`सत्यपीति`), & end-pratīka dominance
  cores_sp = [
    "सत्यपि दीपे ज्ञानेन विना विषयप्रकाशाभावात्।",
    "प्रतिपन्नश्चेत्; तत्स्वरूपज्ञाननिवर्त्यं तदज्ञानं कथमिव तिष्ठति।",
  ]
  segs_sp = [
    "कथं प्रकाशकत्वम् इति शङ्कायां तद् उपपादयति - सत्यपीति ।",
    "विषयप्रकाशाभावाद् इत्य् उक्त्वा इदानीम् उत्तरं शङ्कते - तत्-स्वरूप-ज्ञान-निवर्त्यम् इति ।",
  ]
  plan_sp = align_commentary_segments(cores_sp, segs_sp)
  assert [a["core"] for a in plan_sp["assignments"]] == [0, 1]

  # 4. End-to-end interleave_source_into_markdown (local + post-guarded LLM + sarvASh_TIkAH withholding)
  host_md = (
    "+++\ntitle = \"test\"\n+++\n\n"
    "## अनुवाकः १\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nवेषा᳓य त्वा।\n</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nवेषा॑य त्वा ।\n</details>\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nमे॒घाय॒ स्वाहा᳓।\n</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nमे॒घाय॒ स्वाहा॑ ।\n</details>\n"
  )
  src_comm = (
    "**प्रथमः खण्डः॥**\n\n"
    "शूर्पम् आदत्ते - वेषाय त्वेति ॥\n\n"
    "**वेषाय** वेवेष्टि व्याप्नोतीति वेषः कामः, तस्मै **त्वा** ।\n\n"
    "मेघाय वर्षहेतवे[^5] ॥"
  )
  res_local = interleave_source_into_markdown(
    host_md, src_comm, author_label="भट्टभास्करः", is_sarvash_tikah=False, backend=None
  )
  assert res_local["verification"]["ok"], res_local["verification"]
  md_out = res_local["markdown"]
  assert "### प्रथमः खण्डः" in md_out
  assert md_out.index("भास्करोक्त-विनियोगः") < md_out.index("विश्वास-प्रस्तुतिः")
  assert "[5]" in md_out and "[^5]" not in md_out

  res_st = interleave_source_into_markdown(
    host_md, src_comm, author_label="भट्टभास्करः", is_sarvash_tikah=True, backend=None
  )
  assert res_st["verification"]["ok"]
  assert "विनियोगः" not in res_st["markdown"]
  assert len(res_st["withheld_viniyogas"]) == 1

  # refine_interleave_plan snaps broken LLM core assignment back onto unique strong pratīka anchor
  bad_llm_plan = {
    "assignments": [
      {"seg": 0, "core": 0, "role": "tika"},
      {"seg": 1, "core": 0, "role": "tika"},  # Wrong: तत्-स्वरूप-ज्ञान-निवर्त्यम् uniquely anchors CORE 1!
    ],
    "unmatched_from": 2,
  }
  repaired = refine_interleave_plan(bad_llm_plan, cores_sp, segs_sp)
  assert [a["core"] for a in repaired["assignments"]] == [0, 1]


def test_translation_interleaving_c0_bug_bilingual_dp_and_custom_title(tmp_path):
  from doc_curation.llm import translation_matcher
  from doc_curation.llm.proofreader import (
    align_cores_to_translation_dp,
    refine_translation_mapping,
  )

  # 1. Regression for c_start == 0 (`[0]` in CORE TEXTS must NOT suppress word indexing!)
  raw_c0 = translation_matcher._prompt_for_batch(
    ["एवं च सति ब्रह्मशब्दो मुख्यः।", "तत्र सन्देहः – किमिह प्रत्यगात्मा;", "किं युक्तम्?"],
    c_start=0,
    en_window=(
      "This being so, the word Brahman is primary. "
      "--Here a doubt arises whether it is the individual soul. "
      "--The Purvapakshin replies."
    ).split(),
    e_start=0,
    total_core=4,
    total_en=21,
    upcoming=(3, ["क्षेत्रज्ञ इति।"]),
  )
  # Even with `[0]` in legacy style, annotate_translation_matcher_prompt must still index words
  legacy_c0 = raw_c0.replace("core[0]:", "[0]")
  ann = annotate_translation_matcher_prompt(legacy_c0)
  assert "TRANSLATION WORDS (pre-indexed" in ann
  assert "[0] This" in ann
  assert "split it yourself by regex" not in ann
  assert "BILINGUAL ANCHOR PRIOR" in ann

  # 2. Local bilingual DP aligns pivots (`This being so`, `--Here a doubt`), skips `किं युक्तम्?`,
  #    and stops at `next_en=18` before `--The Purvapakshin replies.`!
  en_w = (
    "This being so, the word Brahman is primary. "
    "--Here a doubt arises whether it is the individual soul. "
    "--The Purvapakshin replies."
  ).split()
  dp_res = align_cores_to_translation_dp(
    ["एवं च सति ब्रह्मशब्दो मुख्यः।", "तत्र सन्देहः – किमिह प्रत्यगात्मा;", "किं युक्तम्?"],
    en_w,
    c_start=0,
    upcoming_cores=["क्षेत्रज्ञ इति।"],
  )
  assert dp_res == {"starts": {"0": 0, "1": 8, "2": 18}, "skip": [2], "next_en": 18}

  # 3. refine_translation_mapping repairs 2x-doubled indices & snaps ±1 off-by-one onto sentence break
  doubled_reply = json.dumps({"starts": {"0": 0, "1": 16, "2": 36}, "skip": [2], "next_en": 36})
  fixed_doubled = json.loads(refine_translation_mapping(doubled_reply, ann))
  assert fixed_doubled == {"starts": {"0": 0, "1": 8, "2": 18}, "skip": [2], "next_en": 18}

  off_by_one = json.dumps({"starts": {"0": 0, "1": 7, "2": 18}, "skip": [], "next_en": 18})
  snapped = json.loads(refine_translation_mapping(off_by_one, ann))
  assert snapped["starts"]["1"] == 8 and snapped["skip"] == [2]

  # 4. End-to-end insert_translation_details with generate_fn=None (local DP) & custom translation_title
  md_file = tmp_path / "host.md"
  tr_file = tmp_path / "01.md"
  md_file.write_text(
    "+++\ntitle = \"test\"\n+++\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nएवं च सति ब्रह्म-शब्दो मुख्यः।\n</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nएवं च सति ब्रह्मशब्दो मुख्यः।\n</details>\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nतत्र सन्देहः – किम् इह प्रत्यगात्मा।\n</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nतत्र सन्देहः – किमिह प्रत्यगात्मा।\n</details>\n",
    encoding="utf-8",
  )
  tr_file.write_text(
    "This being so, the word Brahman is primary.[^1]\n\n"
    "--Here a doubt arises whether it is the individual soul.\n\n"
    "[^1]: Primary sense note.\n",
    encoding="utf-8",
  )
  summary = translation_matcher.insert_translation_details(
    str(md_file), str(tr_file), generate_fn=None, translation_title="Thibaut"
  )
  assert summary["status"] == "done" and summary["sentences"] == 2 and summary["notes"] == 1
  final_md = md_file.read_text(encoding="utf-8")
  assert final_md.count("<summary>Thibaut</summary>") == 2
  assert "<summary>Thibaut - Note</summary>" in final_md







