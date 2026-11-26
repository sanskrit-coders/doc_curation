"""Tests for cross-corpus static sarvASh_TIkAH header qualification and SB cluster compatibility."""
from __future__ import annotations

import pathlib

from doc_curation.sanskrit.accent.shatapatha import _extract_vp_clusters
from doc_curation_projects.veda.dedup.commentary_merger import qualify_cross_corpus_sarva_tika
from doc_curation_projects.veda.dedup.static_fixer import inline_single_caller_veda_static


def _write(path: pathlib.Path, content: str) -> pathlib.Path:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(content, encoding="utf-8")
  return path


def test_qualify_cross_corpus_sarva_tika_sorts_and_qualifies(tmp_path: pathlib.Path) -> None:
  sb_caller = (
    tmp_path
    / "vedAH_yajuH"
    / "content"
    / "vAjasaneyam"
    / "mAdhyandinam"
    / "shatapatha-brAhmaNam"
    / "sarva-prastutiH"
    / "01/08/1.md"
  )
  ms_sarva = """<details><summary>सर्वाष् टीकाः</summary>

<details><summary>Gemini 3.8 Flash</summary>

English gloss.
</details>

<details><summary>मूलम्</summary>

अग्नि᳓म् ईळे।
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

अग्नि᳘म् ईळे॥
</details>

<details><summary>मूलम् - Weber</summary>

अग्नि᳘म् ईळे॥
</details>

<details><summary>पद-पाठः (यान्त्रिकः - 1/2 व्यत्यस्त-स्वराः)</summary>

- अग्नि᳓म् (*RV*-1)
- ईळे (तिङन्तम्)
</details>

<details><summary>पद-पाठः (यान्त्रिकः - माध्यन्दिन-ब्राह्मणम्)</summary>

- अग्नि᳓म् (*RV*-1)
- ईळे (तिङन्तम्)
</details>

<details><summary>सायणः (माध्यन्दिन-ब्राह्मणम्)</summary>

भाष्यम्।
</details>
</details>"""

  out = qualify_cross_corpus_sarva_tika(
    ms_sarva,
    src_url="/vedAH_yajuH/maitrAyaNIyam/saMhitA/Rk/sarvASh_TIkAH/01/01_agnim.md",
    caller_fp=sb_caller,
  )
  assert "<summary>मूलम् - मैत्रायणीयम्</summary>" in out
  assert "<summary>पद-पाठः (यान्त्रिकः - मैत्रायणीयम् - 1/2 व्यत्यस्त-स्वराः)</summary>" in out
  assert out.index("<summary>मूलम् - Weber</summary>") < out.index("<summary>पद-पाठः (यान्त्रिकः - माध्यन्दिन-ब्राह्मणम्)</summary>")
  assert out.index("<summary>पद-पाठः (यान्त्रिकः - माध्यन्दिन-ब्राह्मणम्)</summary>") < out.index("<summary>मूलम् - मैत्रायणीयम्</summary>")
  assert out.index("<summary>मूलम् - मैत्रायणीयम्</summary>") < out.index("<summary>पद-पाठः (यान्त्रिकः - मैत्रायणीयम् - 1/2 व्यत्यस्त-स्वराः)</summary>")
  assert out.index("<summary>पद-पाठः (यान्त्रिकः - मैत्रायणीयम् - 1/2 व्यत्यस्त-स्वराः)</summary>") < out.index("<summary>सायणः (माध्यन्दिन-ब्राह्मणम्)</summary>")

  section = "## ०१\n\n<details open><summary>विश्वास-प्रस्तुतिः - ऋक्</summary>\n\nअग्नि᳓म् ईळे ।\n</details>\n\n" + out
  clusters = _extract_vp_clusters(section)
  assert len(clusters) == 1
  assert clusters[0].existing_pp_match is not None
  assert "माध्यन्दिन-ब्राह्मणम्" in clusters[0].existing_pp_match.group(1)
  assert clusters[0].weber_text == "अग्नि᳘म् ईळे॥"
  assert clusters[0].shri_text == "अग्नि᳘म् ईळे॥"


