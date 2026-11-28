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


def test_resolve_hugo_include_and_audit_includes(tmp_path):
  static_file = tmp_path / "site_a" / "static" / "part" / "01.md"
  static_file.parent.mkdir(parents=True)
  static_file.write_text("+++\ntitle = 'S'\n+++\nStatic body.\n", encoding="utf-8")

  content_file = tmp_path / "site_b" / "content" / "ch" / "02.md"
  content_file.parent.mkdir(parents=True)
  content_file.write_text("+++\ntitle = 'C'\n+++\nContent body.\n", encoding="utf-8")

  section_idx = tmp_path / "site_b" / "content" / "sec" / "_index.md"
  section_idx.parent.mkdir(parents=True)
  section_idx.write_text("+++\ntitle = 'Sec'\n+++\nSection index.\n", encoding="utf-8")

  # Directory named *.md must never be treated as a Markdown file or crash audit_includes.
  (tmp_path / "site_b" / "content" / "dir_named.md").mkdir(parents=True)

  # Ignored build output / theme directories should not pollute scan results.
  ignored_build = tmp_path / "site_b" / "build_github" / "bad.md"
  ignored_build.parent.mkdir(parents=True)
  ignored_build.write_text('<div class="js_include" url="/site_a/nonexistent.md"></div>\n', encoding="utf-8")

  host = tmp_path / "site_b" / "content" / "host.md"
  host.write_text(
    textwrap.dedent("""\
      +++
      title = "Host"
      +++
      <div class="js_include" url="/site_a/./part/01.md#frag"></div>
      <div class="js_include" url="/site_b/ch/02?lang=sa"></div>
      <div class="js_include" url="/site_b/sec/"></div>
      <div class="js_include" url="https://example.com/ignored.md"></div>
      <div class="js_include" url="/site_b/ch/02.md"></div>
      <div class="collapsed js_include" url="/site_a/part/01"></div>
      <div class="js_include" url="/site_missing/part/01.md"></div>
      <div class="js_include" url="/site_b/content/ch/02"></div>
      <div class="js_include" url="/site_a/part/99.md">
      <details open><summary>Unclosed</summary>
    """),
    encoding="utf-8",
  )

  # Strict Hugo resolution vs permissive fallback
  assert include_helper.resolve_hugo_include_file_path("/site_a/./part/01.md#frag", str(tmp_path), str(host)) == str(static_file)
  assert include_helper.resolve_hugo_include_file_path("/site_b/ch/02?lang=sa", str(tmp_path), str(host)) == str(content_file)
  assert include_helper.resolve_hugo_include_file_path("/site_b/sec/", str(tmp_path), str(host)) == str(section_idx)
  assert include_helper.resolve_hugo_include_file_path("/site_b/ch/02.md", str(tmp_path), str(host)) is None
  assert include_helper.resolve_hugo_include_file_path("/site_a/part/01", str(tmp_path), str(host)) is None
  assert include_helper.resolve_include_file_path("/site_b/ch/02.md", str(tmp_path), str(host)) == str(content_file)
  assert include_helper.resolve_include_file_path("/site_a/part/01", str(tmp_path), str(host)) == str(static_file)

  report = include_helper.audit_includes(
    [str(tmp_path / "site_a"), str(tmp_path / "site_b")],
    hugo_base_dir=str(tmp_path),
  )
  assert report.scanned_files == 4  # static/part/01, content/ch/02, content/sec/_index, content/host
  assert [(b.line_number, b.url, b.reason) for b in report.broken_includes] == [
    (8, "/site_b/ch/02.md", "dot_md_points_to_content"),
    (9, "/site_a/part/01", "non_md_points_to_static"),
    (10, "/site_missing/part/01.md", "missing_target"),
    (11, "/site_b/content/ch/02", "redundant_content_or_static_prefix"),
    (12, "/site_a/part/99.md", "missing_target"),
  ]
  assert len(report.unbalanced_files) == 1
  assert report.unbalanced_files[0].file_path == str(host)
  assert report.unbalanced_files[0].details_delta == 1
  assert report.unbalanced_files[0].div_delta == 1

  # Prefix filter restricts strictly by URL prefix.
  filtered = include_helper.audit_includes(
    [str(tmp_path / "site_b")],
    hugo_base_dir=str(tmp_path),
    url_prefix="/site_b",
    check_tags=False,
  )
  assert [b.url for b in filtered.broken_includes] == ["/site_b/ch/02.md", "/site_b/content/ch/02"]
  assert filtered.unbalanced_files == ()


