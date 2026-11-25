from doc_curation.sanskrit.accent import (
  convert_tree_to_us_accents,
  dependent_to_us_preserving,
  split_frontmatter_verbatim,
  to_us_accents_markdown,
)


def test_split_frontmatter_verbatim_toml_and_yaml():
  toml_doc = '+++\ntitle = "अग्निमीळे"\nunicode_script = "devanagari"\n\n+++\nअ॒ग्निमी॑ळे।\n'
  fm, body = split_frontmatter_verbatim(toml_doc)
  assert fm == '+++\ntitle = "अग्निमीळे"\nunicode_script = "devanagari"\n\n+++\n'
  assert body == "अ॒ग्निमी॑ळे।\n"

  yaml_doc = "---\ntitle: या राका\n---\n\nया राका।\n"
  fm_y, body_y = split_frontmatter_verbatim(yaml_doc)
  assert fm_y == "---\ntitle: या राका\n---\n"
  assert body_y == "\nया राका।\n"

  assert split_frontmatter_verbatim("अ॒ग्निः\n") == ("", "अ॒ग्निः\n")


def test_to_us_accents_markdown_preserves_frontmatter_js_includes_and_tags():
  src = (
    '+++\n'
    'title = "०१ ध्रुव"\n\n'
    '+++\n'
    '## शीर्षकम्\n\n'
    '<details open><summary>विश्वास-प्रस्तुतिः</summary>\n'
    'अ॒ग्निमी॑ळे  \n'
    '</details>\n\n'
    '<div class="js_include" unfilled url="/repo/nested.md">\n'
    '<div class="inner">अ॒ग्निमी॑ळे</div>\n'
    '</div>\n\n'
    'अन्ते `अ॒ग्निः` इति।\n'
  )
  out = to_us_accents_markdown(src)
  # Frontmatter, headings without classical accents, summaries, js_include (even nested divs), and inline code stay verbatim.
  assert out.startswith('+++\ntitle = "०१ ध्रुव"\n\n+++\n## शीर्षकम्\n\n')
  assert '<details open><summary>विश्वास-प्रस्तुतिः</summary>\nअग्नि᳓मीळे  \n</details>' in out
  assert '<div class="js_include" unfilled url="/repo/nested.md">\n<div class="inner">अ॒ग्निमी॑ळे</div>\n</div>' in out
  assert 'अन्ते `अ॒ग्निः` इति।' in out

  # Running again is idempotent and leaves already-US text untouched byte-for-byte.
  assert to_us_accents_markdown(out) == out


def test_to_us_accents_markdown_atharva_and_wrapped_padas():
  av_doc = (
    '+++\ntitle = "०१ शं नो देवीरभिष्टये"\n+++\n'
    'शं नो॑ दे॒वीर॒भिष्ट॑य॒ आपो॑ भवन्तु पी॒तये॑ ।\n'
    'य॒ज्ञं या᳡मा॑हु॒र्भुव॑नस्य ।\n'
    'अ॒भि प्रेहि॑१॒ वाजि॑नि ओ३म् ।\n'
  )
  out = to_us_accents_markdown(av_doc)
  assert "शं᳓ नो देवी᳓रभि᳓ष्टय आ᳓पो भवन्तु पीत᳓ये ।" in out
  assert "यज्ञं᳓ या᳙माहुर्भु᳓वनस्य ।" in out
  assert "अभि᳓ प्रे᳓हि᳙ वा᳓जिनि ओ३म् ।\n" in out

  wrapped = (
    '+++\ntitle = "पादाः"\n+++\n'
    'इषे त्वा\n'
    'ऊर्जे त्वा॑ ।\n\n'
    'अत्र अन्या टिप्पनी।\n'
  )
  out_wrapped = to_us_accents_markdown(wrapped, pauses=r"[।॥,;]+")
  assert "इ᳓षे᳓ त्वा᳓\nऊ᳓र्जे᳓ त्वा ।" in out_wrapped
  assert "\nअत्र अन्या टिप्पनी।\n" in out_wrapped


def test_dependent_to_us_preserving_handles_av_svarita():
  mixed = "या᳓ या᳡मा॑हुः"
  converted = dependent_to_us_preserving(mixed)
  assert converted == "या᳓ या᳙माहुः"
  assert dependent_to_us_preserving("या᳡मा॑हुः") == "या᳙माहुः"


def test_convert_tree_to_us_accents_and_transitive_host_refresh(tmp_path):
  hugo_root = tmp_path / "hugo"
  repo_root = hugo_root / "repoA"
  static_dir = repo_root / "static" / "saMhitA"
  content_dir = repo_root / "content" / "sarva"
  static_dir.mkdir(parents=True)
  content_dir.mkdir(parents=True)

  src_file = static_dir / "01_agni.md"
  src_file.write_text(
    '+++\ntitle = "०१ अग्नि"\n\n+++\nअ॒ग्निमी॑ळे ॥\n',
    encoding="utf-8",
  )
  clean_file = static_dir / "02_clean.md"
  clean_file.write_text(
    '+++\ntitle = "०२ स्वच्छ"\n+++\nनमः ॥\n',
    encoding="utf-8",
  )

  host_file = content_dir / "01.md"
  host_file.write_text(
    '+++\ntitle = "होस्ट्"\n+++\n'
    '<div class="js_include" unfilled url="/repoA/saMhitA/01_agni.md">\n'
    '<details open><summary><h2>०१ अग्नि ...{Loading}...</h2></summary>\n'
    'अ॒ग्निमी॑ळे ॥\n'
    '</details>\n'
    '</div>\n',
    encoding="utf-8",
  )

  dry_report = convert_tree_to_us_accents(
    static_dir,
    refresh_host_dirs=[content_dir],
    hugo_base_dir=str(hugo_root),
    dry_run=True,
  )
  assert dry_report["changed_files"] == [str(src_file)]
  assert dry_report["updated_hosts"] == []
  assert "अ॒ग्निमी॑ळे" in src_file.read_text(encoding="utf-8")
  assert "अ॒ग्निमी॑ळे" in host_file.read_text(encoding="utf-8")

  report = convert_tree_to_us_accents(
    static_dir,
    refresh_host_dirs=[content_dir],
    hugo_base_dir=str(hugo_root),
    dry_run=False,
  )
  assert report["changed_files"] == [str(src_file)]
  assert report["updated_hosts"] == [str(host_file)]
  assert "अग्नि᳓मीळे ॥" in src_file.read_text(encoding="utf-8")
  host_updated = host_file.read_text(encoding="utf-8")
  assert "अग्नि᳓मीळे ॥" in host_updated
  assert "अ॒ग्निमी॑ळे" not in host_updated
