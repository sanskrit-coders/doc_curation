"""Tests for RV and AV standalone mUlam/ consolidation into sarvASh_TIkAH/."""
from pathlib import Path

from doc_curation_projects.veda.dedup.mulam_merger import (
  CorpusMulamSpec,
  consolidate_corpus_mula,
  extract_mula_blocks,
)


def _make_spec(tmp_path: Path, name: str, label: str, pada_summary: str) -> CorpusMulamSpec:
  base = tmp_path / "vishvasa" / f"vedAH_{name}" / "static" / "korpus"
  return CorpusMulamSpec(
    name=name,
    shAkha_label=label,
    mula_dir=base / "mUlam",
    sarva_dir=base / "sarvASh_TIkAH",
    mula_url_prefix=f"/vedAH_{name}/korpus/mUlam/",
    vp_url_prefix=f"/vedAH_{name}/korpus/vishvAsa-prastutiH/",
    sarva_url_prefix=f"/vedAH_{name}/korpus/sarvASh_TIkAH/",
    pada_summary=pada_summary,
  )


def test_extract_mula_blocks_rv_bare_and_taittiriya():
  txt = (
    '+++\ntitle = "08"\n+++\n'
    "तं य॒ज्ञम् ।\n\n"
    "<details><summary>मूलम् - तैत्तिरीयम्</summary>\n\nयो दे॒वेभ्यः॑ ।\n</details>\n"
  )
  blocks = extract_mula_blocks(txt, "शाकलम्")
  assert blocks == [
    ("मूलम् - शाकलम्", "तं य॒ज्ञम् ।"),
    ("मूलम् - तैत्तिरीयम्", "यो दे॒वेभ्यः॑ ।"),
  ]


def test_extract_mula_blocks_av_vs_and_vh():
  txt = (
    '+++\ntitle = "03"\n+++\n'
    "<details><summary>मूलम् (VH)</summary>\n\nष॒ळृ॒चेभ्यः॑ ।\n</details>\n\n"
    "<details><summary>मूलम् (VS)</summary>\n\nष॑डृ॒चेभ्यः॑ ।\n</details>\n"
  )
  blocks = extract_mula_blocks(txt, "शौनकम्")
  assert blocks == [
    ("मूलम् - शौनकम्", "ष॑डृ॒चेभ्यः॑ ।"),
    ("मूलम् - शौनकम् (VH)", "ष॒ळृ॒चेभ्यः॑ ।"),
  ]


def test_consolidate_corpus_mula_updates_callers_prefills_and_deletes(tmp_path: Path):
  spec = _make_spec(tmp_path, "RV", "शाकलम्", "पद-पाठः")
  vp_dir = spec.mula_dir.parent / "vishvAsa-prastutiH"
  for d in (spec.mula_dir / "01" / "001", spec.sarva_dir / "01" / "001", vp_dir / "01" / "001"):
    d.mkdir(parents=True)

  (spec.mula_dir / "_index.md").write_text("+++\ntitle = 'mUlam'\n+++\n", encoding="utf-8")
  (spec.mula_dir / "01" / "001" / "01_agni.md").write_text("+++\ntitle = '01'\n+++\nअ॒ग्निमी॑ळे ।\n", encoding="utf-8")
  (vp_dir / "01" / "001" / "01_agni.md").write_text("+++\ntitle = '01'\n+++\nअग्नि᳓म् ईळे ।\n", encoding="utf-8")
  (spec.sarva_dir / "01" / "001" / "01_agni.md").write_text(
    "+++\ntitle = '01'\n+++\n"
    "<details><summary>Griffith</summary>\n\nI laud Agni.\n</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nअ॒ग्निम् आ ई॑ळे ।\n</details>\n\n"
    "<details><summary>पद-पाठः</summary>\n\nअ॒ग्निम् ।\n</details>\n\n"
    "<details><summary>पद-पाठः-तैत्तिरीयः</summary>\n\nअ॒ग्निम् ।\n</details>\n",
    encoding="utf-8",
  )

  content_root = tmp_path / "vishvasa" / "vedAH_RV" / "content"
  other_root = tmp_path / "vishvasa" / "devaH" / "content"
  content_root.mkdir(parents=True)
  other_root.mkdir(parents=True)

  # Host with both mUlam/ and sarvASh_TIkAH/
  host_both = content_root / "01.md"
  host_both.write_text(
    '<div class="js_include" newlevelforh1="5" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH_RV/korpus/vishvAsa-prastutiH/01/001/01_agni.md">\n'
    "<details open><summary><h5>विश्वास-प्रस्तुतिः …{Loading}…</h5></summary>\n\nअग्नि᳓म् ईळे ।\n</details>\n</div>\n"
    '<div class="js_include collapsed" newlevelforh1="5" title="मूलम्" unfilled url="/vedAH_RV/korpus/mUlam/01/001/01_agni.md">\n'
    "<details><summary><h5>मूलम् …{Loading}…</h5></summary>\n\nअ॒ग्निमी॑ळे ।\n</details>\n</div>\n"
    '<div class="js_include collapsed" newlevelforh1="5" title="सर्वाष् टीकाः" unfilled url="/vedAH_RV/korpus/sarvASh_TIkAH/01/001/01_agni.md">\n'
    "<details><summary><h5>सर्वाष् टीकाः …{Loading}…</h5></summary>\n\nold\n</details>\n</div>\n",
    encoding="utf-8",
  )
  # Prayoga caller with includetitle="false" and no sarvASh_TIkAH
  host_prayoga = other_root / "prayoga.md"
  host_prayoga.write_text(
    '<div class="js_include" includetitle="false" newlevelforh1="5" unfilled url="/vedAH_RV/korpus/mUlam/01/001/01_agni.md">\n\nअ॒ग्निमी॑ळे ।\n</div>\n',
    encoding="utf-8",
  )

  res = consolidate_corpus_mula(
    spec,
    caller_roots=(content_root, other_root),
    hugo_base_dir=str(tmp_path / "vishvasa"),
    dry_run=False,
    delete_mula_dir=True,
  )
  assert res["deleted_mula_dir"] is True
  assert res["remaining_refs"] == 0
  assert not spec.mula_dir.exists()

  sarva_out = (spec.sarva_dir / "01" / "001" / "01_agni.md").read_text(encoding="utf-8")
  assert "<summary>मूलम् - शाकलम्</summary>" in sarva_out
  assert "<summary>मूलम् - तैत्तिरीयम्</summary>" in sarva_out
  assert "<summary>पदपाठः - तैत्तिरीयः</summary>" in sarva_out
  assert sarva_out.index("मूलम् - शाकलम्") < sarva_out.index("<summary>पद-पाठः</summary>")

  both_out = host_both.read_text(encoding="utf-8")
  assert "/mUlam/" not in both_out
  assert "<summary>मूलम् - शाकलम्</summary>" in both_out

  prayoga_out = host_prayoga.read_text(encoding="utf-8")
  assert "/vishvAsa-prastutiH/01/001/01_agni.md" in prayoga_out
  assert "अग्नि᳓म् ईळे" in prayoga_out


