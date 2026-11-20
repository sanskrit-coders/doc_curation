"""Unit & integration tests for ``doc_curation.sanskrit.accent.shatapatha_batch``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from doc_curation.sanskrit.accent import (
  AdjudicationBatchReport,
  SbCorpusAuditReport,
  UnifiedVedicLexicon,
  audit_full_sb_corpus,
  discover_sb_content_files,
  run_solver_corpus_pass,
  verify_and_apply_adjudications,
)
from doc_curation.sanskrit.accent.shatapatha_solver import default_data_available

PILOT_SB_ROOT = Path(
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH"
)
PILOT_01_01_1 = PILOT_SB_ROOT / "01/01/1.md"

needs_local_data = pytest.mark.skipif(
  not default_data_available(),
  reason="indic-dict padasvara lexica / VS corpus not installed locally",
)


def _make_synthetic_corpus(tmp_path: Path) -> Path:
  """Create a tiny multi-kāṇḍa synthetic ŚB tree with _index.md, pre-## intro, Kāṇḍa 12 Makoto, and already-US VP."""
  sb_root = tmp_path / "sb"
  (sb_root / "01/01").mkdir(parents=True)
  (sb_root / "02/04").mkdir(parents=True)
  (sb_root / "12/01").mkdir(parents=True)

  # Index/list files that MUST be skipped by discover_sb_content_files / corpus passes
  (sb_root / "01/_index.md").write_text("+++\ntitle='01'\n+++\n", encoding="utf-8")
  (sb_root / "01/01/file_list.md").write_text("list\n", encoding="utf-8")

  # File 01/01/1.md: pre-## intro + clean kaṇḍikā 01 + vyatyasta kaṇḍikā 02 + already-US kaṇḍikā 03
  (sb_root / "01/01/1.md").write_text(
    """+++
title = "१"
+++

<details open><summary>विश्वास-प्रस्तुतिः</summary>

हरिः-ओ३म्।
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

हरिः-ओ३म्।
</details>

## ०१

<details open><summary>विश्वास-प्रस्तुतिः</summary>

यज्ञ᳘मे᳘वैतत्॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

यज्ञ᳘मे᳘वैतत्॥
</details>

<details><summary>मूलम् - Weber</summary>

यज्ञ᳘मेॗवैतत्॥
</details>

<details><summary>मूलम् - विस्वरम्</summary>

यज्ञमेवैतत् ॥ १ ॥
</details>

<details><summary>सायणः</summary>

सायणभाष्यम् १।
</details>

<details><summary>Eggeling</summary>

Eggeling 1.
</details>

## ०२

<details open><summary>विश्वास-प्रस्तुतिः</summary>

व्वज्रमु᳘द्यछति॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

व्वज्रमु᳘द्यछति॥
</details>

<details><summary>मूलम् - Weber</summary>

व᳘ज्रमुद्यछति॥
</details>

<details><summary>मूलम् - विस्वरम्</summary>

वज्रमुद्यच्छति ॥ २ ॥
</details>

## ०३

<details open><summary>विश्वास-प्रस्तुतिः</summary>

(र्मे᳘) त᳓द् वा᳓ अपः᳓ ॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

(र्मे᳘) तद्वा᳘ ऽअपः᳘॥
</details>

<details><summary>मूलम् - Weber</summary>

तद्वा᳘ अपः᳘॥
</details>
""",
    encoding="utf-8",
  )

  # File 02/04/1.md: multi-VP section under one ## heading
  (sb_root / "02/04/1.md").write_text(
    """+++
title = "१"
+++

## ०२

<details open><summary>विश्वास-प्रस्तुतिः</summary>

त᳘दपः᳘॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

त᳘दपः᳘॥
</details>

<details open><summary>विश्वास-प्रस्तुतिः</summary>

यज्ञ᳘मे᳘वैत᳘त्॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

यज्ञ᳘मे᳘वैत᳘त्॥
</details>

<details><summary>मूलम् - Weber</summary>

यज्ञ᳘मेॗवैत᳘त्॥
</details>

<details><summary>सायणः</summary>

सायण २।
</details>
""",
    encoding="utf-8",
  )

  # File 12/01/1.md: double-space heading + हरिस्वामी + trailing मूलम् - Makoto
  (sb_root / "12/01/1.md").write_text(
    """+++
title = "१"
+++

##  ०१

<details open><summary>विश्वास-प्रस्तुतिः</summary>

त᳘दपः᳘॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

त᳘दपः᳘॥
</details>

<details><summary>मूलम् - Weber</summary>

त᳘दपः᳘॥
</details>

<details><summary>हरिस्वामी</summary>

हरिस्वामिभाष्यम्।
</details>

<details><summary>Eggeling</summary>

Eggeling 12.
</details>

<details><summary>मूलम् - Makoto</summary>

Makoto text.
</details>
""",
    encoding="utf-8",
  )

  return sb_root


def test_discover_sb_content_files_skips_index_and_filters_kandas(tmp_path):
  sb_root = _make_synthetic_corpus(tmp_path)
  all_files = discover_sb_content_files(sb_root)
  rels = [p.relative_to(sb_root).as_posix() for p in all_files]
  assert rels == ["01/01/1.md", "02/04/1.md", "12/01/1.md"]

  k1_12 = discover_sb_content_files(sb_root, kandas=[1, "12"])
  assert [p.relative_to(sb_root).as_posix() for p in k1_12] == ["01/01/1.md", "12/01/1.md"]

  (sb_root / "17_bRhadAraNyakam/01").mkdir(parents=True)
  (sb_root / "17_bRhadAraNyakam/01/1.md").write_text("title\n", encoding="utf-8")
  assert [p.relative_to(sb_root).as_posix() for p in discover_sb_content_files(sb_root, kandas=["17"])] == ["17_bRhadAraNyakam/01/1.md"]
  assert [p.relative_to(sb_root).as_posix() for p in discover_sb_content_files(sb_root, kandas=["17_bRhadAraNyakam"])] == ["17_bRhadAraNyakam/01/1.md"]


