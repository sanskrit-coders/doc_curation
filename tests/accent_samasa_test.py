from doc_curation.llm.proofreader.accent_helper import retrieve_accent_candidates
from doc_curation.sanskrit.accent import decompose_samasa_for_padasvara


def test_decompose_samasa_separable_and_sandhi_joints():
  # Separable concatenation / assimilation / visarga / yaṇ compounds
  assert "पुण्य" in decompose_samasa_for_padasvara("पुण्यपापैः")
  assert "आण्ड" in decompose_samasa_for_padasvara("आण्डकोशे")
  assert "जगत्" in decompose_samasa_for_padasvara("जगत्कारणम्")
  assert "मधु" in decompose_samasa_for_padasvara("मध्वरिः")
  assert "हविः" in decompose_samasa_for_padasvara("हविर्वाट्")


def test_decompose_samasa_vowel_mergers_and_nan():
  # Vowel-sandhi mergers vetoed by inline prastuti hyphenation must split for padasvara
  prana_members = decompose_samasa_for_padasvara("प्राणापानौ")
  assert "प्राण" in prana_members
  assert any(m.startswith("अपान") for m in prana_members)

  apodaka_members = decompose_samasa_for_padasvara("अपोदकाभिः")
  assert "अप" in apodaka_members
  assert any(m.startswith("उदक") for m in apodaka_members)

  # Nañ prefix compound
  anir_members = decompose_samasa_for_padasvara("अनिर्भिण्णः")
  assert "अ" in anir_members
  assert "निर्भिण्णः" in anir_members or any("निर्भि" in m for m in anir_members)


def test_retrieve_accent_candidates_ranks_by_frequency_and_splits_samasa():
  hits = retrieve_accent_candidates("रराणः प्राणापानौ अभवः तन्वः")
  joined = "\n".join(hits)
  # रराणः shows both frequency-ranked variants with రरा॑णः first in RV and TS
  rarana_line = next(h for h in hits if h.startswith("- रराणः:"))
  assert "ररा॑णः (10)" in rarana_line
  assert "ररा॑णः (3)" in rarana_line
  assert rarana_line.index("ररा॑णः (3)") < rarana_line.index("र॒रा॒णः (1)")
  # अभवः has zero fake svarita अ॑भवः
  assert "अ॑भवः" not in joined
  assert "अ॒भ॒वः॒ (24)" in joined
  # तन्वः preserves genuine jātya svarita त॒न्वः॑
  assert "त॒न्वः॑ (44)" in joined
  # प्राणापानौ decomposes so प्राण / अपान member accents are retrieved
  assert any(h.startswith("- प्राण:") or h.startswith("- अपान") for h in hits)