def test_fix_include_titles_sarva_rules_and_preservation():
  content = textwrap.dedent("""\
    +++
    title = "01"
    +++
    <div class="js_include" newlevelforh1="3" url="/site/text/sarvASh_TIkAH/01/_index.md">
    <details open><summary><h3>01 ...{Loading}...</h3></summary>
    <details><summary>भूमिका</summary>

    सूक्त-टीका
    </details>
    </details>
    </div>

    <div class="js_include" newlevelforh1="4" url="/site/text/sarvASh_TIkAH/01/01_mantra.md">
    <details open><summary><h4>01 मन्त्रः ...{Loading}...</h4></summary>
    <details><summary>सायणः</summary>

    अर्थः
    </details>
    </details>
    </div>

    <div class="js_include" title="सर्वाः टीकाः" url="/site/text/sarvASh_TIkAH/01/02_alias.md"> </div>

    <div class="js_include" title="विश्वास-प्रस्तुतिः" newlevelforh1="4" url="/site/text/sarvASh_TIkAH/01/03_swapped.md">
    <details open><summary><h4>विश्वास-प्रस्तुतिः …{Loading}…</h4></summary>
    <details><summary>मूलम्</summary>

    ॐ
    </details>
    </details>
    </div>

    <div class="js_include" includetitle="true" url="/site/text/sarvASh_TIkAH/01/04_it_true.md">
    <details open><summary><h4>04 ...{Loading}...</h4></summary>

    टीका
    </details>
    </div>

    <div class="js_include collapsed" title="मेधातिथिः" url="/kalpAntaram/smRtiH/manuH/sarvASh_TIkAH/medhAtithiH/01.md">
    <details><summary><h4>मेधातिथिः …{Loading}…</h4></summary>

    भाष्यम्
    </details>
    </div>

    <div class="js_include" detailsPattern=".*मूलम्.*" title="मूलम्" url="/site/text/sarvASh_TIkAH/01/05_filtered.md">
    <details open><summary><h4>मूलम् …{Loading}…</h4></summary>

    मूलम्
    </details>
    </div>

    <div class="js_include" includetitle="false" url="/site/text/sarvASh_TIkAH/01/06_intentional_false.md">
    अन्तःस्थ-टीका
    </div>
  """)

  updated, changes = include_helper.fix_include_titles_in_content(
    content, file_path="/repo/content/text/sarva-prastutiH/01.md"
  )
  assert [c.reason for c in changes] == [
    "SARVA_MISSING_TITLE",
    "SARVA_MISSING_TITLE",
    "SARVA_ALIAS_TITLE",
    "SARVA_WRONG_TITLE",
    "SARVA_BAD_IT",
  ]
  # _index.md stays non-collapsed & open; leaf gets collapsed & closed details.
  assert '<div class="js_include" newlevelforh1="3" title="सर्वाष् टीकाः" url="/site/text/sarvASh_TIkAH/01/_index.md">' in updated
  assert '<details open><summary><h3>सर्वाष् टीकाः …{Loading}…</h3></summary>' in updated
  assert '<div class="js_include collapsed" newlevelforh1="4" title="सर्वाष् टीकाः" url="/site/text/sarvASh_TIkAH/01/01_mantra.md">' in updated
  assert '<details><summary><h4>सर्वाष् टीकाः …{Loading}…</h4></summary>' in updated
  # Empty body gets attributes normalized without synthesizing an empty <details> wrapper.
  assert '<div class="js_include collapsed" title="सर्वाष् टीकाः" url="/site/text/sarvASh_TIkAH/01/02_alias.md"> </div>' in updated
  assert '<div class="js_include collapsed" title="सर्वाष् टीकाः" newlevelforh1="4" url="/site/text/sarvASh_TIkAH/01/03_swapped.md">' in updated
  assert '<div class="js_include collapsed" title="सर्वाष् टीकाः" url="/site/text/sarvASh_TIkAH/01/04_it_true.md">' in updated
  # Custom sub-commentator, detailsPattern-filtered, and intentional includetitle="false" stay preserved.
  assert 'title="मेधातिथिः"' in updated
  assert 'detailsPattern=".*मूलम्.*" title="मूलम्"' in updated
  assert '<div class="js_include" includetitle="false" url="/site/text/sarvASh_TIkAH/01/06_intentional_false.md">' in updated

  # Running a second pass is a no-op.
  updated2, changes2 = include_helper.fix_include_titles_in_content(
    updated, file_path="/repo/content/text/sarva-prastutiH/01.md"
  )
  assert updated2 == updated
  assert changes2 == []

  # Nested sarvASh_TIkAH inside sarvASh_TIkAH keeps includetitle="false".
  st_host = '<div class="js_include" includetitle="false" url="/site/text/sarvASh_TIkAH/other.md">\nमूलम्\n</div>\n'
  st_out, st_changes = include_helper.fix_include_titles_in_content(
    st_host, file_path="/repo/static/text/sarvASh_TIkAH/01.md"
  )
  assert st_out == st_host and st_changes == []

  # Opt-in flags: fix_sarva_includetitle_false and ensure_sarva_collapsed sync both leaf and _index.md.
  idx_and_leaf = (
    '<div class="js_include collapsed" title="सर्वाष् टीकाः" url="/site/text/sarvASh_TIkAH/01/_index.md"> </div>\n'
    '<div class="js_include" title="सर्वाष् टीकाः" url="/site/text/sarvASh_TIkAH/01/01.md"> </div>\n'
    '<div class="js_include" includetitle="false" url="/site/text/sarvASh_TIkAH/01/02.md"> </div>\n'
  )
  synced, sync_changes = include_helper.fix_include_titles_in_content(
    idx_and_leaf,
    file_path="/repo/content/text/01.md",
    ensure_sarva_collapsed=True,
    fix_sarva_includetitle_false=True,
  )
  assert [c.reason for c in sync_changes] == ["SARVA_COLLAPSED_SYNC", "SARVA_COLLAPSED_SYNC", "SARVA_IT_FALSE"]
  assert '<div class="js_include" title="सर्वाष् टीकाः" url="/site/text/sarvASh_TIkAH/01/_index.md"> </div>' in synced
  assert '<div class="js_include collapsed" title="सर्वाष् टीकाः" url="/site/text/sarvASh_TIkAH/01/01.md"> </div>' in synced
  assert '<div class="js_include collapsed" title="सर्वाष् टीकाः" url="/site/text/sarvASh_TIkAH/01/02.md"> </div>' in synced


