import textwrap

from doc_curation.md.content_processor import include as include_helper


def test_include_to_details():
  content = textwrap.dedent("""
  <div class="js_include" includetitle="true" newlevelforh1="3" url="/kalpAntaram/smRtiH/manuH/vishvAsa-prastutiH/01_praveshaH/001_manum_ekAgram.md">
  <details open><summary><h3>001 मनुम् एकाग्रम् …{Loading}…</h3></summary>

  मनुम् एकाग्रम् **आसीनम्**  
  अभिगम्य महर्षयः ।  
  </details>
  </div>

  <div class="js_include collapsed" newlevelforh1="4" title="सर्वाष् टीकाः" url="/kalpAntaram/smRtiH/manuH/sarvASh_TIkAH/01_praveshaH/001_manum_ekAgram.md">
  <details><summary><h4>सर्वाष् टीकाः …{Loading}…</h4></summary>

  टीका
  </details>
  </div>
  """)

  content_new = include_helper.transform_includes_with_soup(content=content, metadata={"_file_path": "test.md"},
                                                           transformer=include_helper.include_to_details, title="विश्वास-प्रस्तुतिः", url_pattern="vishvAsa-prastutiH")

  # The vishvAsa include is replaced by a plain details block named विश्वास-प्रस्तुतिः, verse intact.
  assert "vishvAsa-prastutiH" not in content_new
  assert "<details open><summary>विश्वास-प्रस्तुतिः</summary>" in content_new
  assert "मनुम् एकाग्रम् **आसीनम्**" in content_new
  assert "001 मनुम् एकाग्रम्" not in content_new

  # Other includes are left untouched.
  assert "sarvASh_TIkAH" in content_new
  assert "<summary><h4>सर्वाष् टीकाः …{Loading}…</h4></summary>" in content_new


def test_includes_to_details_with_prefill(tmp_path):
  static_dir = tmp_path / "kalpAntaram" / "static" / "smRtiH" / "manuH" / "vishvAsa-prastutiH"
  static_dir.mkdir(parents=True)
  (static_dir / "001_manum_ekAgram.md").write_text("+++\ntitle = \"001 मनुम् एकाग्रम्\"\n+++\nमनुम् एकाग्रम् **आसीनम्**  \nअभिगम्य महर्षयः ॥ १.१ ॥\n", encoding="utf-8")

  content_dir = tmp_path / "kalpAntaram" / "content" / "smRtiH" / "manuH" / "sarva-prastutiH"
  content_dir.mkdir(parents=True)
  host_path = content_dir / "01.md"
  host_path.write_text(textwrap.dedent("""
  +++
  title = "०१"
  +++

  <div class="js_include" includetitle="true" newlevelforh1="3" url="/kalpAntaram/smRtiH/manuH/vishvAsa-prastutiH/001_manum_ekAgram.md">
  <details open><summary><h3>001 मनुम् एकाग्रम् ...{Loading}...</h3></summary>

  stale content
  </details>
  </div>
  """), encoding="utf-8")

  include_helper.includes_to_details(dir_path=str(content_dir), title="विश्वास-प्रस्तुतिः", url_pattern="vishvAsa-prastutiH", prefill=True,
                                    hugo_base_dir=str(tmp_path))

  content_new = host_path.read_text(encoding="utf-8")
  assert "js_include" not in content_new
  assert "<details open><summary>विश्वास-प्रस्तुतिः</summary>" in content_new
  assert "मनुम् एकाग्रम् **आसीनम्**" in content_new
  assert "stale content" not in content_new


def test_fix_rel_urls():
  from_path = "/base/repo/static/a/b.md"
  to_path = "/base/repo/content/c/d/e.md"
  content = textwrap.dedent("""
  [rel](img/x.png)
  [mail](mailto:x@example.org?subject=y)
  [js](Javascript:void(0);)
  ![img](../../x.png)
  [abs](/foo/bar)
  """)
  content_new = include_helper.fix_rel_urls(content=content, from_path=from_path, to_path=to_path)
  assert "[mail](mailto:x@example.org?subject=y)" in content_new
  assert "[js](Javascript:void(0);)" in content_new
  assert "[abs](/foo/bar)" in content_new
  assert "[rel](img/x.png)" not in content_new