def test_run_solver_corpus_pass_exports_jsonls_and_applies_auto_clean(tmp_path):
  sb_root = _make_synthetic_corpus(tmp_path)
  out_dir = tmp_path / "solver_out"
  lex = UnifiedVedicLexicon.load_or_build(force_rebuild=False)

  summary = run_solver_corpus_pass(
    sb_root,
    out_dir,
    kandas=["01", "12"],
    apply_auto_clean=True,
    max_workers=1,
    lexicon=lex,
  )
  assert summary["files"] == 2
  assert summary["total_kandikas"] == 4
  assert summary["apply_errors"] == []
  assert (out_dir / "corpus_summary.json").is_file()
  assert (out_dir / "kanda_01_auto_clean.jsonl").is_file()
  assert (out_dir / "kanda_01_adjudication.jsonl").is_file()
  assert (out_dir / "kanda_12_auto_clean.jsonl").is_file()
  assert (out_dir / "kanda_12_adjudication.jsonl").is_file()
  assert summary["auto_clean"] + summary["needs_adjudication"] + summary["skipped"] == 4

  # Verify pre-## intro and already-US VP (with pratīka) stayed verbatim on disk
  txt_01 = (sb_root / "01/01/1.md").read_text(encoding="utf-8")
  assert "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nहरिः-ओ३म्।\n</details>" in txt_01
  assert "(र्मे᳘) त᳓द् वा᳓ अपः᳓ ॥" in txt_01

  # Verify Makoto stays untouched at the end of 12/01/1.md
  txt_12 = (sb_root / "12/01/1.md").read_text(encoding="utf-8")
  assert "<details><summary>मूलम् - Makoto</summary>\n\nMakoto text.\n</details>" in txt_12


