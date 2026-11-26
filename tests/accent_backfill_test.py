"""Tests for the reusable batch Vedic corpus backfill runner and CLI."""

from __future__ import annotations

import pytest

from doc_curation.sanskrit.accent.backfill import backfill_corpora_in_directories, main
from doc_curation.sanskrit.accent.provenance import VedicCorpusCounter, word_to_key_and_marks


def _make_counter() -> VedicCorpusCounter:
  c = VedicCorpusCounter()
  for corp, word, freq in [
    ("TS", "अग्न᳓ये", 128),
    ("TS", "अग्निः᳓", 1067),
    ("KS", "अग्न᳓ये", 19),
    ("KS", "अग्निः᳓", 120),
    ("MS", "अग्न᳓ये", 55),
    ("MS", "अग्निः᳓", 400),
    ("KS", "त्वा", 326),
    ("MS", "त्वा", 812),
  ]:
    km = word_to_key_and_marks(word)
    assert km is not None
    c._add(corp, km[0], km[1], freq=freq)
  c._finalize_secondary_tables()
  return c


def test_backfill_corpora_in_directories_wrapped_and_dry_run(tmp_path):
  c = _make_counter()
  src = tmp_path / "01.md"
  orig = (
    "+++\ntitle = \"01\"\n+++\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअग्न᳓ये त्वा ।\n</details>\n\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- अग्न᳓ये (*TS*-128/1195)\n"
    "- त्वा (अनुदात्तम्, पा॰ ८.१.१८, *TS*-814)\n"
    "</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nअ॒ग्नये॑ त्वा ।\n</details>\n"
    "</details>\n"
  )
  src.write_text(orig, encoding="utf-8")

  # Dry run reports changes without modifying file
  st_dry = backfill_corpora_in_directories(
    [str(tmp_path)], ("KS",), counter=c, forbid_self_corpus="MS", dry_run=True
  )
  assert st_dry.scanned == 1 and st_dry.modified == 1 and st_dry.lines_changed == 2
  assert src.read_text(encoding="utf-8") == orig

  # Real run writes KS without MS and passes idempotence + validation
  st_real = backfill_corpora_in_directories(
    [str(tmp_path)], ("KS",), counter=c, forbid_self_corpus="MS", dry_run=False
  )
  assert st_real.modified == 1 and st_real.self_cite_hits == 0 and st_real.bad_tag_hits == 0
  assert st_real.unbalanced_hits == 0 and st_real.provenance_error_hits == 0
  updated = src.read_text(encoding="utf-8")
  assert "- अग्न᳓ये (*TS*-128/1195, *KS*-19/139)" in updated
  assert "- त्वा (अनुदात्तम्, पा॰ ८.१.१८, *TS*-814, *KS*-326)" in updated
  assert "*MS*" not in updated

  # Second run is a no-op
  st_again = backfill_corpora_in_directories(
    [str(tmp_path)], ("KS",), counter=c, forbid_self_corpus="MS", dry_run=False
  )
  assert st_again.modified == 0


def test_backfill_rejects_self_corpus_and_refreshes_transitive_prefill(tmp_path):
  c = _make_counter()
  with pytest.raises(ValueError, match="forbidden self-corpus"):
    backfill_corpora_in_directories([str(tmp_path)], ("MS",), counter=c, forbid_self_corpus="MS")

  # Set up minimal Hugo repo layout: <tmp>/repo/static/a.md included by <tmp>/repo/content/host.md
  static_dir = tmp_path / "repo" / "static"
  content_dir = tmp_path / "repo" / "content"
  static_dir.mkdir(parents=True)
  content_dir.mkdir(parents=True)

  inc_file = static_dir / "a.md"
  inc_file.write_text(
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- अग्न᳓ये (*TS*-128/1195)\n"
    "</details>\n",
    encoding="utf-8",
  )
  host_file = content_dir / "host.md"
  host_file.write_text(
    "+++\ntitle = \"host\"\n+++\n\n"
    "<div class=\"js_include\" includetitle=\"false\" newlevelforh1=\"3\" url=\"/repo/a.md\">\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n"
    "- अग्न᳓ये (*TS*-128/1195)\n"
    "</details>\n"
    "</div>\n",
    encoding="utf-8",
  )

  st = backfill_corpora_in_directories(
    [str(static_dir)],
    ("KS", "MS"),
    counter=c,
    prefill_roots=[str(static_dir), str(content_dir)],
    hugo_base_dir=str(tmp_path),
  )
  assert st.modified == 1
  assert str(host_file) in st.refreshed_containers
  host_txt = host_file.read_text(encoding="utf-8")
  assert "*KS*-19/139, *MS*-55/455" in host_txt
  assert host_txt.count("<details") == host_txt.count("</details>")


def test_backfill_cli_dry_run(tmp_path, monkeypatch):
  c = _make_counter()
  monkeypatch.setattr(VedicCorpusCounter, "load_or_build", classmethod(lambda cls: c))
  f = tmp_path / "01.md"
  f.write_text("<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- त्वा (*TS*-814)\n</details>\n", encoding="utf-8")
  rc = main(["--dir", str(tmp_path), "--corpora", "KS", "MS", "--dry-run"])
  assert rc == 0
  assert "*KS*" not in f.read_text(encoding="utf-8")