def test_inline_single_caller_cross_corpus_ms_and_ts_into_sbm(tmp_path: pathlib.Path) -> None:
  vishvasa = tmp_path / "vishvAsa"
  static_root = vishvasa / "vedAH_yajuH" / "static"

  ms_static = _write(
    static_root / "maitrAyaNIyam/saMhitA/Rk/sarvASh_TIkAH/01/test_ms.md",
    """+++
title = "test_ms"
+++
<details><summary>Gemini 3.8 Flash</summary>

MS English gloss.
</details>

<details><summary>मूलम् - विस्वरम्</summary>

समित्समित्
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

स᳘मित्॥
</details>

<details><summary>मूलम् - Weber</summary>

स᳘मित्॥
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- स᳓मित् (*RV*-1)
</details>

<details><summary>पद-पाठः (यान्त्रिकः - माध्यन्दिन-ब्राह्मणम्)</summary>

- स᳓मित् (*RV*-1)
</details>
""",
  )

  ts_static = _write(
    static_root / "taittirIyam/sArasvata-vibhAgaH/saMhitA/Rk/sarvASh_TIkAH/01/test_ts.md",
    """+++
title = "test_ts"
+++
<details><summary>Keith</summary>

TS English gloss.
</details>

<details><summary>मूलम् - तैत्तिरीयम्</summary>

समि॑त् ।
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

स᳘मित्॥
</details>

<details><summary>मूलम् - Weber</summary>

स᳘मित्॥
</details>

<details><summary>पद-पाठः</summary>

समित् ।
</details>

<details><summary>पद-पाठः (यान्त्रिकः - माध्यन्दिन-ब्राह्मणम्)</summary>

- स᳓मित् (*RV*-1)
</details>
""",
  )

  sbm_static = _write(
    static_root / "vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/brAhmaNam/sarvASh_TIkAH/01/same_sbm.md",
    """+++
title = "same_sbm"
+++
<details><summary>Eggeling</summary>

SB English gloss.
</details>

<details><summary>मूलम् - श्रीधरादि</summary>

स᳘मित्॥
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- स᳓मित् (*RV*-1)
</details>
""",
  )

  caller = _write(
    vishvasa / "vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH/01/08/1.md",
    """+++
title = "01/08/1"
+++
## ०१

<details open><summary>विश्वास-प्रस्तुतिः - ऋक्</summary>

स᳓मित् ।
</details>

<div class="js_include collapsed" title="सर्वाष् टीकाः" unfilled url="/vedAH_yajuH/maitrAyaNIyam/saMhitA/Rk/sarvASh_TIkAH/01/test_ms.md"></div>

## ०२

<details open><summary>विश्वास-प्रस्तुतिः - ऋक्</summary>

स᳓मित् ।
</details>

<div class="js_include collapsed" title="सर्वाष् टीकाः" unfilled url="/vedAH_yajuH/taittirIyam/sArasvata-vibhAgaH/saMhitA/Rk/sarvASh_TIkAH/01/test_ts.md"></div>

## ०३

<details open><summary>विश्वास-प्रस्तुतिः - ब्राह्मणम्</summary>

स᳓मित् ।
</details>

<div class="js_include collapsed" title="सर्वाष् टीकाः" unfilled url="/vedAH_yajuH/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/brAhmaNam/sarvASh_TIkAH/01/same_sbm.md"></div>
""",
  )

  report = inline_single_caller_veda_static(
    static_roots=(static_root,),
    all_vishvasa_root=vishvasa,
    hugo_base_dir=vishvasa,
    dry_run=False,
  )
  assert report["errors"] == []
  assert not ms_static.exists()
  assert not ts_static.exists()
  assert not sbm_static.exists()

  out = caller.read_text(encoding="utf-8")
  assert "<summary>मूलम् - विस्वरम् (मैत्रायणीयम्)</summary>" in out
  assert "<summary>पद-पाठः (यान्त्रिकः - मैत्रायणीयम्)</summary>" in out
  assert "<summary>पदपाठः - तैत्तिरीयः</summary>" in out
  # Same-corpus SB-M sarvASh_TIkAH preserves its native unqualified header.
  assert "<summary>पद-पाठः (यान्त्रिकः)</summary>" in out

  for sec_hd in ("## ०१", "## ०२"):
    part = out.split(sec_hd, 1)[1].split("## ", 1)[0]
    clusters = _extract_vp_clusters(f"{sec_hd}\n{part}")
    assert len(clusters) == 1
    assert clusters[0].existing_pp_match is not None
    assert "माध्यन्दिन-ब्राह्मणम्" in clusters[0].existing_pp_match.group(1)
