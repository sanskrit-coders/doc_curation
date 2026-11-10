from doc_curation.sanskrit import fixer


def test_is_minor_roman_change_diacritics():
    assert fixer.is_minor_roman_change("rāma", "rama")
    assert fixer.is_minor_roman_change("śivaṃ", "sivam")
    assert fixer.is_minor_roman_change("kṛṣṇa", "krsna")
    assert fixer.is_minor_roman_change("ṛtam", "r̥tam")
    assert fixer.is_minor_roman_change("tapaḥ", "tapah")
    assert not fixer.is_minor_roman_change("rāma", "nāma")


def test_is_minor_roman_change_spaces_and_punctuation():
    assert fixer.is_minor_roman_change("sva-dharma", "svadharma")
    assert fixer.is_minor_roman_change("tapaḥ + sva", "tapaḥ sva")
    assert fixer.is_minor_roman_change("devāḥ, lokāḥ", "devah lokah")
    assert not fixer.is_minor_roman_change("agnim īḷe", "agni īḷe")


def test_is_minor_roman_change_leaves_other_scripts():
    assert not fixer.is_minor_roman_change("अग्निमीळे", "अग्निमीले")


def test_is_minor_dev_change_anunaasika_and_visarga():
    assert fixer.is_minor_dev_change("अँगुलिः", "अंगुलिः")
    assert fixer.is_minor_dev_change("देवाः", "देवास्")
    assert fixer.is_minor_dev_change("अग्निः", "अग्निर्")
    assert not fixer.is_minor_dev_change("रसः", "हसः")
    assert not fixer.is_minor_dev_change("रामः", "नामः")


def test_is_minor_dev_change_spaces_and_punctuation():
    assert fixer.is_minor_dev_change("संस्कृतम् ।", "संस्कृतम्।")
    assert fixer.is_minor_dev_change("रामः गच्छति", "रामस्  गच्छति")
    assert not fixer.is_minor_dev_change("रामः", "राम")


def test_accept_minor_changes():
    text = "देवाः [[रामः|रामस्]] गच्छति [[मातुलंगकैः|मातुलुङ्गकैः]] । [[tejaḥ sva|tejaḥ  sva]] [[prarabvaṁ|prārabdhaṁ]]"
    assert fixer.accept_minor_changes(text) == "देवाः रामस् गच्छति [[मातुलंगकैः|मातुलुङ्गकैः]] । tejaḥ  sva [[prarabvaṁ|prārabdhaṁ]]"


def test_accept_minor_changes_leaves_page_numbers():
    assert fixer.accept_minor_changes("रामः [[P64]]") == "रामः [[P64]]"


def test_accept_minor_changes_does_not_swallow_page_markers():
    text = "[[P12]] tejaḥ sva [[P13]] and more text | with a pipe]] tail"
    assert fixer.accept_minor_changes(text) == text
    text = "[[P12]] [[tejaḥ sva|tejaḥsva]] | prose ]"
    assert fixer.accept_minor_changes(text) == "[[P12]] tejaḥsva | prose ]"


def test_accept_minor_changes_handles_footnote_refs():
    text = "[[names160s|names[^151]]] and [[विद्यास्|विद्यास्]]"
    assert fixer.accept_minor_changes(text) == "[[names160s|names[^151]]] and विद्यास्"
    text = "[[twelve ;146|twelve;[^146]]]"
    assert fixer.accept_minor_changes(text) == "twelve;[^146]"