def test_fix_include_titles_vp_host_and_nested_vp():
  # Inside a vishvAsa-prastutiH/ file: strip title="विश्वास-प्रस्तुतिः" and missing attrs -> includetitle="false",
  # unwrap outer {Loading} wrapper, preserve distinct label & includetitle="true".
  nested_vp_doc = textwrap.dedent("""\
    +++
    title = "outer"
    +++
    <div class="js_include collapsed" newlevelforh1="4" title="विश्वास-प्रस्तुतिः" url="/site/vishvAsa-prastutiH/a.md">
    <details open><summary><h4>विश्वास-प्रस्तुतिः …{Loading}…</h4></summary>

    मन्त्रः ॥१॥
    </details>
    </div>

    <div class="js_include" url="/site/vishvAsa-prastutiH/b.md">
    <details open><summary><h4>b …{Loading}…</h4></summary>

    मन्त्रः ॥२॥
    </details>
    </div>

    <div class="js_include" title="विश्वास-शाकल-प्रस्तुतिः" url="/vedAH_Rk/shAkalam/vishvAsa-prastutiH/c.md">
    <details open><summary><h4>विश्वास-शाकल-प्रस्तुतिः …{Loading}…</h4></summary>

    शाकलम् ॥३॥
    </details>
    </div>

    <div class="js_include" includetitle="true" url="/site/vishvAsa-prastutiH/d.md">
    <details open><summary><h4>d …{Loading}…</h4></summary>

    चतुर्थः ॥४॥
    </details>
    </div>

    <div class="js_include" includetitle="false" url="/site/vishvAsa-prastutiH/e_keep_verse_head.md">
    <details open><summary><h4>०५ मन्त्रः ...{Loading}...</h4></summary>

    पञ्चमः ॥५॥
    </details>
    </div>

    <div class="js_include" includetitle="false" url="/site/vishvAsa-prastutiH/f_stale_vp_wrap.md">
    <details open><summary><h4>विश्वास-प्रस्तुतिः …{Loading}…</h4></summary>

    षष्ठः ॥६॥
    </details>
    </div>
  """)
  vp_out, vp_changes = include_helper.fix_include_titles_in_content(
    nested_vp_doc, file_path="/repo/static/text/vishvAsa-prastutiH/outer.md"
  )
  assert [c.reason for c in vp_changes] == ["NESTED_VP_STRIP_TITLE", "NESTED_VP_SET_FALSE", "NESTED_VP_CLEANUP"]
  assert '<div class="js_include" newlevelforh1="4" includetitle="false" url="/site/vishvAsa-prastutiH/a.md">\nमन्त्रः ॥१॥\n</div>' in vp_out
  assert '<div class="js_include" includetitle="false" url="/site/vishvAsa-prastutiH/b.md">\nमन्त्रः ॥२॥\n</div>' in vp_out
  assert 'title="विश्वास-शाकल-प्रस्तुतिः"' in vp_out
  assert 'includetitle="true"' in vp_out
  assert "<summary><h4>०५ मन्त्रः ...{Loading}...</h4></summary>" in vp_out
  assert '<div class="js_include" includetitle="false" url="/site/vishvAsa-prastutiH/f_stale_vp_wrap.md">\nषष्ठः ॥६॥\n</div>' in vp_out

  # Non-VP host: fix swapped title, empty title, uppercase includetitle, but ignore nested inner prefilled divs.
  host_doc = textwrap.dedent("""\
    <div class="js_include collapsed" title="सर्वाष् टीकाः" newlevelforh1="4" url="/site/vishvAsa-prastutiH/01.md">
    <details><summary><h4>सर्वाष् टीकाः …{Loading}…</h4></summary>

    वाक्यम्
    <div class="js_include" title="विश्वास-प्रस्तुतिः" url="/site/vishvAsa-prastutiH/nested_ignored.md">
    nested prefill should not be directly rewritten by host pass
    </div>
    </details>
    </div>

    <div class="js_include" title="" url="/site/vishvAsa-prastutiH/02.md"> </div>
    <div class="js_include" includetitle="False" url="/site/vishvAsa-prastutiH/03.md"> </div>
    <div class="js_include" includetitle="plain" url="/site/vishvAsa-prastutiH/04.md"> </div>
    <div class="js_include" title="योनि-प्रस्तुतिः" url="/site/vishvAsa-prastutiH/05.md"> </div>
  """)
  host_out, host_changes = include_helper.fix_include_titles_in_content(
    host_doc, file_path="/repo/content/text/sarva-prastutiH/01.md"
  )
  assert [c.reason for c in host_changes] == [
    "HOST_VP_FIX_TITLE",
    "HOST_VP_EMPTY_TITLE",
    "HOST_VP_LOWER_IT",
  ]
  assert '<div class="js_include" title="विश्वास-प्रस्तुतिः" newlevelforh1="4" url="/site/vishvAsa-prastutiH/01.md">' in host_out
  assert '<details open><summary><h4>विश्वास-प्रस्तुतिः …{Loading}…</h4></summary>' in host_out
  # Nested inner prefilled div inside 01.md must NOT be touched directly during host pass.
  assert 'url="/site/vishvAsa-prastutiH/nested_ignored.md"' in host_out
  assert host_out.count('includetitle="false"') == 2
  assert 'includetitle="plain"' in host_out
  assert 'title="योनि-प्रस्तुतिः"' in host_out


