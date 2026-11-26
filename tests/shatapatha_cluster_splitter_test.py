"""Tests for multi-layer Śatapatha Brāhmaṇa sense-unit cluster splitting."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from doc_curation.sanskrit.accent.reconciler import LEAF_DETAILS_RE, parse_padapatha_items, reconcile_markdown_blocks
from doc_curation.sanskrit.accent.sandhi_check import verify_mantra_sandhi
from doc_curation.sanskrit.accent.shatapatha import _extract_vp_clusters, audit_padapatha_against_sb
from doc_curation.sanskrit.accent.shatapatha_batch import audit_full_sb_corpus
from doc_curation_projects.veda.yajuH.vaajasaneyi.shatapatha.cluster_splitter import (
  extract_footnotes,
  format_sb_canonical_blocks,
  parse_section_clusters,
  reorder_sb_translations_below_vp,
  split_english_clauses,
  split_sb_markdown_text,
)

SBM_ROOT = Path(
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH"
)
SBK_ROOT = Path(
  "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/kANvam/shatapatha-brAhmaNam/sarva-prastutiH"
)


def test_split_english_clauses_respects_abbreviations_and_footnotes():
  txt = (
    "1. Looking towards the fire [^egg_85], he enters on the vow (cf. Vāj. S. I, 5 a): "
    "'O Agni!' For Agni is Lord of Vows; therefore he addresses him. "
    "He thus prospers [^egg_86]."
  )
  clauses = split_english_clauses(txt)
  assert len(clauses) == 4
  assert clauses[0].startswith("1. Looking towards") and "Vāj. S. I, 5 a" in clauses[0]
  assert clauses[0].endswith("O Agni!'")
  assert clauses[1] == "For Agni is Lord of Vows;"
  assert clauses[2] == "therefore he addresses him."
  assert clauses[3] == "He thus prospers [^egg_86]."


def test_sbm_synthetic_multi_layer_split_and_footnotes(tmp_path):
  # Construct a minimal two-sentence SBM kaṇḍikā matching authentic ŚB marks + vyatyasta count
  md = """+++
title = "१"
+++

## ०१

<details open><summary>विश्वास-प्रस्तुतिः</summary>

व्रत᳓म् उपैष्य᳓न्न् अप᳓ उ᳓पस्पृशति ।
पवि᳓त्रं वा᳓ आ᳓पः, पवि᳓त्र-पूतो व्रत᳓म् उ᳓पायानी᳓ति त᳓स्माद् अप᳓ उ᳓पस्पृशति ॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

व्व्रत᳘मुपैष्य᳘न्नप ऽउ᳘पस्पृशति पवि᳘त्रं वा ऽआ᳘पः पवि᳘त्रपूतो व्व्रतमु᳘पायानी᳘ति त᳘स्मादप ऽउ᳘पस्पृशति᳘॥
</details>

<details><summary>मूलम् - Weber</summary>

व्रतमु᳘पैष्य᳘न्नप [^wbr_1] उ᳘पस्पृशति पवि᳘त्रं वा आ᳘पः पवि᳘त्रपूतो व्रतमु᳘पायानी᳘ति त᳘स्मादप उ᳘पस्पृशति॥

[^wbr_1]: Test Weber variant note.
</details>

<details><summary>मूलम् - विस्वरम्</summary>

**व्रतोपायनम् ।**

