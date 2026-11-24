import textwrap
from pathlib import Path

from doc_curation.sanskrit.accent.auditor import audit_directory_trees
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

    <details><summary>सायणोक्त-विनियोगः</summary>

    विवाहे सायणविनियोगः।
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

    <details><summary>हरदत्तोक्त-विनियोगः</summary>

    अथ विवाहः सत्येनेति।
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

    <details><summary>पद-पाठः (यान्त्रिकः - 1/13 व्यत्यस्त-स्वराः)</summary>

    - या᳓साम् (*AV*-1) → यासा᳓म्
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

    <details><summary>पद-पाठः (यान्त्रिकः - 1/16)</summary>

    - उ᳓क्थ-उक्थे
    </details>

    <details><summary>हरदत्तोक्त-विनियोगः</summary>

    अथ सोमग्रहः उक्थउक्थे।
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
    '+++\ntitle = "06"\n+++\n<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n- ग᳓तम्\n</details>\n\n<details><summary>हरदत्तः</summary>\n\nगतम्।\n</details>\n',
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

  pre_audit = audit_directory_trees([str(ek)], include_validator_issues=False, base_dir=str(ek))
  assert pre_audit.counts().get("redundant_ek_external_padapatha") == 3

  res = merge_and_refresh_all(str(tmp_path), dry_run=False, prune_wrappers=False)
  assert res["errors"] == []
  assert res["skipped_no_ek_st"] == ["1_05/08_repeat.md"]

  # Typo fixed in vp
  assert "/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/01/030/07_yogeyoge.md" in ek_vp_typo.read_text(encoding="utf-8")

  # RV target got हरदत्तः right after सायण-भाष्यम् and हरदत्तोक्त-विनियोगः right after सायणोक्त-विनियोगः
  rk_text = _assert_balanced(rk_st)
  assert rk_text.index("<summary>सायण-भाष्यम्</summary>") < rk_text.index("<summary>हरदत्तः</summary>") < rk_text.index("<summary>सायणोक्त-विनियोगः</summary>") < rk_text.index("<summary>हरदत्तोक्त-विनियोगः</summary>") < rk_text.index("<summary>Wilson</summary>")
  assert "हरदत्तटीका सत्येनेति।" in rk_text
  assert "अथ विवाहः सत्येनेति।" in rk_text

  # EK 1 got prefilled RV target with proper title and lost standalone हरदत्तः, हरदत्तोक्त-विनियोगः, and yAntrika pada-pATha
  ek1_text = _assert_balanced(ek_st_1)
  assert ek1_text.count("<summary>हरदत्तः</summary>") == 1
  assert ek1_text.count("<summary>हरदत्तोक्त-विनियोगः</summary>") == 1
  assert "पद-पाठः (यान्त्रिकः" not in ek1_text
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

  # Half-merged AV fixed & हरदत्तः placed between विषयः and पदार्थः, yAntrika pada-pATha stripped
  av_text = _assert_balanced(av_st)
  assert av_text.index("विषयः") < av_text.index("<summary>हरदत्तः</summary>") < av_text.index("पदार्थः")
  ek_av_text = _assert_balanced(ek_st_av)
  assert ek_av_text.count("<summary>हरदत्तः</summary>") == 1
  assert "पद-पाठः (यान्त्रिकः" not in ek_av_text
  assert "<summary><h2>०२ यासां राजा ...{Loading}...</h2></summary>" in ek_av_text
  assert "stale av" not in ek_av_text

  # Broken EK url repaired, हरदत्तोक्त-विनियोगः inserted right before existing हरदत्तः, and yAntrika pada-pATha stripped
  broken_text = _assert_balanced(ek_st_broken)
  assert 'url="/vedAH_Rk/shAkalam/saMhitA/sarvASh_TIkAH/07/026/02_uktha.md"' in broken_text
  assert "सायण उक्थे।" in broken_text
  assert "अथ सोमग्रहः उक्थउक्थे।" in broken_text
  assert "stale mantra text" not in broken_text
  assert "पद-पाठः (यान्त्रिकः" not in broken_text
  rk_broken_text = _assert_balanced(rk_broken_st)
  assert rk_broken_text.index("<summary>हरदत्तोक्त-विनियोगः</summary>") < rk_broken_text.index("<summary>हरदत्तः</summary>")

  # Intra-EK untouched (including its padapatha)
  intra_text = _assert_balanced(ek_intra_st)
  assert "गतम्।" in intra_text
  assert "पद-पाठः (यान्त्रिकः)" in intra_text

  # Hosts refreshed (and yAntrika padapatha gone from EK host)
  ek_host_text = _assert_balanced(ek_host)
  assert "हरदत्तटीका सत्येनेति।" in ek_host_text
  assert "पद-पाठः (यान्त्रिकः" not in ek_host_text
  assert "हरदत्तटीका सत्येनेति।" in _assert_balanced(rk_host)

  # Auditor confirms zero redundant EK external padapatha blocks remaining
  post_audit = audit_directory_trees([str(ek)], include_validator_issues=False, base_dir=str(ek))
  assert "redundant_ek_external_padapatha" not in post_audit.counts()

  # Idempotent re-run produces zero target/ek changes
  res2 = merge_and_refresh_all(str(tmp_path), dry_run=False, prune_wrappers=False)
  assert res2["modified_target_files"] == []
  assert res2["modified_ek_st_files"] == []
  assert res2["modified_ek_vp_files"] == []