def test_fix_include_titles_tree_dry_run_and_propagate_transitive(tmp_path):
  static_vp = tmp_path / "site" / "static" / "mantra" / "vishvAsa-prastutiH"
  static_st = tmp_path / "site" / "static" / "mantra" / "sarvASh_TIkAH"
  content_dir = tmp_path / "site" / "content" / "mantra" / "sarva-prastutiH"
  for d in (static_vp, static_st, content_dir):
    d.mkdir(parents=True)

  leaf = static_vp / "leaf.md"
  leaf.write_text('+++\ntitle = "leaf"\n+++\nअग्निमीळे पुरोहितम् ॥१॥\n', encoding="utf-8")

  st_leaf = static_st / "01.md"
  st_leaf.write_text('+++\ntitle = "01"\n+++\n<details><summary>सायणः</summary>\n\nभाष्यम्\n</details>\n', encoding="utf-8")

  outer_vp = static_vp / "outer.md"
  outer_orig = textwrap.dedent("""\
    +++
    title = "outer"
    +++
    <div class="js_include" newlevelforh1="4" title="विश्वास-प्रस्तुतिः" url="/site/mantra/vishvAsa-prastutiH/leaf.md">
    <details open><summary><h4>विश्वास-प्रस्तुतिः …{Loading}…</h4></summary>

    अग्निमीळे पुरोहितम् ॥१॥
    </details>
    </div>
  """)
  outer_vp.write_text(outer_orig, encoding="utf-8")

  host = content_dir / "01.md"
  host_orig = textwrap.dedent("""\
    +++
    title = "01"
    +++
    <div class="js_include" newlevelforh1="3" title="विश्वास-प्रस्तुतिः" url="/site/mantra/vishvAsa-prastutiH/outer.md">
    <details open><summary><h3>विश्वास-प्रस्तुतिः …{Loading}…</h3></summary>

    <div class="js_include" newlevelforh1="4" title="विश्वास-प्रस्तुतिः" url="/site/mantra/vishvAsa-prastutiH/leaf.md">
    <details open><summary><h4>विश्वास-प्रस्तुतिः …{Loading}…</h4></summary>

    stale
    </details>
    </div>
    </details>
    </div>

    <div class="js_include" title="सर्वाः टीकाः" newlevelforh1="4" url="/site/mantra/sarvASh_TIkAH/01.md">
    <details open><summary><h4>सर्वाः टीकाः …{Loading}…</h4></summary>
    <details><summary>सायणः</summary>

    भाष्यम्
    </details>
    </details>
    </div>
  """)
  host.write_text(host_orig, encoding="utf-8")

  roots = [tmp_path / "site" / "static", tmp_path / "site" / "content"]
  dry_report = include_helper.fix_include_titles(roots, dry_run=True, propagate_transitive=True, hugo_base_dir=str(tmp_path))
  assert set(dry_report.changed_files) == {str(outer_vp), str(host)}
  assert dry_report.propagated_files == ()
  assert outer_vp.read_text(encoding="utf-8") == outer_orig
  assert host.read_text(encoding="utf-8") == host_orig

  applied_report = include_helper.fix_include_titles(
    roots, dry_run=False, propagate_transitive=True, hugo_base_dir=str(tmp_path)
  )
  assert set(applied_report.changed_files) == {str(outer_vp), str(host)}
  assert str(host) in applied_report.propagated_files

  outer_new = outer_vp.read_text(encoding="utf-8")
  assert 'includetitle="false"' in outer_new
  assert 'title="विश्वास-प्रस्तुतिः"' not in outer_new
  assert "{Loading}" not in outer_new

  host_new = host.read_text(encoding="utf-8")
  assert '<div class="js_include collapsed" title="सर्वाष् टीकाः" newlevelforh1="4" url="/site/mantra/sarvASh_TIkAH/01.md">' in host_new
  assert '<details><summary><h4>सर्वाष् टीकाः …{Loading}…</h4></summary>' in host_new
  # Transitive prefill pulled updated outer_vp (no double-nested विश्वास-प्रस्तुतिः wrapper inside outer_vp prefill).
  assert host_new.count("विश्वास-प्रस्तुतिः …{Loading}…") == 1
  assert 'includetitle="false" url="/site/mantra/vishvAsa-prastutiH/leaf.md"' in host_new
  assert "stale" not in host_new
  assert include_helper.check_tag_balance(outer_new) is None
  assert include_helper.check_tag_balance(host_new) is None


