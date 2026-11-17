import pytest

from doc_curation.sanskrit.accent.sandhi_check import verify_mantra_sandhi, word_to_slp_options


@pytest.mark.parametrize(
  ("padas", "mula", "expected"),
  [
    # Original padapatha vs samhita visarga/vowel round-trip invariants
    (["पार्थिवस्य", "एकः", "इत्", "वशी"], "पार्थि॑व॒स्यैक॑ इद्व॒शी", True),
    (["पार्थिवस्य", "एकम्", "इत्", "वशी"], "पार्थि॑व॒स्यैक॑ इद्व॒शी", False),
    # Daṇḍa-less viṣama-pāda newline wrap still undergoes external sandhi (visarga-lopa)
    (["भव्यम्", "आः", "इदम्", "तत्"], "भव्य॑म् आ \nइ॒दन् तद्", True),
    (["भव्यम्", "आ", "इदम्", "तत्"], "भव्य॑म् आ \nइ॒दन् तद्", False),
    # Visarga-lopa & s → r / r-final forms before vowels and voiced consonants
    (["नः", "ऊनम्"], "न ऊनम्", True),
    (["न", "ऊनम्"], "न ऊनम्", False),
    (["दिव्याः", "आपः"], "दिव्या आपः", True),
    (["दिव्या", "आपः"], "दिव्या आपः", False),
    (["निपद्यते", "उप"], "निपद्यत उप", True),
    (["निपद्यत", "उप"], "निपद्यत उप", False),
    (["सः", "इदम्"], "स इदम्", True),
    (["स", "इदम्"], "स इदम्", False),
    (["स्वधाः", "अमृताः"], "स्वधा अमृताः", True),
    (["स्वधा", "अमृताः"], "स्वधा अमृताः", False),
    (["अजिह्वाः", "असश्चत"], "अजिह्वा असश्चत", True),
    (["अजिह्वा", "असश्चत"], "अजिह्वा असश्चत", False),
    (["विश्वाः", "आशाः"], "विश्वा आशा", True),
    (["विश्वा", "आशा"], "विश्वा आशा", False),
    (["ज्योतिः-भाः", "असि"], "ज्योतिर्भा असि", True),
    (["ज्योतिः-भा", "असि"], "ज्योतिर्भा असि", False),
    (["कः", "अस्मै"], "करस्मै", True),
    # Pragṛhya / शाकल्य / पा० ६.१.११५ / ऋत्यकः licensed hiatus vs invalid hiatus
    (["इमे", "ऋतवः"], "इम ऋतवः", True),
    (["ते", "अस्मे"], "ते अस्मे", True),
    (["अमी", "अत्र"], "अमी अत्र", True),
    (["अथो", "अहम्"], "अथो अहम्", True),
    (["तदा", "इदम्"], "तदा इदम्", False),
    (["राम", "अत्र"], "राम अत्र", False),
    (["अथो", "उत"], "अथो उत", True),
    (["अथो-उत"], "अथोउत", False),
    # Explicit pause punctuation permits hiatus; newline without daṇḍa does not
    (["अद्य", "अग्ने"], "अद्य । अग्ने", True),
    (["अद्य", "अग्ने"], "अद्य\nअग्ने", False),
    # Pause boundary preserves full target geminate canonicalization (`परस्तात् । तम्`)
    (["परस्तात्", "तम्", "एवम्"], "परस्तात् । तमेवं", True),
    # Multi-line full mantra with mixed sandhi and internal daṇḍas
    (
      [
        "य᳓स्मिन्", "इद᳓म्", "स᳓ञ्च", "वि᳓", "च", "ए᳓ति", "स᳓र्वम्",
        "य᳓स्मिन्", "देवाः᳓", "अ᳓धि", "वि᳓श्वे", "निषेदुः᳓",
        "त᳓त्", "एव᳓", "भूत᳓म्", "त᳓त्", "उ", "भ᳓व्यम्", "आः",
        "इद᳓म्", "त᳓त्", "अक्ष᳓रे", "परमे᳓", "व्यो᳙मन्न्",
      ],
      (
        "यस्मि॑न्न् इ॒दँ सञ् च॒ विचैति॒ सर्वय्ँ॒  \n"
        "यस्मि॑न् दे॒वा अधि॒ विश्वे॑ निषे॒दुः ।  \n"
        "तद् ए॒व भू॒तन् तद् उ॒ भव्य॑म् आ  \n"
        "इ॒दन् तद् अ॒क्षरे॑ पर॒मे व्यो॑मन्न् ॥"
      ),
      True,
    ),
  ],
)
def test_verify_mantra_sandhi(padas, mula, expected):
  ok, _, _, _ = verify_mantra_sandhi(padas, mula)
  assert ok is expected


def test_word_to_slp_options_compound_sandhi():
  opts = word_to_slp_options("ज्योतिः-भाः")
  assert "jyotirBAH" in opts or "jyotirBAs" in opts
  assert "satkftam" in word_to_slp_options("सत्-कृतम्")