व्रतमुपैष्यन्नप उपस्पृशति । पवित्रं वा आपः । पवित्रपूतो व्रतमुपायानीति । तस्मादप उपस्पृशति ॥ १ ॥
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- व्रत᳓म् (*TS*-1)
- उप-एष्य᳓न् (*TS*-1)
- अपः᳓ (*TS*-1)
- उ᳓प (*TS*-1)
- स्पृशति (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
- पवि᳓त्रम् (*TS*-1)
- वै᳓ (*TS*-1)
- आ᳓पः (*TS*-1)
- पवि᳓त्र-पूतः (*SB-M*-1)
- व्रत᳓म् (*TS*-1)
- उ᳓प-अयानि (*TS*-1)
- इ᳓ति (*TS*-1)
- त᳓स्मात् (*TS*-1)
- अपः᳓ (*TS*-1)
- उ᳓प (*TS*-1)
- स्पृशति (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
</details>

<details><summary>सायणः</summary>

**व्रतमुपैष्यन्निति** । व्रतग्रहणार्थम् अपः स्पृशति [^१_१] ।

अथ स्पर्शने हेतुमाह- **पवित्रं वा** इति । जलस्य पावित्र्यादिति भावः [^२_१] ।

[^१_१]: Sāyaṇa note 1.

[^२_१]: Sāyaṇa note 2.
</details>

<details><summary>Eggeling</summary>

1. About to enter on the vow, he touches water [^egg_1]. Pure indeed are the waters; thinking 'pure I will enter the vow', therefore he touches water [^egg_2].

[^egg_1]: Eggeling note 1.

[^egg_2]: Eggeling note 2.
</details>
"""
  res = split_sb_markdown_text(md, wrap_sarva=True)
  assert res.orig_clusters == 1
  assert not res.audit_fallbacks
  assert res.changed
  assert "<summary>सर्वाष् टीकाः</summary>" in res.new_text
  # Translation must sit directly below विश्वास-प्रस्तुतिः inside सर्वाष् टीकाः, before मूलम्
  wrapped_pos = res.new_text.index("<summary>सर्वाष् टीकाः</summary>")
  egg_pos = res.new_text.index("<summary>Eggeling</summary>")
  mula_pos = res.new_text.index("<summary>मूलम् - श्रीधरादि</summary>")
  assert wrapped_pos < egg_pos < mula_pos
  res2 = split_sb_markdown_text(res.new_text, wrap_sarva=True)
  assert not res2.changed
  assert format_sb_canonical_blocks(res.new_text) == res.new_text
  # Wrapped file must pass full ŚB audit cleanly
  p = tmp_path / "01/01/1.md"
  p.parent.mkdir(parents=True, exist_ok=True)
  p.write_text(res.new_text, encoding="utf-8")
  rep = audit_full_sb_corpus(tmp_path, files=[p])
  assert rep.passed and not rep.failures

  # Also test duplicate trailing Eggeling blocks in one cluster (like 04/03/4 ## 33) do not drop footnotes
  dup_md = md.replace(
    "<details><summary>Eggeling</summary>\n\n1. About to enter",
    "<details><summary>Eggeling</summary>\n\nExtra note [^egg_extra].\n\n[^egg_extra]: Kept.\n</details>\n\n<details><summary>Eggeling</summary>\n\n1. About to enter",
  )
  reord = format_sb_canonical_blocks(dup_md)
  assert "[^egg_extra]:" in reord and "[^egg_1]:" in reord and "[^egg_2]:" in reord
  assert format_sb_canonical_blocks(reord) == reord


def test_correlative_and_iti_quote_stay_intact_on_sbm_real_example(tmp_path):
  if not (SBM_ROOT / "01/01/1.md").exists():
    pytest.skip("vedAH_yajuH SBM corpus not present")
  txt = (SBM_ROOT / "01/01/1.md").read_text(encoding="utf-8")
  res = split_sb_markdown_text(txt)
  assert not res.audit_fallbacks
  assert res.new_clusters >= 50
  # Idempotent regardless of whether corpus file is already split/wrapped
  res2 = split_sb_markdown_text(res.new_text)
  assert not res2.changed
  # Check ## ०१ keeps `तद् यद् ...` unified with its `अमेध्यो...` answer & preserves footnotes
  sec1 = re.search(r"^##\s+०१\b.*?(?=^## |\Z)", res.new_text, re.M | re.S).group(0)
  clusters = parse_section_clusters(sec1)
  assert len(clusters) >= 3
  assert "अमेध्यो᳓" in clusters[1].vp_body
  assert "व्रत᳓म् उपैष्य᳓न्न्" in clusters[0].vp_body
  assert sum(len(c.pp_items) for c in clusters) == 48
  # Footnote [^wbr_1] must reside cleanly inside Weber block that references it
  assert "[^wbr_1]:" in dict((s, b) for s, b, _ in clusters[0].mulam_blocks)["मूलम् - Weber"]
  # Canonical reorder + wrap passes audit_full_sb_corpus and stays idempotent
  canon = format_sb_canonical_blocks(res.new_text)
  assert format_sb_canonical_blocks(canon) == canon
  assert not split_sb_markdown_text(canon).changed
  tp = tmp_path / "01/01/1.md"
  tp.parent.mkdir(parents=True, exist_ok=True)
  tp.write_text(canon, encoding="utf-8")
  rep = audit_full_sb_corpus(tmp_path, files=[tp])
  assert rep.passed and not rep.failures


def test_sbk_sandhi_split_and_hiatal_pausa_and_idempotency():
  if not (SBK_ROOT / "04_adhvarakANDam/01/1.md").exists():
    pytest.skip("vedAH_yajuH SBK corpus not present")
  for rel in ("04_adhvarakANDam/01/1.md", "08_ukhAsambharaNakANDam/07/3.md", "13_aShTAdhyAyIkANDam/02/1.md"):
    orig = (SBK_ROOT / rel).read_text(encoding="utf-8")
    res = split_sb_markdown_text(orig)
    res2 = split_sb_markdown_text(res.new_text)
    assert not res2.changed
    canon = format_sb_canonical_blocks(res.new_text)
    assert format_sb_canonical_blocks(canon) == canon
    assert not split_sb_markdown_text(canon).changed
    # All padapāṭha counts across sub-clusters must strictly conserve section pada count
    for s1, s2 in zip(
      re.split(r"(?m)(?=^##\s+)", orig)[1:],
      re.split(r"(?m)(?=^##\s+)", res.new_text)[1:],
    ):
      c1 = parse_section_clusters(s1)
      c2 = parse_section_clusters(s2)
      assert sum(len(c.pp_items) for c in c1) == sum(len(c.pp_items) for c in c2)
      # Every sub-cluster must match summary and leaf structure
      for cl in c2:
        nv = sum(1 for it in cl.pp_items if it.vyat)
        assert (f"({nv}/{len(cl.pp_items)} व्यत्यस्त-स्वराः)" in cl.vp_summary) or (nv == 0)


def test_idempotent_when_sequential_clusters_share_prefix():
  md = """## ०४

<details open><summary>विश्वास-प्रस्तुतिः</summary>

एत᳓द्ध स्म वै᳓ त᳓द्विद्वा᳓न् आ᳓रुणिराह ।
</details>

<details><summary>सर्वाष् टीकाः</summary>

<details><summary>मूलम्</summary>

एत᳘द्ध स्म वै त᳘द्विद्वा᳘न् आ᳘रुणिराह
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- एत᳓त् (*TS*-319)
- ह (अनुदात्तम्, पा॰ ८.१.१८)
- स्म (अनुदात्तम्, पा॰ ८.१.१८)
- वै᳓ (*TS*-2126)
- त᳓त् (*TS*-687)
- विद्वा᳓न् (*TS*-93)
- आ᳓रुणिः (*SB-M*-12)
- आह (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
</details>
</details>

<details open><summary>विश्वास-प्रस्तुतिः</summary>

एत᳓द्ध स्म वै᳓ त᳓द्विद्वा᳓न्ना᳓को मौ᳓द्गल्य आह ।
</details>

<details><summary>सर्वाष् टीकाः</summary>

<details><summary>मूलम्</summary>

एत᳘द्ध स्म वै त᳘द्विद्वा᳓न्ना᳓को मौ᳓द्गल्य आह
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- एत᳓त् (*TS*-319)
- ह (अनुदात्तम्, पा॰ ८.१.१८)
- स्म (अनुदात्तम्, पा॰ ८.१.१८)
- वै᳓ (*TS*-2126)
- त᳓त् (*TS*-687)
- विद्वा᳓न् (*TS*-93)
- ना᳓कः (*SB-M*-17)
- मौ᳓द्गल्यः (*SB-M*-2)
- आह (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८)
</details>
</details>
"""
  res = split_sb_markdown_text(md)
  assert not res.changed
  assert format_sb_canonical_blocks(md) == md