def test_prefill_includes_dry_run(tmp_path):
  static_dir = tmp_path / "kalpAntaram" / "static" / "smRtiH" / "manuH" / "vishvAsa-prastutiH"
  static_dir.mkdir(parents=True)
  (static_dir / "001_manum_ekAgram.md").write_text("+++\ntitle = \"001 मनुम् एकाग्रम्\"\n+++\nमनुम् एकाग्रम् ॥ १.१ ॥\n", encoding="utf-8")

  content_dir = tmp_path / "kalpAntaram" / "content" / "smRtiH" / "manuH" / "sarva-prastutiH"
  content_dir.mkdir(parents=True)
  host_path = content_dir / "01.md"
  host_content = textwrap.dedent("""
  +++
  title = "०१"
  +++

  <div class="js_include" includetitle="true" newlevelforh1="3" url="/kalpAntaram/smRtiH/manuH/vishvAsa-prastutiH/001_manum_ekAgram.md">
  <details open><summary><h3>001 मनुम् एकाग्रम् ...{Loading}...</h3></summary>

  stale content
  </details>
  </div>
  """)
  host_path.write_text(host_content, encoding="utf-8")

  include_helper.prefill_includes(dir_path=str(content_dir), dry_run=True, hugo_base_dir=str(tmp_path))

  assert host_path.read_text(encoding="utf-8") == host_content


def test_include_to_details_without_title(tmp_path):
  """Titleless includes (includetitle="false") are prefilled as bare content and still get wrapped."""
  static_dir = tmp_path / "kalpAntaram" / "static" / "smRtiH" / "manuH" / "vishvAsa-prastutiH"
  static_dir.mkdir(parents=True)
  (static_dir / "046_na_niShkraya.md").write_text("+++\ntitle = \"046 न निष्क्रय\"\n+++\n**न** निष्क्रय-विसर्गाभ्यां  \nभर्तुर् भार्या **विमुच्यते** ॥ ९.४६ ॥\n", encoding="utf-8")

  content_dir = tmp_path / "kalpAntaram" / "content" / "smRtiH" / "manuH" / "sarva-prastutiH"
  content_dir.mkdir(parents=True)
  host_path = content_dir / "01.md"
  host_path.write_text(textwrap.dedent("""
  +++
  title = "०१"
  +++

  <div class="js_include" includetitle="false" newlevelforh1="5" url="/kalpAntaram/smRtiH/manuH/vishvAsa-prastutiH/046_na_niShkraya.md">
  </div>
  """), encoding="utf-8")

  include_helper.includes_to_details(dir_path=str(content_dir), title="विश्वास-प्रस्तुतिः", url_pattern="vishvAsa-prastutiH", prefill=True,
                                    hugo_base_dir=str(tmp_path))

  content_new = host_path.read_text(encoding="utf-8")
  assert "js_include" not in content_new
  assert "<details open><summary>विश्वास-प्रस्तुतिः</summary>" in content_new
  assert "**न** निष्क्रय-विसर्गाभ्यां" in content_new


def test_surgical_prefill_preserves_wrappers_and_nested_children(tmp_path):
  static_dir = tmp_path / "vedAH_yajuH" / "static" / "ekAgnikANDam" / "vishvAsa-prastutiH"
  static_dir.mkdir(parents=True)
  (static_dir / "01_adite.md").write_text(
    '+++\ntitle = "०१ अदिते"\n+++\nअ᳓दिते᳓ऽनु मन्यस्व।\n',
    encoding="utf-8",
  )

  content_dir = tmp_path / "vedAH_yajuH" / "content" / "ekAgnikANDam"
  content_dir.mkdir(parents=True)
  host_path = content_dir / "1.md"
  host_txt = textwrap.dedent("""\
    +++
    title = "१"
    +++
    {{< figure src="keep.jpg" >}}

    <div class="js_include" includetitle="false" newlevelforh1="2" unfilled url="/vedAH_yajuH/karmANi/vaishvadevam/">
    Outer text untouched < b >

    <div class="js_include" includetitle="true" newlevelforh1="3" unfilled url="/vedAH_yajuH/ekAgnikANDam/vishvAsa-prastutiH/01_adite.md">
    <details open><summary><h3>०१ अदिते ...{Loading}...</h3></summary>

    अदि॒तेऽनु॑ मन्यस्व।

    </details>
    </div>
    </div>
  """)
  host_path.write_text(host_txt, encoding="utf-8")

  include_helper.surgical_prefill_includes(
    dir_path=str(content_dir),
    url_filter="/ekAgnikANDam/",
    hugo_base_dir=str(tmp_path),
  )

  updated = host_path.read_text(encoding="utf-8")
  # Hugo shortcodes, stray '<', outer wrapper attributes, and {Loading} summary preserved byte-for-byte
  assert '{{< figure src="keep.jpg" >}}' in updated
  assert "Outer text untouched < b >" in updated
  assert "<details open><summary><h3>०१ अदिते ...{Loading}...</h3></summary>" in updated
  # Inner matching prefill updated cleanly
  assert "अ᳓दिते᳓ऽनु मन्यस्व।" in updated
  assert "अदि॒तेऽनु॑" not in updated


