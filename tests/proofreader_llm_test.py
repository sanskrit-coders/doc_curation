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



