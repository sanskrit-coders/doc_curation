import textwrap
from pathlib import Path

from doc_curation_projects.veda.yajuH.taittiriiyam.aapastamba.ekAgnikANDam import (
  merge_and_refresh_all,
)


def _write(path: Path, text: str) -> Path:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
  return path


def _assert_balanced(path: Path) -> str:
  text = path.read_text(encoding="utf-8")
  assert text.count("<div") == text.count("</div>"), f"Unbalanced div in {path}"
  assert text.count("<details") == text.count("</details>"), f"Unbalanced details in {path}"
  return text


def test_merge_rk_av_duplicates_and_fixes_are_idempotent(tmp_path):
  # 1. Śākala RV target with Sayana + Wilson and nested jamison_brereton_notes
  rk_vp = tmp_path / "vedAH_Rk/static/shAkalam/saMhitA/vishvAsa-prastutiH/10/085/01_test.md"
  _write(rk_vp, '+++\ntitle = "01"\n+++\nसत्येनोत्तभिता भूमिः\n')

  rk_st = tmp_path / "vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH/10/085/01_test.md"
  _write(
    rk_st,
    """\
    +++
    title = "001"
    +++
    <details><summary>सायण-भाष्यम्</summary>

    सत्येन इति सायणः।
    </details>

    <details><summary>Jamison Brereton Notes</summary>

    <div class="js_include" includetitle="true" newlevelforh1="2" unfilled="" url="/vedAH_Rk/shAkalam/saMhitA/jamison_brereton_notes/10/085/01.md">
    <details><summary><h2>01 ...{Loading}...</h2></summary>

    JB note body.
    </details>
    </div>
    </details>

    <details><summary>Wilson</summary>

    Wilson translation.
    </details>
    """,
  )

  # 2. Shared RV target for two EK mantras + typo URL test in ek_vp
  rk_dup_st = tmp_path / "vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH/01/030/07_yogeyoge.md"
  _write(
    rk_dup_st,
    """\
    +++
    title = "007"
    +++
    <details><summary>सायण-भाष्यम्</summary>

    सायणः।
    </details>

    <details><summary>Wilson</summary>

    Wilson.
    </details>
    """,
  )

  # 3. Broken ek_st linking vishvAsa-prastutiH instead of sarvASh_TIkAH
  rk_broken_st = tmp_path / "vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH/07/026/02_uktha.md"
  _write(
    rk_broken_st,
    """\
    +++
    title = "002"
    +++
    <details><summary>सायण-भाष्यम्</summary>

    सायण उक्थे।
    </details>

    <details><summary>हरदत्तः</summary>

    हरदत्तः पूर्वमेव।
    </details>
    """,
  )

  # 4. AV target (half-merged case where हरदत्तः is left outside in ek_st)
  av_st = tmp_path / "vedAH/static/atharva/shaunakam/rUDha-saMhitA/sarvASh_TIkAH/01/033_ApaH/02_yAsAM.md"
  _write(
    av_st,
    """\
    +++
    title = "०२ यासां राजा"
    +++
    <details><summary>पण्डित क्षेमकरणदास त्रिवेदी - विषयः</summary>

    विषयः।
    </details>

    <details><summary>पण्डित क्षेमकरणदास त्रिवेदी - पदार्थः</summary>

    पदार्थः।
    </details>
    """,
  )

  ek = tmp_path / "vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam"

  # EK 1: fresh Śākala include
  _write(
    ek / "vishvAsa-prastutiH/1_06/01_test.md",
    """\
    +++
    title = "01"
    +++
    <div class="js_include" includetitle="false" newlevelforh1="2" unfilled url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/10/085/01_test.md">
    stale
    </div>
    """,
  )
  ek_st_1 = _write(
    ek / "sarvASh_TIkAH/1_06/01_test.md",
    """\
    +++
    title = "01"
    +++
    <details><summary>मूलम्</summary>

    सत्येनोत्तभिता भूमिः।
    </details>

    <details><summary>पद-पाठः (यान्त्रिकः)</summary>

    - सत्ये᳓न
    </details>

    <details><summary>हरदत्तः</summary>

    हरदत्तटीका सत्येनेति।
    </details>
    """,
  )

  # EK 2a & 2b: two EK files targeting 01/030/07, one with /vedAH_RkshAkalam/ typo + विश्वास-टिप्पनी
  ek_vp_typo = _write(
    ek / "vishvAsa-prastutiH/1_06/03_yogeyoge.md",
    """\
    +++
    title = "03"
    +++
    <div class="js_include" url="/vedAH_RkshAkalam/saMhitA/vishvAsa-prastutiH/01/030/07_yogeyoge.md" unfilled newLevelForH1="2">
    stale
    </div>
    """,
  )
  ek_st_2a = _write(
    ek / "sarvASh_TIkAH/1_06/03_yogeyoge.md",
    """\
    +++
    title = "03"
    +++
    <details><summary>मूलम्</summary>

    योगेयोगे।
    </details>

    <details><summary>हरदत्तः</summary>

    प्रथमहरदत्तः।
    </details>
    """,
  )
  _write(
    ek / "vishvAsa-prastutiH/2_04/01_yogeyoge.md",
    """\
    +++
    title = "01"
    +++
    <div class="js_include" url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/01/030/07_yogeyoge.md" unfilled>
    stale
    </div>
    """,
  )
  ek_st_2b = _write(
    ek / "sarvASh_TIkAH/2_04/01_yogeyoge.md",
    """\
    +++
    title = "01"
    +++
    <details><summary>मूलम्</summary>

    योगेयोगे तवस्तरम्।
    </details>

    <details><summary>विश्वास-टिप्पनी</summary>

    एकान्ते विशेषः।
    </details>

    <details><summary>हरदत्तः</summary>

    द्वितीयहरदत्तः।
    </details>
    """,
  )

  # EK 3: half-merged AV file
  _write(
    ek / "vishvAsa-prastutiH/1_02/03_yAsAM.md",
    """\
    +++
    title = "03"
    +++
    <div class="js_include" url="/vedAH/atharva/shaunakam/rUDha-saMhitA/vishvAsa-prastutiH/01/033_ApaH/02_yAsAM.md" unfilled>
    stale
    </div>
    """,
  )
  ek_st_av = _write(
    ek / "sarvASh_TIkAH/1_02/03_yAsAM.md",
    """\
    +++
    title = "03"
    +++
    <details><summary>मूलम्</summary>

    यासां राजा।
    </details>

    <div class="js_include" includetitle="false" newlevelforh1="2" unfilled url="/vedAH/atharva/shaunakam/rUDha-saMhitA/sarvASh_TIkAH/01/033_ApaH/02_yAsAM.md">
    <details open><summary><h2>०२ यासां राजा ...{Loading}...</h2></summary>

    stale av
    </details>
    </div>

    <details><summary>हरदत्तः</summary>

    तृतीयः स्पष्टः।
    </details>
    """,
  )

  # EK 4: broken vishvAsa-prastutiH url inside ek_st
  _write(
    ek / "vishvAsa-prastutiH/2_11/08_uktha.md",
    """\
    +++
    title = "08"
    +++
    <div class="js_include" url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/07/026/02_uktha.md" unfilled>
    stale
    </div>
    """,
  )
  ek_st_broken = _write(
    ek / "sarvASh_TIkAH/2_11/08_uktha.md",
    """\
    +++
    title = "08"
    +++
    <details><summary>मूलम्</summary>

    उक्थउक्थे।
    </details>

    <div class="js_include" includetitle="false" newlevelforh1="5" unfilled url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/07/026/02_uktha.md">
    <details open><summary><h5>02 ...{Loading}...</h5></summary>

    stale mantra text
    </details>
    </div>
    """,
  )

  # EK 5: repeat without sarvASh_TIkAH and intra-EK include (must be skipped cleanly)
  _write(
    ek / "vishvAsa-prastutiH/1_05/08_repeat.md",
    '+++\ntitle = "08"\n+++\n<div class="js_include" url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/10/085/01_test.md" unfilled>x</div>\n',
  )
  ek_intra_st = _write(
    ek / "sarvASh_TIkAH/1_05/06_intra.md",
    '+++\ntitle = "06"\n+++\n<details><summary>हरदत्तः</summary>\n\nगतम्।\n</details>\n',
  )
  _write(
    ek / "vishvAsa-prastutiH/1_05/06_intra.md",
    '+++\ntitle = "06"\n+++\n<div class="js_include" url="/vedAH_yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/vishvAsa-prastutiH/1_06/01_test.md" unfilled>x</div>\n',
  )

  # Host pages that prefill EK and RV
  ek_host = _write(
    tmp_path / "vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/sarva-prastutiH/1_06.md",
    """\
    +++
    title = "१.०६"
    +++
    <div class="js_include" includetitle="false" newlevelforh1="3" unfilled url="/vedAH_yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/sarvASh_TIkAH/1_06/01_test.md">
    <details><summary><h3>०१ ...{Loading}...</h3></summary>

    old ek st
    </details>
    </div>
    """,
  )
  rk_host = _write(
    tmp_path / "vedAH_Rk/content/shAkalam/saMhitA/sarva-prastutiH/10/085.md",
    """\
    +++
    title = "085"
    +++
    <div class="js_include collapsed" newlevelforh1="5" title="सर्वाष् टीकाः" unfilled url="/vedAH_Rk/shAkalam/saMhitA/sarvASh_TIkAH/10/085/01_test.md">
    <details><summary><h5>सर्वाष् टीकाः ...{Loading}...</h5></summary>

    old rk st
    </details>
    </div>
    """,
  )

  res = merge_and_refresh_all(str(tmp_path), dry_run=False)
  assert res["errors"] == []
  assert res["skipped_no_ek_st"] == ["1_05/08_repeat.md"]

  # Typo fixed in vp
  assert "/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/01/030/07_yogeyoge.md" in ek_vp_typo.read_text(encoding="utf-8")

  # RV target got हरदत्तः right after सायण-भाष्यम् and before Wilson
  rk_text = _assert_balanced(rk_st)
  assert rk_text.index("<summary>सायण-भाष्यम्</summary>") < rk_text.index("<summary>हरदत्तः</summary>") < rk_text.index("<summary>Wilson</summary>")
  assert "हरदत्तटीका सत्येनेति।" in rk_text

  # EK 1 got prefilled RV target with proper title and lost standalone हरदत्तः
  ek1_text = _assert_balanced(ek_st_1)
  assert ek1_text.count("<summary>हरदत्तः</summary>") == 1
  assert 'url="/vedAH_Rk/shAkalam/saMhitA/sarvASh_TIkAH/10/085/01_test.md"' in ek1_text
  assert "<summary><h5>001 ...{Loading}...</h5></summary>" in ek1_text
  assert "सत्येनोत्तभिता भूमिः।" in ek1_text
  assert "Jamison Brereton Notes" in ek1_text

  # Duplicate target contains both unique commentaries separated by _________ and EK 2a got refreshed too
  dup_text = _assert_balanced(rk_dup_st)
  assert "प्रथमहरदत्तः।" in dup_text
  assert "द्वितीयहरदत्तः।" in dup_text
  assert "_________" in dup_text
  ek2a_text = _assert_balanced(ek_st_2a)
  assert "<summary><h5>007 ...{Loading}...</h5></summary>" in ek2a_text
  assert "द्वितीयहरदत्तः।" in ek2a_text
  assert "एकान्ते विशेषः।" in _assert_balanced(ek_st_2b)
  assert _assert_balanced(ek_st_2b).count("<summary>हरदत्तः</summary>") == 1

  # Half-merged AV fixed & हरदत्तः placed between विषयः and पदार्थः
  av_text = _assert_balanced(av_st)
  assert av_text.index("विषयः") < av_text.index("<summary>हरदत्तः</summary>") < av_text.index("पदार्थः")
  ek_av_text = _assert_balanced(ek_st_av)
  assert ek_av_text.count("<summary>हरदत्तः</summary>") == 1
  assert "<summary><h2>०२ यासां राजा ...{Loading}...</h2></summary>" in ek_av_text
  assert "stale av" not in ek_av_text

  # Broken EK url repaired
  broken_text = _assert_balanced(ek_st_broken)
  assert 'url="/vedAH_Rk/shAkalam/saMhitA/sarvASh_TIkAH/07/026/02_uktha.md"' in broken_text
  assert "सायण उक्थे।" in broken_text
  assert "stale mantra text" not in broken_text

  # Intra-EK untouched
  assert "गतम्।" in ek_intra_st.read_text(encoding="utf-8")

  # Hosts refreshed
  assert "हरदत्तटीका सत्येनेति।" in _assert_balanced(ek_host)
  assert "हरदत्तटीका सत्येनेति।" in _assert_balanced(rk_host)

  # Idempotent re-run produces zero target/ek changes
  res2 = merge_and_refresh_all(str(tmp_path), dry_run=False)
  assert res2["modified_target_files"] == []
  assert res2["modified_ek_st_files"] == []
  assert res2["modified_ek_vp_files"] == []
