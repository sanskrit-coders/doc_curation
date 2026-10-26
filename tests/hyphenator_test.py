import os
import re
import tomllib

import pytest

from doc_curation.sanskrit.hyphenator import hyphene
from doc_curation.sanskrit.hyphenator import constants as C

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_HYPHENATOR_TESTS") != "1",
    reason="hyphenator results depend on locally generated trie data; "
           "set RUN_HYPHENATOR_TESTS=1 to run these tests.")

_DATA_PATH = os.path.join(C._DATA_DIR, "hyphenations.toml")
with open(_DATA_PATH, "rb") as f:
  _HYPHENATIONS = tomllib.load(f)


def _segments(text):
  return [p for p in re.split(r"[ \-\u2013\u2014]+", text) if p]


def _cases(section):
  return _HYPHENATIONS[section]["cases"]


@pytest.mark.parametrize("case", _cases("non_separable_mergers"),
                         ids=lambda c: c["input"])
def test_non_separable_mergers(case):
  # dIrgha / guNa / vRddhi mergers must never be split (absolute veto).
  assert hyphene(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", _cases("yan_sandhi"),
                         ids=lambda c: c["input"])
def test_yan_sandhi(case):
  assert hyphene(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", _cases("visarga_sandhi"),
                         ids=lambda c: c["input"])
def test_visarga_sandhi(case):
  assert hyphene(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", _cases("avagraha"),
                         ids=lambda c: c["input"])
def test_avagraha(case):
  assert hyphene(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", _cases("final_m_sandhi"),
                         ids=lambda c: c["input"])
def test_final_m_sandhi(case):
  assert hyphene(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", _cases("consonant_assimilation"),
                         ids=lambda c: c["input"])
def test_consonant_assimilation(case):
  assert hyphene(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", _cases("samasa_and_inflected_words"),
                         ids=lambda c: c["input"])
def test_samasa_and_inflected_words(case):
  assert hyphene(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", _cases("bad_split_regressions"),
                         ids=lambda c: c["input"])
def test_bad_split_regressions(case):
  assert hyphene(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", _cases("reference_sentences"),
                         ids=lambda c: c["name"])
def test_reference_sentences(case):
  if case.get("mode") == "exact":
    assert hyphene(case["text"]) == case["expected"]
  else:
    assert _segments(hyphene(case["text"])) == _segments(case["expected"])


@pytest.mark.parametrize("text", _HYPHENATIONS["idempotence"]["texts"])
def test_idempotent(text):
  assert hyphene(text) == text
