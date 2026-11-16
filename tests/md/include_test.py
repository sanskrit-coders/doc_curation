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
