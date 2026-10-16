import re

import pytest

from doc_curation.sanskrit.hyphenator import hyphene


def _segments(text):
  return [p for p in re.split(r"[ -]+", text) if p]


def test_non_separable_mergers():
  # dIrgha / guNa / vRddhi mergers must never be split (absolute veto).
  assert hyphene("दयार्द्र") == "दयार्द्र"
  assert hyphene("अपीच्छा") == "अपीच्छा"
  assert hyphene("धर्मार्थ") == "धर्मार्थ"
  # svaprakAza + advitIya must NOT become svaprakAza-dvitIya.
  assert hyphene("स्वप्रकाशाद्वितीय") == "स्वप्रकाशाद्वितीय"
  assert hyphene("महोत्सव") == "महोत्सव"
  assert hyphene("रामेति") == "रामेति"
  assert hyphene("सदैव") == "सदैव"


def test_yan_sandhi():
  assert hyphene("इत्येवम्") == "इत्य् एवम्"
  assert hyphene("मध्वरिः") == "मध्व्-अरिः"


def test_visarga_sandhi():
  assert hyphene("रामोऽस्ति") == "रामो ऽस्ति"
  assert hyphene("दुष्प्रकृतेरस्य") == "दुष्प्रकृतेर् अस्य"
  assert hyphene("नमस्ते") == "नमस् ते"


def test_final_m_sandhi():
  assert hyphene("फलमश्नुते") == "फलम् अश्नुते"
  assert hyphene("अर्थमिति") == "अर्थम् इति"


def test_consonant_assimilation():
  assert hyphene("तद्धि") == "तद् धि"


def test_samasa_and_inflected_words():
  assert hyphene("हेतुभावे") == "हेतु-भावे"
  assert hyphene("आकाशशब्देन") == "आकाश-शब्देन"
  assert hyphene("जगत्कारणम्") == "जगत्-कारणम्"
  # single inflected words stay whole
  assert hyphene("वृत्तस्य") == "वृत्तस्य"
  assert hyphene("क्षणिकत्वम्") == "क्षणिकत्वम्"
  assert hyphene("सर्वज्ञ") == "सर्वज्ञ"


def test_reference_compound_sentence():
  # Sri-bhasya prastuti reference sentence (space/hyphen choice is free, the
  # segmentation is not): long merged chains (sakala+itara -> sakaletara)
  # must be kept joined and only separable joints cut.
  text = ("एतदुक्तं भवति – परस्यैव ब्रह्मणो "
          "निखिलहेयप्रत्यनीकानन्तज्ञानानन्दैकस्वरूपतया सकलेतरविलक्षणस्य "
          "स्वाभाविकानविधकातिशयासङ्ख्येयकल्याणगुणगणाश्च सन्ति।")
  expected = ("एतद् उक्तं भवति – परस्यैव ब्रह्मणो "
              "निखिल-हेय-प्रत्यनीकानन्त-ज्ञानानन्दैक-स्वरूपतया "
              "सकलेतर-विलक्षणस्य "
              "स्वाभाविकानविधकातिशयासङ्ख्येय- -कल्याण-गुण-गणाश् च सन्ति।")
  assert _segments(hyphene(text)) == _segments(expected)


def test_idempotent():
  for text in ["इत्य् एवम्", "मध्व्-अरिः", "हेतु-भावे", "नमस् ते",
               "रामो ऽस्ति", "फलम् अश्नुते", "धर्मार्थ"]:
    assert hyphene(text) == text