def test_surgical_prefill_titleless_with_nested_loading_and_hash_loading(tmp_path):
  # 1. Titleless outer include (`includetitle="false"`) containing an initial `<details>` note
  #    plus a nested `js_include` with `{Loading}` and ending with `</details>` must NOT mistake
  #    those inner tags for an outer `{Loading}` wrapper (regression for puruSha-sUktam.md).
  sub_dir = tmp_path / "vedAH_yajuH" / "content" / "AraNyakam" / "12_sahasra-shIrShA"
  sub_dir.mkdir(parents=True)
  (sub_dir / "_index.md").write_text(
    textwrap.dedent("""\
      +++
      title = "१२ सहस्रशीर्षा"
      +++
      <details><summary>त्रिभुवनः - Note</summary>

      The Puruṣa Sūkta.
      </details>

      <div class="js_include" newlevelforh1="2" title="सर्वाष् टीकाः" unfilled url="/vedAH_Rk/10/090/_index.md">
      <details open><summary><h2>सर्वाष् टीकाः …{Loading}…</h2></summary>

      टीका
      </details>
      </div>

      <details><summary>पद-पाठः (यान्त्रिकः)</summary>

      - सह᳓स्र-शीर्षा (*TS*-1, *RV*-1)
      </details>
    """),
    encoding="utf-8",
  )

  # 2. Markdown `### Title …{Loading}…` wrapper (`hash_title=True`) must keep its `{Loading}` header.
  vp_dir = tmp_path / "vedAH_yajuH" / "static" / "shrautam"
  vp_dir.mkdir(parents=True)
  (vp_dir / "01.md").write_text(
    '+++\ntitle = "01 मन्त्रान्तेः"\n+++\nमन्त्रान्ते कर्मादीन् संनिपातयेत् १\n',
    encoding="utf-8",
  )

  host_dir = tmp_path / "vedAH_yajuH" / "content" / "host"
  host_dir.mkdir(parents=True)
  host_path = host_dir / "puruSha.md"
  host_path.write_text(
    textwrap.dedent("""\
      +++
      title = "पुरुष-सूक्तम्"
      +++

      <div class="js_include" includetitle="false" newlevelforh1="5" unfilled url="/vedAH_yajuH/AraNyakam/12_sahasra-shIrShA/">
      <details><summary>त्रिभुवनः - Note</summary>

      The Puruṣa Sūkta.
      </details>

      <div class="js_include" newlevelforh1="2" title="सर्वाष् टीकाः" unfilled url="/vedAH_Rk/10/090/_index.md">
      <details open><summary><h7>सर्वाष् टीकाः …{Loading}…</h7></summary>

      टीका
      </details>
      </div>

      <details><summary>पद-पाठः (यान्त्रिकः)</summary>

      - सह᳓स्र-शीर्षा (*TS*, *RV*)
      </details>
      </div>

      <div class="js_include" includetitle="true" newlevelforh1="3" unfilled url="/vedAH_yajuH/shrautam/01.md">

      ### 01 मन्त्रान्तेः …{Loading}…

      stale sUtra

      </div>
    """),
    encoding="utf-8",
  )

  include_helper.surgical_prefill_includes(
    dir_path=str(host_dir),
    hugo_base_dir=str(tmp_path),
  )

  updated = host_path.read_text(encoding="utf-8")
  assert updated.count("<div") == updated.count("</div>") == 3
  assert updated.count("<details") == updated.count("</details>") == 3
  assert updated.count("<summary>त्रिभुवनः - Note</summary>") == 1
  assert "- सह᳓स्र-शीर्षा (*TS*-1, *RV*-1)" in updated
  assert "### 01 मन्त्रान्तेः …{Loading}…" in updated
  assert "मन्त्रान्ते कर्मादीन् संनिपातयेत् १" in updated
  assert "stale sUtra" not in updated