def test_consolidate_corpus_mula_handles_nested_outer_prefill(tmp_path: Path):
  spec = _make_spec(tmp_path, "RV", "शाकलम्", "पद-पाठः")
  vp_dir = spec.mula_dir.parent / "vishvAsa-prastutiH"
  for d in (spec.mula_dir / "01" / "001", spec.sarva_dir / "01" / "001", vp_dir / "01" / "001"):
    d.mkdir(parents=True)
  (spec.mula_dir / "01" / "001" / "01_agni.md").write_text("+++\ntitle = '01'\n+++\nअ॒ग्निमी॑ळे ।\n", encoding="utf-8")
  (vp_dir / "01" / "001" / "01_agni.md").write_text("+++\ntitle = '01'\n+++\nअग्नि᳓म् ईळे ।\n", encoding="utf-8")
  (spec.sarva_dir / "01" / "001" / "01_agni.md").write_text(
    "+++\ntitle = '01'\n+++\n<details><summary>पद-पाठः</summary>\n\nअ॒ग्निम् ।\n</details>\n",
    encoding="utf-8",
  )
  yajuh_content = tmp_path / "vishvasa" / "vedAH_yajuH" / "content"
  deva_content = tmp_path / "vishvasa" / "devaH" / "content"
  yajuh_content.mkdir(parents=True)
  deva_content.mkdir(parents=True)

  mid = yajuh_content / "tb_sec.md"
  mid.write_text(
    '<div class="js_include collapsed" newlevelforh1="5" title="मूलम्" unfilled url="/vedAH_RV/korpus/mUlam/01/001/01_agni.md">\n'
    "<details><summary><h5>मूलम् …{Loading}…</h5></summary>\n\nअ॒ग्निमी॑ळे ।\n</details>\n</div>\n"
    '<div class="js_include collapsed" newlevelforh1="5" title="सर्वाष् टीकाः" unfilled url="/vedAH_RV/korpus/sarvASh_TIkAH/01/001/01_agni.md">\n'
    "<details><summary><h5>सर्वाष् टीकाः …{Loading}…</h5></summary>\n\nold\n</details>\n</div>\n",
    encoding="utf-8",
  )
  outer = deva_content / "stotra.md"
  outer.write_text(
    '<div class="js_include" includetitle="false" newlevelforh1="5" unfilled url="/vedAH_yajuH/tb_sec">\n\n'
    + mid.read_text(encoding="utf-8")
    + "</div>\n",
    encoding="utf-8",
  )
  # Wait: resolve_include_file_path maps /vedAH_yajuH/static/... or /vedAH_yajuH/... -> static or content? Use explicit static/tb_sec.md URL matching repo layout:
  mid_static = tmp_path / "vishvasa" / "vedAH_yajuH" / "static" / "tb_sec.md"
  mid_static.parent.mkdir(parents=True, exist_ok=True)
  mid_static.write_text(mid.read_text(encoding="utf-8"), encoding="utf-8")
  mid.unlink()
  outer.write_text(
    '<div class="js_include" includetitle="false" newlevelforh1="5" unfilled url="/vedAH_yajuH/tb_sec.md">\n\n'
    + mid_static.read_text(encoding="utf-8")
    + "</div>\n",
    encoding="utf-8",
  )

  res = consolidate_corpus_mula(
    spec,
    caller_roots=(mid_static.parent, deva_content),
    hugo_base_dir=str(tmp_path / "vishvasa"),
    dry_run=False,
    delete_mula_dir=True,
  )
  assert res["remaining_refs"] == 0
  assert res["deleted_mula_dir"] is True
  assert "/mUlam/" not in outer.read_text(encoding="utf-8")
  assert "<summary>मूलम् - शाकलम्</summary>" in outer.read_text(encoding="utf-8")