def test_detail_content_pattern_and_filtering_before_second_order_includes(tmp_path):
  static_dir = tmp_path / "notes" / "static" / "sub"
  static_dir.mkdir(parents=True)

  (static_dir / "child_alpha.md").write_text(
    '+++\ntitle = "Child Alpha"\n+++\nTARGET_MARKER hidden in second-order alpha.\n',
    encoding="utf-8",
  )
  (static_dir / "child_beta.md").write_text(
    textwrap.dedent("""\
      +++
      title = "Child Beta"
      +++
      <details><summary>Second Order Child</summary>

      Second order text without marker.
      </details>
    """),
    encoding="utf-8",
  )
  (static_dir / "parent.md").write_text(
    textwrap.dedent("""\
      +++
      title = "Parent"
      +++
      Bare intro outside details.

      <details><summary>Alpha</summary>

      Alpha **plain** body.

      <div class="js_include" url="child_alpha.md" newLevelForH1="4" includeTitle="false"></div>
      </details>

      <details><summary>Beta</summary>

      Beta **bold** body with TARGET_MARKER.

      <div class="js_include" url="child_beta.md" newLevelForH1="4" includeTitle="false"></div>

      <details><summary>Nested Child</summary>

      Inner leaf text.
      </details>
      </details>

      <details><summary>Empty Detail</summary>

      <p></p>
      </details>

      <div class="js_include collapsed" newlevelforh1="4" title="सर्वाष् टीकाः" url="/notes/sub/child_alpha.md">
      <details><summary><h4>सर्वाष् टीकाः …{Loading}…</h4></summary>
      <details><summary>गङ्गानथ-मूलानुवादः</summary>

      Defiling a maiden, selling a tank.
      </details>

      <details><summary>मेधातिथिः</summary>

      कन्याया दूषणम्।
      </details>
      </details>
      </div>

      <details><summary>अन्य-टीकाः</summary>

      <details><summary>गङ्गानथ-मूलानुवादः</summary>

      Other block that must NOT match path.
      </details>
      </details>
    """),
    encoding="utf-8",
  )

  # Direct filter_details_by_pattern checks:
  parent_raw = (static_dir / "parent.md").read_text(encoding="utf-8")
  # 1. detailContentPattern alone (markdown **bold** matches rendered text; summary excluded)
  only_beta = include_helper.filter_details_by_pattern(parent_raw, ".*", "Beta bold body")
  assert "<summary>Beta</summary>" in only_beta
  assert "<summary>Alpha</summary>" not in only_beta
  assert "<summary>Empty Detail</summary>" not in only_beta
  # 2. Anchored child pattern skips Beta and recurses to Nested Child
  only_nested = include_helper.filter_details_by_pattern(parent_raw, None, "^Inner leaf")
  assert "<summary>Nested Child</summary>" in only_nested
  assert "<summary>Beta</summary>" not in only_nested
  # 3. Non-empty filter excludes Empty Detail (<p></p>)
  non_empty = include_helper.filter_details_by_pattern(parent_raw, ".*", r"\S")
  assert "<summary>Empty Detail</summary>" not in non_empty
  # 4. Path-based detailsPattern across nested <details> (including inside prefilled wrapper)
  sarva_ganga = include_helper.filter_details_by_pattern(parent_raw, "सर्वाष् टीकाः.*/गङ्गानथ-मूलानुवादः.*")
  assert sarva_ganga.strip().startswith("<details><summary>गङ्गानथ-मूलानुवादः</summary>")
  assert "Defiling a maiden, selling a tank." in sarva_ganga
  assert "सर्वाष् टीकाः" not in sarva_ganga
  assert "मेधातिथिः" not in sarva_ganga
  assert "Other block that must NOT match path." not in sarva_ganga
  # 5. Non-slash pattern does NOT cross ancestor/child boundary
  assert include_helper.filter_details_by_pattern(parent_raw, "सर्वाष् टीकाः.*गङ्गानथ") == ""
  # 6. Summary match + content mismatch returns empty
  assert include_helper.filter_details_by_pattern(parent_raw, "Alpha", "NO_MATCH") == ""
  # 7. Summary text is NOT treated as detail content
  assert include_helper.filter_details_by_pattern(parent_raw, ".*", "^Alpha$") == ""

  content_dir = tmp_path / "notes" / "content" / "host"
  content_dir.mkdir(parents=True)

  # prefill_includes: filtering happens BEFORE 2nd-order includes are handled
  prefill_host = content_dir / "prefill_host.md"
  prefill_host.write_text(
    '+++\ntitle = "H"\n+++\n'
    '<div class="js_include" url="/notes/sub/parent.md" newLevelForH1="3" includeTitle="false" '
    'detailContentPattern="Beta bold body with TARGET_MARKER"></div>\n',
    encoding="utf-8",
  )
  include_helper.prefill_includes(dir_path=str(prefill_host), hugo_base_dir=str(tmp_path))
  prefill_out = prefill_host.read_text(encoding="utf-8")
  assert "<summary>Beta</summary>" in prefill_out
  assert "<summary>Alpha</summary>" not in prefill_out
  assert "hidden in second-order alpha" not in prefill_out
  assert "<summary>Second Order Child</summary>" in prefill_out
  assert "Second order text without marker." in prefill_out

  # surgical_prefill_content parity (path detailsPattern + detailContentPattern)
  surg_host = content_dir / "surg_host.md"
  surg_in = (
    '+++\ntitle = "S"\n+++\n'
    '<div class="js_include" url="/notes/sub/parent.md" newLevelForH1="3" includeTitle="false" '
    'detailsPattern="Beta" detailContentPattern="Inner leaf"></div>\n'
    '<div class="js_include" url="/notes/sub/parent.md" newLevelForH1="3" includeTitle="false" '
    'detailsPattern="सर्वाष् टीकाः.*/गङ्गानथ-मूलानुवादः.*"></div>\n'
  )
  surg_out, n_surg = include_helper.surgical_prefill_content(surg_in, str(surg_host), hugo_base_dir=str(tmp_path))
  assert n_surg == 2
  assert "<summary>Beta</summary>" in surg_out
  assert "<summary>Alpha</summary>" not in surg_out
  assert "Defiling a maiden, selling a tank." in surg_out
  assert "Other block that must NOT match path." not in surg_out

  # deinclude_content(prefill=True): filtering MUST happen BEFORE surgical_prefill_content handles 2nd-order includes
  deinc_prefill_out, _ = include_helper.deinclude_content(
    '<div class="js_include" url="/notes/sub/parent.md" newLevelForH1="3" includeTitle="false" '
    'detailContentPattern="TARGET_MARKER"></div>\n',
    str(prefill_host),
    prefill=True,
    hugo_base_dir=str(tmp_path),
  )
  assert "<summary>Alpha</summary>" not in deinc_prefill_out
  assert "hidden in second-order alpha" not in deinc_prefill_out
  assert "<summary>Beta</summary>" in deinc_prefill_out
  assert "<summary>Second Order Child</summary>" in deinc_prefill_out

  # deinclude_content(prefill=False): respects detailContentPattern on already-prefilled body
  deinc_noprefill_out, _ = include_helper.deinclude_content(
    '<div class="js_include" url="/notes/sub/parent.md" newLevelForH1="3" includeTitle="false" '
    'detailContentPattern="KeepBody">\n'
    '<details><summary>One</summary>SkipBody</details>\n'
    '<details><summary>Two</summary>KeepBody</details>\n'
    '</div>\n',
    str(prefill_host),
    prefill=False,
    hugo_base_dir=str(tmp_path),
  )
  assert "KeepBody" in deinc_noprefill_out and "SkipBody" not in deinc_noprefill_out

  # fix_include_titles preserves custom title when detailContentPattern is set on sarvASh_TIkAH/
  fixed_txt, fixed_changes = include_helper.fix_include_titles_in_content(
    '<div class="js_include" detailContentPattern=".*मूलम्.*" title="मूलम्" url="/site/text/sarvASh_TIkAH/01/05.md"> </div>\n',
    file_path="/repo/content/text/sarva-prastutiH/01.md",
  )
  assert fixed_changes == []
  assert 'title="मूलम्"' in fixed_txt


