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


def test_normalize_mAdhyandina():
    assert fixer.normalize_mAdhyandina("प्र᳓त्युष्टाऽअ᳓रातयः") == "प्र᳓त्युष्टा अ᳓रातयः"
    assert fixer.normalize_mAdhyandina("बह्वी᳓ः बु॒ध्न्य᳙ः देवा॒व्य᳖ँ") == "बह्वीः᳓ बु॒ध्न्यः᳙ देवा॒व्यँ᳖"
    assert fixer.normalize_mAdhyandina("आ᳓प्यायध्वमघ्न्याऽइ᳓न्द्राय भागं᳓") == "आ᳓प्यायध्वमघ्न्या इ᳓न्द्राय भाग᳓म्"
    assert fixer.normalize_mAdhyandina("आ। प्या॒य॒ध्व॒म्। अ॒घ्न्याः॒। इन्द्रा॑य। भा॒गं।") == "आ। प्या॒य॒ध्व॒म्। अ॒घ्न्याः॒। इन्द्रा॑य। भा॒गम्।"
    assert fixer.normalize_mAdhyandina("आप्या॑यध्वमघ्न्या॒ऽइन्द्रा॑य भा॒गं", normalize_pre_vowel_avagrahas=False) == "आप्या॑यध्वमघ्न्या॒ऽइन्द्रा॑य भा॒गम्"
    assert fixer.normalize_mAdhyandina("जुषाणो᳓ऽ अग्नि᳓र् त᳓दग्नेऽसि") == "जुषाणो᳓ अग्नि᳓र् त᳓दग्नेऽसि"
    assert fixer.normalize_mAdhyandina("स᳓कामाँ२ ॥ऽअ᳓ध्वनस्कुरु") == "स᳓कामाँ२ ॥ अ᳓ध्वनस्कुरु"
    assert fixer.normalize_mAdhyandina("त्॒वा। द्वि॒ऽपदीम्॑। संँ᳓रा") == "त्वा॒। द्वि॒ऽपदी॑म्। सँ᳓रा"
    assert fixer.normalize_mAdhyandina("ता᳓न् उ᳓ज्जेषंम्") == "ता᳓न् उ᳓ज्जेषम्"
    # Preserve +++(...)+++ annotations and Hindi-style -ें/-ों endings
    assert fixer.normalize_mAdhyandina("स॒रम्+++(=सरणं)+++ में॒। पूर्वें॑।") == "स॒रम्+++(=सरणं)+++ में॒। पूर्वें॑।"
    assert fixer.normalize_mAdhyandina("स्वयं-भूः") == "स्वयं-भूः"
