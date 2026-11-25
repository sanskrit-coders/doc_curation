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


def test_surgical_prefill_transitive_multi_hop_and_directory_index(tmp_path):
  # Leaf in static/ -> intermediate _index.md in content/mid/ (referenced via trailing-slash directory URL) -> top.md
  static_dir = tmp_path / "vedAH_yajuH" / "static" / "ekAgnikANDam"
  static_dir.mkdir(parents=True)
  leaf = static_dir / "01_leaf.md"
  leaf.write_text('+++\ntitle = "०१"\n+++\nपोषयित्नु᳓ आ᳓\n', encoding="utf-8")
  unchanged = static_dir / "02_other.md"
  unchanged.write_text('+++\ntitle = "०२"\n+++\nअग्निः᳓\n', encoding="utf-8")

  mid_dir = tmp_path / "vedAH_yajuH" / "content" / "AraNyakam" / "12_mid"
  mid_dir.mkdir(parents=True)
  mid_idx = mid_dir / "_index.md"
  mid_idx.write_text(
    textwrap.dedent("""\
      +++
      title = "१२"
      +++
      <div class="js_include" includetitle="true" newlevelforh1="3" url="/vedAH_yajuH/ekAgnikANDam/01_leaf.md">
      <details open><summary><h3>०१ …{Loading}…</h3></summary>

      stale leaf
      </details>
      </div>
    """),
    encoding="utf-8",
  )

  top_dir = tmp_path / "vedAH_yajuH" / "content" / "prayogaH"
  top_dir.mkdir(parents=True)
  top = top_dir / "top.md"
  top_orig = textwrap.dedent("""\
    +++
    title = "प्रयोगः"
    +++
    <div class="js_include" includetitle="false" newlevelforh1="2" url="/vedAH_yajuH/AraNyakam/12_mid/">

    stale mid
    </div>

    <div class="js_include" includetitle="true" newlevelforh1="3" url="/vedAH_yajuH/ekAgnikANDam/02_other.md">
    <details open><summary><h3>०२ …{Loading}…</h3></summary>

    keep untouched sibling
    </details>
    </div>
  """)
  top.write_text(top_orig, encoding="utf-8")

  # Excluded directory must never be touched
  excl_dir = tmp_path / "vedAH_yajuH" / "content" / "shatapatha-brAhmaNam"
  excl_dir.mkdir(parents=True)
  excl = excl_dir / "sb.md"
  excl_orig = '<div class="js_include" url="/vedAH_yajuH/ekAgnikANDam/01_leaf.md">\nstale sb\n</div>\n'
  excl.write_text(excl_orig, encoding="utf-8")

  # Dry run reports both mid_idx and top without writing
  dry_touched = include_helper.surgical_prefill_transitive(
    [static_dir.parent, tmp_path / "vedAH_yajuH" / "content"],
    [leaf],
    hugo_base_dir=str(tmp_path),
    exclude_path_substrings=("shatapatha-brAhmaNam",),
    dry_run=True,
  )
  assert dry_touched == {str(mid_idx), str(top)}
  assert "stale mid" in top.read_text(encoding="utf-8")

  # Real run updates leaf -> mid/_index.md -> top.md across 2 waves, preserving untouched sibling & excluded dir
  touched = include_helper.surgical_prefill_transitive(
    [static_dir.parent, tmp_path / "vedAH_yajuH" / "content"],
    [leaf],
    hugo_base_dir=str(tmp_path),
    exclude_path_substrings=("shatapatha-brAhmaNam",),
  )
  assert touched == {str(mid_idx), str(top)}
  assert "पोषयित्नु᳓ आ᳓" in mid_idx.read_text(encoding="utf-8")
  top_after = top.read_text(encoding="utf-8")
  assert "पोषयित्नु᳓ आ᳓" in top_after
  assert "keep untouched sibling" in top_after
  assert excl.read_text(encoding="utf-8") == excl_orig


def test_surgical_prefill_transitive_skips_non_utf8_and_dot_git(tmp_path):
  static_dir = tmp_path / "vedAH_Rk" / "static" / "vp"
  static_dir.mkdir(parents=True)
  leaf = static_dir / "01.md"
  leaf.write_text('+++\ntitle = "०१"\n+++\nअभ्य् अ᳙साक्षि\n', encoding="utf-8")

  content_dir = tmp_path / "vedAH_Rk" / "content"
  content_dir.mkdir(parents=True)
  host = content_dir / "host.md"
  host.write_text(
    '+++\ntitle = "१"\n+++\n<div class="js_include" url="/vedAH_Rk/vp/01.md">\nstale\n</div>\n',
    encoding="utf-8",
  )

  # Binary non-UTF-8 file masquerading as .md and a .git directory with .md should be skipped cleanly.
  (content_dir / "bad_image.md").write_bytes(b"\xff\xd8\xff\xe0not utf8")
  git_dir = content_dir / ".git"
  git_dir.mkdir()
  (git_dir / "ignored.md").write_bytes(b"\xff\xfe")

  touched = include_helper.surgical_prefill_transitive(
    [static_dir.parent, content_dir],
    [leaf],
    hugo_base_dir=str(tmp_path),
  )
  assert touched == {str(host)}
  assert "अभ्य् अ᳙साक्षि" in host.read_text(encoding="utf-8")