def test_quote_parameter_prefill_surgical_deinclude_and_fixer(tmp_path):
  static_dir = tmp_path / "notes" / "static" / "sub"
  static_dir.mkdir(parents=True)
  (static_dir / "q.md").write_text(
    textwrap.dedent("""\
      +++
      title = "Quoted Leaf"
      +++
      Line one.

      > Inner quote.
    """),
    encoding="utf-8",
  )

  content_dir = tmp_path / "notes" / "content" / "host"
  content_dir.mkdir(parents=True)
  host = content_dir / "host.md"
  host.write_text(
    textwrap.dedent("""\
      +++
      title = "Host"
      +++
      <div id="q0" class="js_include" url="/notes/sub/q.md" newLevelForH1="4" includeTitle="false" quote="0"></div>

      <div id="q1" class="js_include" url="/notes/sub/q.md" newLevelForH1="4" includeTitle="false" quote="1"></div>

      <div id="q2" class="js_include" url="/notes/sub/q.md" newLevelForH1="4" includeTitle="true" quote="2"></div>
    """),
    encoding="utf-8",
  )

  include_helper.prefill_includes(dir_path=str(host), hugo_base_dir=str(tmp_path))
  after = host.read_text(encoding="utf-8")
  assert "Line one.\n\n> Inner quote." in after
  assert "> Line one.\n>\n> > Inner quote." in after
  assert '>> <details open><summary><h4>Quoted Leaf …{Loading}…</h4></summary>\n>>\n>> Line one.\n>>\n>> > Inner quote.\n>>\n>> </details>' in after

  # surgical_prefill_content leaves q1 and q2 byte-identical (only normalizes q0's outer blank lines) and is idempotent
  surg_q2, n_first = include_helper.surgical_prefill_content(after, str(host), hugo_base_dir=str(tmp_path))
  assert n_first == 1
  surg_q2_again, n_unchanged = include_helper.surgical_prefill_content(surg_q2, str(host), hugo_base_dir=str(tmp_path))
  assert n_unchanged == 0 and surg_q2_again == surg_q2

  changed_to_1 = after.replace('quote="2"', 'quote="1"')
  surg_q1, n1 = include_helper.surgical_prefill_content(changed_to_1, str(host), hugo_base_dir=str(tmp_path))
  assert n1 >= 1
  assert '> <details open><summary><h4>Quoted Leaf …{Loading}…</h4></summary>\n>\n> Line one.\n>\n> > Inner quote.\n>\n> </details>' in surg_q1

  changed_to_0 = surg_q1.replace('quote="1"', 'quote="0"')
  surg_q0, _ = include_helper.surgical_prefill_content(changed_to_0, str(host), hugo_base_dir=str(tmp_path))
  assert '<details open><summary><h4>Quoted Leaf …{Loading}…</h4></summary>\n\nLine one.\n\n> Inner quote.\n\n</details>' in surg_q0

  # deinclude_content(prefill=False) & deinclude_content(prefill=True) with quote
  deinc_np, _ = include_helper.deinclude_content(
    '<div class="js_include" url="/notes/sub/q.md" newLevelForH1="4" includeTitle="false" quote="2">\n\n>> Line one.\n>>\n>> > Inner quote.\n\n</div>\n',
    str(host),
    prefill=False,
    hugo_base_dir=str(tmp_path),
  )
  assert deinc_np.strip() == ">> Line one.\n>>\n>> > Inner quote."

  deinc_p, _ = include_helper.deinclude_content(
    '<div class="js_include" url="/notes/sub/q.md" newLevelForH1="4" includeTitle="true" quote="1"></div>\n',
    str(host),
    prefill=True,
    hugo_base_dir=str(tmp_path),
  )
  assert deinc_p.strip() == "> <details open><summary>Quoted Leaf</summary>\n>\n> Line one.\n>\n> > Inner quote.\n> </details>"

  # fix_include_titles preserves quote wrapper cleanly
  sarva_quoted = (
    '<div class="js_include" newlevelforh1="4" quote="1" title="सर्वाः टीकाः" url="/site/text/sarvASh_TIkAH/01/01.md">\n\n'
    '> <details open><summary><h4>सर्वाः टीकाः …{Loading}…</h4></summary>\n>\n> टीका\n>\n> </details>\n\n'
    '</div>\n'
  )
  fixed_q, changes_q = include_helper.fix_include_titles_in_content(
    sarva_quoted, file_path="/repo/content/text/sarva-prastutiH/01.md"
  )
  assert [c.reason for c in changes_q] == ["SARVA_ALIAS_TITLE"]
  assert '> <details><summary><h4>सर्वाष् टीकाः …{Loading}…</h4></summary>\n>\n> टीका\n>\n> </details>' in fixed_q





