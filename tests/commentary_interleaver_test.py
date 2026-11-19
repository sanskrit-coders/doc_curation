"""Unit tests for ``doc_curation.md.content_processor.commentary.interleaver``."""
from doc_curation.md.content_processor.commentary import interleaver


def test_interleave_tika_below_mula_vedic_accents_bold_and_custom_title(tmp_path):
  dest = tmp_path / "dest.md"
  comm = tmp_path / "comm.md"
  dest.write_text(
    "+++\ntitle = \"test\"\n+++\n\n"
    "<details><summary>मूलम्</summary>\n\n"
    "हिर॑ण्यवर्णा॒श् शुच॑यᳶ पाव॒का +++(=शोधकाः)+++ ।\n"
    "</details>\n\n"
    "<details><summary>मूलम्</summary>\n\n"
    "ऽहोरा॒त्रे नि॑मे॒षो॑ , ऽर्धमा॒साᳶ पर्वा॑णि ।\n"
    "</details>\n",
    encoding="utf-8",
  )
  comm.write_text(
    "**हिरण्यवर्णाः** हितरमणीयवर्णाः । 'पावकादीनां छन्दसि' इतीत्वाभावः । "
    "'तद्दशहोताऽन्वसृज्यत । प्रजापतिर्वै दशहोता' इति ब्राह्मणम् ॥\n\n"
    "अहोरात्रे इत्य् अनेन कालो लक्ष्यते ॥\n",
    encoding="utf-8",
  )

  res = interleaver.interleave_TIkA_below_mUla(
    str(dest), str(comm), tika_title="भट्टभास्कर-टीका"
  )
  assert res["inserted"] == 2
  txt = dest.read_text(encoding="utf-8")
  assert txt.count("<summary>भट्टभास्कर-टीका</summary>") == 2
  # First tika placed under first mula (with single-quoted sutra + internal danda preserved intact!)
  first_mula_end = txt.index("</details>")
  second_mula_start = txt.index("<details><summary>मूलम्</summary>", first_mula_end)
  between = txt[first_mula_end:second_mula_start]
  assert "हितरमणीयवर्णाः" in between
  assert "प्रजापतिर्वै दशहोता" in between

  ver = interleaver.verify_sentence_order(
    str(dest), str(comm), tika_title="भट्टभास्कर-टीका"
  )
  assert ver["ok"], ver


def test_realign_and_remove_custom_tika_title_hyphenated_compounds(tmp_path):
  dest = tmp_path / "sri.md"
  dest.write_text(
    "<details><summary>मूलम्</summary>\nसत्यपि दीपे विषयप्रकाशाभावात्।\n</details>\n\n"
    "<details><summary>मूलम्</summary>\nतत्स्वरूपज्ञाननिवर्त्यं तदज्ञानम्।\n</details>\n\n"
    "<details><summary>श्रुत-प्रकाशिका</summary>\n"
    "उपपादयति - सत्यपीति । शङ्कते - तत्-स्वरूप-ज्ञान-निवर्त्यम् इति ।\n"
    "</details>\n",
    encoding="utf-8",
  )

  rep = interleaver.realign_TIkA_below_mUla(
    str(dest), start_string="उपपादयति", tika_title="श्रुत-प्रकाशिका"
  )
  assert rep["ok"] and rep["changed"]
  txt = dest.read_text(encoding="utf-8")
  assert txt.count("<summary>श्रुत-प्रकाशिका</summary>") == 2

  rem = interleaver.remove_commentary_blocks(
    str(dest), start_string="तत्स्वरूपज्ञान", tika_title="श्रुत-प्रकाशिका"
  )
  assert rem["ok"] and rem["removed"] == 1
  assert dest.read_text(encoding="utf-8").count("<summary>श्रुत-प्रकाशिका</summary>") == 1
