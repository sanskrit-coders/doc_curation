from doc_curation import text_utils


def test_remove_parenthized_text():
  assert text_utils.remove_parenthized_text("[^1]पुरुषार्थ[^2]ज्ञानमि[^3]दं गुह्यं परमर्षिणा समाख्यातम् ।") == "पुरुषार्थज्ञानमिदं गुह्यं परमर्षिणा समाख्यातम् ।"


def test_title_from_text():
  assert text_utils.title_from_text("[^1]पुरुषार्थ[^2]ज्ञानमि[^3]दं गुह्यं परमर्षिणा समाख्यातम् ।") == "पुरुषार्थज्ञानमिदङ्"
