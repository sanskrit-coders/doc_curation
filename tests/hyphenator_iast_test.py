"""Unit tests for IAST Sanskrit hyphenation and validation helpers."""
from doc_curation.sanskrit.hyphenator import (
  apply_iast_hyphenation_map,
  build_validated_iast_map,
  find_iast_merger_violations,
  has_iast_merger_violation,
  iast_to_devanagari,
  is_valid_iast_hyphen_edit,
  reconcile_iast_hyphenation,
)


def test_iast_to_devanagari_normalizes_anusvara_and_quotes():
  assert iast_to_devanagari("Saṁrāṭ nā’lpe") == "संराट् नाऽल्पे"


def test_is_valid_iast_hyphen_edit_compound_and_sandhi():
  # Valid plain samāsa splits
  assert is_valid_iast_hyphen_edit("Bhagavadgītā", "Bhagavad-gītā")
  assert is_valid_iast_hyphen_edit("Devyaparādha", "Devy-aparādha")
  # Valid separable sandhi splits
  assert is_valid_iast_hyphen_edit("Harimīḍe", "Harim īḍe")
  assert is_valid_iast_hyphen_edit("tvātmacaturtha", "tv ātma-caturtha")

  # Inline dīrgha / guṇa / vṛddhi merger-veto violations must be rejected
  assert has_iast_merger_violation("dharmārtha", "dharma-artha")
  assert not is_valid_iast_hyphen_edit("dharmārtha", "dharma-artha")
  assert not is_valid_iast_hyphen_edit("mahotsava", "maha-utsava")
  assert not is_valid_iast_hyphen_edit("sadaiva", "sadā-eva")
  assert not is_valid_iast_hyphen_edit("Advaitabhāvopaniṣad", "Advaita-bhāva-upaniṣad")

  # Casing, non-IAST, English-derived words, and lexical mutations rejected
  assert not is_valid_iast_hyphen_edit("Bhagavadgītā", "bhagavad-gītā")
  assert not is_valid_iast_hyphen_edit("Vaiṣṇavism", "Vaiṣṇav-ism")
  assert not is_valid_iast_hyphen_edit("Upaniṣadic", "Upa-niṣadic")
  assert not is_valid_iast_hyphen_edit("philosophy", "philo-sophy")
  assert not is_valid_iast_hyphen_edit("kṛṣṇa", "kṛṣna")


def test_build_validated_iast_map_filters_and_expands_case():
  raw = {
    "Bhagavadgītā": "Bhagavad-gītā",
    "dharmārtha": "dharma-artha",  # merger veto -> rejected
    "varṇādharma": "varṇa-dharma",  # silent edit -> rejected
    "salokatā": "sa-lokatā",  # excluded -> rejected
  }
  vetted = build_validated_iast_map(raw, excluded_tokens={"salokatā"}, expand_case_variants=True)
  assert vetted["Bhagavadgītā"] == "Bhagavad-gītā"
  assert vetted["bhagavadgītā"] == "bhagavad-gītā"
  assert "dharmārtha" not in vetted
  assert "varṇādharma" not in vetted
  assert "salokatā" not in vetted


def test_apply_iast_hyphenation_map_preserves_markup_and_splits_subtokens():
  hmap = build_validated_iast_map(
    {
      "Ekavrātya": "Eka-vrātya",
      "Śrautasūtra": "Śrauta-sūtra",
      "karmayoga": "karma-yoga",
      "Varṇadharma": "Varṇa-dharma",
    },
    expand_case_variants=True,
  )
  src = (
    "Called Ekavrātya.[^269_160a] Baudhāyana-Śrautasūtra pairs with *karmayoga*—not "
    "[[Ekavrātya|Ekavrātyaḥ]] or *varṇadharma*.\n\n"
    "<details><summary>मूलम्</summary>\nEkavrātya stays untouched.\n</details>"
  )
  out, changes = apply_iast_hyphenation_map(src, hmap)
  assert "Called Eka-vrātya.[^269_160a]" in out
  assert "Baudhāyana-Śrauta-sūtra" in out
  assert "*karma-yoga*—not" in out
  assert "[[Ekavrātya|Ekavrātyaḥ]]" in out
  assert "*varṇa-dharma*" in out
  assert "<details><summary>मूलम्</summary>\nEkavrātya stays untouched.\n</details>" in out
  assert ("Ekavrātya", "Eka-vrātya") in changes


def test_reconcile_iast_hyphenation_rejects_prose_edits_and_vetoes():
  orig = "The *Bhagavadgītā* teaches [[P10]] Śrautasūtra and dharma-artha or philosophy."
  # Masked tokens must be sent as §§P0000§§ if mimicking LLM round-trip
  cand = "The *Bhagavad-gītā* teaches §§P0000§§ Śrauta-sūtra and dharma-artha or philo-sophy and silent edit."
  out, chg = reconcile_iast_hyphenation(orig, cand)
  assert "*Bhagavad-gītā*" in out
  assert "[[P10]]" in out
  assert "Śrauta-sūtra" in out
  assert "dharma-artha" in out
  assert "philo-sophy" not in out
  assert "silent" not in out
  assert chg == [("Bhagavadgītā", "Bhagavad-gītā"), ("Śrautasūtra", "Śrauta-sūtra")]

  # If candidate drops placeholder, entire chunk safely falls back to orig
  assert reconcile_iast_hyphenation("See Bhagavadgītā.[^1_1]", "See Bhagavad-gītā.") == ("See Bhagavadgītā.[^1_1]", [])


def test_find_iast_merger_violations():
  text = (
    "Valid *Bhagavad-gītā*, *śiva-cult*, and *Śiva-image*, bad *dharma-artha* and *maha-utsava*, "
    "ignored [[dharma-artha|dharmārtha]]."
  )
  hits = find_iast_merger_violations(text)
  assert [tok for tok, _ in hits] == ["dharma-artha", "maha-utsava"]

  # With raw_text baseline: pre-existing bibliographic hyphens are preserved, only new splits flagged.
  raw = "In *Taittirīya-Upaniṣad*, seek *dharmārtha* and *Bhagavadgītā*."
  edited = "In *Taittirīya-Upaniṣad*, seek *dharma-artha* and *Bhagavad-gītā*."
  assert [tok for tok, _ in find_iast_merger_violations(edited, raw_text=raw)] == ["dharma-artha"]