def test_deinclude_selective_preserves_open_collapsed_and_deletes_unreferenced(tmp_path):
  # Set up two mantras: 01 (yajus -> de-include vp + st, keep mUlam), 02 (Rk -> keep all includes)
  static_root = tmp_path / "vedAH_yajuH" / "static" / "saMhitA"
  for sub in ("vishvAsa-prastutiH/01", "mUlam/01", "sarvASh_TIkAH/01"):
    (static_root / sub).mkdir(parents=True)

  vp1 = static_root / "vishvAsa-prastutiH" / "01" / "01_iShe.md"
  vp1.write_text('+++\ntitle = "०१ इषे"\n+++\nइ॒षे त्वो॒र्जे त्वा॑ fresh ॥१॥\n', encoding="utf-8")
  mu1 = static_root / "mUlam" / "01" / "01_iShe.md"
  mu1.write_text('+++\ntitle = "०१ इषे"\n+++\nइ॒षे त्वो॒र्जे त्वा॑ ॥१॥\n', encoding="utf-8")
  st1 = static_root / "sarvASh_TIkAH" / "01" / "01_iShe.md"
  st1.write_text(
    '+++\ntitle = "०१ इषे"\n+++\n<details><summary>महीधरः</summary>\n\nयजुः टीका।\n</details>\n',
    encoding="utf-8",
  )

  vp2 = static_root / "vishvAsa-prastutiH" / "01" / "02_rk.md"
  vp2.write_text('+++\ntitle = "०२ ऋक्"\n+++\nतत्सवितुर्वरेण्यम् ॥२॥\n', encoding="utf-8")
  st2 = static_root / "sarvASh_TIkAH" / "01" / "02_rk.md"
  st2.write_text('+++\ntitle = "०२ ऋक्"\n+++\n<details><summary>महीधरः</summary>\n\nगायत्री।\n</details>\n', encoding="utf-8")

  # Also a 3rd yajus whose vp is referenced externally by another file -> must NOT be deleted!
  vp3 = static_root / "vishvAsa-prastutiH" / "01" / "03_shared.md"
  vp3.write_text('+++\ntitle = "०३ अभिधा"\n+++\nअभिधा असि ॥३॥\n', encoding="utf-8")

  content_dir = tmp_path / "vedAH_yajuH" / "content" / "saMhitA" / "sarva-prastutiH"
  content_dir.mkdir(parents=True)
  host = content_dir / "01.md"
  host.write_text(
    textwrap.dedent("""\
      +++
      title = "०१"
      +++
      {{< figure src="keep.jpg" >}}

      ## ०१ इषे
      <div class="js_include" newlevelforh1="3" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH_yajuH/saMhitA/vishvAsa-prastutiH/01/01_iShe.md">
      <details open><summary><h3>विश्वास-प्रस्तुतिः ...{Loading}...</h3></summary>

      stale text
      </details>
      </div>
      <div class="js_include collapsed" newlevelforh1="3" title="मूलम्" unfilled url="/vedAH_yajuH/saMhitA/mUlam/01/01_iShe.md">
      <details><summary><h3>मूलम् ...{Loading}...</h3></summary>

      इ॒षे त्वो॒र्जे त्वा॑ ॥१॥
      </details>
      </div>
      <div class="js_include collapsed" newlevelforh1="3" title="सर्वाष् टीकाः" unfilled url="/vedAH_yajuH/saMhitA/sarvASh_TIkAH/01/01_iShe.md">
      <details><summary><h3>सर्वाष् टीकाः ...{Loading}...</h3></summary>
      <details><summary>महीधरः</summary>

      stale tika
      </details>
      </details>
      </div>

      ## ०२ ऋक्
      <div class="js_include" newlevelforh1="3" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH_yajuH/saMhitA/vishvAsa-prastutiH/01/02_rk.md">
      <details open><summary><h3>विश्वास-प्रस्तुतिः ...{Loading}...</h3></summary>

      तत्सवितुर्वरेण्यम् ॥२॥
      </details>
      </div>
      <div class="js_include collapsed" newlevelforh1="3" title="सर्वाष् टीकाः" unfilled url="/vedAH_yajuH/saMhitA/sarvASh_TIkAH/01/02_rk.md">
      <details><summary><h3>सर्वाष् टीकाः ...{Loading}...</h3></summary>
      <details><summary>महीधरः</summary>

      गायत्री।
      </details>
      </details>
      </div>

      ## ०३ अभिधा
      <div class="js_include" newlevelforh1="3" title="विश्वास-प्रस्तुतिः" unfilled url="/vedAH_yajuH/saMhitA/vishvAsa-prastutiH/01/03_shared.md">
      <details open><summary><h3>विश्वास-प्रस्तुतिः ...{Loading}...</h3></summary>

      अभिधा असि ॥३॥
      </details>
      </div>
    """),
    encoding="utf-8",
  )

  # External file referencing 03_shared.md
  other_dir = tmp_path / "vedAH_yajuH" / "content" / "prayogaH"
  other_dir.mkdir(parents=True)
  (other_dir / "ext.md").write_text(
    '<div class="js_include" url="/vedAH_yajuH/saMhitA/vishvAsa-prastutiH/01/03_shared.md">\n</div>\n',
    encoding="utf-8",
  )

  url_filter = lambda u: ("01_iShe.md" in u or "03_shared.md" in u) and "/mUlam/" not in u

  # Dry run leaves disk untouched while reporting exact changes
  dry_res = include_helper.deinclude(
    dir_path=str(content_dir),
    url_filter=url_filter,
    prefill=True,
    delete_included_files=True,
    reference_check_roots=[tmp_path / "vedAH_yajuH"],
    hugo_base_dir=str(tmp_path),
    dry_run=True,
  )
  assert dry_res["updated_files"] == {str(host)}
  assert dry_res["deleted_files"] == {str(vp1), str(st1)}
  assert dry_res["retained_referenced_files"] == {str(vp3)}
  assert vp1.exists() and st1.exists() and vp3.exists()
  assert "stale text" in host.read_text(encoding="utf-8")

  # Real run updates host, deletes vp1 & st1, retains vp3 (externally referenced) & untouched vp2/st2/mu1
  res = include_helper.deinclude(
    dir_path=str(content_dir),
    url_filter=url_filter,
    prefill=True,
    delete_included_files=True,
    reference_check_roots=[tmp_path / "vedAH_yajuH"],
    hugo_base_dir=str(tmp_path),
    dry_run=False,
  )
  assert res["updated_files"] == {str(host)}
  assert res["deleted_files"] == {str(vp1), str(st1)}
  assert res["retained_referenced_files"] == {str(vp3)}
  assert not vp1.exists() and not st1.exists()
  assert mu1.exists() and vp2.exists() and st2.exists() and vp3.exists()

  out = host.read_text(encoding="utf-8")
  assert '{{< figure src="keep.jpg" >}}' in out
  assert "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nइ॒षे त्वो॒र्जे त्वा॑ fresh ॥१॥\n</details>" in out
  assert "<details><summary>सर्वाष् टीकाः</summary>\n<details><summary>महीधरः</summary>\n\nयजुः टीका।\n</details>\n</details>" in out
  assert "stale text" not in out and "stale tika" not in out
  # mUlam and 02_rk remain js_include
  assert 'url="/vedAH_yajuH/saMhitA/mUlam/01/01_iShe.md"' in out
  assert 'url="/vedAH_yajuH/saMhitA/vishvAsa-prastutiH/01/02_rk.md"' in out
  assert 'url="/vedAH_yajuH/saMhitA/sarvASh_TIkAH/01/02_rk.md"' in out
  # Balanced tags
  assert out.count("<details") == out.count("</details>")
  assert out.count("<div") == out.count("</div>")
  # Old broken deincludify is gone
  assert not hasattr(include_helper, "deincludify")


