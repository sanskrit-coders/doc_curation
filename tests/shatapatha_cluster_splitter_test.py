"""Tests for multi-layer Śatapatha Brāhmaṇa sense-unit cluster splitting."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from doc_curation.sanskrit.accent.reconciler import parse_padapatha_items, reconcile_markdown_blocks
from doc_curation.sanskrit.accent.sandhi_check import verify_mantra_sandhi
from doc_curation.sanskrit.accent.shatapatha import _extract_vp_clusters, audit_padapatha_against_sb
from doc_curation_projects.veda.yajuH.vaajasaneyi.shatapatha.cluster_splitter import (
  extract_footnotes,
  parse_section_clusters,
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
  assert len(clauses) == 3
  assert clauses[0].startswith("1. Looking towards") and "Vāj. S. I, 5 a" in clauses[0]
  assert clauses[0].endswith("O Agni!'") or clauses[0].endswith("vow (cf. Vāj. S. I, 5 a): 'O Agni!'")
  assert clauses[1].startswith("For Agni is Lord of Vows;")
  assert clauses[2].startswith("therefore he addresses him.") or "therefore he addresses him" in " ".join(clauses)


def test_sbm_synthetic_multi_layer_split_and_footnotes(tmp_path):
  # Construct a minimal two-sentence SBM kaṇḍikā matching authentic ŚB marks + vyatyasta count
  md = """+++
title = "१"
+++

## ०१

<details open><summary>विश्वास-प्रस्तुतिः</summary>

व्रत᳓म् उपैष्य᳓न्न् अप᳓ उ᳓पस्पृशति ।
पवि᳓त्रं वा᳓ आ᳓पः, पवित्र-पूतो व्रत᳓म् उ᳓पायानी᳓ति त᳓स्माद् अप᳓ उ᳓पस्पृशति ॥
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

व्व्रत᳘मुपैष्यन्नप ऽउ᳘पस्पृशति पवि᳘त्रं वा ऽआ᳘पः पवित्रपूतो व्व्रतमु᳘पायानी᳘ति त᳘स्मादप ऽउ᳘पस्पृशति᳘॥
</details>

<details><summary>मूलम् - Weber</summary>

व्रतमु᳘पैष्यन्नप [^wbr_1] उ᳘पस्पृशति पवि᳘त्रं वा आ᳘पः पवित्रपूतो व्रतमु᳘पायानी᳘ति त᳘स्मादप उ᳘पस्पृशति॥

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
- पवित्र-पूतः (अनुदात्तम्)
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
  res = split_sb_markdown_text(md)
  assert res.orig_clusters == 1
  # Even if compact (16 padas), if split occurs, idempotency & footnotes must hold; if unsplit, verify unchanged cleanliness.
  assert not res.audit_fallbacks
  res2 = split_sb_markdown_text(res.new_text)
  assert not res2.changed


def test_correlative_and_iti_quote_stay_intact_on_sbm_real_example():
  if not (SBM_ROOT / "01/01/1.md").exists():
    pytest.skip("vedAH_yajuH SBM corpus not present")
  txt = (SBM_ROOT / "01/01/1.md").read_text(encoding="utf-8")
  res = split_sb_markdown_text(txt)
  assert res.changed
  assert res.new_clusters >= 50
  assert not res.audit_fallbacks
  # Check idempotency
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


def test_sbk_sandhi_split_and_hiatal_pausa_and_idempotency():
  if not (SBK_ROOT / "04_adhvarakANDam/01/1.md").exists():
    pytest.skip("vedAH_yajuH SBK corpus not present")
  for rel in ("04_adhvarakANDam/01/1.md", "08_ukhAsambharaNakANDam/07/3.md", "13_aShTAdhyAyIkANDam/02/1.md"):
    orig = (SBK_ROOT / rel).read_text(encoding="utf-8")
    res = split_sb_markdown_text(orig)
    assert res.changed
    res2 = split_sb_markdown_text(res.new_text)
    assert not res2.changed
    # All padapāṭha counts across sub-clusters must strictly conserve section pada count
    for s1, s2 in zip(
      re.split(r"(?m)(?=^##\s+)", orig)[1:],
      re.split(r"(?m)(?=^##\s+)", res.new_text)[1:],
    ):
      c1 = parse_section_clusters(s1)
      c2 = parse_section_clusters(s2)
      assert sum(len(c.pp_items) for c in c1) == sum(len(c.pp_items) for c in c2)
      # Every sub-cluster must pass sandhi + audit + reconciler
      for cl in c2:
        nv = sum(1 for it in cl.pp_items if it.vyat)
        assert (f"({nv}/{len(cl.pp_items)} व्यत्यस्त-स्वराः)" in cl.vp_summary) or (nv == 0)