def test_prune_external_ek_wrappers_deletes_pairs_and_rewrites_transitively(tmp_path: Path):
  # 1. RV pure wrapper target (like 1_18/01 -> RV 10/163/01)
  rv_vp = _write(tmp_path / "vedAH_Rk/static/shAkalam/saMhitA/vishvAsa-prastutiH/10/163/01_axI.md", '+++\ntitle = "०१ अक्षीभ्यां ते"\n+++\nअक्षी᳓भ्यान् ते।\n')
  rv_st = _write(
    tmp_path / "vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH/10/163/01_axI.md",
    """\
    +++
    title = "001"
    +++
    <details><summary>सायण-भाष्यम्</summary>

    अक्षीभ्यामिति सायणः।
    </details>
    """,
  )

  # 2. AV pure wrapper target (1_02/03)
  _write(tmp_path / "vedAH/static/atharva/shaunakam/rUDha-saMhitA/vishvAsa-prastutiH/01/033_ApaH/02_yAsAM.md", '+++\ntitle = "०२ यासां"\n+++\nयासां राजा AV।\n')
  _write(
    tmp_path / "vedAH/static/atharva/shaunakam/rUDha-saMhitA/sarvASh_TIkAH/01/033_ApaH/02_yAsAM.md",
    '+++\ntitle = "०२ यासां"\n+++\n<details><summary>Whitney</summary>\n\nWhitney AV.\n</details>\n',
  )

  # 3. TS pure wrapper target (2_07/16)
  _write(tmp_path / "vedAH_yajuH/static/taittirIyam/sArasvata-vibhAgaH/saMhitA/Rk/vishvAsa-prastutiH/5/6/01/03_hiraNya.md", '+++\ntitle = "03 हिरण्य"\n+++\nहिरण्यवर्णाश् TS।\n')
  _write(
    tmp_path / "vedAH_yajuH/static/taittirIyam/sArasvata-vibhAgaH/saMhitA/Rk/sarvASh_TIkAH/5/6/01/03_hiraNya.md",
    '+++\ntitle = "03 हिरण्य"\n+++\n<details><summary>भट्टभास्कर-टीका</summary>\n\nभास्करः TS।\n</details>\n',
  )

  # 4. RV targets for 2_04/03 (extra VP coda) and 2_18/08 (obsolete TippanI)
  _write(tmp_path / "vedAH_Rk/static/shAkalam/saMhitA/vishvAsa-prastutiH/01/089/09_shatam.md", '+++\ntitle = "०९ शतमिन्नु"\n+++\nशत᳓म् इ᳓न् नु᳓।\n')
  _write(tmp_path / "vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH/01/089/09_shatam.md", '+++\ntitle = "009"\n+++\n<details><summary>सायण-भाष्यम्</summary>\n\nशतमिति सायणः।\n</details>\n')
  _write(tmp_path / "vedAH_Rk/static/shAkalam/saMhitA/vishvAsa-prastutiH/01/022/15_syonA.md", '+++\ntitle = "१५ स्योना"\n+++\nस्योना᳓ पृथिवि भव।\n')
  rv_syona_st = _write(tmp_path / "vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH/01/022/15_syonA.md", '+++\ntitle = "015"\n+++\n<details><summary>सायण-भाष्यम्</summary>\n\nस्योनेति सायणः।\n</details>\n')

  ek = tmp_path / "vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam"
  del_files = [
    _write(ek / "vishvAsa-prastutiH/1_18/01_axI.md", '+++\ntitle = "०१"\n+++\n<div class="js_include" url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/10/163/01_axI.md">old</div>\n'),
    _write(
      ek / "sarvASh_TIkAH/1_18/01_axI.md",
      '+++\ntitle = "०१"\n+++\n<details><summary>मूलम्</summary>\n\nअक्षीभ्यान्ते।\n</details>\n\n<details><summary>हरदत्तः</summary>\n\nहरदत्तो यक्ष्मे।\n</details>\n\n<div class="js_include" url="/vedAH_Rk/shAkalam/saMhitA/sarvASh_TIkAH/10/163/01_axI.md">old</div>\n',
    ),
    _write(ek / "vishvAsa-prastutiH/1_02/03_yAsAM.md", '+++\ntitle = "०३"\n+++\n<div class="js_include" url="/vedAH/atharva/shaunakam/rUDha-saMhitA/vishvAsa-prastutiH/01/033_ApaH/02_yAsAM.md">old</div>\n'),
    _write(ek / "sarvASh_TIkAH/1_02/03_yAsAM.md", '+++\ntitle = "०३"\n+++\n<details><summary>मूलम्</summary>\n\nयासां राजा।\n</details>\n\n<div class="js_include" url="/vedAH/atharva/shaunakam/rUDha-saMhitA/sarvASh_TIkAH/01/033_ApaH/02_yAsAM.md">old</div>\n'),
    _write(ek / "vishvAsa-prastutiH/2_07/16_hiraNya.md", '+++\ntitle = "१६"\n+++\n<div class="js_include" url="/vedAH_yajuH/taittirIyam/sArasvata-vibhAgaH/saMhitA/Rk/vishvAsa-prastutiH/5/6/01/03_hiraNya.md">old</div>\n'),
    _write(ek / "sarvASh_TIkAH/2_07/16_hiraNya.md", '+++\ntitle = "१६"\n+++\n<details><summary>मूलम्</summary>\n\nहिरण्यवर्णाः।\n</details>\n\n<div class="js_include" url="/vedAH_yajuH/taittirIyam/sArasvata-vibhAgaH/saMhitA/Rk/sarvASh_TIkAH/5/6/01/03_hiraNya.md">old</div>\n'),
    _write(ek / "vishvAsa-prastutiH/1_05/08_repeat.md", '+++\ntitle = "०८"\n+++\n<div class="js_include" url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/10/163/01_axI.md">old</div>\n'),
    _write(ek / "vishvAsa-prastutiH/2_04/03_shatam.md", '+++\ntitle = "०३"\n+++\n<div class="js_include" url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/01/089/09_shatam.md">old</div>\n\n(देवे᳓भ्यः इ᳓दन्न᳓ म᳓म । )\n'),
    _write(ek / "sarvASh_TIkAH/2_04/03_shatam.md", '+++\ntitle = "०३"\n+++\n<details><summary>मूलम्</summary>\n\nशतमिन्नु।\n</details>\n\n<div class="js_include" url="/vedAH_Rk/shAkalam/saMhitA/sarvASh_TIkAH/01/089/09_shatam.md">old</div>\n'),
    _write(ek / "vishvAsa-prastutiH/2_18/08_syonA.md", '+++\ntitle = "०८"\n+++\n<div class="js_include" url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/01/022/15_syonA.md">old</div>\n'),
    _write(
      ek / "sarvASh_TIkAH/2_18/08_syonA.md",
      '+++\ntitle = "०८"\n+++\n<details><summary>मूलम्</summary>\n\nस्योना।\n</details>\n\n<details><summary>विश्वास-टिप्पनी</summary>\n\nभव॑ इत्य् उदात्तो दोषाय। शाकले तन् नास्ति।\n</details>\n\n<div class="js_include" url="/vedAH_Rk/shAkalam/saMhitA/sarvASh_TIkAH/01/022/15_syonA.md">old</div>\n',
    ),
  ]

  # Non-external EK pair + intra-EK repeat -> must remain
  kept_vp = _write(ek / "vishvAsa-prastutiH/1_02/04_yAsAn.md", '+++\ntitle = "०४"\n+++\nयासां देवाः EK।\n')
  kept_st = _write(ek / "sarvASh_TIkAH/1_02/04_yAsAn.md", '+++\ntitle = "०४"\n+++\n<details><summary>हरदत्तः</summary>\n\nरक्षणीयः।\n</details>\n')
  kept_intra = _write(ek / "vishvAsa-prastutiH/1_05/06_intra.md", '+++\ntitle = "०६"\n+++\n<div class="js_include" url="/vedAH_yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/vishvAsa-prastutiH/1_02/04_yAsAn.md">x</div>\n')

  # Hosts: direct content page, intermediate sutra page, transitive parent page, and prose note
  ek_sp = _write(
    tmp_path / "vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/sarva-prastutiH/1_18.md",
    """\
    +++
    title = "1 18"
    +++
    <div class="js_include" includetitle="true" newlevelforh1="2" unfilled url="/vedAH_yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/vishvAsa-prastutiH/1_18/01_axI.md">
    <details open><summary><h2>०१ ...{Loading}...</h2></summary>
    old
    </details>
    </div>
    <div class="js_include" includetitle="false" newlevelforh1="3" unfilled url="/vedAH_yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/sarvASh_TIkAH/1_18/01_axI.md">
    <details><summary><h3>०१ ...{Loading}...</h3></summary>
    old st
    </details>
    </div>
    <div class="js_include" includetitle="true" newlevelforh1="2" unfilled url="/vedAH_yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/vishvAsa-prastutiH/1_02/03_yAsAM.md">
    stale av
    </div>
    <div class="js_include" includetitle="true" newlevelforh1="2" unfilled url="/vedAH_yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/vishvAsa-prastutiH/2_07/16_hiraNya.md">
    stale ts
    </div>
    <div class="js_include" includetitle="true" newlevelforh1="2" unfilled url="/vedAH_yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/vishvAsa-prastutiH/1_05/08_repeat.md">
    stale repeat
    </div>
    <div class="js_include" includetitle="false" newlevelforh1="3" unfilled url="/vedAH_yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/sarvASh_TIkAH/2_18/08_syonA.md">
    stale syona
    </div>
    """,
  )
  sutra_11_06 = _write(
    tmp_path / "vedAH_yajuH/static/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH/vishvAsa-prastutiH/07/11_06.md",
    """\
    +++
    title = "11 06"
    +++
    <div class="js_include bg-light-yellow" includetitle="false" newlevelforh1="2" unfilled url="/vedAH_yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/vishvAsa-prastutiH/2_04/03_shatam.md">
    old shatam
    </div>
    """,
  )
  ek_1_full = _write(
    tmp_path / "vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/1.md",
    """\
    +++
    title = "1"
    +++
    <div class="js_include" includetitle="false" newlevelforh1="2" unfilled url="/vedAH_yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/sUtra-pAThaH/vishvAsa-prastutiH/07/11_06.md">
    stale 11 06
    </div>
    """,
  )
  prose = _write(
    tmp_path / "vedAH/content/contribution/mantra-sangrahaNam.md",
    "उदाहरणम् yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/ekAgnikANDam/vishvAsa-prastutiH/1_18/01_axI.md इत्यत्र।\n",
  )

  # Dry-run previews deletions without mutating files
  dry_res = merge_and_refresh_all(str(tmp_path), dry_run=True, prune_wrappers=True)
  assert dry_res["errors"] == []
  assert dry_res["prune_skipped_extras"] == []
  assert len(dry_res["deleted_wrapper_files"]) == len(del_files)
  assert all(p.exists() for p in del_files)

  res = merge_and_refresh_all(str(tmp_path), dry_run=False, prune_wrappers=True)
  assert res["errors"] == []
  assert res["prune_skipped_extras"] == []
  assert all(not p.exists() for p in del_files)
  assert kept_vp.exists() and kept_st.exists() and kept_intra.exists()

  # Commentary merged into RV 10/163/01, obsolete टिप्पनी dropped from 01/022/15
  assert "हरदत्तो यक्ष्मे।" in _assert_balanced(rv_st)
  assert "विश्वास-टिप्पनी" not in _assert_balanced(rv_syona_st)
  assert "शाकले तन् नास्ति" not in _assert_balanced(rv_syona_st)

  # Direct host rewritten to RV/AV/TS and refreshed
  sp_text = _assert_balanced(ek_sp)
  assert "ekAgnikANDam/" not in sp_text
  assert sp_text.count("/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/10/163/01_axI.md") == 2
  assert "/vedAH_Rk/shAkalam/saMhitA/sarvASh_TIkAH/10/163/01_axI.md" in sp_text
  assert "/vedAH/atharva/shaunakam/rUDha-saMhitA/vishvAsa-prastutiH/01/033_ApaH/02_yAsAM.md" in sp_text
  assert "/vedAH_yajuH/taittirIyam/sArasvata-vibhAgaH/saMhitA/Rk/vishvAsa-prastutiH/5/6/01/03_hiraNya.md" in sp_text
  assert "हरदत्तो यक्ष्मे।" in sp_text
  assert "स्योनेति सायणः।" in sp_text
  assert "शाकले तन् नास्ति" not in sp_text

  # Sutra host rewritten with (देवे᳓भ्यः...) inlined right below and transitively propagated into 1.md
  sutra_text = _assert_balanced(sutra_11_06)
  assert 'url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/01/089/09_shatam.md"' in sutra_text
  assert "शत᳓म् इ᳓न् नु᳓।" in sutra_text
  assert "(देवे᳓भ्यः इ᳓दन्न᳓ म᳓म । )" in sutra_text
  full_1_text = _assert_balanced(ek_1_full)
  assert 'url="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/01/089/09_shatam.md"' in full_1_text
  assert "(देवे᳓भ्यः इ᳓दन्न᳓ म᳓म । )" in full_1_text

  # Prose citation untouched
  assert "ekAgnikANDam/vishvAsa-prastutiH/1_18/01_axI.md" in prose.read_text(encoding="utf-8")

  # Auditor reports zero EK external wrapper/padapatha issues; idempotent re-run makes zero edits
  post_audit = audit_directory_trees([str(ek)], include_validator_issues=False, base_dir=str(ek))
  assert "redundant_ek_external_padapatha" not in post_audit.counts()
  assert "redundant_ek_external_wrapper" not in post_audit.counts()

  res2 = merge_and_refresh_all(str(tmp_path), dry_run=False, prune_wrappers=True)
  assert res2["deleted_wrapper_files"] == []
  assert res2["rewritten_direct_hosts"] == []
  assert res2["refreshed_transitive_hosts"] == []
  assert rv_vp.exists()