def test_deinclude_content_no_prefill_and_titleless():
  content = textwrap.dedent("""\
    <div class="js_include" includetitle="true" newlevelforh1="3" url="/repo/a.md">
    <details open><summary><h3>०१ शीर्षकम् …{Loading}…</h3></summary>

    अन्तर्वस्तु
    </details>
    </div>

    <div class="js_include" includetitle="false" newlevelforh1="5" url="/repo/b.md">

    अशीर्षकम्
    </div>
  """)
  out, _ = include_helper.deinclude_content(content, "/tmp/host.md", prefill=False)
  assert "js_include" not in out
  assert "{Loading}" not in out
  assert "<h3>" not in out
  assert "<details open><summary>०१ शीर्षकम्</summary>\n\nअन्तर्वस्तु\n</details>" in out
  assert "अशीर्षकम्" in out
  assert out.count("<details") == out.count("</details>") == 1


def test_prefill_details_pattern_frontmatter_and_js_parity(tmp_path):
  static_dir = tmp_path / "notes" / "static" / "sub"
  static_dir.mkdir(parents=True)
  (static_dir / "leaf.md").write_text(
    textwrap.dedent("""\
      +++
      title = "Leaf"
      author = "Test Author"
      +++

      # Top Heading

      ## Sub Heading

      <img src="leaf.png">

      Intro bare text.

      <details><summary>Alpha</summary>

      Alpha body.
      </details>

      <details><summary>Beta</summary>

      Beta body.

      <details><summary>Nested Child</summary>

      Nested body.
      </details>
      </details>
    """),
    encoding="utf-8",
  )

  content_dir = tmp_path / "notes" / "content" / "host"
  content_dir.mkdir(parents=True)
  host = content_dir / "page.md"
  host.write_text(
    textwrap.dedent("""\
      +++
      title = "Host"
      +++

      <div id="default_case" class="js_include" url="/notes/sub/leaf.md" newLevelForH1="3" includeTitle="false" title="ShouldBeHidden" detailsPattern=".*" fieldNames="author" metadataDetailName="false"></div>

      <div id="beta_case" class="js_include" url="/notes/sub/leaf.md" newLevelForH1="3" includeTitle="false" detailsPattern="Beta"></div>

      <div id="nested_case" class="js_include" url="/notes/sub/leaf.md" newLevelForH1="3" includeTitle="false" detailsPattern="Nested Child"></div>

      <div id="meta_case" class="js_include" url="/notes/sub/leaf.md" newLevelForH1="3" includeTitle="plain" detailsPattern="Custom Meta" metadataDetailName="Custom Meta"></div>
    """),
    encoding="utf-8",
  )

  include_helper.prefill_includes(dir_path=str(host), hugo_base_dir=str(tmp_path))
  after = host.read_text(encoding="utf-8")

  # default detailsPattern=".*", fieldNames, metadataDetailName="false", includeTitle="false" over title
  assert "ShouldBeHidden …{Loading}…" not in after
  assert "<h3" not in after
  assert "author : Test Author" in after
  assert "Intro bare text." in after
  assert "### Top Heading" in after
  assert "#### Sub Heading" in after
  assert "../../sub/leaf.png" in after
  assert "<summary>Metadata</summary>" not in after
  assert "<summary>Leaf …{Loading}…</summary>" in after
  assert "<summary>Custom Meta</summary>" in after
  assert "<h3>Leaf" not in after
  assert '"author": "Test Author"' in after

  # Check surgical prefill + camelCase attrs + b[] headings at EOF + detailsPattern parity
  surg_host = content_dir / "surg.md"
  surg_host.write_text(
    textwrap.dedent("""\
      +++
      title = "Surg"
      +++
      <div class="js_include" url="/notes/sub/leaf.md" newLevelForH1="3" includeTitle="false" detailsPattern="Nested Child">
      stale
      </div>
      <div class="js_include" url="/notes/sub/leaf.md" newLevelForH1="b[]" includeTitle="false" detailsPattern="Beta">
      stale2
      </div>
    """),
    encoding="utf-8",
  )
  updated, n = include_helper.surgical_prefill_content(
    surg_host.read_text(encoding="utf-8"),
    str(surg_host),
    hugo_base_dir=str(tmp_path),
  )
  assert n == 2
  assert "Nested body." in updated
  assert "Alpha body." not in updated
  assert "Beta body." in updated

  # Verify nested newLevelForH1 math & h6 clamping in prefill_include: outer=5 + inner=4 -> min(6, (4-1)+5)=6 (never h7)
  (static_dir / "deep_leaf.md").write_text('+++\ntitle = "Deep"\n+++\nDeep text.\n', encoding="utf-8")
  (static_dir / "mid.md").write_text(
    '+++\ntitle = "Mid"\n+++\n<div class="js_include" url="deep_leaf.md" newLevelForH1="4" includeTitle="true"></div>\n',
    encoding="utf-8",
  )
  deep_host = content_dir / "deep_host.md"
  deep_host.write_text(
    '+++\ntitle = "Deep Host"\n+++\n<div class="js_include" url="/notes/sub/mid.md" newLevelForH1="5" includeTitle="true"></div>\n',
    encoding="utf-8",
  )
  include_helper.prefill_includes(dir_path=str(deep_host), hugo_base_dir=str(tmp_path))
  deep_out = deep_host.read_text(encoding="utf-8")
  assert "<h5>Mid …{Loading}…</h5>" in deep_out
  assert "<h6>Deep …{Loading}…</h6>" in deep_out
  assert "<h7>" not in deep_out

  # Verify deinclude matches includeTitle="false" precedence + detailsPattern
  deinc_out, _ = include_helper.deinclude_content(
    '<div class="js_include" url="/notes/sub/leaf.md" newLevelForH1="3" includeTitle="false" title="ShouldHide" detailsPattern="Nested Child"></div>\n',
    str(host),
    hugo_base_dir=str(tmp_path),
  )
  assert "ShouldHide" not in deinc_out
  assert deinc_out.strip().startswith("<details><summary>Nested Child</summary>")



