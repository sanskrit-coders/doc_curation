"""Loader must reuse existing rAmAnujIya tries instead of rebuilding them.

Normal hyphenation used to rewrite every ``rAmAnujIya*.trie`` file whenever
any of the ~679 corpus sources was newer than the tries - so each fresh
process after a near-daily source edit dirtied the working tree.  Only the
explicit ``rebuild_ra_trie()`` may rewrite them now.
"""
import hashlib
import os
import shutil
import time

from doc_curation.sanskrit.hyphenator import constants as C
from doc_curation.sanskrit.hyphenator import corpus_ra as RA
from doc_curation.sanskrit.hyphenator import tries as T

_RA_PATH_ATTRS = (
    "_RA_TRIE_PATH",
    "_RA_FORMS_TRIE_PATH",
    "_RA_NGRAM_TRIE_PATH",
    "_RA_ATTESTATIONS_TRIE_PATH",
    "_RA_BADSPLITS_TRIE_PATH",
    "_RA_SEPS_TRIE_PATH",
)


def _snapshot(path):
  with open(path, "rb") as f:
    digest = hashlib.sha1(f.read()).hexdigest()
  return os.path.getmtime(path), digest


def test_stale_ra_tries_are_loaded_not_rebuilt(tmp_path, monkeypatch):
  copies = {}
  for attr in _RA_PATH_ATTRS:
    src = getattr(C, attr)
    assert os.path.exists(src), src
    dst = str(tmp_path / os.path.basename(src))
    shutil.copy2(src, dst)
    monkeypatch.setattr(C, attr, dst)
    copies[attr] = dst
  before = {dst: _snapshot(dst) for dst in copies.values()}

  smap = T._get_scheme_map()
  word_tries, _ = T._load_word_tries()
  rt_dcs = T._load_dcs_trie(smap)
  # Pretend every corpus source is newer than the tries.
  out = T._load_ra_tries(smap, time.time() + 3600, word_tries, rt_dcs)

  assert set(out) == {"ra", "forms", "ngram", "attestations", "badsplits",
                      "seps"}
  assert all(v is not None for v in out.values())
  after = {dst: _snapshot(dst) for dst in copies.values()}
  assert after == before


def test_missing_ra_source_warns(tmp_path, monkeypatch, caplog):
  toml_path = tmp_path / "rAmAnujIya-sources.toml"
  toml_path.write_text('[[source]]\npath = "/nonexistent/xyz.md"\n')
  monkeypatch.setattr(C, "_RA_SOURCES_TOML", str(toml_path))
  with caplog.at_level("WARNING"):
    assert list(RA._ra_file_configs()) == []
  assert "xyz.md" in caplog.text