def test_verify_and_apply_adjudications_accepts_clean_and_rejects_defects(tmp_path):
  sb_root = _make_synthetic_corpus(tmp_path)
  adj_path = tmp_path / "adj.jsonl"

  records = [
    # 0. Valid clean kaṇḍikā with पा॰ ८.२.६ svarita (`एवै᳙त᳓त्`)
    {
      "rel_path": "01/01/1.md",
      "heading": "०१",
      "sub_idx": 0,
      "vp_clean": "यज्ञम् एवैतत् ॥",
      "items": [
        {"pada": "यज्ञ᳓म्", "just": "*RV*, *TS*", "vyat_from": None},
        {"pada": "एव᳓", "just": "*RV*, *TS*", "vyat_from": None},
        {"pada": "एत᳓त्", "just": "*RV*, *TS*", "vyat_from": None},
      ],
    },
    # 1. Valid vyatyasta kaṇḍikā with separated पा॰ ८.१.७१ upasarga + tiṅanta
    {
      "rel_path": "01/01/1.md",
      "heading": "०२",
      "sub_idx": 0,
      "vp_clean": "वज्रम् उद्यच्छति ॥",
      "items": [
        {"pada": "व᳓ज्रम्", "just": "*RV*, *TS*; Weber-पाठः", "vyat_from": None},
        {"pada": "उत्", "just": "तिङि चोदात्तवति पा॰ ८.१.७१; Weber-पाठः; श्रीधरादि उ᳘त्", "vyat_from": None},
        {
          "pada": "य᳓च्छति",
          "just": "यद्वृत्तान्नित्यम् पा॰ ८.१.६६; Weber उद्यछति, श्रीधरादि उ᳘द्यछति",
          "vyat_from": "यच्छति",
        },
      ],
    },
    # 2. Valid already-US preserved kaṇḍikā (`vp_clean=None`) with pratīka `(र्मे᳘)`
    {
      "rel_path": "01/01/1.md",
      "heading": "०३",
      "sub_idx": 0,
      "vp_clean": None,
      "items": [
        {"pada": "त᳓त्", "just": "*RV*, *TS*", "vyat_from": None},
        {"pada": "वै᳓", "just": "*RV*, *TS*", "vyat_from": None},
        {"pada": "अपः᳓", "just": "*RV*, *TS*", "vyat_from": None},
      ],
    },
    # 3. REJECTED: unsplit subordinate upasarga+tiṅanta on 02/04/1.md sub_idx=0
    {
      "rel_path": "02/04/1.md",
      "heading": "०२",
      "sub_idx": 0,
      "vp_clean": "तद् उपस्पृशति ॥",
      "items": [
        {"pada": "त᳓त्", "just": "*RV*", "vyat_from": None},
        {"pada": "उप-स्पृश᳓ति", "just": "यद्वृत्तान्नित्यम् पा॰ ८.१.६६, पा॰ ८.१.७१", "vyat_from": None},
      ],
    },
    # 4. ACCEPTED on SAME file 02/04/1.md sub_idx=1 (partial file acceptance works cleanly!)
    {
      "rel_path": "02/04/1.md",
      "heading": "०२",
      "sub_idx": 1,
      "vp_clean": "यज्ञम् एवैतत् ॥",
      "items": [
        {"pada": "यज्ञ᳓म्", "just": "*RV*, *TS*", "vyat_from": None},
        {"pada": "एव᳓", "just": "*RV*, *TS*", "vyat_from": None},
        {"pada": "एत᳓त्", "just": "*RV*, *TS*", "vyat_from": None},
      ],
    },
    # 5. ACCEPTED on Kāṇḍa 12 with double-spaced heading + trailing Makoto (also verifies पा\u0966 -> पा॰ auto-normalization)
    {
      "rel_path": "12/01/1.md",
      "heading": "०१",
      "sub_idx": 0,
      "vp_clean": "तद् अपः ॥",
      "items": [
        {"pada": "त᳓त्", "just": "*RV*, *TS*, पा\u0966 ६.१.१५८", "vyat_from": None},
        {"pada": "अपः᳓", "just": "*RV*, *TS*", "vyat_from": None},
      ],
    },
  ]
  adj_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")

  # Dry run leaves files untouched
  orig_01 = (sb_root / "01/01/1.md").read_text(encoding="utf-8")
  dry_rep = verify_and_apply_adjudications(sb_root, adj_path, dry_run=True)
  assert isinstance(dry_rep, AdjudicationBatchReport)
  assert dry_rep.accepted == 5
  assert dry_rep.rejected == 1
  assert dry_rep.files_written == []
  assert (sb_root / "01/01/1.md").read_text(encoding="utf-8") == orig_01

  # Real apply writes passing files and reports exact REJECTED diagnostics
  rep = verify_and_apply_adjudications(sb_root, adj_path, dry_run=False)
  assert rep.accepted == 5
  assert rep.rejected == 1
  assert rep.files_written == ["01/01/1.md", "02/04/1.md", "12/01/1.md"]
  rej = [r for r in rep.records if r.status == "REJECTED"][0]
  assert rej.rel_path == "02/04/1.md"
  assert rej.sub_idx == 0
  assert any("unsplit_upasarga_tinanta" in v for v in rej.validation_issues)

  # Check rendered 01/01/1.md: inline [[उद्यच्छति|उद्य᳓च्छति]] + verbatim preserved (र्मे᳘) VP
  txt_01 = (sb_root / "01/01/1.md").read_text(encoding="utf-8")
  assert "यज्ञ᳓म् एवै᳙त᳓त् ॥" in txt_01
  assert "व᳓ज्रम् [[उद्यच्छति|उद्य᳓च्छति]] ॥" in txt_01
  assert "(र्मे᳘) त᳓द् वा᳓ अपः᳓ ॥" in txt_01
  # Verify 12/01/1.md auto-normalized पा\u0966 -> पा॰
  txt_12 = (sb_root / "12/01/1.md").read_text(encoding="utf-8")
  assert "पा॰ ६.१.१५८" in txt_12
  assert "पा\u0966" not in txt_12

  # Now fix 02/04/1.md sub_idx=0 in a second pass and verify multi-pass + full Phase 4 corpus audit!
  adj_path2 = tmp_path / "adj2.jsonl"
  adj_path2.write_text(
    json.dumps(
      {
        "rel_path": "02/04/1.md",
        "heading": "०२",
        "sub_idx": 0,
        "vp_clean": "तद् अपः ॥",
        "items": [
          {"pada": "त᳓त्", "just": "*RV*, *TS*", "vyat_from": None},
          {"pada": "अपः᳓", "just": "*RV*, *TS*", "vyat_from": None},
        ],
      },
      ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
  )
  rep2 = verify_and_apply_adjudications(sb_root, adj_path2, dry_run=False)
  assert rep2.accepted == 1 and rep2.rejected == 0

  # Phase 4 audit across the entire synthetic corpus must PASS with 0 failures and note `(र्मे᳘)` pratīka!
  audit_rep = audit_full_sb_corpus(sb_root)
  assert isinstance(audit_rep, SbCorpusAuditReport)
  assert audit_rep.passed is True
  assert audit_rep.files_scanned == 3
  assert audit_rep.total_kandikas == 6
  assert audit_rep.converted_kandikas == 6
  assert audit_rep.unconverted_kandikas == 0
  assert audit_rep.failures == []
  assert any("01/01/1.md::०३" in note and "र्मे᳘" in note for note in audit_rep.preserved_pratika_sb_marks)


def test_audit_full_sb_corpus_catches_leftover_sb_marks_and_misplaced_pp(tmp_path):
  sb_root = _make_synthetic_corpus(tmp_path)
  # Inject a broken converted kaṇḍikā with leftover ᳘ outside pratīka and misplaced पद-पाठः after सायणः
  bad_file = sb_root / "01/01/2.md"
  bad_file.write_text(
    """+++
title = "२"
+++

## ०१

<details open><summary>विश्वास-प्रस्तुतिः</summary>

यज्ञ᳓म् एवै᳘त᳓त् ॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

यज्ञ᳘मे᳘वैत᳘त्॥
</details>

<details><summary>मूलम् - Weber</summary>

यज्ञ᳘मेॗवैत᳘त्॥
</details>

<details><summary>सायणः</summary>

भाष्यम्।
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- यज्ञ᳓म् (*RV*, *TS*)
- एव᳓ (*RV*, *TS*)
- एत᳓त् (*RV*, *TS*)
</details>
""",
    encoding="utf-8",
  )
  rep = audit_full_sb_corpus(sb_root, files=[bad_file])
  assert rep.passed is False
  kinds = {f.kind for f in rep.failures}
  assert "leftover_sb_marks" in kinds
  assert "missing_padapatha" in kinds
  assert "misplaced_padapatha" in kinds

  # Also verify Bug 2 (bogus 0/P header + missing N/P header), पा\u0966 guard, and *TS*-0 guard
  bad_hdr = sb_root / "01/01/3.md"
  bad_hdr.write_text(
    """+++
title = "३"
+++

## ०१

<details open><summary>विश्वास-प्रस्तुतिः (0/2 व्यत्यस्त-स्वराः)</summary>

त᳓द् अपः᳓ ॥
</details>

<details><summary>मूलम् - Weber</summary>

त᳘दपः᳘॥
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- त᳓त् (*TS*-0, पा\u0966 ६.१.१५८)
- अपः᳓ (*RV*-10)
</details>

## ०२

<details open><summary>विश्वास-प्रस्तुतिः</summary>

व᳓ज्रम् [[उद्यच्छति|उद्य᳓च्छति]] ॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

व्वज्रमु᳘द्यछति॥
</details>

<details><summary>मूलम् - Weber</summary>

व᳘ज्रमुद्यछति॥
</details>

<details><summary>पद-पाठः (यान्त्रिकः - 1/3 व्यत्यस्त-स्वराः)</summary>

- व᳓ज्रम् (*RV*-10; Weber-पाठः)
- उत् (तिङि चोदात्तवति पा॰ ८.१.७१; Weber-पाठः)
- यच्छति → **य᳓च्छति** (यद्वृत्तान्नित्यम् पा॰ ८.१.६६)
</details>
""",
    encoding="utf-8",
  )
  rep2 = audit_full_sb_corpus(sb_root, files=[bad_hdr])
  assert rep2.passed is False
  kinds2 = {f.kind for f in rep2.failures}
  assert "zero_abbrev_sign" in kinds2
  assert "zero_corpus_count" in kinds2
  assert sum(1 for f in rep2.failures if f.kind == "vp_summary_vyatyasta_mismatch") == 2


@pytest.mark.skipif(not PILOT_01_01_1.is_file(), reason="Pilot ŚB 01/01/1.md not present locally")
def test_audit_full_sb_corpus_smoke_on_pilot_01_01_1():
  rep = audit_full_sb_corpus(PILOT_SB_ROOT, files=[PILOT_01_01_1])
  assert rep.passed is True, f"Pilot 01/01/1.md audit failures: {rep.failures}"
  assert rep.files_scanned == 1
  assert rep.total_kandikas == 22
  assert rep.converted_kandikas == 22
  assert rep.unconverted_kandikas == 0
  assert rep.failures == []


def test_verify_adjudications_edge_guards_and_multipass_preserved_human_us(tmp_path):
  sb_root = _make_synthetic_corpus(tmp_path)
  # Put a human-edited US block with an intentional double-udātta (like 01/04/2.md `स᳓र्व्वे᳓भ्यो`) in 01/01/1.md ## ०३
  p01 = sb_root / "01/01/1.md"
  p01.write_text(
    p01.read_text(encoding="utf-8").replace("(र्मे᳘) त᳓द् वा᳓ अपः᳓ ॥", "(र्मे᳘) त᳓द् वा᳓ अ᳓पः᳓ ॥"),
    encoding="utf-8",
  )

  # Pass 1: preserve human-edited ## ०३ verbatim and insert its पद-पाठः
  adj1 = tmp_path / "p1.jsonl"
  adj1.write_text(
    json.dumps(
      {
        "rel_path": "01/01/1.md",
        "heading": "०३",
        "sub_idx": 0,
        "vp_clean": None,
        "items": [
          {"pada": "त᳓त्", "just": "*RV*, *TS*", "vyat_from": None},
          {"pada": "वै᳓", "just": "*RV*, *TS*", "vyat_from": None},
          {"pada": "अपः᳓", "just": "*RV*, *TS*", "vyat_from": None},
        ],
      },
      ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
  )
  r1 = verify_and_apply_adjudications(sb_root, adj1, dry_run=False)
  assert r1.accepted == 1 and r1.rejected == 0

  # Pass 2: update ## ०१ and ## ०२ in the SAME file without being blocked by preserved human ## ०३,
  # while also testing duplicate-key, path-traversal, and non-solid vyatyasta rejections.
  adj2 = tmp_path / "p2.jsonl"
  rows = [
    {
      "rel_path": "01/01/1.md",
      "heading": "०१",
      "sub_idx": 0,
      "vp_clean": "यज्ञम् एवैतत् ॥",
      "items": [
        {"pada": "यज्ञ᳓म्", "just": "*RV*, *TS*", "vyat_from": None},
        {"pada": "एव᳓", "just": "*RV*, *TS*", "vyat_from": None},
        {"pada": "एत᳓त्", "just": "*RV*, *TS*", "vyat_from": None},
      ],
    },
    # Duplicate key in same batch -> REJECTED
    {
      "rel_path": "01/01/1.md",
      "heading": "०१",
      "sub_idx": 0,
      "vp_clean": "यज्ञम् एवैतत् ॥",
      "items": [{"pada": "त᳓त्", "just": "*RV*", "vyat_from": None}],
    },
    # Path traversal -> REJECTED
    {
      "rel_path": "../outside.md",
      "heading": "०१",
      "sub_idx": 0,
      "vp_clean": "तत् ॥",
      "items": [{"pada": "त᳓त्", "just": "*RV*", "vyat_from": None}],
    },
    # Non-solid vyatyasta provenance (bare *MW*) -> REJECTED
    {
      "rel_path": "12/01/1.md",
      "heading": "०१",
      "sub_idx": 0,
      "vp_clean": "तद् अपः ॥",
      "items": [
        {"pada": "त᳓त्", "just": "*MW*", "vyat_from": "तत्"},
        {"pada": "अपः᳓", "just": "*RV*", "vyat_from": None},
      ],
    },
    # Valid ## ०२ so ## ०१'s cross-kaṇḍikā boundary matches `व᳓ज्रम्`
    {
      "rel_path": "01/01/1.md",
      "heading": "०२",
      "sub_idx": 0,
      "vp_clean": "वज्रम् उद्यच्छति ॥",
      "items": [
        {"pada": "व᳓ज्रम्", "just": "*RV*, *TS*; Weber-पाठः", "vyat_from": None},
        {"pada": "उत्", "just": "तिङि चोदात्तवति पा॰ ८.१.७१; Weber-पाठः; श्रीधरादि उ᳘त्", "vyat_from": None},
        {
          "pada": "य᳓च्छति",
          "just": "यद्वृत्तान्नित्यम् पा॰ ८.१.६६; Weber उद्यछति, श्रीधरादि उ᳘द्यछति",
          "vyat_from": "यच्छति",
        },
      ],
    },
  ]
  adj2.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
  r2 = verify_and_apply_adjudications(sb_root, adj2, dry_run=False)
  assert r2.accepted == 2
  assert r2.rejected == 3
  assert r2.files_written == ["01/01/1.md"]
  rej_errs = " | ".join(e for r in r2.records if r.status == "REJECTED" for e in r.errors)
  assert "duplicate_kandika_in_batch" in rej_errs
  assert "path traversal" in rej_errs
  assert "lacks solid provenance" in rej_errs
  # Human-edited ## ०३ stayed byte-for-byte verbatim!
  assert "(र्मे᳘) त᳓द् वा᳓ अ᳓पः᳓ ॥" in p01.read_text(encoding="utf-8")

  # Audit 01/01/1.md right after Pass 2:
  # (a) Without preserved_kandika_ids, strict audit flags the human-edited double-udātta reconcile_diff
  strict_audit = audit_full_sb_corpus(sb_root, files=[p01])
  assert strict_audit.passed is False
  assert any(f.kind == "reconcile_diff" and f.kandika_id == "01/01/1.md::०३" for f in strict_audit.failures)

  # (b) With preserved_kandika_ids={"01/01/1.md::०३"}, Phase 4 audit PASSES while logging preserved_us_notes!
  pres_audit = audit_full_sb_corpus(sb_root, files=[p01], preserved_kandika_ids={"01/01/1.md::०३"})
  assert pres_audit.passed is True, f"Unexpected failures: {pres_audit.failures}"
  assert pres_audit.failures == []
  assert any("01/01/1.md::०३" in n and "reconcile_diff" in n for n in pres_audit.preserved_us_notes)




def test_enrich_provenance_with_corpus_counts_formats_dedupes_and_is_idempotent(monkeypatch):
  import doc_curation.sanskrit.accent.shatapatha_batch as sbb
  from doc_curation.sanskrit.accent import PadapathaItem, enrich_items_with_corpus_counts
  from doc_curation.sanskrit.accent.shatapatha_batch import enrich_provenance_with_corpus_counts as enrich

  fake = {
    "सर्व᳓तः": {"TS": 12, "RV": 2, "TB": 2},
    "सं-स्था᳓म्": {"TS": 2, "VS": 1},
    "अ᳓स्मि": {},
  }
  monkeypatch.setattr(sbb, "lookup_corpus_counts", lambda lex, pada: dict(fake.get(pada, {})))

  # 1. Bare tags -> exact counts, editorial/sūtra segments verbatim, पा\u0966 -> पा॰
  new, unv = enrich(None, "सर्व᳓तः", "*RV*, *TS*; श्रीधरादि-पाठः")
  assert new == "*TS*-12, *RV*-2, *TB*-2; श्रीधरादि-पाठः" and unv == []
  new, _ = enrich(None, "सर्व᳓तः", "अनुदात्तम्, पा\u0966 ८.१.१८, *TS*")
  assert new == "अनुदात्तम्, पा॰ ८.१.१८, *TS*-12, *RV*-2, *TB*-2"
  # 2. Inline form citation keeps its form, gains its count, no duplicate tag
  new, _ = enrich(None, "सं-स्था᳓म्", "*TS* सँ॒स्थाम्")
  assert new == "*TS*-2 सँ॒स्थाम्, *VS*-1"
  # 3. Verse refs and dictionary tags untouched
  new, _ = enrich(None, "सर्व᳓तः", "*VS* १.५, *MW*")
  assert new.startswith("*VS* १.५, *MW*") and "*TS*-12" in new
  # 4. Unattested exact form: unverifiable bare tag dropped when sūtra support remains (reported, never -0);
  #    kept verbatim (and reported) when it is the only support
  new, unv = enrich(None, "अ᳓स्मि", "यद्वृत्तान्नित्यम् पा॰ ८.१.६६, *TS*")
  assert new == "यद्वृत्तान्नित्यम् पा॰ ८.१.६६" and unv == ["TS"] and "-0" not in new
  new, unv = enrich(None, "अ᳓स्मि", "*TS*")
  assert new == "*TS*" and unv == ["TS"]
  # 5. Idempotent
  for pada, just in (("सर्व᳓तः", "*RV*, *TS*; श्रीधरादि-पाठः"), ("सं-स्था᳓म्", "*TS* सँ॒स्थाम्")):
    once, _ = enrich(None, pada, just)
    twice, _ = enrich(None, pada, once)
    assert once == twice
  # 6. Item-level helper keeps solidity and arrows
  items = [PadapathaItem(ar="सर्वतः", ref="सर्व᳓तः", prov="*TS*", vyat=True, solid=True)]
  out, warn = enrich_items_with_corpus_counts(None, items)
  assert out[0].vyat and out[0].solid and out[0].ar == "सर्वतः" and warn == {}
  assert out[0].prov == "*TS*-12, *RV*-2, *TB*-2"


@needs_local_data
def test_verify_and_apply_adjudications_enriches_counts_end_to_end(tmp_path):
  sb_root = _make_synthetic_corpus(tmp_path)
  lex = UnifiedVedicLexicon.load_or_build(force_rebuild=False)
  adj = tmp_path / "adj_counts.jsonl"
  adj.write_text(
    json.dumps(
      {
        "rel_path": "12/01/1.md",
        "heading": "०१",
        "sub_idx": 0,
        "vp_clean": "तद् अपः ॥",
        "items": [
          {"pada": "त᳓त्", "just": "*RV*, *TS*", "vyat_from": None},
          {"pada": "अपः᳓", "just": "*RV*, *TS*", "vyat_from": None},
        ],
      },
      ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
  )
  rep = verify_and_apply_adjudications(sb_root, adj, lexicon=lex)
  assert rep.accepted == 1 and rep.rejected == 0
  txt = (sb_root / "12/01/1.md").read_text(encoding="utf-8")
  import re as _re
  bullets = [ln for ln in txt.splitlines() if ln.startswith("- त᳓त्") or ln.startswith("- अपः᳓")]
  assert len(bullets) == 2
  for ln in bullets:
    tags = _re.findall(r"\*(?:VS|TS|RV|AV|TB|TA)\*-(\d+)", ln)
    assert tags and all(int(n) > 0 for n in tags)
  assert audit_full_sb_corpus(sb_root, files=[sb_root / "12/01/1.md"]).failures == []


def test_apply_marks_to_token_preserves_virama_independent_vowel_hiatus():
  from doc_curation.sanskrit.accent import apply_marks_to_token

  # Regression (14/01-05/.../03/1.md): `र्ऋ` must not be coalesced into `रृ` by join_strings
  assert apply_marks_to_token("नाभिर्ऋतस्य", ["U", "", "", "U", ""]) == "ना᳓भिर्ऋत᳓स्य"
  assert apply_marks_to_token("स्वर्अश्वः", ["", "U", ""]) == "स्वर्अ᳓श्वः"


def test_run_solver_corpus_pass_export_all_adds_rel_path_and_auto_clean_drafts(tmp_path):
  sb_root = _make_synthetic_corpus(tmp_path)
  lex = UnifiedVedicLexicon.load_or_build(force_rebuild=False)
  base = run_solver_corpus_pass(sb_root, tmp_path / "o1", kandas=["01"], lexicon=lex)
  full = run_solver_corpus_pass(sb_root, tmp_path / "o2", kandas=["01"], lexicon=lex, export_all_to_adjudication=True)
  recs_base = [json.loads(x) for x in (tmp_path / "o1/kanda_01_adjudication.jsonl").read_text(encoding="utf-8").splitlines()]
  recs_full = [json.loads(x) for x in (tmp_path / "o2/kanda_01_adjudication.jsonl").read_text(encoding="utf-8").splitlines()]
  assert len(recs_base) == base["needs_adjudication"]
  assert len(recs_full) == base["needs_adjudication"] + base["auto_clean"]
  assert all(r["rel_path"] == "01/01/1.md" and r["file"].endswith("01/01/1.md") for r in recs_full)
  assert full["auto_clean"] == base["auto_clean"]


def test_verify_and_apply_reports_disagree_details(tmp_path):
  sb_root = _make_synthetic_corpus(tmp_path)
  adj = tmp_path / "bad_audit.jsonl"
  # Wrong accent on `यज्ञ᳓म्` -> `य᳓ज्ञम्` against Weber/Shri `यज्ञ᳘मेॗवैत᳘त्॥`
  adj.write_text(
    json.dumps(
      {
        "rel_path": "01/01/1.md",
        "heading": "०१",
        "sub_idx": 0,
        "vp_clean": "यज्ञम् एवैतत् ॥",
        "items": [
          {"pada": "य᳓ज्ञम्", "just": "*RV*", "vyat_from": None},
          {"pada": "एव᳓", "just": "*RV*", "vyat_from": None},
          {"pada": "एत᳓त्", "just": "*RV*", "vyat_from": None},
        ],
      },
      ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
  )
  rep = verify_and_apply_adjudications(sb_root, adj, dry_run=True, enrich_counts=False)
  assert rep.rejected == 1
  rec = rep.records[0]
  assert rec.disagree_details, "expected compact disagree_details on audit rejection"
  d0 = rec.disagree_details[0]
  assert {"pada_idx", "pada", "syl", "us_mark", "exp_w", "act_w", "exp_s", "act_s", "status"} <= set(d0.keys())
  assert d0["pada_idx"] == 0 and d0["status"] == "both_disagree"


@needs_local_data
def test_ta_source_is_dropped_by_enrichment_and_rejected_by_audit(tmp_path):
  from doc_curation.sanskrit.accent.shatapatha_batch import (
    SB_CORPUS_TAGS,
    enrich_provenance_with_corpus_counts,
  )

  assert "TA" not in SB_CORPUS_TAGS
  assert SB_CORPUS_TAGS == ("VS", "TS", "RV", "AV", "TB")

  lex = UnifiedVedicLexicon.load_or_build(force_rebuild=False)
  new_j, _ = enrich_provenance_with_corpus_counts(lex, "यज्ञ᳓म्", "*TA*, *TS*, *RV*")
  assert "*TA*" not in new_j
  assert "*TS*-" in new_j or "*RV*-" in new_j

  # Inline *TA* citation is also dropped cleanly
  new_j2, _ = enrich_provenance_with_corpus_counts(lex, "अन᳓स्तमिते", "*TA* अनस्तमिते, पा॰ ६.२.२")
  assert "*TA*" not in new_j2 and "पा॰ ६.२.२" in new_j2

  new_ek, _ = enrich_provenance_with_corpus_counts(lex, "यज्ञ᳓म्", "*EK* मूल-पाठः, *TS*, *RV*")
  assert "*EK*" not in new_ek and "*TS*" in new_ek

  # verify_and_apply_adjudications with enrich_counts=False rejects *TA*
  sb_root = _make_synthetic_corpus(tmp_path)
  adj = tmp_path / "ta_adj.jsonl"
  adj.write_text(
    json.dumps(
      {
        "rel_path": "12/01/1.md",
        "heading": "०१",
        "sub_idx": 0,
        "vp_clean": "तद् अपः ॥",
        "items": [
          {"pada": "त᳓त्", "just": "*TA*-3, *TS*-1", "vyat_from": None},
          {"pada": "अपः᳓", "just": "*RV*-1", "vyat_from": None},
        ],
      },
      ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
  )
  rep = verify_and_apply_adjudications(sb_root, adj, dry_run=True, enrich_counts=False)
  assert rep.rejected == 1
  assert any("forbidden_ta_source" in e for e in rep.records[0].errors)

  # audit_full_sb_corpus rejects any *TA* in a ŚB file's पद-पाठः
  md_12 = sb_root / "12/01/1.md"
  md_12.write_text(
    """+++
title = "12.1.1"
+++

## ०१

<details open><summary>विश्वास-प्रस्तुतिः</summary>

त᳓द् अपः᳓ ॥
</details>
<details><summary>मूलम् - Weber</summary>

त᳘दपः᳘॥
</details>
<details><summary>मूलम् - श्रीधरादि</summary>

त᳘दपः᳘॥
</details>
<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- त᳓त् (*TA*-3, *TS*-1)
- अपः᳓ (*RV*-1)
</details>
""",
    encoding="utf-8",
  )
  aud = audit_full_sb_corpus(sb_root, files=[md_12])
  assert not aud.passed
  assert any(f.kind == "forbidden_ta_source" for f in aud.failures)

  md_ek = sb_root / "12/01/1.md"
  md_ek.write_text(md_12.read_text(encoding="utf-8").replace("*TA*-3", "*EK* मूल-पाठः"), encoding="utf-8")
  aud_ek = audit_full_sb_corpus(sb_root, files=[md_ek])
  assert not aud_ek.passed
  assert any(f.kind == "forbidden_ek_source" for f in aud_ek.failures)


def test_audit_accepts_ta_ab_stem_counts_and_rejects_zero_bare(tmp_path):
  sb_root = _make_synthetic_corpus(tmp_path)
  md_12 = sb_root / "12/01/1.md"
  base = """+++
title = "12.1.1"
+++

## ०१

<details open><summary>विश्वास-प्रस्तुतिः</summary>

त᳓द् अपः᳓ ॥
</details>
<details><summary>मूलम् - Weber</summary>

त᳘दपः᳘॥
</details>
<details><summary>मूलम् - श्रीधरादि</summary>

त᳘दपः᳘॥
</details>
<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- त᳓त् (*TS*-10/25, *VS*-0/3)
- अपः᳓ (*RV*-5/12)
</details>
"""
  md_12.write_text(base, encoding="utf-8")
  aud_ok = audit_full_sb_corpus(sb_root, files=[md_12])
  assert aud_ok.passed and aud_ok.failures == []

  # Bare -0 and -0/0 are still rejected
  for bad_tag in ("*VS*-0", "*VS*-0/0", "*SB-M*-0", "*SB-K*-0/0"):
    md_12.write_text(base.replace("*VS*-0/3", bad_tag), encoding="utf-8")
    aud_bad = audit_full_sb_corpus(sb_root, files=[md_12])
    assert not aud_bad.passed
    assert any(f.kind == "zero_corpus_count" for f in aud_bad.failures)


def test_kanva_single_witness_bootstrap_and_sbm_tags(tmp_path):
  """Single-witness Kāṇva files (मूलम् + C R Swaminathan) solve, insert open VP, collapse मूलम्, and pass audit."""
  from doc_curation.sanskrit.accent import VedicCorpusCounter, annotate_padapatha_markdown_counts, word_to_key_and_marks

  sb_root = tmp_path / "kanva_sb"
  (sb_root / "01_ekapAtkANDam/01").mkdir(parents=True)
  kanva_md = sb_root / "01_ekapAtkANDam/01/1.md"
  kanva_md.write_text(
    """+++
title = "१"
+++
## ०१

<details open><summary>मूलम्</summary>

त᳘दपः सं᳘भरति॥१॥
</details>

<details><summary>C R Swaminathan</summary>

He collects those waters.
</details>
""",
    encoding="utf-8",
  )

  lex = UnifiedVedicLexicon()
  lex._add_form("तत्", ("U",), "SB-M", freq=10)
  lex._add_form("अपः", ("", "U"), "SB-M", freq=5)
  lex._add_form("सम्", ("U",), "SB-M", freq=10)
  lex._add_form("भरति", ("", "", ""), "SB-M", freq=10)
  lex._get_slp_stems()
  lex.slp_vocab = {"tat": 10, "apaH": 5, "sam": 10, "Barati": 10}

  out_dir = tmp_path / "kanva_out"
  summary = run_solver_corpus_pass(
    sb_root, out_dir, apply_auto_clean=True, max_workers=1, lexicon=lex, witness_mode="single",
  )
  assert summary["apply_errors"] == []
  assert summary["auto_clean"] == 1

  written = kanva_md.read_text(encoding="utf-8")
  assert "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nत᳓दपः᳓ सं᳓भरति॥\n</details>" in written
  assert "<details><summary>मूलम्</summary>\n\nत᳘दपः सं᳘भरति॥१॥\n</details>" in written
  assert "<details><summary>पद-पाठः (यान्त्रिकः)</summary>" in written
  assert "*SB-M*-10" in written
  assert "<details><summary>C R Swaminathan</summary>" in written

  aud = audit_full_sb_corpus(sb_root, files=[kanva_md])
  assert aud.passed and aud.failures == []

  # SB-M and SB-K provenance counting work cleanly with skip_tags
  vc = VedicCorpusCounter()
  for corp, w, f in [
    ("SB-M", "त᳓त्", 12), ("SB-M", "अपः᳓", 6), ("SB-M", "स᳓म्", 11), ("SB-M", "भरति", 10),
    ("SB-K", "त᳓त्", 9),
  ]:
    km = word_to_key_and_marks(w)
    assert km is not None
    vc._add(corp, km[0], km[1], freq=f)
  vc._finalize_secondary_tables()
  enriched, unres = annotate_padapatha_markdown_counts(
    written, vc, prune_unverified_standalone_tags=True, enrich_major_corpora=True,
    major_corpora=("SB-M",), skip_tags=frozenset({"SB-K", "ŚB"}),
  )
  assert unres == []
  assert "*SB-K*" not in enriched

  enriched_with_k, unres_with_k = annotate_padapatha_markdown_counts(
    written, vc, prune_unverified_standalone_tags=True, enrich_major_corpora=True,
    major_corpora=("SB-M", "SB-K"), skip_tags=frozenset({"ŚB"}),
  )
  assert unres_with_k == []
  assert "*SB-K*-9" in enriched_with_k


def test_kanva_orthography_quirks_and_unaccented_yantra(tmp_path):
  """Kāṇva ꣳ/:/ZWJ/line-wrap quirks normalize cleanly and unaccented blocks verify via (यन्त्र-स्वरः)."""
  from doc_curation.sanskrit.accent import (
    extract_sb_syllables,
    normalize_kanva_mula_for_sb,
    normalize_sb_orthography,
    verify_and_apply_adjudications,
  )

  # Normalization + syllable extraction checks
  assert normalize_kanva_mula_for_sb("श\u200dृणो᳘ति:") == "शृणो᳘तिः"
  assert normalize_kanva_mula_for_sb("सौम्यादा᳘ज्य- भागाद्यन्ति य᳘था-यथा") == "सौम्यादा᳘ज्यभागाद्यन्ति य᳘था-यथा"
  assert normalize_sb_orthography("पा᳘ꣳ᳘") == "पां"
  syls = extract_sb_syllables("पा᳘ꣳ᳘ तपः᳘", source="shri")
  assert [s.mark for s in syls] == ["H", "", "H"]

  sb_root = tmp_path / "kanva_edge"
  (sb_root / "01_ekapAtkANDam/06").mkdir(parents=True)
  md = sb_root / "01_ekapAtkANDam/06/4.md"
  md.write_text(
    """+++
title = "४"
+++
## ०५

<details open><summary>मूलम्</summary>

पा᳘ꣳ श\u200dृणोति त᳘प:।
</details>

<details><summary>C R Swaminathan</summary>

Kandika 5.
</details>

## ०६

<details open><summary>मूलम्</summary>

त᳘द- पः सं᳘भरति॥६॥
</details>

<details><summary>C R Swaminathan</summary>

Kandika 6.
</details>

## ०७

<details open><summary>मूलम्</summary>

तदपः॥७॥
</details>

<details><summary>C R Swaminathan</summary>

Unaccented Kandika 7.
</details>
""",
    encoding="utf-8",
  )

  lex = UnifiedVedicLexicon()
  for w, m, f in [
    ("पाम्", ("U",), 8),
    ("शृणोति", ("", "", ""), 8),
    ("तपः", ("U", ""), 8),
    ("तत्", ("U",), 10),
    ("अपः", ("", "U"), 5),
    ("सम्", ("U",), 10),
    ("भरति", ("", "", ""), 10),
  ]:
    lex._add_form(w, m, "SB-M", freq=f)
  lex._get_slp_stems()
  lex.slp_vocab = {"pAm": 8, "SfRoti": 8, "tapaH": 8, "tat": 10, "apaH": 5, "sam": 10, "Barati": 10}

  out_dir = tmp_path / "kanva_edge_out"
  summary = run_solver_corpus_pass(
    sb_root, out_dir, apply_auto_clean=True, max_workers=1, lexicon=lex, witness_mode="single",
  )
  assert summary["apply_errors"] == []
  assert summary["auto_clean"] == 2
  assert summary["needs_adjudication"] == 1

  written1 = md.read_text(encoding="utf-8")
  assert "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nपा᳓ꣳ" not in written1
  assert "पां᳓ शृणोति त᳓पः।" in written1
  assert "त᳓दपः᳓ सं᳘भरति॥" not in written1
  assert "त᳓दपः᳓ सं᳓भरति॥" in written1

  adj_in = out_dir / "yantra_fix.jsonl"
  import json
  adj_in.write_text(
    json.dumps({
      "rel_path": "01_ekapAtkANDam/06/4.md",
      "heading": "०७",
      "sub_idx": 0,
      "kandika_id": "01/06/4.07",
      "vp_clean": "तदपः॥",
      "items": [
        {"pada": "त᳓त्", "just": "*SB-M*-10"},
        {"pada": "अपः᳓", "just": "*SB-M*-5"},
      ],
    }, ensure_ascii=False) + "\n",
    encoding="utf-8",
  )
  adj_res = verify_and_apply_adjudications(sb_root, adj_in, dry_run=False, enrich_counts=False)
  assert adj_res.rejected == 0 and adj_res.accepted == 1

  written2 = md.read_text(encoding="utf-8")
  assert "<details open><summary>विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)</summary>\n\nत᳓दपः᳓॥\n</details>" in written2
  aud = audit_full_sb_corpus(sb_root, files=[md])
  assert aud.passed and aud.failures == []

  # Unspaced Kāṇva avagraha chunks (`वज्रोऽसीति`, `सवनेऽभिषिञ्चन्ति`) and `ॐ` split cleanly
  from doc_curation.sanskrit.accent.shatapatha_solver import split_chunk_to_padas_dp
  assert split_chunk_to_padas_dp("ॐ", lex) == ["ओम्"]
  lex_av = UnifiedVedicLexicon()
  for w, m, f in [("वज्रः", ("U", ""), 10), ("असि", ("", ""), 10), ("इति", ("U", ""), 10), ("सवने", ("", "", "U"), 5), ("अपि", ("U", ""), 10)]:
    lex_av._add_form(w, m, "SB-M", freq=f)
  lex_av._get_slp_stems()
  lex_av.slp_vocab = {"vajraH": 10, "asi": 10, "iti": 10, "savane": 5, "api": 10}
  assert split_chunk_to_padas_dp("वज्रोऽसीति", lex_av) == ["वज्रः", "असि", "इति"]
  assert split_chunk_to_padas_dp("सवनेऽपीति", lex_av) == ["सवने", "अपि", "इति"]
